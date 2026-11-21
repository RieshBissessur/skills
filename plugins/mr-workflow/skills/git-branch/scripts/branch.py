#!/usr/bin/env python3
"""Create a feature branch named by convention from the base branch.

Name:  <type>/<ticket>-<slug>   e.g. feat/abc-123-add-login-form
       <type>/<slug>            e.g. fix/null-pointer-on-logout

Exit codes: 0 success, 2 invalid input (fix parameters and rerun), 1 git failure.
"""

import argparse
import json
import re
import subprocess
import sys

TYPES = ["feat", "fix", "hotfix", "chore", "docs", "refactor", "test", "ci", "build", "perf"]
TICKET_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*-\d+$")
SUMMARY_MAX = 80
SLUG_MAX = 50


class BranchError(Exception):
    pass


class ValidationError(Exception):
    def __init__(self, problems):
        super().__init__("invalid branch parameters")
        self.problems = problems


def git(*args, check=True):
    try:
        proc = subprocess.run(["git", *args], capture_output=True, text=True)
    except OSError as error:
        raise BranchError(f"could not run git: {error}")
    if check and proc.returncode:
        raise BranchError(f"git {' '.join(args)} failed: {(proc.stderr or proc.stdout).strip()}")
    output = proc.stdout.strip() if proc.returncode == 0 else (proc.stderr or proc.stdout).strip()
    return proc.returncode == 0, output


def valid_ref(name):
    ok, _ = git("check-ref-format", "--branch", name, check=False)
    return ok


def slugify(text):
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:SLUG_MAX].rstrip("-")


def default_base():
    ok, ref = git("symbolic-ref", "--short", "refs/remotes/origin/HEAD", check=False)
    if ok and ref:
        return ref.removeprefix("origin/")
    return "main"


def validate(args):
    problems = []
    summary = args.summary.strip()
    if not summary:
        problems.append("--summary is required")
    elif len(summary) > SUMMARY_MAX:
        problems.append(f"--summary is {len(summary)} chars; maximum is {SUMMARY_MAX}")
    elif not re.search(r"[A-Za-z0-9]", summary):
        problems.append("--summary must contain letters or digits")
    if args.ticket and not TICKET_RE.fullmatch(args.ticket):
        problems.append(f"--ticket must look like ABC-123; got '{args.ticket}'")
    if args.base and not valid_ref(args.base):
        problems.append(f"--base is not a valid branch name: '{args.base}'")
    if problems:
        raise ValidationError(problems)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Create a convention-named branch.")
    parser.add_argument("--type", required=True, help=f"one of: {', '.join(TYPES)}")
    parser.add_argument("--summary", required=True, help="short description of the work, max 80 chars")
    parser.add_argument("--ticket", help="ticket id such as ABC-123")
    parser.add_argument("--base", help="base branch (default: remote default branch, else main)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        if args.type not in TYPES:
            raise ValidationError([f"--type must be one of {', '.join(TYPES)}; got '{args.type}'"])
        summary = validate(args)
        slug = slugify(summary)
        if not slug:
            raise ValidationError(["--summary produced an empty name; use more letters or digits"])
        name = f"{args.type}/{args.ticket.lower()}-{slug}" if args.ticket else f"{args.type}/{slug}"
        if not valid_ref(name):
            raise ValidationError([f"'{name}' is not a valid branch name"])

        base = args.base or default_base()
        if git("rev-parse", "--verify", f"refs/heads/{name}", check=False)[0]:
            raise ValidationError([f"branch '{name}' already exists; choose a different --summary or --ticket"])
        remote_ref = f"origin/{base}"
        has_remote = git("rev-parse", "--verify", remote_ref, check=False)[0]

        if args.dry_run:
            base_ref = remote_ref if has_remote else base
            print(json.dumps({"branch": name, "base": base_ref, "created": False, "dry_run": True, "fetched": False}, indent=2))
            return 0

        fetched, fetch_message = git("fetch", "origin", base, check=False)
        if fetched:
            base_ref = remote_ref
        elif has_remote:
            raise BranchError(f"could not refresh '{remote_ref}'; refusing to use a stale base: {fetch_message}")
        else:
            base_ref = base
        if not git("rev-parse", "--verify", base_ref, check=False)[0]:
            detail = f": {fetch_message}" if fetch_message else ""
            raise BranchError(f"base '{base_ref}' does not exist{detail}")

        git("switch", "-c", name, base_ref)
        print(json.dumps({"branch": name, "base": base_ref, "created": True, "dry_run": False, "fetched": fetched}, indent=2))
        return 0
    except ValidationError as error:
        print(json.dumps({"error": "invalid branch parameters", "problems": error.problems}, indent=2), file=sys.stderr)
        return 2
    except BranchError as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
