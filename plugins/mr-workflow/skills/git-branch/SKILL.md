---
name: git-branch
description: Create a convention-named git branch from the latest base branch. Use when starting work, creating a feature/fix/hotfix branch, or naming a branch for a ticket.
---

# git-branch

Creates a correctly named branch from the up-to-date base branch. The script builds the name from parameters, validates them, fetches the base, and switches to the new branch. Do not run `git checkout -b` yourself.

Script: `scripts/branch.py` in this skill's folder. Use the base directory of this SKILL.md as `<skill-dir>`. Naming rules and examples are in `references/conventions.md`.

## Parameters

| Parameter | Required | Value | Example |
|-----------|----------|-------|---------|
| `--type` | yes | one of `feat`, `fix`, `hotfix` (urgent production fix), `chore`, `docs`, `refactor`, `test`, `ci`, `build`, `perf` | `feat` |
| `--summary` | yes | short description of the work, **max 80 chars**; becomes the slug (max 50 chars) | `add login form` |
| `--ticket` | no | ticket id, letters, a dash, and digits | `ABC-123` |
| `--base` | no | base branch name; default is the remote default branch, else `main` | `main` |
| `--dry-run` | no | show the name without creating the branch | |

Resulting names: `feat/abc-123-add-login-form` (with ticket) or `fix/crash-on-logout` (without).

## Steps

1. **Choose the parameters.** Pick `--type` from the table. Ask the user only if the type is genuinely unclear. Include `--ticket` only when the user gave one.

2. **Preview** (optional, when the name matters to the user):
   ```
   python3 <skill-dir>/scripts/branch.py --type feat --summary "add login form" --ticket ABC-123 --dry-run
   ```

3. **Check the working tree** with `git status --short`. If it is dirty, tell the user that changes will carry over before creating the branch.

4. **Create**:
   ```
   python3 <skill-dir>/scripts/branch.py --type feat --summary "add login form" --ticket ABC-123
   ```

5. **Report** the branch name and base in one line.

## Errors

Exit code 2 means invalid parameters. The output lists each problem in `problems`. Fix the parameter and rerun. Examples: the summary is too long, the ticket format is wrong, or the branch already exists (choose a different summary or ticket).

Exit code 1 means git failed. Report the message.

## Output

- Report one line: `Created <branch> from <base>.` or the problem.
- No preamble, no explanation of the naming rules unless asked.

## Notes

- Dry runs validate the name without fetching or changing refs.
- Stop after reporting unless the user also requested implementation. For follow-up work, commit with `../git-commit/SKILL.md`.
- `../mr-create/SKILL.md` calls this skill when the user is on a protected branch and needs a feature branch first.
