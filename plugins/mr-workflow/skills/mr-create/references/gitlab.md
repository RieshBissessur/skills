# mr-create: GitLab (merge requests)

Read this only when `forge.py context` reports `provider: gitlab`.

## Names

| Concept | GitLab |
|---------|--------|
| Name | merge request (MR) |
| Reference | `!123` |
| Draft | `--draft` |
| Close an issue on merge | `Closes #123` in the description |

## Template locations

`forge.py templates` checks these and returns existing paths; `templates --path` loads one:

- `.gitlab/merge_request_templates/*.md`. Multiple templates are allowed. `Default.md` is used when none is chosen.

## Underlying commands

The wrapper runs these. You do not run them yourself.

| Wrapper | Runs |
|---------|------|
| `mr-create` | `glab api --input - -X POST projects/<url-encoded path>/merge_requests` with a JSON body |
| `mr-view` | `glab api projects/<url-encoded path>/merge_requests/N` |
| `push` | `git push -u origin <branch>` |

Notes:

- The wrapper streams JSON on stdin, so the description is not exposed through argv or OS argument-length limits.
- The API returns structured MR data, including the canonical `web_url`.
- Self-hosted GitLab hosts are set through `GITLAB_HOST`, which the wrapper sets from the remote.
- Auth check: `glab auth status`.
