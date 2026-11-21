# mr-review: GitHub (pull requests)

Read this only when `provider` from `review_tools.py start` is `github`.

## Intent sources
- Linked issues: `closingIssuesReferences` (the `Closes #N` keywords). The `source` field is `closes`.
- `#N` mentions remain in `mentioned_issues`; fetch only central ones with `mr-issue`. `#N` may be a PR. Check `kind`; if it is `merge_request`, read that PR's description as intent for the related work.
- Issue bodies come from `gh api repos/<owner>/<repo>/issues/<N>`.

## Diff and worktree
- Diff: paginated PR-files API. Entries without a patch have `too_large: true` and are regenerated locally by `start`. If `diff.patch` still ends mid-file or `count` looks low, regenerate inside the worktree:
  ```
  git -C <worktree> diff <base_sha>...HEAD
  ```
- The worktree is fetched from `refs/pull/<N>/head`, so PRs from forks work.

## Underlying commands

| Step | Runs |
|------|------|
| Provider and repo | `git remote get-url origin` |
| MR details | `gh pr view <N> --json number,title,url,state,isDraft,headRefName,baseRefName,headRefOid,body` |
| Commits | `gh pr view <N> --json commits` |
| Linked issues | `gh pr view <N> --json closingIssuesReferences`, then `gh api repos/<o>/<r>/issues/<N>` per issue |
| Diff | `gh api repos/<owner>/<repo>/pulls/<N>/files --paginate` |
| Worktree | `git fetch origin +refs/pull/<N>/head:refs/remotes/origin/review/<N>` then `git worktree add --detach` |
