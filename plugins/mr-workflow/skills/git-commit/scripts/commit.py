#!/usr/bin/env python3
"""Create a Conventional Commit from typed parameters, validated before committing.

The header is built from parameters, never from free text:

    type(service/package)!: message

  --type      required  one of TYPES
  --service   optional  lowercase slug, max 20 chars, e.g. billing
  --package   optional  lowercase slug, max 20 chars, e.g. invoices
  --message   required  lowercase imperative, max 50 chars, no trailing period
  --breaking  optional  adds "!" after the scope

Limits: message <= 50 chars, header <= 72 chars.
Exit codes: 0 success, 2 invalid input (fix the parameters and rerun), 1 git failure.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TYPES = ["feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore", "revert"]
PROTECTED_BRANCHES = {"main", "master", "develop", "trunk"}
HEADER_MAX = 72
MESSAGE_MAX = 50
SLUG_MAX = 20
BODY_MAX_CHARS = 4000
BODY_LINE_MAX = 72
SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{0,19}$")


class CommitError(Exception):
    pass


class ValidationError(Exception):
    def __init__(self, problems):
        super().__init__("invalid commit parameters")
        self.problems = problems


def git(*args, cwd=None):
    try:
        proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    except OSError as error:
        raise CommitError(f"could not run git: {error}")
    if proc.returncode:
        raise CommitError(f"git {' '.join(args)} failed: {(proc.stderr or proc.stdout).strip()}")
    return proc.stdout.strip()


def repo_root():
    return Path(git("rev-parse", "--show-toplevel"))


def default_branch(root):
    proc = subprocess.run(
        ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip().removeprefix("origin/") if proc.returncode == 0 else None


def build_scope(service, package):
    return "/".join(part for part in (service, package) if part) or None


def build_header(ctype, scope, message, breaking):
    scope_part = f"({scope})" if scope else ""
    return f"{ctype}{scope_part}{'!' if breaking else ''}: {message}"


def validate_message(message, problems):
    if not message:
        problems.append("--message is required")
        return
    if "\n" in message or "\r" in message:
        problems.append("--message must be a single line")
    if len(message) > MESSAGE_MAX:
        problems.append(f"--message is {len(message)} chars; maximum is {MESSAGE_MAX}. Shorten it, put detail in --body-file")
    if message[0].isupper():
        problems.append("--message must start with a lowercase letter")
    if message.endswith("."):
        problems.append("--message must not end with a period")


def validate_body(path, problems):
    file = Path(path)
    if not file.is_file():
        problems.append(f"--body-file not found: {path}")
        return
    text = file.read_text(encoding="utf-8").strip()
    if not text:
        problems.append("--body-file is empty; omit it or add content")
        return
    if len(text) > BODY_MAX_CHARS:
        problems.append(f"--body-file is {len(text)} chars; maximum is {BODY_MAX_CHARS}")
    for line in text.splitlines():
        if len(line) > BODY_LINE_MAX:
            problems.append(f"body line is {len(line)} chars; maximum is {BODY_LINE_MAX}: {line[:40]}...")
            break


def validate_paths(root, paths, problems):
    for path in paths:
        if path.startswith("-") or Path(path).is_absolute() or ".." in Path(path).parts:
            problems.append(f"--add path must be relative and inside the repo: {path}")
            continue
        if not (root / path).exists() and not git("ls-files", "--", path, cwd=root):
            problems.append(f"--add path does not exist and is not tracked: {path}")


def validate(args, root):
    problems = []
    if args.type not in TYPES:
        problems.append(f"--type must be one of {', '.join(TYPES)}; got '{args.type}'")
    for name, value in (("--service", args.service), ("--package", args.package)):
        if value is not None and not SLUG_RE.fullmatch(value):
            problems.append(f"{name} must be lowercase letters, digits or '-', start with a letter, max {SLUG_MAX} chars; got '{value}'")
    if args.package and not args.service:
        problems.append("--package requires --service")
    message = (args.message or "").strip()
    validate_message(message, problems)
    scope = build_scope(args.service, args.package)
    header = build_header(args.type, scope, message, args.breaking)
    if len(header) > HEADER_MAX:
        problems.append(f"header '{header}' is {len(header)} chars; maximum is {HEADER_MAX}. Shorten --service, --package or --message")
    if args.body_file:
        validate_body(args.body_file, problems)
    if args.add:
        validate_paths(root, args.add, problems)
    if args.all and args.add:
        problems.append("use either --add or --all, not both")
    if not args.validate_only and not (args.add or args.all):
        problems.append("nothing selected: pass --add PATH... or --all")
    if problems:
        raise ValidationError(problems)
    return header, message


def main(argv=None):
    parser = argparse.ArgumentParser(description="Create a Conventional Commit from parameters.")
    parser.add_argument("--type", required=True, help=f"one of: {', '.join(TYPES)}")
    parser.add_argument("--service", help="service or area, e.g. billing")
    parser.add_argument("--package", help="package or module inside the service, e.g. invoices")
    parser.add_argument("--message", required=True, help="short lowercase imperative summary, max 50 chars")
    parser.add_argument("--breaking", action="store_true", help="mark as a breaking change")
    parser.add_argument("--body-file", help="optional body text file, wrapped at 72 columns")
    parser.add_argument("--add", nargs="+", metavar="PATH", help="paths to stage and commit")
    parser.add_argument("--all", action="store_true", help="stage all changes (git add -A)")
    parser.add_argument("--validate-only", action="store_true", help="check parameters, do not commit")
    args = parser.parse_args(argv)

    try:
        root = repo_root() if args.add or not args.validate_only else None
        header, message = validate(args, root)
        if args.validate_only:
            print(json.dumps({"valid": True, "header": header, "length": len(header)}, indent=2))
            return 0

        branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=root)
        if branch in PROTECTED_BRANCHES or branch == default_branch(root):
            raise CommitError(f"refusing to commit directly on protected branch '{branch}'; create a branch with git-branch first")
        if args.add:
            staged_before = set(git("diff", "--cached", "--name-only", cwd=root).splitlines())
            selected_before = set(git("diff", "--cached", "--name-only", "--", *args.add, cwd=root).splitlines())
            unrelated = sorted(staged_before - selected_before)
            if unrelated:
                raise ValidationError([
                    "--add would also commit unrelated pre-staged paths: " + ", ".join(unrelated)
                    + "; unstage them or use --all only if every change belongs"
                ])
        if args.all:
            git("add", "-A", cwd=root)
        else:
            git("add", "--", *args.add, cwd=root)
        staged = git("diff", "--cached", "--name-only", cwd=root).splitlines()
        selected = git("diff", "--cached", "--name-only", "--", *args.add, cwd=root).splitlines() if args.add else staged
        if not selected:
            raise CommitError("nothing selected to commit; check the --add paths")

        body = Path(args.body_file).read_text(encoding="utf-8").strip() if args.body_file else ""
        text = header + (f"\n\n{body}" if body else "") + "\n"
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
            handle.write(text)
            message_path = handle.name
        try:
            git("commit", "-F", message_path, cwd=root)
        finally:
            os.remove(message_path)
        sha = git("rev-parse", "--short", "HEAD", cwd=root)
        print(json.dumps({"sha": sha, "header": header, "branch": branch, "files": staged}, indent=2))
        return 0
    except ValidationError as error:
        print(json.dumps({"error": error.args[0], "problems": error.problems}, indent=2), file=sys.stderr)
        return 2
    except (CommitError, OSError, UnicodeError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
