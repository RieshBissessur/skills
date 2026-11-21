#!/usr/bin/env bash
# Proves the native Git pre-commit hook works, in a scratch copy of the repo.
#
#   1. a commit that stages Python runs the pipeline and succeeds
#   2. a docs-only commit skips the pipeline
#   3. a commit whose pipeline fails is rejected
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/verify-hook.XXXXXX")"
trap 'rm -rf "$SCRATCH"' EXIT

(
  cd "$REPO"
  tar --exclude=.git --exclude=__pycache__ -cf - .
) | (
  cd "$SCRATCH"
  tar -xf -
)

cd "$SCRATCH"
git init -q -b main
git config user.email "verify@example.com"
git config user.name "verify"
git config commit.gpgsign false
git config core.hooksPath .git/hooks
git add -A
git commit -qm "chore: baseline"

git config core.hooksPath .githooks
chmod +x .githooks/pre-commit

echo "== case 1: a staged Python file runs the pipeline"
echo "print('hi')" > scripts/new_thing.py
git add scripts/new_thing.py
git commit -qm "feat: add new script"
git log -1 --format='  committed: %s'

echo "== case 2: a docs-only commit skips the pipeline"
before="$(git rev-parse HEAD)"
printf '\nExtra docs.\n' >> README.md
git add README.md
git commit -qm "docs: update readme"
after="$(git rev-parse HEAD)"
if [ "$before" = "$after" ]; then
  echo "  FAIL: docs commit did not go through" >&2
  exit 1
fi
echo "  ok: docs commit went through without running the pipeline"

echo "== case 3: a failing pipeline rejects the commit"
cat > tests/test_hook_failure.py <<'PY'
import unittest


class HookFailure(unittest.TestCase):
    def test_fails_on_purpose(self):
        self.fail("intentional failure for verify_hook.sh")
PY
git add tests/test_hook_failure.py
before="$(git rev-parse HEAD)"
if git commit -qm "test: should be blocked"; then
  echo "  FAIL: commit succeeded even though the pipeline failed" >&2
  exit 1
fi
after="$(git rev-parse HEAD)"
if [ "$before" != "$after" ]; then
  echo "  FAIL: commit moved despite the pipeline failure" >&2
  exit 1
fi
echo "  ok: commit rejected"

# Remove the intentionally failing test, then prove a deleted Python file still
# runs the pipeline (a deletion is a change to Python code).
git reset -q HEAD tests/test_hook_failure.py
rm -f tests/test_hook_failure.py

echo "== case 4: deleting a Python file runs the pipeline"
git rm -q scripts/new_thing.py
git commit -qm "chore: remove new script"
git log -1 --format='  committed: %s'

echo "verify_hook: ok"
