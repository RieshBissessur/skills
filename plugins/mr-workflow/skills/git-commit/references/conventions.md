# Commit body and examples

Read this only when you are writing a `--body-file`, or need examples. Parameters, types, and limits are in `../SKILL.md`.

## When to write a body

Write one when the reason for the change is not visible from the diff:

- a bug's cause, if it is not obvious from the fix
- a non-obvious constraint, ordering, or workaround
- a breaking change: what callers must do

Skip it for renames, typos, formatting, and changes whose purpose is in the message.

## Body format

- Plain text or short markdown. Wrap lines at 72 columns.
- Explain **why** and the consequence. Do not list files changed.
- A breaking change needs a line starting with `BREAKING CHANGE:` describing what callers must change.

Example `<run-tmp>/commit-body.md` in a fresh `mktemp -d` directory:

```
Refresh tokens were accepted for up to 24 hours after expiry because
the middleware compared timestamps in local time. Compare in UTC.

BREAKING CHANGE: clients receive 401 for tokens that were accepted before.
```

## Examples of parameters

| Change | Parameters |
|--------|------------|
| New export option, no body needed | `--type feat --service reports --message "add csv export"` |
| Crash fix with explanation | `--type fix --service auth --message "compare token expiry in utc"` plus the body above |
| Pipeline lint fix | `--type style --message "apply prettier to src"` |
| Test-only change | `--type test --service billing --message "cover rounding edge cases"` |
| Dependency bump | `--type build --message "bump pnpm to 9.x"` |
| Breaking API change | `--type refactor --service billing --package invoices --message "rename status values" --breaking` |

## Shortening a message that is too long

| Too long (over 50 chars) | Shorter |
|--------------------------|---------|
| `add the new coupon code validation step to the payment flow` | `validate coupon codes before payment` |
| `refactor the entire invoice pdf rendering pipeline into modules` | `split invoice pdf renderer` |

Move the extra detail into `--body-file`. Do not drop the reason.
