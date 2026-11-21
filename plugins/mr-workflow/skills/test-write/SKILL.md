---
name: test-write
description: Write and run tests for changed or named code, following repository and language conventions. Use when adding tests, generating test cases, or improving coverage.
---

# test-write

Writes tests that fit the repo. It detects the language, picks the test types the change needs, follows the language reference, and runs the tests with `scripts/test_runner.py`.

Script: `scripts/test_runner.py` in this skill's folder. Use the base directory of this SKILL.md as `<skill-dir>`. Reference paths such as `references/rust.md` are relative to the same directory.

## Steps

1. **Detect the language and runner**
   ```
   python3 <skill-dir>/scripts/test_runner.py detect
   ```
   Note `language` and `runner`. If detection fails, ask for the test command and use `run --command "<command>"`; do not improvise a runner.

2. **Read the test-type guide** (always): `references/test-types.md`.

3. **Read one language reference**, the one that matches `language`:
   - `rust` → `references/rust.md`
   - `go` → `references/go.md`
   - anything else → no reference file exists. Skip this step and follow the repo's existing tests.

   Do not read the other language's file.

4. **Learn the repo's conventions** from existing tests (glob, then read one or two): file names and locations, helpers, fixtures, mocking, assertion style. If the repo differs from the reference file, follow the repo.

5. **Pick the targets.** Use the files or functions the user named. Otherwise run:
   ```
   python3 <skill-dir>/scripts/test_runner.py changed
   ```
   Keep source files; skip tests, generated files, and config.

6. **Choose the test types and cases** for each target using `test-types.md`. Cover the success path, edge cases, error paths, and a regression test for any bug the task fixes.

7. **Write the tests** in the location and style from steps 3 and 4. Keep integration tests separate, the way the language reference says.

8. **Run the tests**
   ```
   python3 <skill-dir>/scripts/test_runner.py run --target <relative path>
   ```
   Start with the target, then run the affected package or suite. Run the full suite only for broad/shared changes or when the user asks. Read `tail` on failure. For integration tests excluded from the normal run, target only the affected package or test binary using the language reference; never run every ignored or tagged test indiscriminately.

9. **Fix test-side failures for at most three targeted cycles.** Stop on a repeated identical failure, a pre-existing or environmental failure, or when production code is wrong; report the bug and ask before production edits. Never weaken an assertion to pass.

10. **Report**: files added, test count per type, pass/fail, and anything not tested with the reason. Do not commit unless the user asks. If they do, commit with `../git-commit/SKILL.md` using `--type test`.

## Output

- Short list: `<file>: <n> tests (<types>)`, then `Result: N passed, M failed` and any untested area with its reason.
- For a failure: the failing test name and the one assertion line that failed. No full logs.

## Commands

### `detect`
No parameters. Returns `language`, `runner`, `command`, `root`.

### `run`
| Parameter | Required | Value |
|-----------|----------|-------|
| `--target` | no | relative test path/package; Go files map to their package, Rust accepts `tests/<name>.rs`; Maven/Gradle require no target |
| `--timeout` | no | seconds, 1 to 3600, default 900 |
| `--command` | no | explicit test command, parsed without a shell; use when detection fails |

Returns `language`, `runner`, `command`, `exit_code`, `passed`, `tail` (last 80 lines).

### `changed`
| Parameter | Required | Value |
|-----------|----------|-------|
| `--base` | no | base branch name such as `main`; default is the remote default branch |

Returns `base` and `files`.

## Errors

Exit code 2: invalid parameters. Read `problems`, fix, rerun. Exit code 1: the runner or git failed; report the message.

## Rules

- Do not change production code unless the user explicitly asks; otherwise report the exposed bug and stop.
- Do not delete or skip existing tests.
- Keep test data small and inline unless the repo uses fixture files.
