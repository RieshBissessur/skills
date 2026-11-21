# Writing an MR/PR description

A description is for a reviewer who has not seen the work. It should be readable in about a minute and answer:

1. **Why** does this change exist?
2. **What** approach was taken, and why this one?
3. **What** would a reviewer not see from the diff? (nuances, risks, follow-ups)
4. **How** was it verified?
5. **Where** should the reviewer focus?

It is **not** a line-by-line list of changes. The diff already shows that.

## Default structure (use when the repo has no template)

```markdown
## Summary
One to three sentences: the problem and the outcome.

## Why
The motivation: the ticket, bug, user need, or constraint. Link it.

## Approach
The chosen solution and the main alternative that was rejected, with the reason.

## Things to know
- Non-obvious behaviour, edge cases, or assumptions
- Migrations, feature flags, config or env changes, rollout order
- Backwards compatibility or breaking changes
- Known limitations and follow-up work (link tickets)

## Testing
How it was verified: tests added, manual steps, what was not tested.

## Reviewer focus
Where careful review matters most (for example, the retry logic in `sync.ts`).

Closes #123
```

Use `Closes #123` (GitHub) or the issue reference your GitLab tracker uses. For this default structure, omit truly irrelevant optional sections. For a repo template, keep every required heading and write `N/A` instead of removing it.

## Good vs weak

| Weak (describes the diff) | Good (explains the change) |
|---------------------------|----------------------------|
| "Changed `retry.ts` and added a `maxAttempts` option." | "Sync was retrying forever on 401s, which hid expired credentials. Retries now stop after 3 attempts and surface the auth error." |
| "Updated tests." | "Added tests for the timeout path, since that is where the original bug lived." |
| "Refactored the billing module." | "Split billing into invoice and payment modules so the webhook handler no longer depends on the PDF generator. No behaviour change." |

## Surfacing nuances

Ask yourself these before finishing:

- Does anything here only work because of an ordering assumption (deploy first, migrate first)?
- Is there a behaviour change that existing users or other services will notice?
- Did a shortcut get taken that a future reader should know about?
- Is there a reason the obvious alternative was not used?

Each yes becomes a bullet under "Things to know".

## Filling a repo template

1. Run `forge.py templates` and read the content.
2. Keep the headings, order, and checkboxes exactly as the template has them.
3. Replace each placeholder or instruction comment (`<!-- ... -->`) with real content. Delete the comments.
4. Tick checkboxes only for things that are actually true. Leave unticked items the user still has to do and say so in "Things to know".
5. Add the description sections above only where the template has no equivalent. Do not duplicate content that already has a slot.
6. Do not invent test results. If a check was not run, say so.

## Formatting

- Markdown. Use short paragraphs and bullets.
- Inline code for identifiers, paths, flags, and config keys.
- Keep the whole description under about 300 words unless the change is large. If it is large, that is a sign it should be split.
- Title: imperative, 72 characters or fewer, matches the commit style, for example `feat(auth): add refresh token rotation`.
