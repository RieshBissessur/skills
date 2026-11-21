# Triage and reply guide

Read this when classifying comments and writing replies. Commands are in `../SKILL.md`.

## Categories

| Category | Criteria | Action | Reply | Resolve |
|----------|----------|--------|-------|---------|
| **FIX** | Clear bug, typo, missing null check, naming, small test gap, unused import, style the repo already enforces. Local and low risk. | Fix | `Addressed in <sha>: ...` | Yes |
| **DECIDE** | Changes behaviour or public API, adds a dependency, trades performance for readability, picks between approaches, or conflicts with a requirement. | Ask the user first | After the answer: `Addressed in <sha>: ...` | Yes, after the fix |
| **ANSWER** | Question, praise, or a note needing no change. | None | Direct answer in one to three sentences | No, unless it asked for a change |
| **PUSHBACK** | The suggestion is wrong, misreads the code, would break a requirement, or is already covered by a test. | None | `Not changed: <reason>.` | No |
| **OUTDATED** | `outdated: true`, or the code it refers to is gone and the concern is already handled. | None | `Already handled by <sha or description>.` | Yes |

When unsure between FIX and DECIDE, choose DECIDE.

## Validity checks

1. Open the file at the commented line. Does the claim match the code?
2. Is it still true on the current head? Check `outdated`.
3. Would the change break a test, a contract, or a stated requirement?
4. Is the request beyond this MR's scope? Reply that a follow-up is needed (PUSHBACK or ANSWER). Only promise a follow-up if a ticket is created.

## Examples

| Comment | Category | Reply |
|---------|----------|-------|
| "This can be null when the session expires." | FIX | `Addressed in 3f2a9c1: added a null check and a test for the expired-session path.` |
| "Should this return 409 instead of 400?" | DECIDE | Ask the user. After the answer: `Addressed in 9b1d0e4: switched to 409 Conflict, matching the other write endpoints.` |
| "Why not use a map?" | ANSWER | `The list has at most three items and is read in order, so a map adds indirection without benefit.` |
| "Please make this async." | PUSHBACK | `Not changed: the caller is synchronous, and async would change the public signature.` |
| "Rename `x` to `retryCount`." (line gone) | OUTDATED | `Already handled: retry logic moved to retry.ts as retryCount.` |

## Reply style

- Lead with the outcome: `Addressed`, `Not changed`, or `Already handled`.
- One sentence on what changed and why. Include the short SHA when code changed.
- No apology, no thanks, no restating the comment, no filler.
- At most 1000 characters (the script enforces this); aim for under 300.

## Asking about DECIDE items

Ask one question per distinct decision, batching independent decisions in one interaction where possible. Include the comment in one line, two or three realistic options, and your recommendation first marked "(Recommended)". Do not change code for a DECIDE item until the user answers.
