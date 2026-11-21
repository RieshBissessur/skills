# Review areas and report format

Work through these in order. Skip an area only when it truly does not apply, and do not write "N/A" for each one.

## 1. Intent fit
- Every acceptance criterion is met (see the requirement check in `intent.md`).
- No unrelated changes (scope check).

## 2. Logic
- Inverted or off-by-one conditions, wrong operator precedence, wrong comparison (`<` vs `<=`).
- Unhandled branches: `else` missing, `switch` without default, unexpected enum values.
- State transitions: can the object reach an invalid state? Is an update lost if two happen at once?
- Defaults and fallbacks: is a zero, empty string, or null value treated as "not set" when it is a real value?
- Money, time, and units: floats for money, time zones, seconds vs milliseconds, integer overflow.

## 3. Edge cases and failure
- Empty input, a single item, very large input, duplicates, unicode.
- Partial failure: if step 2 fails after step 1 succeeds, is the state consistent? Transactions, rollback, compensation.
- Retries and timeouts: is the operation idempotent? Can a retry double-charge, double-send, or double-insert?
- Resource cleanup on every path: files, connections, locks, temporary data.

## 4. Error handling
- Errors swallowed, logged and ignored, or replaced with a vague message.
- Errors that leak internals to the user, or sensitive values into logs.
- Errors that change type or status code without a reason the caller can see.

## 5. Security
- New endpoints or actions: is authorization checked on the server, for the right object (not just "logged in")?
- Input used in SQL, shell commands, file paths, URLs, or HTML without validation or escaping.
- Secrets, tokens, or keys in code, tests, or logs.
- New dependencies: necessary, maintained, license acceptable.

## 6. Performance
- N+1 queries: a query inside a loop over query results.
- Unbounded work: loading all rows, reading whole files into memory, unpaginated API calls.
- New query patterns without a supporting index (look at the migration or schema).
- Repeated expensive work in a hot path, or work that could be cached but is not, or cached but should not be.
- Synchronous calls to slow external services in a request path.

## 7. Concurrency
- Shared mutable state accessed without a lock or atomic operation.
- Check-then-act races (for example "check if exists, then insert").
- Lock ordering that can deadlock. Work done while holding a lock that could be done outside it.
- Background work with no owner, no cancellation, or no error reporting.

## 8. Compatibility and rollout
- Breaking change to a public API, event, schema, or config default, without a version or migration plan.
- Migrations: are they reversible? Do they lock a large table? Is the backfill separate from the schema change?
- Feature flag or staged rollout for risky changes. Is the flag removed later?
- Deploy order: does the code work during a mixed-version rollout?

## 9. Tests
- The new behaviour has a test that would fail without the change.
- A bug fix has a regression test.
- Tests check behaviour, not implementation details. No real sleeps, no order dependence.
- Missing test types for the risk (for example no integration test for a new query). See `../../test-write/references/test-types.md`.

## 10. Repo conventions
- Follows `CONTRIBUTING.md`, `AGENTS.md`, or `CLAUDE.md` if present.
- Matches existing patterns for similar code. Compare with one neighbouring file.
- Naming, folder placement, error types, and logging style match the repo.
- Lint and format config respected. CI covers most of this; only report what CI would not catch.

## 11. Language conventions
- Apply the file for the detected language (`rust.md` or `go.md`), if one was read.

## 12. Readability and maintainability
- Names that hide intent. Functions doing several jobs. Duplicated logic that will drift.
- Comments that describe what the code does instead of why it does it, or that are now wrong.
- Dead code, commented-out code, debug leftovers.

## 13. Docs and observability
- Public behaviour changes reflected in docs or the changelog if the repo keeps one.
- New failure paths have logs or metrics that are useful when they fire.

## Severity

| Severity | Meaning | Action |
|----------|---------|--------|
| **blocker** | Wrong behaviour, security hole, data loss, or a break with no plan. | Must fix before merge. |
| **major** | Real risk or a missing requirement. | Should fix before merge. |
| **minor** | Clear improvement with a real benefit. | Fix now or in a follow-up. |
| **nit** | Preference or small style point. | Optional. |
| **question** | You cannot decide without the author. | Author answers. |

## Finding format

One finding per entry. Keep each part to one or two lines.

```
1. **[blocker] src/orders/refund.ts:42 — refund can run twice**
   Problem: the retry path calls `refund()` again when the response times out, and no idempotency key is sent.
   Fix: send the order's `idempotency_key` on the call, or check status before retrying.
```

Include a code snippet only when the problem is not clear without it, and keep it to three lines.

## Report format

Use this structure and nothing more.

```
## Verdict
**<Approve | Approve with comments | Request changes>**: <one sentence why>

## Intent
<goal, in one or two sentences>. Sources: <issue #N, description, commits>.

## Requirements
| Requirement | Status | Where |
|-------------|--------|-------|

## Findings
<blockers, then majors, then minors (max 5), then nits (max 3), then questions>

## Not verified
- <what you did not check, one line each, or "nothing">
```

Keep the whole report readable in one screen where the findings allow it. Do not repeat the intent card in the report.
