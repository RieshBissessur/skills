---
name: git-commit
description: Create a validated Conventional Commit from structured inputs. Use when committing or saving changes, writing a commit message, or when another workflow skill needs a commit.
---

# git-commit

Commits the requested files with a canonical header. You pass parameters, never a free-text commit message. The script builds the header, checks every limit, and commits.

Script: `scripts/commit.py` in this skill's folder. Use the base directory of this SKILL.md as `<skill-dir>`.

## Parameters

| Parameter | Required | Value | Example |
|-----------|----------|-------|---------|
| `--type` | yes | one of `feat` (new feature), `fix` (bug fix), `docs`, `style` (formatting only), `refactor` (no behaviour change), `perf`, `test`, `build` (build system or dependencies), `ci` (pipeline config), `chore` (other maintenance), `revert` | `fix` |
| `--service` | no | the service or area, lowercase, letters, digits, `-`; starts with a letter; max 20 chars | `billing` |
| `--package` | no | package/module inside the service; requires `--service`, same slug rules | `invoices` |
| `--message` | yes | short imperative summary, lowercase first letter, no trailing period, **max 50 chars** | `reject expired refresh tokens` |
| `--breaking` | no | flag; adds `!` to the header for a breaking change | |
| `--body-file` | no | text file with a longer explanation, wrapped at 72 columns, max 4000 chars | `<run-tmp>/commit-body.md` |
| `--add PATH...` | one of | files to stage and commit (relative paths) | `src/auth/refresh.ts` |
| `--all` | one of | stage every change (`git add -A`); use only when all changes belong in this commit | |
| `--validate-only` | no | check parameters without committing | |

The header is built as `type(service/package)!: message`. Examples:

| Parameters | Header |
|------------|--------|
| `--type feat --message "add pdf export"` | `feat: add pdf export` |
| `--type fix --service billing --message "round totals"` | `fix(billing): round totals` |
| `--type refactor --service billing --package invoices --message "split pdf renderer" --breaking` | `refactor(billing/invoices)!: split pdf renderer` |

## Steps

1. **Look at the changes** (read-only):
   ```
   git status --short
   git diff --stat
   ```
   Read the diff where needed to understand the change.

2. **Choose the parameters.** Pick `--type` from the table. Use `--service` and `--package` only when the change is clearly scoped to them. Write `--message` as a short summary of what the change does.

3. **Add a body only if it adds value.** Skip it for small, self-explanatory changes. Otherwise create a fresh directory with `mktemp -d` and write `<run-tmp>/commit-body.md` with the reason and any non-obvious consequence (see `references/conventions.md`).

4. **Commit** the intended files. The script validates everything before staging:
   ```
   python3 <skill-dir>/scripts/commit.py --type fix --service billing --message "round totals" --add src/billing/totals.ts src/billing/totals.test.ts
   ```
   If you created a body, add `--body-file "<run-tmp>/commit-body.md"`. Use `--validate-only` only to preview the header without committing; do not run it before every commit.

5. **Report** the short SHA and the header.

## Errors

The script exits with code 2 and lists every invalid parameter in `problems`. Fix each one and rerun. Typical fix: shorten `--message`, moving detail into `--body-file`.

Exit code 1 means git failed (for example a pre-commit hook). Report the hook output. Do not bypass hooks.

## Rules

- The script refuses to commit on `main`, `master`, `develop`, `trunk`, or the remote default branch. Create a branch with `../git-branch/SKILL.md` first.
- With `--add`, unrelated pre-staged paths are rejected so they cannot be committed accidentally.
- Do not amend, rebase, or use `--no-verify` unless the user explicitly asks.
- Other skills use the commit step and parameters above; they do not define their own commit format.

## Output

- Success: one line, `<sha> <header>`.
- Failure: the first problem in plain words and the fix, nothing else.

## Used by

- `../mr-comment-addresser/SKILL.md`: commit review fixes (`--type fix`, or `refactor`/`test`/`docs` as the change needs)
- `../mr-babysit/SKILL.md`: commit pipeline fixes
- `../test-write/SKILL.md`: commit tests only when the user asks (`--type test`)

Body wording and examples are in `references/conventions.md`.
