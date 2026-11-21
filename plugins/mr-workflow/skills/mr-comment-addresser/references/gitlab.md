# mr-comment-addresser: GitLab (merge requests)

Read this only when `forge.py context` reports `provider: gitlab`.

## Thread ids

- Discussions: the discussion id (hex string). Pass it to `mr-reply` and `mr-resolve` exactly as returned.
- Standalone MR notes: `general:<id>`. They cannot be resolved; `mr-reply` posts a new MR comment.

## `resolved` on GitLab

A discussion is `resolved: true` only when every resolvable note in it is resolved. A discussion with no resolvable notes is `kind: general`.

## Underlying commands

The wrapper runs these. `<enc>` is the URL-encoded project path.

| Wrapper | Runs |
|---------|------|
| `mr-comments` | `glab api --paginate projects/<enc>/merge_requests/<n>/discussions` |
| `mr-reply` (thread) | `glab api -X POST projects/<enc>/merge_requests/<n>/discussions/<id>/notes -f body=<text>` |
| `mr-reply` (general) | `glab api -X POST projects/<enc>/merge_requests/<n>/notes -f body=<text>` |
| `mr-resolve` | `glab api -X PUT projects/<enc>/merge_requests/<n>/discussions/<id>?resolved=true` |
| `mr-resolve --unresolve` | same with `?resolved=false` |

Notes:

- `path` and `line` come from the note's `position`.
- System notes (for example "changed the target branch") are dropped.
- A reply to an already-resolved discussion keeps it resolved. Resolve again only if the fix is in.
