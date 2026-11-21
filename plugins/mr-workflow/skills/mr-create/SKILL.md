---
name: mr-create
description: Push the branch and create a GitHub PR or GitLab MR with a template-aware description. Use when opening, creating, or raising a PR/MR.
---

# mr-create

Creates a merge request (GitLab) or pull request (GitHub). You write the description to a markdown file, fill in the repo's template, and submit it with `scripts/forge.py`. Never run `gh` or `glab` yourself.

Script: `scripts/forge.py` in this skill's folder. Use the base directory of this SKILL.md as `<skill-dir>`. Other skills use it for provider data and pushing; their commands are documented in their own SKILL.md files.

## Steps

1. **Run preflight once**
   ```
   python3 <skill-dir>/scripts/forge.py preflight
   ```
   Add `--base <branch>` when the user chose a target. The script rejects protected branches and returns `base`, `base_ref`, `commits_ahead`, `dirty`, and `existing_mrs`.
   - If an MR exists, return its URL and stop; if several exist, ask which one to inspect instead of creating another.
   - If `commits_ahead` is zero, stop: there is no committed change to publish. If `dirty` is true, explain that uncommitted work is excluded and commit intended changes first with `../git-commit/SKILL.md`.
   - Reuse the returned `base` and `base_ref`; do not independently guess another target.

2. **Select one template without loading every template**
   ```
   python3 <skill-dir>/scripts/forge.py templates
   ```
   The result contains paths only. For one template, or an obvious `Default.md`/change-specific match, load it with `templates --path <path>`. Ask the user only when multiple templates are materially ambiguous. For no template, use the default structure in `references/description-guide.md`.

3. **Understand the change** (read-only git):
   ```
   git log --oneline <base_ref>..HEAD
   git diff <base_ref>...HEAD --stat
   ```
   Find the **why**: ticket, bug, reason for the approach. If it is not in the code, commits, or ticket, ask the user one short question rather than guessing.

4. **Write the description** to a fresh `mktemp -d` directory as `<run-tmp>/description.md`. For a repo template, read only "Filling a repo template" and "Formatting" in `references/description-guide.md`, preserve every heading, write `N/A` where needed, and remove comments. Without a template, read the default structure and formatting guidance instead. Load the examples only when wording needs improvement.

5. **Write the title** as `type(service/package): message`, max 72 characters. Reuse a representative commit header when possible; otherwise use a lowercase imperative message with no trailing period.

6. **Create** with the same base from preflight:
   ```
   python3 <skill-dir>/scripts/forge.py mr-create --title "feat(billing): add pdf export" --body-file "<run-tmp>/description.md" --base <base>
   ```
   Add `--draft` if the work is incomplete or the user asks. The script pushes the branch first and returns an existing MR's URL instead of creating a duplicate.

7. **Report** the URL from the output. Read the matching provider reference (`references/github.md` or `references/gitlab.md`) only for provider-specific behavior or troubleshooting.

## Commands

### `context`
No parameters. Returns `provider`, `host`, `path`, `current_branch`, `default_branch`.

### `preflight`
`--base` is optional. Validates the source/base and returns existing MRs before any drafting work; see step 1.

### `templates`
Without options, returns `[{path}]`. `--path <discovered-path>` returns `{path, content}` for that template only.

### `push`
| Parameter | Required | Value |
|-----------|----------|-------|
| `--remote` | no | remote name, default `origin` |

Refuses protected branches.

### `mr-create`
| Parameter | Required | Value |
|-----------|----------|-------|
| `--title` | yes | single line, max 72 chars |
| `--body-file` | yes | markdown file with the description, max 60000 chars |
| `--base` | no | target branch name |
| `--head` | no | source branch (default: current); must be current when pushing |
| `--draft` | no | flag |
| `--no-push` | no | flag; requires the remote source branch to exist and match local HEAD |

### `mr-view`
| Parameter | Required | Value |
|-----------|----------|-------|
| `--mr` | no | number such as `42`; default is the MR for the current branch |

Returns `number`, `title`, `url`, `state`, `draft`, `source_branch`, `target_branch`, `head_sha`, `description`.

## Errors

Exit code 2: invalid parameters. The output lists each problem in `problems`; fix it and rerun. Exit code 1: provider or git failure; report the message.

### `mr-diff`, `mr-commits`, `mr-issues`
Read-only; used by `../mr-review/SKILL.md`.

| Command | Parameters | Returns |
|---------|------------|---------|
| `mr-diff` | `--mr` (optional) | `{mr, count, files: [{old_path, new_path, status, too_large, diff}]}` |
| `mr-commits` | `--mr` (optional) | `[{sha, title, body}]`, oldest first |
| `mr-issues` | `--mr` (optional) | `{issues: [{number, kind, title, state, labels, url, body, source}], mentioned_issues, truncated, external_refs}` |

`source` is `closes` (closing keyword in the MR) or `mentioned` (`#N` in the description, commits, or branch). Review startup fetches closing issues only and leaves incidental mentions in `mentioned_issues`; `mr-issue --issue N` fetches a central mention on demand. `external_refs` lists tracker keys such as `ABC-123`; they are not fetched.

## Output

- Success: the URL, nothing else.
- Failure: the first problem in plain words and the fix.

## Rules

- Always pass the description with `--body-file`, never as a direct command-line argument. The wrapper may safely stream its contents to the provider.
- Return an existing MR's URL from preflight (or the create fallback) instead of creating a duplicate.
