---
name: mr-review
description: Review a PR/MR against its intent, correctness, performance, security, tests, and conventions. Use for branch or pre-merge reviews. Reports findings only; does not post comments.
---

# mr-review

Reviews an MR/PR in an isolated worktree, so the current branch is never changed. Intent comes first, then the code is checked against it. The output is a report in chat; nothing is posted to the MR.

Scripts and references are in folders next to this file. Use the base directory of this SKILL.md as `<skill-dir>`. This skill calls sibling skills through `../`: `../mr-create/scripts/forge.py` (provider data) and `../test-write/scripts/test_runner.py` (language detection, optional test run). Install all skills together.

## Output style

- Concise, direct, no filler. Every finding states the problem, its location, and the fix.
- No praise padding, no restating the diff, no repeating the MR description.
- Only report what you verified by reading code. Unverified suspicions go under "Not verified", one line each.

## Steps

1. **Gather context**
   ```
   python3 <skill-dir>/scripts/review_tools.py start --mr <N>
   ```
   Omit `--mr` to use the current branch's MR. Keep the returned `mr`, `provider`, `base_sha`, `head_sha`, `work_dir`, `context_file`, `diff_file`, `worktree`, `language`, `convention_files`, `issues`, `mentioned_issues`, and `external_refs` for the next steps. If a diff is incomplete, read only the matching provider reference (`references/github.md` or `references/gitlab.md`) for recovery.

2. **Read intent once**: `context_file` contains the MR title, description, commits, and closing-issue bodies. Follow `references/intent.md`; do not reread each issue separately. Incidental `#N` mentions stay unfetched in `mentioned_issues`. Only when one is central to intent, fetch it with `python3 <skill-dir>/../mr-create/scripts/forge.py mr-issue --issue <N>`.

3. **Write the intent card** (five lines maximum): goal, acceptance criteria, non-goals, approach, and named risks. Ask the user only when missing external criteria or acceptance criteria make the goal impossible to judge; otherwise record them as not fetched.

4. **Read only applicable conventions** from `convention_files`. Prioritize instructions governing changed paths, then relevant lint/format or CI config. Do not read every listed file.

5. **Read one language reference** when `language` is `rust` (`references/rust.md`) or `go` (`references/go.md`); otherwise skip and use repo conventions.

6. **Inspect by risk, not by volume.**
   - Read `diff_file` per changed source file. Skip generated, binary, vendored, and lockfile bodies; inspect their metadata or source inputs instead.
   - Read full small files in `worktree`. For large files, read hunk context plus relevant definitions and control flow rather than the whole file.
   - Search callers only for changed public contracts whose signature or semantics changed. Deduplicate symbols and batch them:
     ```
     python3 <skill-dir>/scripts/review_tools.py callers --mr <N> --symbol <name-a> --symbol <name-b>
     ```
     For endpoints, inspect route consumers and contract tests instead of forcing routes into identifier searches.

7. **Review** with `references/review-areas.md` in its stated order, including docs and observability. Record verified findings with `file:line`.

8. **Run tests only when requested or needed to confirm a suspected bug.** Use the narrowest relevant target and set the shell working directory to `worktree`:
   ```
   python3 <skill-dir>/../test-write/scripts/test_runner.py run --target <path>
   ```
   Do not modify source files; test-generated artifacts are allowed only inside the disposable worktree.

9. **Write the report** in the format at the end of `references/review-areas.md`. Lead with the verdict.

10. **Always clean up**, including after a failed review or test:
    ```
    python3 <skill-dir>/scripts/review_tools.py cleanup --mr <N>
    ```

## Command reference

### `review_tools.py start`
| Parameter | Required | Value |
|-----------|----------|-------|
| `--mr` | no | number such as `42`; default is the current branch's MR |

Creates a repo-specific `<tmp>/mr-review-.../` with `context.json`, `diff.patch`, and `worktree/` (detached at the MR head). Safe to rerun for the same repo and MR; it replaces that review's previous worktree.

### `review_tools.py callers`
| Parameter | Required | Value |
|-----------|----------|-------|
| `--mr` | yes | number such as `42` |
| `--symbol` | yes, repeatable | identifiers such as `parse_config`; deduplicate and batch related contracts |

Returns up to 60 matches per symbol as `path:line:text`. Needs `start` to have run first.

### `review_tools.py cleanup`
| Parameter | Required | Value |
|-----------|----------|-------|
| `--mr` | yes | number such as `42` |

Removes the worktree and temp files. Does not touch the branch.

## Errors

Exit code 2: invalid parameters. Read `problems`, fix, rerun. Exit code 1: provider or git failure. Report the message in one line and stop. Run `cleanup` if a worktree was created.

## Rules

- Never edit source files in the worktree or the user's branch. Tests may create disposable artifacts in the worktree.
- Never post comments or approve the MR.
- Do not report style issues the CI linters already enforce. Say once that lint is covered by CI, if it is.
- Do not flood with nits. Report blockers and majors fully; cap minors at 5 and nits at 3.

## Related

- To respond to existing review threads on this MR, use `../mr-comment-addresser/SKILL.md`.
- To make the pipeline green after review fixes, use `../mr-babysit/SKILL.md`.
