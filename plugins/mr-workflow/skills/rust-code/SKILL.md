---
name: rust-code
description: Write safe, idiomatic Rust with exhaustive matching, explicit errors, clear naming, and tests in separate files. Use when writing, changing, or reviewing Rust code.
---

# rust-code

Writes Rust that is safe by default and explicit about failure. Apply this when adding, changing, or refactoring Rust code. The repo wins; when the repo is silent, these opinions decide.

Read `references/conventions.md` before anything beyond a trivial edit. It holds the full rules, examples, and canonical sources.

## Non-negotiables

- **Safe Rust by default.** Put `#![forbid(unsafe_code)]` in the crate root. If the crate genuinely needs `unsafe`, keep the block minimal, prove the invariant in a `// SAFETY:` comment immediately above it, and test the boundary.
- **No panics for recoverable failure.** No `unwrap` or `expect` on user input, I/O, parsing, environment, or network. `expect` is allowed only for a proven local invariant, with a message that names it.
- **Match exhaustively and handle every error.** Prefer `match` over a catch-all `_` when every variant matters. Propagate with `?`, add context, and never discard a `Result` or `Option` with `let _ =` unless a comment says why that is correct.
- **Name by RFC 430 and the API guidelines.** `UpperCamelCase` types and variants, `snake_case` functions and modules, `SCREAMING_SNAKE_CASE` constants. Use `as_` / `to_` / `into_` for conversions, `is_` / `has_` for predicates, no `get_` prefix, and `iter` / `iter_mut` / `into_iter` for iteration.
- **Document the contract.** `///` on every public item, with `# Errors`, `# Panics`, and `# Safety` where they apply. `//` comments explain why or an invariant; they never restate the code.
- **Tests live in separate files.** Unit tests go in `src/<module>/tests.rs` behind `#[cfg(test)] mod tests;`. Integration tests go in `tests/<feature>.rs`. Keep production files free of large inline test modules.

## Order of work

1. **Read the crate first.** Match its error type, module layout, lints, feature flags, and test placement. Consistency beats this skill.
2. **Design with the type system.** Make illegal states unrepresentable; prefer an enum over a set of booleans; use newtypes for identifiers and units.
3. **Decide the error boundary.** Typed errors in libraries, `anyhow` in binaries, and context at every boundary the caller cannot see through.
4. **Write the implementation with borrowed parameters** and return owned values. Avoid `.clone()` by reflex.
5. **Write tests in their own files** covering the success path, boundaries, and each error variant.
6. **Verify** with the commands below and fix every finding.

## Verify

```
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test
```

For test layout, runners, async tests, and doc tests, use `../test-write/references/rust.md`. To run or target tests, use `../test-write/SKILL.md`.

## Review checklist

- [ ] `cargo fmt --check` and clippy clean; no unexplained `#[allow(...)]`.
- [ ] No `unwrap` / `expect` on fallible external input; every `Result` handled.
- [ ] `match` is exhaustive; no catch-all that would hide a new variant.
- [ ] Every `unsafe` block has a `// SAFETY:` proof and is as small as possible.
- [ ] No `as` truncation on external values; no unchecked indexing; overflow handled.
- [ ] Naming follows RFC 430 and the conversion prefixes; no `get_` prefix.
- [ ] Public items documented, including errors, panics, and safety.
- [ ] Unit tests in `src/<module>/tests.rs`; integration tests in `tests/<feature>.rs`.

## Output

When writing code, report the files changed, the public surface added or changed, and the verification commands with their result. Do not commit unless the user asks; then use `../git-commit/SKILL.md` with `--type feat`, `fix`, or `refactor` as appropriate.
