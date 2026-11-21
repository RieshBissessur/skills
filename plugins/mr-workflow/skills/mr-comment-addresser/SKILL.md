---
name: mr-comment-addresser
description: Triage PR/MR review threads, fix valid feedback, commit and push, reply, and resolve addressed threads. Use when addressing or replying to review comments.
---

# mr-comment-addresser

Works through the unresolved review threads on the MR/PR for the current branch. It fixes what is valid, asks about design decisions, replies to every thread, and resolves only the threads it actually addressed.

Scripts are in sibling skills. Use the base directory of this SKILL.md as `<skill-dir>`, and reach the other skills through `../`:

| Need | Script | Documented in |
|------|--------|---------------|
| MR context, push, MR details | `../mr-create/scripts/forge.py` | `../mr-create/SKILL.md` |
| Comments, replies, resolving | `../mr-create/scripts/forge.py` | this file, below |
| Commit | `../git-commit/scripts/commit.py` | `../git-commit/SKILL.md` |
| Run tests | `../test-write/scripts/test_runner.py` | `../test-write/SKILL.md` |

Install these skills together; the paths above depend on them.

## Steps

1. **Check the starting point**
   ```
   git status --short
   python3 <skill-dir>/../mr-create/scripts/forge.py mr-view
   ```
   - If the working tree has unrelated changes, stop and ask before switching branches or editing.
   - If `source_branch` differs from the current branch, switch to it only with a clean tree.
   - Read `references/github.md` **or** `references/gitlab.md` only when provider-specific behavior or an error requires it.

2. **Fetch unresolved comments**
   ```
   python3 <skill-dir>/../mr-create/scripts/forge.py mr-comments --unresolved-only --review-only
   ```
   Read each item's `notes` in full, not only `body`. If there are none, report that and stop. Process general comments only when the user explicitly asks; in that case omit `--review-only`. Skip your own previous replies and status-only automated notes, but triage actionable bot findings.

3. **Triage** each item with `references/triage.md`: FIX, DECIDE, ANSWER, PUSHBACK, or OUTDATED.

4. **Ask about DECIDE items before changing code.** Batch independent decisions in one interaction where possible. Give each decision realistic options, with your recommendation first and marked "(Recommended)".

5. **Only for FIX or answered DECIDE items**, apply the smallest resolving changes. Run the narrowest relevant test or package; add a broader suite only for shared or high-risk changes:
   ```
   python3 <skill-dir>/../test-write/scripts/test_runner.py run --target <test-path-or-package>
   ```
   Skip this step and steps 6–7 when no code changed.

6. **Commit code changes** with `../git-commit/SKILL.md`. Use one commit for the review batch unless the fixes are clearly separate. Choose `--type` and `--message` from the change itself, not from "review feedback". Add a body only when it explains non-obvious rationale, using the same value-based rule as `git-commit`.

7. **Push code changes**:
   ```
   python3 <skill-dir>/../mr-create/scripts/forge.py push
   ```

8. **Reply once to every selected thread.** Create a fresh temp directory with `mktemp -d` and write replies to `<run-tmp>/reply-<n>.md`. Reply wording is in `references/triage.md`; include the commit SHA only when code changed. Before posting, check `notes` for an equivalent reply already sent. After a partial failure or rerun, skip existing replies and finish only missing replies/resolutions.

9. **Resolve only addressed threads.** Resolve FIX, DECIDE (after the fix), and OUTDATED threads. Leave PUSHBACK threads open; the reviewer decides. General comments cannot be resolved.

10. **Report** a table only: thread, category, outcome. Then one line listing threads left open for the reviewer.

## Output

- Replies: one to three sentences, outcome first (see `references/triage.md`).
- Questions to the user: one line of context, options, recommendation.
- Final report: the table from step 10, no narrative.

## Commands owned by this skill

### `mr-comments`
| Parameter | Required | Value |
|-----------|----------|-------|
| `--mr` | no | number such as `42`; default is the MR for the current branch |
| `--unresolved-only` | no | flag; hide resolved threads |
| `--review-only` | no | flag; exclude general MR/PR comments |

Each item: `thread_id`, `kind` (`review_thread` or `general`), `resolvable`, `resolved`, `outdated`, `path`, `line`, `author`, `body`, `notes`.

### `mr-reply`
| Parameter | Required | Value |
|-----------|----------|-------|
| `--thread-id` | yes | `thread_id` from `mr-comments`, exactly as returned |
| `--body-file` | yes | reply text file, **max 1000 chars**, keep it to one to three sentences |
| `--mr` | no | number such as `42` |

### `mr-resolve`
| Parameter | Required | Value |
|-----------|----------|-------|
| `--thread-id` | yes | `thread_id` from `mr-comments` |
| `--unresolve` | no | flag; reopen a thread |
| `--mr` | no | number such as `42` |

## Errors

Exit code 2 means invalid parameters. Read `problems`, fix the input, and rerun. For example, a reply over 1000 characters must be shortened. Exit code 1 means the provider or git failed; report the message.

## Rules

- Resolve only threads you verified are addressed.
- Give each selected thread one reply; never duplicate an existing reply.
- Do not bypass hooks or force-push.
