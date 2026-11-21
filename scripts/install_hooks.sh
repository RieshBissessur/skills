#!/usr/bin/env bash
# Install the repository's native Git hooks (tracked in .githooks/).
#
# This uses core.hooksPath so the hook is version-controlled and survives
# checkouts, instead of living only in an untracked .git/hooks file.
#
#   scripts/install_hooks.sh
#
# Do not also run `pre-commit install` in the same clone: the pre-commit
# framework refuses to install while core.hooksPath is set. Choose one:
#   - native hooks:   scripts/install_hooks.sh
#   - pre-commit:     pre-commit install
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

if [ ! -f .githooks/pre-commit ]; then
  echo "error: .githooks/pre-commit is missing" >&2
  exit 1
fi

chmod +x .githooks/pre-commit
git config core.hooksPath .githooks
echo "installed native Git hooks from .githooks (core.hooksPath=.githooks)"
