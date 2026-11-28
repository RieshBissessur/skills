#!/usr/bin/env bash
# Installs the mr-workflow skills for OpenCode and/or Claude Code without the plugin system.
#
#   scripts/install.sh --opencode            -> ~/.config/opencode/skills
#   scripts/install.sh --claude              -> ~/.claude/skills (OpenCode also reads this path)
#   scripts/install.sh --dir /path/to/repo/.opencode/skills   -> project-local install
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/plugins/mr-workflow/skills"
SKILLS=(git-branch git-commit mr-create mr-comment-addresser mr-babysit test-write mr-review go-code rust-code)

targets=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --opencode) targets+=("${XDG_CONFIG_HOME:-$HOME/.config}/opencode/skills") ;;
    --claude) targets+=("$HOME/.claude/skills") ;;
    --dir) targets+=("$2"); shift ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
  shift
done

if [[ ${#targets[@]} -eq 0 ]]; then
  echo "usage: $0 [--opencode] [--claude] [--dir PATH]" >&2
  exit 1
fi

for target in "${targets[@]}"; do
  mkdir -p "$target"
  for skill in "${SKILLS[@]}"; do
    rm -rf "$target/$skill"
    cp -R "$SRC/$skill" "$target/$skill"
  done
  echo "installed ${#SKILLS[@]} skills to $target"
done
