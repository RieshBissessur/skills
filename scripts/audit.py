#!/usr/bin/env python3
"""Audit the marketplace for safety and public-repo quality.

Checks, from the repo root:
  Safety:   token/key patterns in tracked files, dangerous shell/eval/exec,
            secret-looking paths on disk, uncommitted changes.
  Identity: commit authors and emails in the history.
  Hooks:    the pre-commit YAML and the native .githooks/pre-commit exist,
            and core.hooksPath points at them.
  Quality:  the pipeline passes, the hook proof passes, install smoke passes.

Run: python3 scripts/audit.py
Exit: 0 when no findings, 1 otherwise (all findings are printed).
"""

import collections
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TOKEN_RE = re.compile(
    r"(?:ghp_[A-Za-z0-9]{36}|glpat-[A-Za-z0-9_-]{8,}|AKIA[0-9A-Z]{16}"
    r"|-----BEGIN [A-Z ]+PRIVATE KEY-----|ssh-[a-z0-9]+ [A-Za-z0-9+/=]{20,})"
)
USER_RE = re.compile(r"/Users/[^\s'\"`\\]+")
BAD_SHELL = re.compile(r"shell\s*=\s*True|os\.system\s*\(|\beval\s*\(|\bexec\s*\(|open\s*\(\s*['\"](/etc|/proc|/dev)")
SECRET_FILENAMES = re.compile(
    r"(^|/)\.env$|(^|/)\.env\.[^/]+$|/\.ssh/|id_(rsa|ed25519|ecdsa|dsa)$"
    r"|credentials\.json$|\.pem$|\.p12$|\.pfx$|\.key$|\.crt$"
)


def sh(*args, cwd=None):
    proc = subprocess.run(["git", *args], cwd=cwd or ROOT, capture_output=True, text=True)
    return proc.stdout


def main():
    findings = []

    tracked = [Path(p) for p in sh("ls-files").split() if p]

    # Safety: tokens in tracked files
    for f in tracked:
        path = ROOT / f
        if not path.is_file():
            continue
        for i, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            for match in TOKEN_RE.findall(line):
                findings.append(f"safety: token pattern in {f}:{i}: {match[:12]}...")

    # Safety: dangerous shell patterns in scripts and hooks
    for f in tracked:
        if f.suffix not in (".py", ".sh") and ".githooks" not in f.parts:
            continue
        path = ROOT / f
        if not path.is_file():
            continue
        for i, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            if BAD_SHELL.search(line):
                findings.append(f"safety: shell pattern in {f}:{i}: {line.strip()[:80]}")

    # Safety: secret-looking paths on disk, without walking .git
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", "node_modules")]
        for name in filenames:
            rel = Path(dirpath, name).relative_to(ROOT)
            if SECRET_FILENAMES.search(str(rel)):
                findings.append(f"safety: secret-looking path on disk: {rel}")

    # Safety: uncommitted changes
    status = sh("status", "--porcelain").strip()
    if status:
        findings.append(f"gap: {len(status.splitlines())} change(s) not committed")

    # Identity: authors in history
    authors = collections.Counter()
    for line in sh("log", "--format=%an|%ae").splitlines():
        name, email = line.split("|", 1)
        authors[(name, email)] += 1
    for (name, email), count in sorted(authors.items()):
        if "noreply.github.com" not in email:
            findings.append(f"identity: {name} <{email}> on {count} commit(s); set git identity to a noreply address")

    # Gaps: personal paths in docs
    for i, line in enumerate((ROOT / "README.md").read_text().splitlines(), 1):
        for match in USER_RE.findall(line):
            findings.append(f"gap: README.md:{i} names a personal path: {match}")

    # Hooks: both canonical forms must exist and the native one must be active
    precommit_yaml = ROOT / ".pre-commit-config.yaml"
    if not precommit_yaml.is_file():
        findings.append("hooks: .pre-commit-config.yaml is missing")
    else:
        text = precommit_yaml.read_text()
        if "scripts/pipeline_check.py" not in text:
            findings.append("hooks: .pre-commit-config.yaml does not run scripts/pipeline_check.py")
        if r"files: '\.py$'" not in text:
            findings.append("hooks: .pre-commit-config.yaml does not limit the hook to Python files")

    native_hook = ROOT / ".githooks" / "pre-commit"
    if not native_hook.is_file():
        findings.append("hooks: .githooks/pre-commit is missing")
    elif not os.access(native_hook, os.X_OK):
        findings.append("hooks: .githooks/pre-commit is not executable")

    hooks_path = sh("config", "--get", "core.hooksPath").strip()
    if hooks_path != ".githooks":
        findings.append(f"hooks: core.hooksPath is '{hooks_path or 'unset'}'; run scripts/install_hooks.sh")

    # Quality: pipeline passes
    r1 = subprocess.run([sys.executable, str(ROOT / "scripts/pipeline_check.py")], cwd=ROOT, capture_output=True, text=True)
    if r1.returncode != 0:
        tail = "\n".join((r1.stdout + r1.stderr).splitlines()[-5:])
        findings.append(f"quality: pipeline_check.py failed:\n{tail}")

    # Quality: hook proof passes
    r2 = subprocess.run(["bash", str(ROOT / "scripts/verify_hook.sh")], cwd=ROOT, capture_output=True, text=True)
    if r2.returncode != 0:
        tail = "\n".join((r2.stdout + r2.stderr).splitlines()[-5:])
        findings.append(f"quality: verify_hook.sh failed:\n{tail}")

    # Quality: install smoke test
    with tempfile.TemporaryDirectory() as d:
        r3 = subprocess.run(["bash", str(ROOT / "scripts/install.sh"), "--dir", d], cwd=ROOT, capture_output=True, text=True)
        wanted = ["git-branch", "git-commit", "mr-create", "mr-comment-addresser", "mr-babysit", "test-write", "mr-review", "go-code", "rust-code"]
        missing = [s for s in wanted if not (Path(d) / s).is_dir()]
        if r3.returncode != 0 or missing:
            findings.append(f"quality: install smoke test failed (missing: {missing}, rc={r3.returncode})")

    print(f"audit: found {len(findings)}")
    for finding in findings:
        print(" -", finding)
    print()
    print("identity in history:")
    for (name, email), count in sorted(authors.items()):
        print(f"  {count:>2}  {name} <{email}>")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
