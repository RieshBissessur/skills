# mr-review: GitLab (merge requests)

Read this only when `provider` from `review_tools.py start` is `gitlab`.

## Intent sources
- Linked issues: the MR's `closes_issues` endpoint (the `Closes #N` keywords). `source` is `closes`.
- `#N` mentions remain in `mentioned_issues`; fetch only central ones with `mr-issue`. On GitLab `#N` is always an issue.
- `!N` mentions refer to other MRs. They are not fetched. Read one yourself only if it is central to the goal.
- Issue descriptions come from `projects/<enc>/issues/<N>`.

## Diff and worktree
- Diff: `projects/<enc>/merge_requests/<N>/diffs`. A file flagged `too_large: true` has no diff text. For those files, regenerate from the worktree:
  ```
  git -C <worktree> diff <base_sha>...HEAD -- <path>
  ```
- The worktree is fetched from `refs/merge-requests/<N>/head`.

## Underlying commands

`<enc>` is the URL-encoded project path.

| Step | Runs |
|------|------|
| MR details | `glab api projects/<enc>/merge_requests/<N>` |
| Commits | `glab api --paginate projects/<enc>/merge_requests/<N>/commits` |
| Linked issues | `glab api --paginate projects/<enc>/merge_requests/<N>/closes_issues`, then `glab api projects/<enc>/issues/<N>` per issue |
| Diff | `glab api --paginate projects/<enc>/merge_requests/<N>/diffs` |
| Worktree | `git fetch origin +refs/merge-requests/<N>/head:refs/remotes/origin/review/<N>` then `git worktree add --detach` |
