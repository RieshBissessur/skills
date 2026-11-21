# Branch naming rules

Read this only when a branch name looks wrong or you need examples. Parameters are in `../SKILL.md`.

## Rules the script enforces

- The name is `<type>/<ticket>-<slug>` or `<type>/<slug>`.
- `ticket` is lowercased and must match letters, a dash, and digits (`ABC-123` becomes `abc-123`).
- `slug` is the summary lowercased, with each run of non-alphanumeric characters replaced by one `-`, trimmed, and capped at 50 characters.
- Only lowercase letters, digits, `-`, and a single `/` appear in the name.
- The name must not already exist locally.

## Type guide

| Type | Use for |
|------|---------|
| `feat` | new user-facing behaviour |
| `fix` | bug fix |
| `hotfix` | urgent production fix, usually branched from the production branch |
| `chore` | maintenance, dependency updates, tooling |
| `docs` | documentation only |
| `refactor` | code change with no behaviour change |
| `test` | adding or fixing tests only |
| `ci` | pipeline or automation configuration |
| `build` | build system or packaging |
| `perf` | performance improvement |

## Examples

| Request | Parameters | Branch |
|---------|------------|--------|
| "start ABC-123, add login form" | `--type feat --ticket ABC-123 --summary "add login form"` | `feat/abc-123-add-login-form` |
| "fix the crash on logout" | `--type fix --summary "crash on logout"` | `fix/crash-on-logout` |
| "urgent: payment webhook 500s, ticket OPS-9" | `--type hotfix --ticket OPS-9 --summary "payment webhook 500s"` | `hotfix/ops-9-payment-webhook-500s` |
| "bump deps" | `--type chore --summary "bump deps"` | `chore/bump-deps` |

## Base branch

The base defaults to the remote default branch (`origin/HEAD`), falling back to `main`. Creation refreshes the remote-tracking base and fails rather than using a stale one. A local base is used only when no remote-tracking base exists. Dry runs do not fetch.
