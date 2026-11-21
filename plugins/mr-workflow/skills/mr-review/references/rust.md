# Rust review conventions

Read this only when `language` is `rust`. Repo conventions win over this file. Check these in the changed code, not the whole crate.

## Error handling
- `unwrap()` / `expect()` on a path that user input or I/O can reach. `expect` needs a message that says what invariant broke.
- `let _ = fallible();` drops an error silently. Justify it or handle it.
- Errors cross boundaries with context (`anyhow::Context` or the repo's error type). A bare `?` loses where it came from.
- Library code returns typed errors. Binaries may use `anyhow`. Match what the crate already does.

## Panics and numeric safety
- Indexing `v[i]` without a bounds check on external data. Prefer `get`.
- `as` casts truncate silently. Use `try_from` for values that can be out of range.
- Integer arithmetic on external values: `checked_*` or `saturating_*` where overflow matters.

## Ownership and cost
- `.clone()` in a hot loop or a per-request path. Ask whether a borrow works.
- Public APIs taking `String` where `&str` or `impl AsRef<str>` would do, or returning `Vec` where an iterator would do.
- `Arc<Mutex<_>>` added where ownership could be simpler.

## Async
- A `std::sync::Mutex` or `RefCell` guard held across `.await`. Use `tokio::sync::Mutex` or restructure.
- Blocking calls inside async code: `std::fs`, `std::thread::sleep`, heavy CPU work. Use the async equivalent or `spawn_blocking`.
- `tokio::spawn` whose `JoinHandle` is dropped, so its panic or error vanishes.

## Unsafe
- Every `unsafe` block has a `// SAFETY:` comment naming the invariant.
- Check the invariant actually holds at every call site, not only in the comment.

## Public API and compatibility
- New `pub` items are intentional. Prefer `pub(crate)` for internals.
- Public enums in libraries that may grow: `#[non_exhaustive]`.
- Breaking a public signature needs a semver-major plan.

## Dependencies and features
- New crate: needed, maintained, license acceptable, features minimal (`default-features = false` where the default pulls in too much).
- `rust-version` (MSRV) in `Cargo.toml` still satisfied by new syntax or APIs.

## Lints and formatting
- Changed code is clippy-clean under the repo's config (`clippy.toml`, `[lints]` in `Cargo.toml`). Do not introduce `#[allow(...)]` without a reason comment.
- Formatting follows `rustfmt.toml` or the default. CI usually enforces this; report only if it is not.

## Serde and data
- `#[serde(deny_unknown_fields)]` decided deliberately, not by accident.
- Default values for new fields keep old data loadable.
