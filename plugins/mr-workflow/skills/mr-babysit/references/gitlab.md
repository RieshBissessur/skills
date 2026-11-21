# mr-babysit: GitLab (merge requests)

Read this only when `forge.py context` reports `provider: gitlab`.

## Where the data comes from

| Data | Source |
|------|--------|
| `pipeline` | The MR's `head_pipeline` (id, status, url) |
| `checks` | Jobs of the head pipeline, excluding retried jobs. `job_id` is the GitLab job id. |
| `head_sha` | The MR's `sha` |
| `annotations` | Always empty on GitLab. Warnings appear as jobs with `bucket: warning`. |

## Bucket mapping

| GitLab job status | Bucket |
|-------------------|--------|
| `failed`, not `allow_failure` | `fail` |
| `failed`, `allow_failure` | `warning` |
| `created`, `pending`, `running`, `waiting_for_resource`, `preparing`, `scheduled` | `pending` |
| `success` | `pass` |
| `canceled` | `cancel` |
| `manual`, `skipped` | `skipping` |

## Underlying commands

`<enc>` is the URL-encoded project path.

| Wrapper | Runs |
|---------|------|
| `pipeline-status` | `glab api projects/<enc>/merge_requests/<n>` (reads `head_pipeline`), then `glab api --paginate projects/<enc>/pipelines/<pid>/jobs?per_page=100` |
| `job-log --job <id>` | `glab api projects/<enc>/jobs/<id>/trace` |
| `rerun --job <id>` | `glab api -X POST projects/<enc>/jobs/<id>/retry` |

## GitLab specifics

- `job-log` returns the whole trace; the wrapper prints the last `--tail` lines.
- `overall: success` can still have `warning` checks: a failed job with `allow_failure` does not fail the pipeline, but it still needs attention.
- Retried jobs are excluded; you see the newest attempt of each job.
- No `head_pipeline` means the pipeline has not started. Wait.
