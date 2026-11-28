# Rust conventions

Read this before writing or changing Rust code. The repo wins; this file decides when the repo is silent.

## Formatting and lints

- `cargo fmt` is the only formatting authority. Do not hand-format.
- `cargo clippy --all-targets --all-features -- -D warnings` must pass under the repo's config.
- Never add `#[allow(...)]` without a comment naming the reason and, where possible, the narrowest scope.
- Respect the crate's MSRV (`rust-version`) when choosing syntax or APIs.

## Safety

Safe Rust is the default and the point.

- Put `#![forbid(unsafe_code)]` at the crate root. Remove it only when the crate genuinely needs `unsafe`; then use `#![deny(unsafe_op_in_unsafe_fn)]`.
- Keep every `unsafe` block as small as possible. Put the proof in a `// SAFETY:` comment immediately above the block.
- The comment must state the invariant and why it holds at this call site. "This is safe" is not a proof.
- Test the safe wrapper around `unsafe`, including boundary and invalid-input cases.
- Prefer safe alternatives: `get` over indexing, `try_from` over `as`, `checked_*` over raw arithmetic, `split_at_checked` over manual slicing.

```rust
// SAFETY: `index` was checked against `slice.len()` above, and the slice
// is not mutated for the duration of this borrow.
let item = unsafe { slice.get_unchecked(index) };
```

## Naming

Follow RFC 430 and the Rust API Guidelines.

| Item | Convention | Example |
|------|------------|---------|
| Modules | `snake_case` | `http_client` |
| Types, traits, enum variants | `UpperCamelCase` | `HttpClient`, `ParseError::Empty` |
| Functions, methods, locals | `snake_case` | `parse_header`, `retry_count` |
| Constants, statics | `SCREAMING_SNAKE_CASE` | `MAX_RETRIES` |
| Type parameters | short `UpperCamelCase` | `T`, `E`, `K`, `V` |
| Lifetimes | short lowercase | `'a`, `'de` |

### Conversions

| Prefix | Meaning | Example |
|--------|---------|---------|
| `as_` | cheap, borrowed to borrowed | `str::as_bytes` |
| `to_` | expensive, borrowed to owned | `str::to_owned`, `Path::to_path_buf` |
| `into_` | consuming conversion | `String::into_bytes` |

- Use `From` / `TryFrom` for the trait implementations; the prefixes are for inherent methods.
- `as` is for primitive numeric casts only, and only when truncation cannot happen or is intended and documented. It is never a general conversion.

### Methods

- Simple getters have no prefix and no `get_`: `fn name(&self) -> &str`.
- Setters are `set_name`.
- Predicates are `is_` or `has_` and return `bool`.
- A fallible variant of an infallible method uses `try_`: `try_reserve`.
- Iteration is `iter`, `iter_mut`, `into_iter`; do not invent `get_all`.
- Constructors are `new`. Use `with_capacity`, `from_*`, or `Default` for variants.
- Avoid abbreviations; spell the word. `url`, `id`, `http` are fine because they are canonical.

### Modules and crates

- Name a module for what it contains, not its layer. `parser`, not `utils`.
- No `utils`, `helpers`, `common`, or `misc` dumping grounds.
- Keep the public surface deliberate: `pub(crate)` by default, `pub` is a commitment.

## Comments and documentation

- `///` on every public item. The first line is a one-sentence summary, then a blank line, then detail.
- Document the contract, not the implementation: what it does, what it returns, and what it assumes.
- Use the standard sections where they apply:
  - `# Examples` — compiles and runs as a doc test.
  - `# Errors` — every error variant and when it is returned.
  - `# Panics` — every panic condition.
  - `# Safety` — the caller's obligations for an `unsafe fn`.
- Doc examples use `?` and hidden setup lines (`# let x = ...;`) so they stay short and still compile.
- `//` comments explain why, an invariant, or a tradeoff. Never restate the code.
- `// SAFETY:` is mandatory before every `unsafe` block and inside every `unsafe fn` body.
- `// TODO(name): reason` for known gaps. Link an issue when it matters.
- Delete commented-out code.

```rust
/// Parses a decimal TCP port in the range 1-65535.
///
/// # Errors
///
/// Returns [`PortError::OutOfRange`] for `0` and values above `65535`,
/// and [`PortError::NotANumber`] for anything else.
pub fn parse_port(input: &str) -> Result<u16, PortError>
```

## Errors and matching

- Recoverable failure returns `Result<T, E>`. Do not panic, abort, or exit.
- Propagate with `?`. Add context where the caller cannot see the source:
  `.context("reading config")` with `anyhow`, or `map_err` into the crate's error type.
- Libraries define a typed error, usually an enum, with `thiserror` or a hand-written `impl std::error::Error`. Binaries may use `anyhow`.
- Do not return `Box<dyn Error>` from a library API. Do not model errors as strings.
- Implement `Display` for user-facing text and `Error` for the error trait. Keep `source()` intact so the chain survives.
- `match` exhaustively on enums you own. A `_ =>` arm hides a new variant from the compiler; add it only for a genuinely irrelevant case or a foreign `#[non_exhaustive]` enum.
- Use `match` when every variant matters, `if let` when exactly one does, and `let ... else` for an early exit.
- Handle every `Result` and `Option`. `let _ =` is allowed only with a comment explaining why the value is safe to drop.
- `unwrap` / `expect`: only for a proven, local invariant. `expect` must name the invariant. Never on user input, file I/O, parsing, environment variables, or network data.
- `panic!` and `unreachable!` are for states the type system cannot express and that truly cannot happen. Prefer `debug_assert!` for internal invariants.

## Numeric and data safety

- Do not index with external data. Use `get` / `get_mut` and handle `None`.
- `as` truncates and wraps silently. Use `try_from` / `try_into` for values that may be out of range; use `From` for lossless conversions.
- Use `checked_*`, `saturating_*`, or `overflowing_*` where overflow is possible. Release builds wrap; debug builds panic.
- Validate lengths before slicing. Prefer `split_at_checked` or `get(range)`.
- Do not hold a `std::sync::MutexGuard`, `RwLockGuard`, or `RefCell` borrow across `.await`.
- Do not block an async runtime: use async I/O, or `spawn_blocking` for CPU-heavy or blocking work.
- Keep `tokio::spawn` handles when the task's failure matters.

## Ownership and API design

- Parameters borrow: `&str`, `&[T]`, `&T`. Return owned values when the caller needs to keep them.
- At API boundaries, accept `impl AsRef<Path>`, `impl AsRef<str>`, or `impl Into<String>` when it genuinely helps callers. Do not use it everywhere.
- Avoid `.clone()` by reflex. Clone to end a borrow or cross a boundary, not to silence the borrow checker.
- Make illegal states unrepresentable. Prefer an enum over several booleans, and a newtype over a bare `String` or `u64` identifier.
- Derive `Debug` on public types. Derive `Clone`, `PartialEq`, `Eq`, `Hash`, `Default` when the semantics are real, not by habit.
- Mark public enums and structs that may grow `#[non_exhaustive]`.
- Prefer iterators and combinators over manual index loops, but keep chains short enough to read.
- Keep `unsafe` out of public APIs unless the caller can actually uphold the contract.

## Tests: separate files

Unit tests live next to the module but in their own file. The production file stays free of large test modules.

```text
src/
├── lib.rs
├── parse.rs
└── parse/
    └── tests.rs
```

```rust
// src/parse.rs
pub fn parse_port(input: &str) -> Result<u16, PortError> { ... }

#[cfg(test)]
mod tests;
```

```rust
// src/parse/tests.rs
use super::*;

#[test]
fn parse_port_rejects_zero() {
    let err = parse_port("0").unwrap_err();
    assert_eq!(err, PortError::OutOfRange);
}

#[test]
fn parse_port_accepts_the_upper_bound() {
    assert_eq!(parse_port("65535"), Ok(65535));
}
```

- `mod tests;` resolves to `src/<module>/tests.rs` for a module declared in `src/<module>.rs`. For an inline module, it resolves to a sibling file.
- Integration tests go in `tests/<feature>.rs` and use only the public API. Shared helpers go in `tests/common/mod.rs`.
- Name tests `subject_condition_expected`, for example `parse_port_rejects_zero`.
- Use `assert_eq!` / `assert_ne!` with a message when the values are not self-explanatory.
- Return `Result` from fallible tests and use `?`; do not `unwrap` setup.
- `#[should_panic(expected = "...")]` only when the panic message is the contract.
- Use `tempfile` for temporary directories. Never share mutable state through a `static`.

Full test layout, runners, async tests, doc tests, and property tests: `../test-write/references/rust.md`.

## Verify

```
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test
```

Fix every finding. Do not add an `allow` to silence a real issue.

## Sources

- Rust API Guidelines, naming: https://rust-lang.github.io/api-guidelines/naming.html
- Rust API Guidelines, checklist: https://rust-lang.github.io/api-guidelines/checklist.html
- The Rust Style Guide: https://doc.rust-lang.org/nightly/style-guide/
- The Rust Programming Language, test organization: https://doc.rust-lang.org/book/ch11-03-test-organization.html
- Effective Rust, testing: https://www.lurklurk.org/effective-rust/testing.html
- The Rust Reference, unsafe blocks: https://doc.rust-lang.org/reference/unsafe-blocks.html
- Clippy lint list: https://rust-lang.github.io/rust-clippy/master/
- `thiserror`: https://docs.rs/thiserror
- `anyhow`: https://docs.rs/anyhow
