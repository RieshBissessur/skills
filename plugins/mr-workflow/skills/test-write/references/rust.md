# Rust test conventions

Read this file only when `test_runner.py detect` reports `language: rust`. Repo conventions win over this file.

## Where each type lives

| Type | Location | Compiled as |
|------|----------|-------------|
| Unit | `src/<module>/tests.rs`, declared with `#[cfg(test)] mod tests;` | Part of the crate, can test private items |
| Integration | `tests/<name>.rs` at the crate root | Separate crate, public API only |
| Shared helpers | `tests/common/mod.rs` (imported with `mod common;`) | Not a test on its own |
| Doc / example | `///` code blocks in public items | Run by `cargo test --doc` |
| Property-based | Same as unit or integration, using `proptest` | Depends on placement |
| Fuzz | `fuzz/fuzz_targets/<name>.rs` (cargo-fuzz) | Separate tool, not in `cargo test` |
| Benchmark | `benches/<name>.rs` using `criterion` | `cargo bench` |

Do not put a file directly in `tests/` for shared helpers: each top-level file in `tests/` becomes its own test binary. Use `tests/common/mod.rs`.

Unit tests go in their own file, not in a large inline block. Keep the production file to one line, `#[cfg(test)] mod tests;`, and put the tests in `src/<module>/tests.rs`. For a module declared in `src/parse.rs`, that file is `src/parse/tests.rs`; for an inline module, it is the sibling file next to the declaring module.

## Commands

| Goal | Command |
|------|---------|
| All tests in the crate | `cargo test` |
| Whole workspace | `cargo test --workspace` |
| Unit tests only | `cargo test --lib` |
| One integration test file | `cargo test --test <file-name-without-.rs>` |
| Doc tests only | `cargo test --doc` |
| One test by name filter | `cargo test <name_substring>` |
| Include ignored (slow) tests | `cargo test -- --ignored` |
| Show stdout from passing tests | `cargo test -- --nocapture` |
| All feature flags | `cargo test --all-features` |

## Writing unit tests

```rust
// src/parse.rs
#[cfg(test)]
mod tests;
```

```rust
// src/parse/tests.rs
use super::*;

#[test]
fn parse_port_rejects_zero() {
    let err = parse_port("0").unwrap_err();
    assert_eq!(err.kind(), ErrorKind::OutOfRange);
}
```

- Name the test `<unit>_<condition>_<result>` or as a sentence in snake_case.
- Use `assert_eq!` / `assert_ne!` with a message when the value is not obvious: `assert_eq!(got, want, "after retry")`.
- For `Result`-returning code, either `unwrap_err()` and check the kind, or return `Result<(), Box<dyn std::error::Error>>` from the test and use `?`.
- Use `#[should_panic(expected = "...")]` only when the panic message is the contract.
- Use `pretty_assertions` only if the repo already depends on it.

## Integration tests

```rust
// tests/orders.rs
mod common;

#[test]
fn creating_an_order_persists_it() -> Result<(), Box<dyn std::error::Error>> {
    let db = common::temp_db()?;
    let order = shop::create_order(&db, "sku-1", 2)?;
    assert_eq!(shop::load_order(&db, order.id)?.quantity, 2);
    Ok(())
}
```

- Only public items are visible here. If you need private access, the test belongs in unit tests.
- For temp files and directories use the `tempfile` crate (`tempfile::tempdir()`). It deletes on drop.
- Mark tests that need an external service, such as a database on localhost, with `#[ignore = "requires postgres on localhost:5432"]`. Run only the affected ignored test by name or test binary; do not run every ignored test. Or gate it behind a Cargo feature if the repo does that.

## Async tests

- Use the runtime the repo uses: `#[tokio::test]` for tokio, `#[async_std::test]` for async-std.
- Do not use `thread::sleep` in async tests. Use `tokio::time::pause()` with `start_paused = true` for time-based logic.

## Mocking and fakes

- Prefer a hand-written fake that implements the trait the production code depends on.
- `mockall` is fine if the repo already uses it. Do not add it just for one test.
- Inject the clock and randomness through a trait or a parameter so tests control them.

## Property and fuzz tests

- `proptest` for property tests: put them in the same module or in `tests/`. Keep the case count default unless the repo says otherwise.
- `cargo fuzz run <target>` for fuzzing. It needs nightly and is not part of `cargo test`. Only add a fuzz target when the task asks for it.

## Doc tests

- Every example in a `///` block is a test. Use `# ` (hash space) to hide setup lines that must compile but are not shown.
- Use `no_run` for examples that compile but should not execute, and `ignore` only as a last resort.

## Benchmarks

- Use `criterion` with `benches/`. Add `[[bench]] harness = false` to `Cargo.toml` if the repo does not already have it.
- Benchmarks do not assert correctness. Keep correctness tests separate.

## Common mistakes

- Putting `#[test]` functions in `src/` for code that is only public-API behaviour. Move them to `tests/` when that makes the test clearer.
- Leaving a large inline `#[cfg(test)] mod tests { ... }` block in a production file. Move it to `src/<module>/tests.rs`.
- Forgetting `#[cfg(test)]` on the test module, which compiles test code into release builds.
- Using `unwrap()` in helpers where the failure would be unclear. Use `expect("what was being set up")`.
- Sharing state between tests through `static`. Each test should build its own state.
