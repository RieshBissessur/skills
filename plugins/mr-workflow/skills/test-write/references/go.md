# Go test conventions

Read this file only when `test_runner.py detect` reports `language: go`. Repo conventions win over this file.

## Where each type lives

| Type | Location | Notes |
|------|----------|-------|
| Unit (white-box) | `foo_test.go` with `package foo` | Can reach unexported identifiers |
| Unit (black-box) | `foo_test.go` with `package foo_test` | Public API only; preferred for components |
| Integration | `foo_integration_test.go` with `//go:build integration` as the first line | Excluded from default runs |
| Shared helpers | `internal/testutil/` or a `_test.go` file in the same package | Helpers must not be exported from production packages |
| Golden / fixture data | `testdata/` next to the package | Go ignores this directory when building |
| Example / doc test | `func ExampleFoo()` in `example_test.go` with `// Output:` | Run by `go test` and shown in docs |
| Fuzz | `func FuzzFoo(f *testing.F)` in `_test.go` | Corpus in `testdata/fuzz/FuzzFoo/` |
| Benchmark | `func BenchmarkFoo(b *testing.B)` in `_test.go` | Run with `-bench` |

## Commands

| Goal | Command |
|------|---------|
| All unit tests | `go test ./...` |
| Skip slow tests | `go test -short ./...` (guard with `if testing.Short() { t.Skip(...) }`) |
| Integration tests | `go test -tags=integration ./pkg/store` (target the affected package) |
| One test by name | `go test -run 'TestParseConfig/empty' ./pkg/config` |
| Race detector | `go test -race ./...` |
| Disable test cache | `go test -count=1 ./...` |
| Verbose output | `go test -v ./...` |
| Coverage | `go test -coverprofile=cover.out ./... && go tool cover -func=cover.out` |
| Fuzz for 30 seconds | `go test -run=^$ -fuzz=FuzzParse -fuzztime=30s ./pkg/parse` |
| Benchmarks | `go test -run=^$ -bench=. -benchmem ./...` |

## Writing unit tests: table-driven

Prefer table-driven tests with subtests:

```go
func TestParsePort(t *testing.T) {
    t.Parallel()
    tests := []struct {
        name    string
        input   string
        want    int
        wantErr bool
    }{
        {name: "valid", input: "8080", want: 8080},
        {name: "zero is out of range", input: "0", wantErr: true},
        {name: "not a number", input: "abc", wantErr: true},
    }
    for _, tt := range tests {
        tt := tt // required before Go 1.22
        t.Run(tt.name, func(t *testing.T) {
            t.Parallel()
            got, err := ParsePort(tt.input)
            if (err != nil) != tt.wantErr {
                t.Fatalf("ParsePort(%q) error = %v, wantErr %v", tt.input, err, tt.wantErr)
            }
            if got != tt.want {
                t.Errorf("ParsePort(%q) = %d, want %d", tt.input, got, tt.want)
            }
        })
    }
}
```

- Name cases by the condition, so `-run` can select them.
- `t.Parallel()` only when the test has no shared state. Note that the loop variable must be copied (`tt := tt`) on Go versions before 1.22.
- Use `t.Fatalf` when continuing would panic or give a misleading result. Use `t.Errorf` otherwise.
- Use `t.Helper()` in helper functions so failures point to the caller.
- Use `cmp.Diff` (from `github.com/google/go-cmp`) for structs if the repo already uses it. Otherwise compare fields explicitly.
- Testify (`assert`, `require`) only if the repo already imports it. Match the repo's choice.

## Test setup and cleanup

- `t.TempDir()` for temporary directories. It is removed automatically.
- `t.Cleanup(func() { ... })` to release resources, in reverse order of setup.
- `t.Setenv("KEY", "value")` for environment variables. It cannot be combined with `t.Parallel()`.

## Integration tests

```go
//go:build integration

package store_test

func TestStoreSaveAndLoad(t *testing.T) {
    db := openTestDB(t) // helper that skips with t.Skip when TEST_DB_URL is unset
    ...
}
```

- Gate on an environment variable and call `t.Skip` with a clear reason if it is missing.
- Use `httptest.NewServer` for HTTP integration. Do not hit real external hosts.
- Clean up data the test created.

## Fakes and mocks

- Define a small interface in the consumer package and write a fake in the test file. Keep interfaces small.
- Do not mock types you do not own; wrap them behind your own interface.
- `httptest.NewRecorder` and `httptest.NewServer` cover most HTTP needs without a mocking library.
- `gomock` or `mockery` only if the repo already uses them.

## Golden files

- Keep expected output in `testdata/<name>.golden`.
- Update them with a flag, for example `var update = flag.Bool("update", false, "rewrite golden files")`, and only when the change is intended. Review the diff.

## Fuzz tests

```go
func FuzzParsePort(f *testing.F) {
    f.Add("8080")
    f.Add("")
    f.Fuzz(func(t *testing.T, s string) {
        _, _ = ParsePort(s) // must not panic
    })
}
```

- Seed the corpus with `f.Add` for interesting inputs.
- Fuzzing must not panic and must return consistent results. Assert invariants when there are any.
- Only add a fuzz target when the task asks for it or the code parses untrusted input.

## Example tests

```go
func ExampleParsePort() {
    port, _ := ParsePort("8080")
    fmt.Println(port)
    // Output: 8080
}
```

- Example tests are compiled and checked on every `go test` run. Keep the `// Output:` line exact.

## Benchmarks

```go
func BenchmarkParsePort(b *testing.B) {
    for i := 0; i < b.N; i++ {
        _, _ = ParsePort("8080")
    }
}
```

- Use `b.ResetTimer()` after expensive setup, and `b.ReportAllocs()` when allocations matter.
- Benchmarks do not assert correctness. Keep them separate from unit tests.

## Common mistakes

- Using `time.Sleep` to wait for goroutines. Use channels, `sync.WaitGroup`, or a fake clock.
- Forgetting the `//go:build` line must be followed by a blank line before `package`.
- Putting test helpers in production files, which ships them in the binary's package.
- Comparing errors with `err.Error() == "..."`. Use `errors.Is` or `errors.As` in the test.
