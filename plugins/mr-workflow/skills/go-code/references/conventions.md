# Go conventions

Read this before writing or changing Go code. The repo wins; this file decides when the repo is silent.

## Formatting and tooling

- Run `gofmt` (or `goimports`) on every change. Formatting is not a review topic.
- `goimports` groups imports as standard library, third-party, then local, matching the repo. Remove unused imports.
- `go vet ./...` must be clean. Respect `.golangci.yml` when present.
- Run `go mod tidy` after dependency changes and commit the `go.mod` / `go.sum` result.
- There is no line-length limit. Break lines where the meaning breaks, not at a column.
- Do not write `else` after a branch that returns. Return early and keep the happy path unindented.

## Naming

Go names are read far more often than written. Optimise for the reader at the call site.

### Casing and initialisms

Use `MixedCaps`, never `snake_case` or `ALL_CAPS` for exported identifiers. Initialisms are all caps or all lower, never mixed:

| Correct | Wrong |
|---------|-------|
| `userID`, `UserID` | `userId`, `UserId` |
| `parseURL`, `URLParser` | `parseUrl`, `UrlParser` |
| `httpClient`, `HTTPClient` | `httpclient`, `HttpClient` |
| `apiKey`, `APIKey` | `api_key`, `ApiKey` |
| `sqlDB`, `SQLDB` | `sqlDb`, `SqlDB` |

Canonical initialisms include `ACL`, `API`, `ASCII`, `CPU`, `CSS`, `DNS`, `EOF`, `GUID`, `HTML`, `HTTP`, `HTTPS`, `ID`, `IP`, `JSON`, `QPS`, `RAM`, `RPC`, `SLA`, `SMTP`, `SQL`, `SSH`, `TCP`, `TLS`, `TTL`, `UDP`, `UI`, `UID`, `UUID`, `URI`, `URL`, `UTF8`, `VM`, `XML`, `XMPP`, `XSRF`, `XSS`.

### Length follows scope

- Small scope (`i`, `n`, `r`, `w`, `ctx`, `err`, `ok`): short is better.
- Package scope or exported API: spell it out. `ParseConfiguration`, not `ParseCfg`.
- Avoid abbreviations unless they are canonical (`cfg`, `req`, `resp`, `buf` are common and fine).
- A name should not repeat its package: `http.Client`, not `http.HTTPClient`.

### Packages

- Short, lowercase, one word, no underscores or mixed caps: `config`, `auth`, `store`.
- The package name is part of every call. Avoid stutter: `chubby.File`, not `chubby.ChubbyFile`.
- Never name a package `util`, `common`, `helpers`, `models`, `base`, or `types`. Those names describe nothing and become a dumping ground.
- Name the package for what it provides, not where it sits.

### Functions and methods

- No `Get` prefix. `user.Name()`, `store.Find(id)`, not `GetName` or `GetUser`.
- Constructors are `NewThing`, or `New` when the package already names the thing (`http.NewRequest`, `bytes.NewBuffer`).
- Boolean-returning functions read as assertions: `IsReady`, `HasSpace`, `CanRetry`. Avoid negatives such as `IsNotReady`.
- Function names describe the action and result: `ParsePort`, `ValidateToken`, `WriteFile`. Avoid vague verbs (`Handle`, `Process`, `Do`) unless the domain uses them.
- Methods that mutate should sound like it (`SetTimeout`, `Add`, `Close`); methods that only read should not.

### Receivers

- One or two letters derived from the type: `func (s *Server)`, `func (b *Buffer)`. Never `this` or `self`.
- Use the same receiver name for every method of a type.
- Use a pointer receiver when the method mutates, when the type is large, or when another method already uses a pointer. Do not mix pointer and value receivers on one type.

### Interfaces

- Name one-method interfaces with `-er`: `Reader`, `Writer`, `Stringer`, `Closer`.
- Define the interface in the package that consumes it, not the package that implements it.
- Keep interfaces to one or two methods. If it has five, it is probably a struct or several interfaces.
- Do not define an interface in anticipation of a second implementation. Define it when the second implementation or a test fake exists.

## Comments and documentation

The rule: a comment must tell the reader something the code cannot. Behaviour, contract, and reasons qualify. Mechanics do not.

### Doc comments

- Every exported package, type, function, method, constant, and variable gets a doc comment.
- Start with the name of the thing: `// Server serves HTTP requests.` Not `// This function...`.
- Write complete sentences and end with a period.
- The first sentence is the summary shown by `go doc`; keep it standalone.
- Document the contract: units, ownership, nil handling, concurrency safety, side effects, and which errors are returned.
- Deprecated APIs start with `// Deprecated:` and say what to use instead.

```go
// ParsePort parses a decimal TCP port in the range 1-65535.
// It returns ErrInvalidPort for any other value.
func ParsePort(s string) (int, error)
```

### Inline comments

Good comments explain why, or state something surprising:

```go
// Retry twice because the upstream resets idle connections without warning.
for attempt := 0; attempt < 2; attempt++ {
```

```go
// mu guards cache. Hold it only while reading or writing the map.
mu sync.Mutex
```

Bad comments restate the code:

```go
i++ // increment i
return nil // return nil
```

- Comment unexported code only when its behaviour is non-obvious.
- Keep the comment next to the code it describes. A comment separated from its subject drifts.
- Update or delete the comment in the same change as the code. A stale comment is worse than none.
- Use `// TODO(name): reason` for known gaps. Link an issue when it matters.
- Delete commented-out code. Git remembers it.
- Do not use comments to compensate for a bad name. Rename the thing instead.

## Errors

- Return errors for expected failure. Panic only for programmer errors or impossible states, and only during initialisation.
- Handle every error. `_ = f()` needs a comment saying why ignoring it is correct.
- Wrap with context and `%w`:

```go
if err := json.Unmarshal(data, &cfg); err != nil {
    return fmt.Errorf("decode config: %w", err)
}
```

- Use `%w` when callers need `errors.Is` / `errors.As`; use `%v` only when the chain is deliberately broken.
- Error strings are lowercase, have no trailing punctuation, and do not repeat the wrapping context: `open config: permission denied`, not `Failed to open config: Permission denied.`
- Define sentinel errors as `var ErrNotFound = errors.New("not found")`; define typed errors as `type ParseError struct { ... }` with an `Error() string` method.
- Compare with `errors.Is` and `errors.As`. Never compare `err.Error()` strings.
- Do not both log and return the same error. Choose the layer that owns the decision.
- Use `errors.Join` when the caller needs every failure.
- Never put secrets, tokens, or personal data in an error string.

## API design

- Accept interfaces, return concrete types. Callers can adapt a concrete return; they cannot recover information hidden behind an interface.
- Make the zero value useful. If it is not, document that and provide a constructor.
- Pass dependencies explicitly. Avoid package-level mutable state and `init()` except for registration that has no other home.
- Export only what callers need. Start unexported and promote when a real caller appears.
- Use `time.Duration` and `time.Time`, not integers with a unit in the name or strings.
- Prefer a config struct or functional options over many positional booleans.
- Keep functions small enough to read in one screen. Extract a helper when a function has more than one reason to change.
- Return early; avoid deep nesting and long `if` ladders.

## Concurrency

- Every goroutine needs an exit path. Tie it to `ctx.Done()`, a closed channel, or a `WaitGroup` the caller waits on.
- The sender closes a channel. The receiver never closes it.
- Never copy a `sync.Mutex`, `sync.WaitGroup`, or `sync.Cond`. Pass pointers.
- Use channels to transfer ownership; use a mutex to guard shared state. Do not use a channel as a mutex.
- Document who owns a value and whether a method is safe for concurrent use.
- Guard maps: concurrent writes panic.
- Run `go test -race ./...` for any concurrent change.

## Context

- `context.Context` is the first parameter, named `ctx`.
- Never store a context in a struct.
- Pass the caller's context down. Do not replace it with `context.Background()` mid-stack.
- Honour cancellation and deadlines in HTTP, database, and external calls.

## Tests

Table-driven tests are the default for anything with more than one case.

```go
func TestParsePort(t *testing.T) {
    t.Parallel()
    tests := []struct {
        name    string
        input   string
        want    int
        wantErr error
    }{
        {name: "valid", input: "8080", want: 8080},
        {name: "zero is out of range", input: "0", wantErr: ErrInvalidPort},
        {name: "not a number", input: "abc", wantErr: ErrInvalidPort},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            t.Parallel()
            got, err := ParsePort(tt.input)
            if !errors.Is(err, tt.wantErr) {
                t.Fatalf("ParsePort(%q) error = %v, want %v", tt.input, err, tt.wantErr)
            }
            if got != tt.want {
                t.Errorf("ParsePort(%q) = %d, want %d", tt.input, got, tt.want)
            }
        })
    }
}
```

- Name cases by the condition, so `-run TestParsePort/zero` selects one.
- Use `got` and `want`. Include the input in the failure message.
- `t.Fatalf` when continuing would mislead or panic; `t.Errorf` otherwise.
- `t.Parallel()` only when the case shares no state. Go 1.22+ makes `tt := tt` unnecessary; keep it if `go.mod` declares an older version.
- `t.Helper()` in helpers so failures point at the caller.
- `t.TempDir()`, `t.Cleanup()`, and `t.Setenv()` for setup and teardown.
- Test through the public API (`package foo_test`) unless internals are the point.
- Compare errors with `errors.Is` / `errors.As`, never strings.
- Do not use `time.Sleep` to wait for goroutines. Use channels, `WaitGroup`, or a fake clock.
- Fuzz parsers and anything that reads untrusted input.

Full test layout, runners, integration tags, fuzzing, and benchmarks: `../test-write/references/go.md`.

## Verify

```
gofmt -l .
go vet ./...
go test ./...
go test -race ./...     # concurrent code
```

Fix every line of output. Do not suppress a finding without a comment that explains why.

## Sources

- Effective Go: https://go.dev/doc/effective_go
- Go Code Review Comments: https://go.dev/wiki/CodeReviewComments
- Go table-driven tests: https://go.dev/wiki/TableDrivenTests
- Google Go Style Guide, decisions: https://google.github.io/styleguide/go/decisions
- Google Go Style Guide, best practices: https://google.github.io/styleguide/go/best-practices
- Go blog, errors are values: https://go.dev/blog/errors-are-values
- Go 1.13 error wrapping: https://go.dev/blog/go1.13-errors
- The Go standard library is the reference implementation of these rules.
