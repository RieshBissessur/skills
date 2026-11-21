# Test types

Read this file to decide which kinds of test a change needs. The language-specific file (`rust.md` or `go.md`) says how to write and run each type in that language.

## Definitions

| Type | What it tests | Dependencies | Speed | Typical share |
|------|---------------|--------------|-------|---------------|
| **Unit** | One function, method, or type in isolation | Faked or stubbed | Milliseconds | Most tests (~70%) |
| **Component / module** | One package or module through its public API | Internal parts real; external edges (network, clock, third-party) faked | Milliseconds to seconds | ~15% |
| **Integration** | Several real components together, such as code plus a real database, filesystem, or HTTP server | Real, usually local or containerised | Seconds | ~10% |
| **Contract** | That two sides of an interface (service API, message schema) agree | Recorded or generated contract | Seconds | Only when there are external consumers |
| **End-to-end (E2E)** | A full user journey through the outside surface (HTTP, CLI, browser) | Everything real | Seconds to minutes | Few (~5%), critical paths only |
| **Regression** | A specific bug stays fixed | Depends on the bug | Fast if possible | One per bug fixed |
| **Property-based** | An invariant holds for many generated inputs | Usually none | Fast | Parsers, encoders, math, sorting, serialisation |
| **Fuzz** | The code does not crash or hang on arbitrary input | None | Runs until stopped or time-boxed | Parsers and anything taking untrusted input |
| **Example / doc test** | Documentation examples compile and produce the stated output | None | Fast | Public API with examples |
| **Benchmark** | Performance of a hot path | Real | Slow | Only when performance is the task. Not pass/fail. |
| **Smoke** | The app starts and the key path responds | Real | Seconds | After deploy, or as a gate before E2E |

## Choosing types for a change

| The change | Write | Why |
|------------|-------|-----|
| Pure logic or calculation | Unit | Fast, exact, easy edge cases |
| Function that reads or writes a database, file, or HTTP call | Unit with fake, plus one integration test | Fake covers logic, integration covers the real query or call |
| New endpoint or handler | Component (through the handler with fake services) and one integration test | Checks routing, validation, and the real store |
| Bug fix | Regression test that fails before the fix | Proves the bug is fixed and stays fixed |
| Parser, serialiser, encoder, or validator | Unit, plus property-based or fuzz | Hand-picked cases miss odd inputs |
| Change to a published API or event schema | Contract test, plus example tests if public | Protects other teams |
| User-visible workflow across several services | E2E on the critical path only | Expensive, so keep to the key journey |
| Hot path flagged as slow | Benchmark, before and after | Measures, does not assert correctness |

Do not write every type for every change. Match the test type to the risk.

## Scope rules

- **Unit tests** fake the network, real clock, and shared filesystem. Isolated temporary directories are allowed when filesystem behavior is the unit under test.
- **Integration tests** use real dependencies and must clean up their own data. Keep them separate from unit tests so they can be run and skipped on their own.
- **E2E tests** run against an environment built for them. They should not depend on unit-test helpers.
- **Slow tests** are opt-in. Mark or tag them so the default run stays fast. Use the language reference for the mechanism.

## Test case checklist (any type)

- [ ] Typical input, expected output
- [ ] Boundaries: zero, one, max, empty, first, last
- [ ] Absent or null input, where the type allows it
- [ ] Invalid input and the expected error or rejection
- [ ] Failure of a dependency, if the code handles it
- [ ] Ordering, concurrency, or retries, if the code relies on them
- [ ] Regression case for any bug in the task

Aim for the behaviour a reviewer would ask about, not one test per line.

## Naming

Name the test after the behaviour and the condition.

| Good | Weak |
|------|------|
| `rejects refresh tokens after expiry` | `test_refresh` |
| `returns 404 for unknown project ids` | `works` |
| `retries at most three times on 503` | `retry test 2` |

## Structure and mocking

- Arrange, act, assert. Keep the parts visible.
- One behaviour per test. Several asserts on one result are fine.
- Mock only at the boundary: network, clock, filesystem, third-party services. Never mock the unit under test.
- Prefer the repo's existing mocking style. If none, prefer hand-written fakes behind interfaces or traits.
- Reset state between tests. Do not depend on test order.

## Flakiness

- No real sleeps. Use an injected or fake clock.
- Fixed seeds for randomness.
- No dependence on wall-clock time or on the machine's locale or timezone.
- A flaky test is a bug. Fix it or report it. Do not retry-loop it into passing.
