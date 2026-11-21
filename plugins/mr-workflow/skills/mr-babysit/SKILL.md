---
name: mr-babysit
description: Watch a PR/MR pipeline, diagnose and fix failures or warnings, push fixes, and repeat until checks pass or limits are reached. Use for CI babysitting or failing CI.
---

# mr-babysit

Keeps an MR/PR pipeline moving until it is green. It fixes failures, pushes, and waits for the next run. It stops on success, an exhausted time/poll/rerun/fix budget, or a human decision.

Scripts are in sibling skills. Use the base directory of this SKILL.md as `<skill-dir>`, and reach the other skills through `../`:

| Need | Script | Documented in |
|------|--------|---------------|
| Provider, push | `../mr-create/scripts/forge.py` | `../mr-create/SKILL.md` |
| Pipeline status, job logs, reruns | `../mr-create/scripts/forge.py` | this file, below |
| Commit | `../git-commit/scripts/commit.py` | `../git-commit/SKILL.md` |
| Run tests | `../test-write/scripts/test_runner.py` | `../test-write/SKILL.md` |

Install these skills together; the paths above depend on them.

## Preflight

```
git status --short
git rev-parse HEAD
python3 <skill-dir>/../mr-create/scripts/forge.py mr-view
```

Stop for unrelated working-tree changes. If `source_branch` differs, switch only with a clean tree. Before editing, require local `HEAD` to equal the MR's `head_sha`; otherwise stop and ask whether to push or synchronize. Never carry unrelated changes across branches.

## Loop

Use at most **5 fix/push rounds**, **60 total polls**, **60 minutes**, and **one rerun per job/run**. Polls and reruns do not consume fix rounds. Track these budgets and stop with a resume action when any is exhausted. Read `references/failure-triage.md` when the first failure or warning needs classification. Read `references/github.md` **or** `references/gitlab.md` only for provider-specific behavior or troubleshooting.

1. **Get pipeline state**
   ```
   python3 <skill-dir>/../mr-create/scripts/forge.py pipeline-status
   ```
   Read `overall`, `head_sha`, `checks`, and `annotations`.

2. **Wait or stop when there is nothing to fix**
   - First require `head_sha` to match the intended local/pushed SHA. If it differs, treat the result as stale even when `overall` is `success`; wait within the polling budget.
   - `overall: pending`, or `none` just after a push: wait 60 seconds and check again.
   - Unexpected `none`: stop and report that no pipeline exists.
   - `overall: success` with no warnings on the intended SHA: stop and report success.

3. **Inspect failures and warnings**
   - Warnings are checks with `bucket: warning` or annotations with `level: warning`. Leave clearly out-of-scope warnings unfixed and report them.
   - Use annotations first. Fetch a log only when the cause is not already clear:
     ```
     python3 <skill-dir>/../mr-create/scripts/forge.py job-log --job <job_id> --tail 200
     ```
   - If a failed external check has no `job_id` and annotations do not explain it, stop with its `link`; do not guess a fix.
   - Treat skipped/manual checks as neutral unless the repository requires them; ask before triggering a required manual check.

4. **Classify each item** with `references/failure-triage.md`:
   - **Code fix**: lint, type, test, or build error. Continue to step 5.
   - **Infra, flake, or cancellation**: rerun once, then return to step 1. Do not change code, commit, or push.
   - **Needs a human**: secret, permission, or product decision. Stop and ask.

5. **Fix locally**, using the smallest change that makes the job pass. Reproduce the job's command and run the nearest related check:
   ```
   python3 <skill-dir>/../test-write/scripts/test_runner.py run --target <test-path-or-package>
   ```

6. **Commit** with `../git-commit/SKILL.md`. Choose `--type` from its table: `fix` for code bugs, `test` for test fixes, `ci` for pipeline config, `style` for lint or formatting, `build` for dependency problems.

7. **Push**:
   ```
   python3 <skill-dir>/../mr-create/scripts/forge.py push
   ```

8. Return to step 1 and check the new `head_sha`.

## Commands owned by this skill

### `pipeline-status`
| Parameter | Required | Value |
|-----------|----------|-------|
| `--mr` | no | number such as `42`; default is the MR for the current branch |

Returns `mr`, `head_sha`, `overall` (`success`, `failed`, `pending`, `none`), `pipeline` (GitLab only, else `null`), `checks`, `annotations`.

Each check: `name`, `bucket` (`pass`, `fail`, `warning`, `pending`, `cancel`, `skipping`), `state`, `link`, `job_id`, `run_id`.

Each annotation: `check`, `level` (`warning`, `failure`, `notice`), `path`, `line`, `message`. Annotations are GitHub only.

### `job-log`
| Parameter | Required | Value |
|-----------|----------|-------|
| `--job` | yes | `job_id` from `pipeline-status` |
| `--tail` | no | lines from the end of the log, 1 to 5000, default 200 |

Prints plain text. If the real error is earlier than the tail, rerun with a larger `--tail`.

### `rerun`
| Parameter | Required | Value |
|-----------|----------|-------|
| `--run` | GitHub only | `run_id` from `pipeline-status` |
| `--job` | GitLab always; GitHub optional | `job_id` from `pipeline-status` |

GitHub with `--run` alone reruns all failed jobs in that run. GitLab needs `--job`.

## Errors

Exit code 2: invalid parameters, read `problems` and fix. Exit code 1: provider or git failure, report the message.

## Output

- Each round: one line per failing check, `<check>: <cause> → <action>`.
- Final: one line, `Green` or `Stopped: <reason>, needs <decision or action>`.
- No logs pasted into the reply; quote at most the single error line that matters.

## Stop conditions

- `overall: success` and no warnings left: report success.
- A time, poll, rerun, or fix-round budget is exhausted: summarize what was tried and how to resume.
- A human decision is needed: stop and ask.
- The same job fails with the same error after a code fix or infra rerun: stop. Do not repeat the same approach.

## Rules

- Never weaken or delete a failing test to make the pipeline pass.
- Never disable a lint rule, skip a check, or mark a job `allow_failure` unless the user asks.
- Do not force-push or bypass hooks.
