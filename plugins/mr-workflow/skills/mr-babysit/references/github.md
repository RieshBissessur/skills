# mr-babysit: GitHub (pull requests)

Read this only when `forge.py context` reports `provider: github`.

## Where the data comes from

| Data | Source |
|------|--------|
| `checks` | `gh pr checks <n> --json name,state,bucket,link,workflow`. `job_id` and `run_id` are parsed from the link (`/runs/<run_id>/job/<job_id>`). |
| `head_sha` | `gh pr view <n> --json headRefOid` |
| `annotations` | Check runs for `head_sha`, then their annotations. Linters and test reporters put warnings and errors here with `path` and `line`. |
| `pipeline` | Always `null` on GitHub. |

## Underlying commands

| Wrapper | Runs |
|---------|------|
| `pipeline-status` | `gh pr checks`, `gh pr view --json headRefOid`, `gh api repos/<o>/<r>/commits/<sha>/check-runs`, `gh api repos/<o>/<r>/check-runs/<id>/annotations` |
| `job-log --job <id>` | `gh run view --job <id> --log-failed` |
| `rerun --run <run_id> --job <id>` | `gh run rerun <run_id> --job <id>` |
| `rerun --run <run_id>` | `gh run rerun <run_id> --failed` |

## GitHub specifics

- A check's `bucket` is `pass`, `fail`, `pending`, `skipping`, or `cancel`. Warnings never appear in `bucket`; they come from `annotations`.
- An annotation with `level: warning` counts as a warning even when its check passed.
- `job-log` needs `job_id`. Checks from external apps have no GitHub Actions job, so no log. Report the `link` instead.
- Reruns need `--run` on GitHub.
- A `pending` check is not a failure. Wait. Pending polls skip annotation requests; terminal results include them.
