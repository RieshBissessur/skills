#!/usr/bin/env python3
"""Detect the project's language and test runner, run tests, and list changed files.

Subcommands:
  detect                                   language, runner and command for this repo
  run [--target PATH] [--timeout SECONDS]  run the suite, or one file/package, and summarize
  run --command COMMAND                    use an explicit test command when detection fails
  changed [--base BRANCH]                  files changed vs the base branch and in the working tree

Exit codes: 0 success (including completed failed tests), 2 invalid input, 1 runner/git failure.
"""

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

TIMEOUT_MIN = 1
TIMEOUT_MAX = 3600
TIMEOUT_DEFAULT = 900


class RunnerError(Exception):
    pass


class ValidationError(Exception):
    def __init__(self, problems):
        super().__init__("invalid test parameters")
        self.problems = problems


def git(*args, check=True):
    try:
        proc = subprocess.run(["git", *args], capture_output=True, text=True)
    except OSError as error:
        raise RunnerError(f"could not run git: {error}")
    if check and proc.returncode:
        raise RunnerError(f"git {' '.join(args)} failed: {(proc.stderr or proc.stdout).strip()}")
    output = proc.stdout.strip() if proc.returncode == 0 else (proc.stderr or proc.stdout).strip()
    return output


def repo_root():
    return Path(git("rev-parse", "--show-toplevel"))


def detect(root):
    package = root / "package.json"
    if package.is_file():
        try:
            package_data = json.loads(package.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeError, OSError) as error:
            raise RunnerError(f"could not read {package}: {error}")
        if not isinstance(package_data, dict):
            raise RunnerError(f"could not read {package}: top level must be an object")
        scripts = package_data.get("scripts", {})
        if not isinstance(scripts, dict):
            raise RunnerError(f"could not read {package}: scripts must be an object")
        if "test" in scripts:
            if (root / "pnpm-lock.yaml").exists():
                return {"language": "javascript", "runner": "pnpm", "command": ["pnpm", "test"]}
            if (root / "yarn.lock").exists():
                return {"language": "javascript", "runner": "yarn", "command": ["yarn", "test"]}
            return {"language": "javascript", "runner": "npm", "command": ["npm", "test", "--silent"]}
    if any((root / f).exists() for f in ["pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini"]):
        return {"language": "python", "runner": "pytest", "command": [sys.executable, "-m", "pytest", "-q"]}
    if (root / "go.mod").exists():
        return {"language": "go", "runner": "go", "command": ["go", "test", "./..."]}
    if (root / "Cargo.toml").exists():
        return {"language": "rust", "runner": "cargo", "command": ["cargo", "test"]}
    if (root / "Gemfile").exists():
        return {"language": "ruby", "runner": "rspec", "command": ["bundle", "exec", "rspec"]}
    if (root / "pom.xml").exists():
        return {"language": "java", "runner": "maven", "command": ["mvn", "-q", "test"]}
    if (root / "gradlew").exists() or (root / "gradlew.bat").exists():
        wrapper = "gradlew.bat" if os.name == "nt" else "./gradlew"
        return {"language": "java", "runner": "gradle", "command": [wrapper, "test"]}
    if (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
        return {"language": "java", "runner": "gradle", "command": ["gradle", "test"]}
    raise RunnerError("no known test runner found; ask for a command and use run --command")


def validate_target(root, target):
    if target.startswith("-") or Path(target).is_absolute() or ".." in Path(target).parts:
        return f"--target must be a relative path inside the repo: '{target}'"
    if not (root / target).exists():
        return f"--target does not exist: '{target}'"
    return None


def validate_timeout(value):
    if not TIMEOUT_MIN <= value <= TIMEOUT_MAX:
        return f"--timeout must be between {TIMEOUT_MIN} and {TIMEOUT_MAX} seconds; got {value}"
    return None


def targeted_command(info, target):
    """Translate a repo-relative target without invoking a shell."""
    runner = info["runner"]
    command = list(info["command"])
    path = Path(target)
    if runner in ("npm", "pnpm", "yarn", "custom"):
        return command + ["--", target] if runner != "custom" else command + [target]
    if runner == "go":
        package = path.parent if path.suffix == ".go" else path
        package_text = package.as_posix()
        if package_text in ("", "."):
            package_text = "."
        elif not package_text.startswith("."):
            package_text = f"./{package_text}"
        command[-1] = package_text
        return command
    if runner == "cargo":
        if len(path.parts) == 2 and path.parts[0] == "tests" and path.suffix == ".rs":
            return command + ["--test", path.stem]
        raise ValidationError([
            "Cargo --target supports only tests/<name>.rs; omit --target for crate or workspace tests"
        ])
    if runner in ("pytest", "rspec"):
        return command + [target]
    if runner in ("maven", "gradle"):
        raise ValidationError([f"{runner} does not support --target here; omit it to run the test suite"])
    raise ValidationError([f"--target is not supported for runner '{runner}'"])


def cmd_detect(args):
    root = repo_root()
    info = detect(root)
    info["root"] = str(root)
    return info


def cmd_run(args):
    root = repo_root()
    problems = []
    if args.target:
        problem = validate_target(root, args.target)
        if problem:
            problems.append(problem)
    problem = validate_timeout(args.timeout)
    if problem:
        problems.append(problem)
    command = None
    if args.command:
        try:
            command = shlex.split(args.command)
        except ValueError as error:
            problems.append(f"--command could not be parsed: {error}")
        if not command:
            problems.append("--command must not be empty")
    if problems:
        raise ValidationError(problems)

    info = detect(root) if command is None else {"language": None, "runner": "custom", "command": command}
    command = targeted_command(info, args.target) if args.target else list(info["command"])
    try:
        proc = subprocess.run(
            command,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=args.timeout,
        )
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        tail = "\n".join(output.splitlines()[-20:])
        suffix = f"\n{tail}" if tail else ""
        raise RunnerError(f"tests timed out after {args.timeout}s: {shlex.join(command)}{suffix}")
    except OSError as error:
        raise RunnerError(f"could not run '{command[0]}': {error}")
    output = (proc.stdout or "").splitlines()
    return {
        "language": info["language"],
        "runner": info["runner"],
        "command": shlex.join(command),
        "exit_code": proc.returncode,
        "passed": proc.returncode == 0,
        "tail": "\n".join(output[-80:]),
    }


def default_base():
    try:
        return git("symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    except RunnerError:
        return "main"


def cmd_changed(args):
    if args.base:
        proc = subprocess.run(
            ["git", "check-ref-format", "--branch", args.base],
            capture_output=True,
            text=True,
        )
        if proc.returncode:
            raise ValidationError([f"--base must be a valid branch name such as main; got '{args.base}'"])
    base = args.base or default_base()
    candidates = [base]
    if not base.startswith("origin/"):
        candidates.append(f"origin/{base}")
    for candidate in candidates:
        exists = subprocess.run(
            ["git", "rev-parse", "--verify", candidate],
            capture_output=True,
            text=True,
        )
        if exists.returncode == 0:
            merge_base = git("merge-base", candidate, "HEAD")
            committed = git("diff", "--name-only", f"{merge_base}...HEAD").splitlines()
            base = candidate
            break
    else:
        raise RunnerError(f"base '{base}' does not exist locally or as an origin branch; fetch it and rerun")
    working = git("diff", "--name-only", "HEAD").splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    files = sorted(set(f for f in committed + working + untracked if f))
    return {"base": base, "files": files}


def build_parser():
    parser = argparse.ArgumentParser(description="Run and discover project tests.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("detect", help="show language, runner and command")
    p = sub.add_parser("run", help="run tests")
    p.add_argument("--target", help="relative path to a test file or package")
    p.add_argument("--timeout", type=int, default=TIMEOUT_DEFAULT, help=f"seconds, {TIMEOUT_MIN}-{TIMEOUT_MAX}")
    p.add_argument("--command", help="explicit test command, parsed without a shell")
    p = sub.add_parser("changed", help="list changed files")
    p.add_argument("--base", help="base branch name, e.g. main")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    handlers = {"detect": cmd_detect, "run": cmd_run, "changed": cmd_changed}
    try:
        print(json.dumps(handlers[args.cmd](args), indent=2))
        return 0
    except ValidationError as error:
        print(json.dumps({"error": error.args[0], "problems": error.problems}, indent=2), file=sys.stderr)
        return 2
    except (RunnerError, OSError, UnicodeError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
