# mr-create: GitHub (pull requests)

Read this only when `forge.py context` reports `provider: github`.

## Names

| Concept | GitHub |
|---------|--------|
| Name | pull request (PR) |
| Reference | `#123` |
| Draft | `--draft` |
| Close an issue on merge | `Closes #123` in the body |

## Template locations

`forge.py templates` checks these and returns existing paths; `templates --path` loads one:

- `PULL_REQUEST_TEMPLATE.md` (repo root)
- `.github/PULL_REQUEST_TEMPLATE.md` or `.github/pull_request_template.md`
- `docs/PULL_REQUEST_TEMPLATE.md` or `docs/pull_request_template.md`
- every `*.md` in `.github/PULL_REQUEST_TEMPLATE/` (multiple templates; choose by change type)

## Underlying commands

The wrapper runs these. You do not run them yourself.

| Wrapper | Runs |
|---------|------|
| `mr-create` | `gh pr create --title T --body-file F --base B --head H [--draft]` |
| `mr-view` | `gh pr view N --json number,title,url,state,isDraft,headRefName,baseRefName,headRefOid,body` |
| `push` | `git push -u origin <branch>` |

Notes:

- `--body-file` passes the markdown file as-is, so formatting is preserved.
- The wrapper never uses `--fill`. The description always comes from the file.
- Auth check: `gh auth status`. GitHub Enterprise hosts are set through `GH_HOST`, which the wrapper sets from the remote.
