#!/usr/bin/env python3
"""GitHub (gh) and GitLab (glab) wrapper for merge request workflows. Stdlib only.

Provider is detected from the git remote "origin". Override with
FORGE_PROVIDER=github or FORGE_PROVIDER=gitlab for unusual self-hosted hosts.

Output: JSON on stdout, except job-log which prints plain text.
Exit codes: 0 success, 2 invalid input (fix the parameter and rerun),
1 provider or git failure (read the error message).
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

PROTECTED_BRANCHES = {"main", "master", "develop", "trunk"}
TITLE_MAX = 72
MR_BODY_MAX_CHARS = 60000
REPLY_MAX_CHARS = 1000
TAIL_MAX = 5000
REMOTE_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
THREAD_RE = re.compile(r"^[A-Za-z0-9_=+/:.-]{1,200}$")
NUMBER_RE = re.compile(r"^[1-9][0-9]{0,9}$")


GH_THREADS_QUERY = """
query($owner: String!, $repo: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          comments(first: 100) {
            pageInfo { hasNextPage endCursor }
            nodes { databaseId body url createdAt author { login } }
          }
        }
      }
    }
  }
}
"""

GH_THREAD_COMMENTS_QUERY = """
query($thread: ID!, $after: String) {
  node(id: $thread) {
    ... on PullRequestReviewThread {
      comments(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes { databaseId body url createdAt author { login } }
      }
    }
  }
}
"""

GH_REPLY_MUTATION = """
mutation($thread: ID!, $body: String!) {
  addPullRequestReviewThreadReply(input: {pullRequestReviewThreadId: $thread, body: $body}) {
    comment { id url }
  }
}
"""

GH_RESOLVE_MUTATION = """
mutation($thread: ID!) {
  resolveReviewThread(input: {threadId: $thread}) { thread { id isResolved } }
}
"""

GH_UNRESOLVE_MUTATION = """
mutation($thread: ID!) {
  unresolveReviewThread(input: {threadId: $thread}) { thread { id isResolved } }
}
"""

TEMPLATE_FILES = {
    "github": [
        "PULL_REQUEST_TEMPLATE.md",
        ".github/PULL_REQUEST_TEMPLATE.md",
        ".github/pull_request_template.md",
        "docs/PULL_REQUEST_TEMPLATE.md",
        "docs/pull_request_template.md",
    ],
    "gitlab": [".gitlab/merge_request_templates/Default.md"],
}

TEMPLATE_DIRS = {
    "github": [".github/PULL_REQUEST_TEMPLATE"],
    "gitlab": [".gitlab/merge_request_templates"],
}

ISSUE_REF_RE = re.compile(r"(?<![\w&/])#(\d{1,9})\b")
EXTERNAL_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d{1,7})\b")
ISSUE_FETCH_MAX = 20
ISSUE_BODY_MAX = 4000

PENDING_GITLAB_STATUSES = {"created", "pending", "running", "waiting_for_resource", "preparing", "scheduled"}


class ForgeError(Exception):
    pass


class ValidationError(Exception):
    def __init__(self, problems):
        super().__init__("invalid parameters")
        self.problems = problems


def fail(message):
    raise ForgeError(message)


def run(cmd, ok=(0,), input_text=None):
    try:
        proc = subprocess.run(cmd, input=input_text, capture_output=True, text=True)
    except OSError as error:
        fail(f"could not run '{cmd[0]}': {error}")
    if proc.returncode not in ok:
        fail(f"`{' '.join(cmd[:3])}` failed: {(proc.stderr or proc.stdout).strip()}")
    return proc.stdout


def default_base():
    proc = subprocess.run(
        ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip().removeprefix("origin/")
    return "main"


def protected_branches():
    return PROTECTED_BRANCHES | {default_base()}


def parse_remote(url):
    match = re.match(r"^(?:[a-z+]+://)?(?:[^@/]+@)?([^:/]+)(?::\d+)?[:/](.+?)(?:\.git)?/?$", url)
    if not match:
        fail(f"cannot parse remote URL: {url}")
    return match.group(1), match.group(2)


def current_branch():
    return run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip()


def valid_branch_name(name):
    proc = subprocess.run(["git", "check-ref-format", "--branch", name], capture_output=True, text=True)
    return proc.returncode == 0


def json_stream(text):
    decoder = json.JSONDecoder()
    items, index, text = [], 0, text.strip()
    while index < len(text):
        value, index = decoder.raw_decode(text, index)
        items.extend(value if isinstance(value, list) else [value])
        while index < len(text) and text[index].isspace():
            index += 1
    return items


def check_number(value, name):
    if value is None:
        return None
    cleaned = str(value).strip().lstrip("#!")
    if not NUMBER_RE.fullmatch(cleaned):
        raise ValidationError([f"{name} must be a positive whole number such as 42; got '{value}'"])
    return cleaned


def read_limited(path, max_chars, name):
    file = Path(path)
    if not file.is_file():
        raise ValidationError([f"{name} file not found: {path}"])
    text = file.read_text(encoding="utf-8").strip()
    if not text:
        raise ValidationError([f"{name} file is empty"])
    if len(text) > max_chars:
        raise ValidationError([f"{name} is {len(text)} chars; maximum is {max_chars}"])
    return text


def check_thread(value):
    if not THREAD_RE.fullmatch(value or ""):
        raise ValidationError([f"--thread-id is not valid: '{value}'. Use the thread_id from mr-comments"])
    return value


def detect_context():
    host, path = parse_remote(run(["git", "remote", "get-url", "origin"]).strip())
    provider = os.environ.get("FORGE_PROVIDER")
    if not provider:
        if "github" in host:
            provider = "github"
        elif "gitlab" in host:
            provider = "gitlab"
        else:
            fail(f"cannot infer provider from host '{host}'; set FORGE_PROVIDER=github or gitlab")
    if provider not in ("github", "gitlab"):
        fail(f"FORGE_PROVIDER must be github or gitlab; got '{provider}'")
    ctx = {"provider": provider, "host": host, "path": path}
    if provider == "github":
        ctx["owner"], ctx["repo"] = path.rsplit("/", 1)
        if host != "github.com":
            os.environ["GH_HOST"] = host
    else:
        ctx["encoded"] = urllib.parse.quote(path, safe="")
        if host != "gitlab.com":
            os.environ["GITLAB_HOST"] = host
    return ctx


def gl_api(path, method=None, fields=None, paginate=False):
    cmd = ["glab", "api"]
    if paginate:
        cmd.append("--paginate")
    if method:
        cmd += ["-X", method]
    for key, value in (fields or {}).items():
        cmd += ["-f", f"{key}={value}"]
    cmd.append(path)
    out = run(cmd)
    if paginate:
        return json_stream(out)
    return json.loads(out) if out.strip() else None


def gh_api(path, paginate=False):
    cmd = ["gh", "api"] + (["--paginate"] if paginate else []) + [path]
    out = run(cmd)
    return json_stream(out) if paginate else json.loads(out)


def gh_graphql(query, **variables):
    cmd = ["gh", "api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        if value is None:
            continue
        cmd += ["-F" if isinstance(value, int) else "-f", f"{key}={value}"]
    data = json.loads(run(cmd))
    if data.get("errors"):
        fail(f"GraphQL error: {data['errors']}")
    return data["data"]


def open_branch_mrs(ctx, branch):
    if ctx["provider"] == "github":
        data = json.loads(run([
            "gh", "pr", "list", "--head", branch, "--state", "open", "--limit", "50",
            "--json", "number,url,baseRefName,headRefOid",
        ]))
        return [
            {"number": item["number"], "url": item["url"], "target_branch": item["baseRefName"], "head_sha": item["headRefOid"]}
            for item in data
        ]
    query = urllib.parse.urlencode({"state": "opened", "source_branch": branch, "per_page": 100})
    data = gl_api(f"projects/{ctx['encoded']}/merge_requests?{query}")
    return [
        {"number": item["iid"], "url": item["web_url"], "target_branch": item["target_branch"], "head_sha": item["sha"]}
        for item in data
    ]


def resolve_mr(ctx, mr):
    number = check_number(mr, "--mr")
    if number:
        return number
    branch = current_branch()
    if ctx["provider"] == "github":
        return str(json.loads(run(["gh", "pr", "view", "--json", "number"]))["number"])
    found = open_branch_mrs(ctx, branch)
    if not found:
        fail(f"no open merge request for branch '{branch}'")
    if len(found) > 1:
        fail(f"multiple open merge requests for branch '{branch}'; pass --mr explicitly")
    return str(found[0]["number"])


def make_item(thread_id, kind, resolvable, resolved, path, line, notes, outdated=False):
    first = notes[0] if notes else {}
    return {
        "thread_id": thread_id,
        "kind": kind,
        "resolvable": resolvable,
        "resolved": resolved,
        "outdated": outdated,
        "path": path,
        "line": line,
        "author": first.get("author"),
        "body": first.get("body", ""),
        "url": first.get("url"),
        "notes": notes,
    }


def gh_threads(ctx, number):
    threads, after = [], None
    while True:
        data = gh_graphql(GH_THREADS_QUERY, owner=ctx["owner"], repo=ctx["repo"], number=int(number), after=after)
        page = data["repository"]["pullRequest"]["reviewThreads"]
        threads.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            return threads
        after = page["pageInfo"]["endCursor"]


def gh_all_thread_comments(thread):
    comments = list(thread["comments"]["nodes"])
    page = thread["comments"]
    while page["pageInfo"]["hasNextPage"]:
        data = gh_graphql(GH_THREAD_COMMENTS_QUERY, thread=thread["id"], after=page["pageInfo"]["endCursor"])
        page = data["node"]["comments"]
        comments.extend(page["nodes"])
    return comments


def gh_comments(ctx, number, include_general=True):
    items = []
    for thread in gh_threads(ctx, number):
        notes = [
            {
                "id": c["databaseId"],
                "author": (c["author"] or {}).get("login"),
                "body": c["body"],
                "created_at": c["createdAt"],
                "url": c["url"],
            }
            for c in gh_all_thread_comments(thread)
        ]
        items.append(make_item(thread["id"], "review_thread", True, thread["isResolved"],
                               thread["path"], thread["line"], notes, thread["isOutdated"]))
    if not include_general:
        return items
    general = gh_api(f"repos/{ctx['owner']}/{ctx['repo']}/issues/{number}/comments?per_page=100", paginate=True)
    for comment in general:
        note = {
            "id": comment["id"],
            "author": comment["user"]["login"],
            "body": comment["body"],
            "created_at": comment["created_at"],
            "url": comment["html_url"],
        }
        items.append(make_item(f"issue:{comment['id']}", "general", False, False, None, None, [note]))
    return items


def gl_comments(ctx, number, include_general=True):
    discussions = gl_api(f"projects/{ctx['encoded']}/merge_requests/{number}/discussions?per_page=100", paginate=True)
    items = []
    for discussion in discussions:
        notes = [n for n in discussion["notes"] if not n.get("system")]
        if not notes:
            continue
        resolvable = any(n.get("resolvable") for n in notes)
        resolved = resolvable and all(n.get("resolved") for n in notes if n.get("resolvable"))
        position = next((n["position"] for n in notes if n.get("position")), {})
        path = position.get("new_path") or position.get("old_path")
        line = position.get("new_line") or position.get("old_line")
        normalized = [
            {"id": n["id"], "author": n["author"]["username"], "body": n["body"], "created_at": n["created_at"], "url": None}
            for n in notes
        ]
        general = bool(discussion.get("individual_note")) or not resolvable
        if general and not include_general:
            continue
        thread_id = f"general:{discussion['id']}" if general else discussion["id"]
        kind = "general" if general else "review_thread"
        items.append(make_item(thread_id, kind, resolvable, resolved, path, line, normalized))
    return items


def overall(items):
    buckets = {item["bucket"] for item in items}
    if "fail" in buckets or "cancel" in buckets:
        return "failed"
    if "pending" in buckets:
        return "pending"
    return "success" if items else "none"


def gh_raw_checks(number):
    cmd = ["gh", "pr", "checks", number, "--json", "name,state,bucket,link,workflow"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except OSError as error:
        fail(f"could not run 'gh': {error}")
    if proc.returncode not in (0, 1, 8):
        fail(f"`gh pr checks` failed: {(proc.stderr or proc.stdout).strip()}")
    text = proc.stdout.strip()
    if not text and proc.returncode == 1:
        fail(f"`gh pr checks` failed: {(proc.stderr or proc.stdout).strip()}")
    try:
        data = json.loads(text or "[]")
    except json.JSONDecodeError:
        fail(f"`gh pr checks` did not return check data: {(proc.stderr or proc.stdout).strip()}")
    if not isinstance(data, list):
        fail("`gh pr checks` returned an unexpected response")
    return data


def gh_check_runs(base, head_sha):
    results = []
    page = 1
    while True:
        data = gh_api(f"{base}/commits/{head_sha}/check-runs?per_page=100&page={page}")
        batch = data["check_runs"]
        results.extend(batch)
        if len(batch) < 100:
            return results
        page += 1


def gh_pipeline(ctx, number):
    raw = gh_raw_checks(number)
    checks = []
    for check in raw:
        link = check.get("link") or ""
        job = re.search(r"/job/(\d+)", link)
        run_id = re.search(r"/runs/(\d+)", link)
        checks.append({
            "name": check["name"],
            "workflow": check.get("workflow"),
            "bucket": check["bucket"],
            "state": check["state"],
            "link": link,
            "run_id": run_id.group(1) if run_id else None,
            "job_id": job.group(1) if job else None,
        })
    status = overall(checks)
    head_sha = json.loads(run(["gh", "pr", "view", number, "--json", "headRefOid"]))["headRefOid"]
    annotations = []
    # Pending polls stay cheap; annotations matter only for terminal results.
    if status != "pending":
        base = f"repos/{ctx['owner']}/{ctx['repo']}"
        for check_run in gh_check_runs(base, head_sha):
            if not (check_run.get("output") or {}).get("annotations_count", 0):
                continue
            for note in gh_api(f"{base}/check-runs/{check_run['id']}/annotations?per_page=100", paginate=True):
                annotations.append({
                    "check": check_run["name"],
                    "level": note["annotation_level"],
                    "path": note["path"],
                    "line": note["start_line"],
                    "message": note["message"],
                })
    return {
        "head_sha": head_sha,
        "overall": status,
        "pipeline": None,
        "checks": checks,
        "annotations": annotations,
    }


def gl_pipeline(ctx, number):
    enc = ctx["encoded"]
    mr = gl_api(f"projects/{enc}/merge_requests/{number}")
    head = mr.get("head_pipeline") or {}
    jobs = []
    if head:
        for job in gl_api(f"projects/{enc}/pipelines/{head['id']}/jobs?per_page=100", paginate=True):
            status = job["status"]
            if status == "failed":
                bucket = "warning" if job.get("allow_failure") else "fail"
            elif status in PENDING_GITLAB_STATUSES:
                bucket = "pending"
            elif status == "success":
                bucket = "pass"
            elif status == "canceled":
                bucket = "cancel"
            else:
                bucket = "skipping"
            jobs.append({
                "name": job["name"],
                "stage": job["stage"],
                "bucket": bucket,
                "state": status,
                "job_id": str(job["id"]),
                "link": job["web_url"],
            })
    return {
        "head_sha": mr["sha"],
        "overall": overall(jobs),
        "pipeline": {"id": head.get("id"), "status": head.get("status"), "url": head.get("web_url")} if head else None,
        "checks": jobs,
        "annotations": [],
    }


def push_branch(remote="origin", branch=None):
    branch = branch or current_branch()
    if branch in protected_branches():
        raise ValidationError([f"refusing to push protected branch '{branch}'; create a branch with git-branch first"])
    run(["git", "push", "-u", remote, branch])
    return {"branch": branch, "remote": remote, "pushed": True}


def cmd_context(args):
    ctx = detect_context()
    ctx["current_branch"] = current_branch()
    ctx["default_branch"] = default_base()
    return ctx


def cmd_preflight(args):
    ctx = detect_context()
    branch = current_branch()
    if branch in protected_branches():
        raise ValidationError([f"refusing to create an MR from protected branch '{branch}'; create a branch with git-branch first"])
    base = args.base or default_base()
    if not valid_branch_name(base):
        raise ValidationError([f"--base is not a valid branch name: '{base}'"])
    existing = open_branch_mrs(ctx, branch)
    result = {**ctx, "current_branch": branch, "base": base, "existing_mrs": existing}
    if existing:
        return result
    remote_ref = f"origin/{base}"
    has_remote = subprocess.run(
        ["git", "rev-parse", "--verify", remote_ref], capture_output=True, text=True,
    ).returncode == 0
    base_ref = remote_ref if has_remote else base
    run(["git", "rev-parse", "--verify", base_ref])
    result.update({
        "base_ref": base_ref,
        "head_sha": run(["git", "rev-parse", "HEAD"]).strip(),
        "commits_ahead": int(run(["git", "rev-list", "--count", f"{base_ref}..HEAD"]).strip()),
        "dirty": bool(run(["git", "status", "--porcelain"]).strip()),
    })
    return result


def cmd_push(args):
    if not REMOTE_RE.fullmatch(args.remote):
        raise ValidationError([f"--remote is not valid: '{args.remote}'"])
    detect_context()
    return push_branch(args.remote)


def cmd_templates(args):
    ctx = detect_context()
    root = Path(run(["git", "rev-parse", "--show-toplevel"]).strip())
    candidates = [root / p for p in TEMPLATE_FILES[ctx["provider"]]]
    for directory in TEMPLATE_DIRS[ctx["provider"]]:
        if (root / directory).is_dir():
            candidates += sorted((root / directory).glob("*.md"))
    seen, paths = set(), []
    for path in candidates:
        if not path.is_file():
            continue
        stat_result = path.stat()
        identity = (stat_result.st_dev, stat_result.st_ino)
        if identity in seen:
            continue
        seen.add(identity)
        paths.append(path)
    relative = [str(path.relative_to(root)) for path in paths]
    if args.path:
        if args.path not in relative:
            raise ValidationError([f"--path must be one of the discovered templates: {', '.join(relative) or 'none'}"])
        selected = paths[relative.index(args.path)]
        return {"path": args.path, "content": selected.read_text(encoding="utf-8")}
    return [{"path": path} for path in relative]


def existing_mr_result(ctx, head):
    existing = open_branch_mrs(ctx, head)
    if len(existing) == 1:
        return {"url": existing[0]["url"], "number": existing[0]["number"], "existing": True}
    if len(existing) > 1:
        fail(f"multiple open MRs exist for branch '{head}'; use mr-view --mr explicitly")
    return None


def cmd_mr_create(args):
    title = args.title.strip()
    problems = []
    if not title:
        problems.append("--title is required")
    elif len(title) > TITLE_MAX:
        problems.append(f"--title is {len(title)} chars; maximum is {TITLE_MAX}")
    if "\n" in title or "\r" in title:
        problems.append("--title must be a single line")
    for name, value in (("--base", args.base), ("--head", args.head)):
        if value and not valid_branch_name(value):
            problems.append(f"{name} is not a valid branch name: '{value}'")
    try:
        body = read_limited(args.body_file, MR_BODY_MAX_CHARS, "--body-file")
    except ValidationError as error:
        problems.extend(error.problems)
        body = ""
    if problems:
        raise ValidationError(problems)

    ctx = detect_context()
    head = args.head or current_branch()
    if not args.no_push and head != current_branch():
        raise ValidationError(["--head must be the current branch when pushing; switch to it or use --no-push"])
    base = args.base or default_base()

    if args.no_push:
        local_sha = run(["git", "rev-parse", head]).strip()
        remote = run(["git", "ls-remote", "--heads", "origin", f"refs/heads/{head}"]).strip()
        if not remote:
            raise ValidationError([f"--no-push requires remote branch 'origin/{head}' to exist"])
        if remote.split()[0] != local_sha:
            raise ValidationError([f"--no-push requires 'origin/{head}' to match local '{head}'; push it first"])
    else:
        push_branch(branch=head)

    try:
        if ctx["provider"] == "github":
            cmd = ["gh", "pr", "create", "--title", title, "--body-file", args.body_file, "--head", head, "--base", base]
            if args.draft:
                cmd.append("--draft")
            return {"url": run(cmd).strip(), "existing": False}
        payload = {
            "source_branch": head,
            "target_branch": base,
            "title": title,
            "description": body,
            "draft": bool(args.draft),
        }
        raw = run(
            ["glab", "api", "--input", "-", "-X", "POST", f"projects/{ctx['encoded']}/merge_requests"],
            input_text=json.dumps(payload),
        )
        mr = json.loads(raw)
        return {"url": mr["web_url"], "number": mr["iid"], "existing": False}
    except ForgeError as create_error:
        try:
            existing = existing_mr_result(ctx, head)
        except ForgeError:
            raise create_error
        if existing:
            return existing
        raise create_error


def mr_view(ctx, number=None):
    if ctx["provider"] == "github":
        fields = "number,title,url,state,isDraft,headRefName,baseRefName,headRefOid,body"
        cmd = ["gh", "pr", "view"]
        if number:
            cmd.append(number)
        cmd += ["--json", fields]
        data = json.loads(run(cmd))
        return {
            "number": data["number"],
            "title": data["title"],
            "url": data["url"],
            "state": data["state"].lower(),
            "draft": data["isDraft"],
            "source_branch": data["headRefName"],
            "target_branch": data["baseRefName"],
            "head_sha": data["headRefOid"],
            "description": data["body"] or "",
        }
    number = resolve_mr(ctx, number)
    mr = gl_api(f"projects/{ctx['encoded']}/merge_requests/{number}")
    return {
        "number": mr["iid"],
        "title": mr["title"],
        "url": mr["web_url"],
        "state": mr["state"],
        "draft": mr.get("draft", mr.get("work_in_progress", False)),
        "source_branch": mr["source_branch"],
        "target_branch": mr["target_branch"],
        "head_sha": mr["sha"],
        "description": mr.get("description") or "",
    }


def cmd_mr_view(args):
    ctx = detect_context()
    number = check_number(args.mr, "--mr")
    return mr_view(ctx, number)


def cmd_mr_comments(args):
    ctx = detect_context()
    number = resolve_mr(ctx, args.mr)
    include_general = not args.review_only
    items = gh_comments(ctx, number, include_general) if ctx["provider"] == "github" else gl_comments(ctx, number, include_general)
    if args.unresolved_only:
        items = [item for item in items if item["resolved"] is not True]
    if args.review_only:
        items = [item for item in items if item["kind"] == "review_thread"]
    return items


def cmd_mr_reply(args):
    thread = check_thread(args.thread_id)
    body = read_limited(args.body_file, REPLY_MAX_CHARS, "reply --body-file")
    ctx = detect_context()
    number = resolve_mr(ctx, args.mr)
    if ctx["provider"] == "github":
        if thread.startswith("issue:"):
            run(["gh", "pr", "comment", number, "--body", body])
            return {"posted": True, "scope": "merge_request"}
        data = gh_graphql(GH_REPLY_MUTATION, thread=thread, body=body)
        return {"posted": True, "url": data["addPullRequestReviewThreadReply"]["comment"]["url"]}
    enc = ctx["encoded"]
    if thread.startswith("general:"):
        note = gl_api(f"projects/{enc}/merge_requests/{number}/notes", method="POST", fields={"body": body})
        return {"posted": True, "scope": "merge_request", "note_id": note["id"]}
    note = gl_api(f"projects/{enc}/merge_requests/{number}/discussions/{thread}/notes", method="POST", fields={"body": body})
    return {"posted": True, "note_id": note["id"]}


def cmd_mr_resolve(args):
    thread = check_thread(args.thread_id)
    if thread.startswith(("issue:", "general:")):
        raise ValidationError(["general merge request comments cannot be resolved; use mr-reply instead"])
    ctx = detect_context()
    number = resolve_mr(ctx, args.mr)
    if ctx["provider"] == "github":
        gh_graphql(GH_UNRESOLVE_MUTATION if args.unresolve else GH_RESOLVE_MUTATION, thread=thread)
    else:
        state = "false" if args.unresolve else "true"
        gl_api(f"projects/{ctx['encoded']}/merge_requests/{number}/discussions/{thread}?resolved={state}", method="PUT")
    return {"thread_id": thread, "resolved": not args.unresolve}


def cmd_pipeline_status(args):
    ctx = detect_context()
    number = resolve_mr(ctx, args.mr)
    result = gh_pipeline(ctx, number) if ctx["provider"] == "github" else gl_pipeline(ctx, number)
    result["mr"] = number
    return result


def cmd_job_log(args):
    job = check_number(args.job, "--job")
    if not 1 <= args.tail <= TAIL_MAX:
        raise ValidationError([f"--tail must be between 1 and {TAIL_MAX}; got {args.tail}"])
    ctx = detect_context()
    if ctx["provider"] == "github":
        out = run(["gh", "run", "view", "--job", job, "--log-failed"])
    else:
        out = run(["glab", "api", f"projects/{ctx['encoded']}/jobs/{job}/trace"])
    return "\n".join(out.splitlines()[-args.tail:])


def cmd_rerun(args):
    job = check_number(args.job, "--job") if args.job else None
    run_id = check_number(args.run, "--run") if args.run else None
    ctx = detect_context()
    if ctx["provider"] == "github":
        if not run_id:
            raise ValidationError(["GitHub reruns need --run (run_id from pipeline-status)"])
        cmd = ["gh", "run", "rerun", run_id, "--job", job] if job else ["gh", "run", "rerun", run_id, "--failed"]
        run(cmd)
        return {"rerun": True, "run": run_id, "job": job}
    if not job:
        raise ValidationError(["GitLab reruns need --job (job_id from pipeline-status)"])
    result = gl_api(f"projects/{ctx['encoded']}/jobs/{job}/retry", method="POST")
    return {"rerun": True, "job": job, "new_job_id": str(result["id"]) if result else None}


def mr_diff(ctx, number):
    if ctx["provider"] == "github":
        base = f"repos/{ctx['owner']}/{ctx['repo']}"
        files = gh_api(f"{base}/pulls/{number}/files?per_page=100", paginate=True)
        result = []
        for item in files:
            new = item["filename"]
            old = item.get("previous_filename") or new
            patch = item.get("patch") or ""
            if patch and not patch.endswith("\n"):
                patch += "\n"
            result.append({
                "old_path": old,
                "new_path": new,
                "status": "deleted" if item["status"] == "removed" else item["status"],
                "too_large": "patch" not in item,
                "diff": f"diff --git a/{old} b/{new}\n{patch}",
            })
        return result
    files = gl_api(f"projects/{ctx['encoded']}/merge_requests/{number}/diffs?per_page=100", paginate=True)
    result = []
    for f in files:
        if f.get("new_file"):
            status = "added"
        elif f.get("deleted_file"):
            status = "deleted"
        elif f.get("renamed_file"):
            status = "renamed"
        else:
            status = "modified"
        result.append({
            "old_path": f["old_path"],
            "new_path": f["new_path"],
            "status": status,
            "too_large": bool(f.get("too_large")),
            "diff": f"diff --git a/{f['old_path']} b/{f['new_path']}\n{f.get('diff') or ''}",
        })
    return result


def mr_commits(ctx, number):
    if ctx["provider"] == "github":
        data = json.loads(run(["gh", "pr", "view", number, "--json", "commits"]))
        return [
            {"sha": c["oid"][:12], "title": c["messageHeadline"], "body": (c.get("messageBody") or "").strip()}
            for c in data["commits"]
        ]
    commits = gl_api(f"projects/{ctx['encoded']}/merge_requests/{number}/commits?per_page=100", paginate=True)
    result = []
    for c in commits:
        message = (c.get("message") or "").strip()
        body = message.split("\n", 1)[1].strip() if "\n" in message else ""
        result.append({"sha": c["short_id"], "title": c["title"], "body": body})
    return result


def closing_issue_numbers(ctx, number):
    if ctx["provider"] == "github":
        data = json.loads(run(["gh", "pr", "view", number, "--json", "closingIssuesReferences"]))
        return [str(i["number"]) for i in data.get("closingIssuesReferences", [])]
    issues = gl_api(f"projects/{ctx['encoded']}/merge_requests/{number}/closes_issues?per_page=100", paginate=True)
    return [str(i["iid"]) for i in issues]


def fetch_issue(ctx, number):
    if ctx["provider"] == "github":
        data = gh_api(f"repos/{ctx['owner']}/{ctx['repo']}/issues/{number}")
        return {
            "number": number,
            "kind": "merge_request" if "pull_request" in data else "issue",
            "title": data["title"],
            "state": data["state"],
            "labels": [label["name"] for label in data.get("labels", [])],
            "url": data["html_url"],
            "body": (data.get("body") or "")[:ISSUE_BODY_MAX],
        }
    data = gl_api(f"projects/{ctx['encoded']}/issues/{number}")
    return {
        "number": number,
        "kind": "issue",
        "title": data["title"],
        "state": data["state"],
        "labels": data.get("labels", []),
        "url": data["web_url"],
        "body": (data.get("description") or "")[:ISSUE_BODY_MAX],
    }


def cmd_mr_diff(args):
    ctx = detect_context()
    number = resolve_mr(ctx, args.mr)
    files = mr_diff(ctx, number)
    return {"mr": number, "count": len(files), "files": files}


def cmd_mr_commits(args):
    ctx = detect_context()
    number = resolve_mr(ctx, args.mr)
    return mr_commits(ctx, number)


def mr_issues(ctx, number, view=None, commits=None, include_mentioned=True):
    view = view or mr_view(ctx, number)
    commits = commits if commits is not None else mr_commits(ctx, number)
    text = "\n".join(
        [view["title"], view["description"], view["source_branch"]]
        + [f"{c['title']}\n{c['body']}" for c in commits]
    )
    closing = closing_issue_numbers(ctx, number)
    mentioned = sorted({m for m in ISSUE_REF_RE.findall(text)} - set(closing), key=int)
    wanted = [(n, "closes") for n in closing]
    if include_mentioned:
        wanted += [(n, "mentioned") for n in mentioned]
    issues = []
    for issue_number, source in wanted[:ISSUE_FETCH_MAX]:
        try:
            item = fetch_issue(ctx, issue_number)
        except ForgeError as error:
            item = {"number": issue_number, "error": str(error)}
        item["source"] = source
        issues.append(item)
    return {
        "issues": issues,
        "mentioned_issues": [] if include_mentioned else mentioned,
        "truncated": len(wanted) > ISSUE_FETCH_MAX,
        "external_refs": sorted(set(EXTERNAL_KEY_RE.findall(text))),
    }


def cmd_mr_issues(args):
    ctx = detect_context()
    number = resolve_mr(ctx, args.mr)
    return mr_issues(ctx, number)


def cmd_mr_issue(args):
    ctx = detect_context()
    number = check_number(args.issue, "--issue")
    item = fetch_issue(ctx, number)
    item["source"] = "mentioned"
    return item


def cmd_review_context(args):
    ctx = detect_context()
    number = check_number(args.mr, "--mr")
    view = mr_view(ctx, number)
    number = str(view["number"])
    commits = mr_commits(ctx, number)
    issues = mr_issues(ctx, number, view=view, commits=commits, include_mentioned=False)
    files = mr_diff(ctx, number)
    final_view = mr_view(ctx, number)
    if final_view["head_sha"] != view["head_sha"]:
        fail(f"MR {number} changed from {view['head_sha']} to {final_view['head_sha']} while gathering context; rerun")
    return {
        "provider": ctx["provider"],
        "view": view,
        "commits": commits,
        "issues": issues,
        "files": files,
    }


def build_parser():
    parser = argparse.ArgumentParser(description="GitHub/GitLab wrapper for merge request workflows.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("context", help="show provider, repo and current branch")
    p = sub.add_parser("preflight", help="validate branch/base and find an existing MR before drafting")
    p.add_argument("--base", help="target branch (default: remote default branch)")
    p = sub.add_parser("templates", help="list merge/pull request templates")
    p.add_argument("--path", help="return content for one discovered template path")

    p = sub.add_parser("push", help="push current branch with upstream set")
    p.add_argument("--remote", default="origin")

    p = sub.add_parser("mr-create", help="create an MR/PR from a markdown body file")
    p.add_argument("--title", required=True, help=f"single line, max {TITLE_MAX} chars")
    p.add_argument("--body-file", required=True, help="markdown file with the description")
    p.add_argument("--base", help="target branch")
    p.add_argument("--head", help="source branch (default: current branch)")
    p.add_argument("--draft", action="store_true")
    p.add_argument("--no-push", action="store_true", help="skip pushing the branch first")

    p = sub.add_parser("mr-view", help="show MR/PR details")
    p.add_argument("--mr", help="number, e.g. 42 (default: MR for current branch)")

    p = sub.add_parser("mr-comments", help="list review threads and comments as JSON")
    p.add_argument("--mr", help="number, e.g. 42 (default: MR for current branch)")
    p.add_argument("--unresolved-only", action="store_true")
    p.add_argument("--review-only", action="store_true", help="exclude general MR/PR comments")

    p = sub.add_parser("mr-reply", help="reply to a thread, or post a general comment")
    p.add_argument("--mr", help="number, e.g. 42")
    p.add_argument("--thread-id", required=True, help="thread_id from mr-comments")
    p.add_argument("--body-file", required=True, help=f"reply text file, max {REPLY_MAX_CHARS} chars")

    p = sub.add_parser("mr-resolve", help="resolve or unresolve a review thread")
    p.add_argument("--mr", help="number, e.g. 42")
    p.add_argument("--thread-id", required=True, help="thread_id from mr-comments")
    p.add_argument("--unresolve", action="store_true")

    p = sub.add_parser("pipeline-status", help="pipeline checks, failures and warnings")
    p.add_argument("--mr", help="number, e.g. 42")

    p = sub.add_parser("job-log", help="tail of a job log")
    p.add_argument("--job", required=True, help="job_id from pipeline-status")
    p.add_argument("--tail", type=int, default=200, help=f"lines, 1-{TAIL_MAX}")

    p = sub.add_parser("rerun", help="rerun failed jobs")
    p.add_argument("--run", help="GitHub run_id from pipeline-status")
    p.add_argument("--job", help="job_id from pipeline-status")

    p = sub.add_parser("mr-diff", help="changed files with unified diffs")
    p.add_argument("--mr", help="number, e.g. 42")

    p = sub.add_parser("mr-commits", help="commits in the MR, oldest first")
    p.add_argument("--mr", help="number, e.g. 42")

    p = sub.add_parser("mr-issues", help="linked issues (closing and mentioned) and external ticket keys")
    p.add_argument("--mr", help="number, e.g. 42")

    p = sub.add_parser("mr-issue", help="fetch one mentioned issue when it is central to intent")
    p.add_argument("--issue", required=True, help="issue number, e.g. 42")

    p = sub.add_parser("review-context", help="gather review data with shared provider requests")
    p.add_argument("--mr", help="number, e.g. 42 (default: MR for current branch)")

    return parser


COMMANDS = {
    "context": cmd_context,
    "preflight": cmd_preflight,
    "push": cmd_push,
    "templates": cmd_templates,
    "mr-create": cmd_mr_create,
    "mr-view": cmd_mr_view,
    "mr-comments": cmd_mr_comments,
    "mr-reply": cmd_mr_reply,
    "mr-resolve": cmd_mr_resolve,
    "pipeline-status": cmd_pipeline_status,
    "job-log": cmd_job_log,
    "rerun": cmd_rerun,
    "mr-diff": cmd_mr_diff,
    "mr-commits": cmd_mr_commits,
    "mr-issues": cmd_mr_issues,
    "mr-issue": cmd_mr_issue,
    "review-context": cmd_review_context,
}


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = COMMANDS[args.cmd](args)
    except ValidationError as error:
        print(json.dumps({"error": "invalid parameters", "problems": error.problems}, indent=2), file=sys.stderr)
        return 2
    except (ForgeError, OSError, UnicodeError, json.JSONDecodeError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1
    if isinstance(result, str):
        print(result)
    else:
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
