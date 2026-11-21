# mr-comment-addresser: GitHub (pull requests)

Read this only when `forge.py context` reports `provider: github`.

## Thread ids

- Review threads: GraphQL node ids starting with `PRRT_`. Pass them to `mr-reply` and `mr-resolve` exactly as returned.
- General PR comments: `issue:<id>`. They cannot be resolved; `mr-reply` posts a new PR comment.

## Underlying commands

The wrapper runs these. You do not run them yourself.

| Wrapper | Runs |
|---------|------|
| `mr-comments` (review threads) | `gh api graphql` on `repository.pullRequest.reviewThreads`, paginated 100 at a time |
| `mr-comments` (general) | `gh api repos/<owner>/<repo>/issues/<n>/comments --paginate` |
| `mr-reply` (thread) | `gh api graphql` `addPullRequestReviewThreadReply(pullRequestReviewThreadId, body)` |
| `mr-reply` (general) | `gh pr comment <n> --body <text>` |
| `mr-resolve` | `gh api graphql` `resolveReviewThread(threadId)` |
| `mr-resolve --unresolve` | `gh api graphql` `unresolveReviewThread(threadId)` |

Notes:

- A thread reply does not submit a new review. The reviewer is notified through the thread.
- `outdated: true` means the line changed after the comment. Check whether the concern still applies before replying.
