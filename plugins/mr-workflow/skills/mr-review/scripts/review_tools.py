#!/usr/bin/env python3
"""Gather context for reviewing a GitHub PR or GitLab MR and prepare an isolated worktree.

Subcommands:
  start [--mr N]                         fetch shared context and create a detached worktree
  callers --mr N --symbol S [--symbol S] find symbol uses in one repository scan
  cleanup --mr N                         remove the worktree and temp files

Files are written to a repo-specific <tmp>/mr-review-.../ directory.
Exit codes: 0 success, 2 invalid input (fix and rerun), 1 provider or git failure.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parents[2]
FORGE = SKILLS_DIR / "mr-create" / "scripts" / "forge.py"
TEST_RUNNER = SKILLS_DIR / "test-write" / "scripts" / "test_runner.py"
NUMBER_RE = re.compile(r"^[1-9][0-9]{0,9}$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SYMBOL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,80}$")
CALLERS_MAX = 60
CONVENTION_FILES = [
    "AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md", "README.md",
    "CODEOWNERS", ".github/CODEOWNERS", ".gitlab/CODEOWNERS", "docs/CODEOWNERS",
    ".editorconfig", ".pre-commit-config.yaml", "Makefile",
    "rustfmt.toml", ".rustfmt.toml", "clippy.toml", ".clippy.toml",
    ".golangci.yml", ".golangci.yaml",
    "eslint.config.js", ".eslintrc.json", ".prettierrc", "ruff.toml", "pyproject.toml",
    ".gitlab-ci.yml",
]
CONVENTION_GLOBS = [".github/workflows/*.yml", ".github/workflows/*.yaml", "**/AGENTS.md"]


class ReviewError(Exception):
    pass


class ValidationError(Exception):
    def __init__(self, problems):
        super().__init__("invalid parameters")
        self.problems = problems


def run(cmd, cwd=None, ok=(0,)):
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    except OSError as error:
        raise ReviewError(f"could not run '{cmd[0]}': {error}")
    if proc.returncode not in ok:
        raise ReviewError(f"`{' '.join(cmd[:3])}` failed: {(proc.stderr or proc.stdout).strip()}")
    return proc.stdout


def check_number(value):
    cleaned = str(value).strip().lstrip("#!")
    if not NUMBER_RE.fullmatch(cleaned):
        raise ValidationError([f"--mr must be a positive whole number such as 42; got '{value}'"])
    return cleaned


def repo_root():
    return Path(run(["git", "rev-parse", "--show-toplevel"]).strip()).resolve()


def forge(repo, *args):
    if not FORGE.is_file():
        raise ReviewError(f"mr-create skill not found next to mr-review (expected {FORGE})")
    output = run([sys.executable, str(FORGE), *args], cwd=repo)
    try:
        return json.loads(output)
    except json.JSONDecodeError as error:
        raise ReviewError(f"forge.py returned invalid JSON: {error}")


def work_dir(repo, number):
    repo_id = hashlib.sha256(str(repo.resolve()).encode("utf-8")).hexdigest()[:12]
    return Path(tempfile.gettempdir()) / f"mr-review-{repo_id}-{number}"


def ensure_work_dir(repo, number):
    work = work_dir(repo, number)
    if work.is_symlink():
        raise ReviewError(f"refusing to use symlinked review directory: {work}")
    if work.exists():
        mode = work.stat().st_mode
        if not stat.S_ISDIR(mode):
            raise ReviewError(f"review path is not a directory: {work}")
        if hasattr(os, "getuid") and work.stat().st_uid != os.getuid():
            raise ReviewError(f"review directory is owned by another user: {work}")
    else:
        work.mkdir(mode=0o700, parents=True)
    work.chmod(0o700)
    return work


def count_changes(diff):
    added = sum(1 for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff.splitlines() if line.startswith("-") and not line.startswith("---"))
    return added, removed


def detect_language(worktree):
    proc = subprocess.run(
        [sys.executable, str(TEST_RUNNER), "detect"], cwd=worktree, capture_output=True, text=True,
    )
    if proc.returncode:
        return None, None
    try:
        info = json.loads(proc.stdout)
    except json.JSONDecodeError as error:
        raise ReviewError(f"test runner detection returned invalid JSON: {error}")
    return info["language"], info["runner"]


def existing_conventions(worktree):
    found = {p for p in CONVENTION_FILES if (worktree / p).is_file()}
    for pattern in CONVENTION_GLOBS:
        found.update(str(p.relative_to(worktree)) for p in worktree.glob(pattern) if p.is_file())
    return sorted(found)


def remove_worktree(repo, worktree):
    if worktree.is_symlink():
        raise ReviewError(f"refusing to remove symlinked worktree: {worktree}")
    if worktree.exists():
        proc = subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        if proc.returncode:
            if (worktree / ".git").exists():
                raise ReviewError(f"could not remove worktree {worktree}: {(proc.stderr or proc.stdout).strip()}")
            shutil.rmtree(worktree)
        if worktree.exists():
            raise ReviewError(f"worktree still exists after removal: {worktree}")
    run(["git", "worktree", "prune"], cwd=repo)


def regenerate_large_diffs(worktree, base, head, files):
    regenerated = []
    for item in files:
        if not item.get("too_large") and item.get("diff"):
            continue
        paths = [item["old_path"]] if item["old_path"] == item["new_path"] else [item["old_path"], item["new_path"]]
        item["diff"] = run(["git", "diff", f"{base}...{head}", "--", *paths], cwd=worktree)
        item["too_large"] = False
        regenerated.append(item["new_path"])
    return regenerated


def cmd_start(args):
    repo = repo_root()
    request = ["review-context"]
    if args.mr is not None:
        request += ["--mr", check_number(args.mr)]
    data = forge(repo, *request)
    provider = data["provider"]
    view = data["view"]
    commits = data["commits"]
    issues = data["issues"]
    files = data["files"]
    number = str(view["number"])

    target, head = view["target_branch"], view["head_sha"]
    if not BRANCH_RE.fullmatch(target):
        raise ReviewError(f"unexpected target branch name from provider: {target}")
    if not SHA_RE.fullmatch(head):
        raise ReviewError(f"unexpected head sha from provider: {head}")

    work = ensure_work_dir(repo, number)
    worktree = work / "worktree"
    remove_worktree(repo, worktree)

    mr_ref = f"refs/pull/{number}/head" if provider == "github" else f"refs/merge-requests/{number}/head"
    run([
        "git", "fetch", "origin",
        f"+{mr_ref}:refs/remotes/origin/review/{number}",
        f"+refs/heads/{target}:refs/remotes/origin/{target}",
    ], cwd=repo)
    run(["git", "worktree", "add", "--detach", str(worktree), head], cwd=repo)
    base = run(["git", "merge-base", f"origin/{target}", head], cwd=repo).strip()
    regenerated = regenerate_large_diffs(worktree, base, head, files)

    (work / "diff.patch").write_text("".join(f["diff"] for f in files), encoding="utf-8")
    summary = []
    for item in files:
        added, removed = count_changes(item["diff"])
        summary.append({
            "path": item["new_path"],
            "old_path": item["old_path"] if item["old_path"] != item["new_path"] else None,
            "status": item["status"],
            "added": added,
            "removed": removed,
            "too_large": item.get("too_large", False),
        })
    context = {
        "mr": view,
        "provider": provider,
        "commits": commits,
        "issues": issues,
        "files": summary,
        "base_sha": base,
        "regenerated_files": regenerated,
    }
    (work / "context.json").write_text(json.dumps(context, indent=2), encoding="utf-8")

    language, runner = detect_language(worktree)
    return {
        "mr": number,
        "title": view["title"],
        "provider": provider,
        "state": view["state"],
        "draft": view["draft"],
        "work_dir": str(work),
        "context_file": str(work / "context.json"),
        "diff_file": str(work / "diff.patch"),
        "worktree": str(worktree),
        "base_sha": base,
        "head_sha": head,
        "language": language,
        "runner": runner,
        "changed_files": len(summary),
        "issues": [
            {"number": issue.get("number"), "title": issue.get("title"), "source": issue.get("source")}
            for issue in issues["issues"]
        ],
        "external_refs": issues["external_refs"],
        "mentioned_issues": issues.get("mentioned_issues", []),
        "regenerated_files": regenerated,
        "convention_files": existing_conventions(worktree),
    }


def cmd_callers(args):
    number = check_number(args.mr)
    symbols = sorted(set(args.symbol))
    for symbol in symbols:
        if not SYMBOL_RE.fullmatch(symbol):
            raise ValidationError([f"--symbol must be an identifier such as parse_config; got '{symbol}'"])
    worktree = work_dir(repo_root(), number) / "worktree"
    if not worktree.is_dir() or worktree.is_symlink():
        raise ValidationError([f"no worktree for MR {number} in this repository; run start first"])
    command = ["git", "grep", "-n", "-w", "-F", "-I"]
    for symbol in symbols:
        command += ["-e", symbol]
    proc = subprocess.run(command, cwd=worktree, capture_output=True, text=True)
    if proc.returncode not in (0, 1):
        raise ReviewError(f"git grep failed: {proc.stderr.strip()}")
    lines = proc.stdout.splitlines()
    results = {}
    for symbol in symbols:
        pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(symbol)}(?![A-Za-z0-9_])")
        matches = [line for line in lines if pattern.search(line)]
        results[symbol] = {
            "total": len(matches),
            "matches": matches[:CALLERS_MAX],
            "truncated": len(matches) > CALLERS_MAX,
        }
    if len(symbols) == 1:
        return {"symbol": symbols[0], **results[symbols[0]]}
    return {"symbols": symbols, "results": results}


def cmd_cleanup(args):
    number = check_number(args.mr)
    repo = repo_root()
    work = work_dir(repo, number)
    if work.is_symlink():
        raise ReviewError(f"refusing to clean symlinked review directory: {work}")
    if not work.exists():
        return {"mr": number, "removed": False}
    remove_worktree(repo, work / "worktree")
    shutil.rmtree(work)
    return {"mr": number, "removed": True, "path": str(work)}


def build_parser():
    parser = argparse.ArgumentParser(description="Gather review context and prepare a worktree for an MR/PR.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("start", help="gather context and create the review worktree")
    p.add_argument("--mr", help="number, e.g. 42 (default: MR for current branch)")
    p = sub.add_parser("callers", help="find uses of symbols in the reviewed code")
    p.add_argument("--mr", required=True, help="number, e.g. 42")
    p.add_argument("--symbol", required=True, action="append", help="identifier; repeat to batch")
    p = sub.add_parser("cleanup", help="remove the review worktree and temp files")
    p.add_argument("--mr", required=True, help="number, e.g. 42")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    handlers = {"start": cmd_start, "callers": cmd_callers, "cleanup": cmd_cleanup}
    try:
        print(json.dumps(handlers[args.cmd](args), indent=2))
        return 0
    except ValidationError as error:
        print(json.dumps({"error": "invalid parameters", "problems": error.problems}, indent=2), file=sys.stderr)
        return 2
    except (ReviewError, OSError, UnicodeError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
