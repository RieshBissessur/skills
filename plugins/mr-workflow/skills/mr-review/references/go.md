# Go review conventions

Read this only when `language` is `go`. Repo conventions win over this file. Check these in the changed code.

## Errors
- Returned errors are not ignored (`_ = f()` or a bare call to a function that returns an error). Justify it or handle it.
- Errors are wrapped with context using `%w`, so callers can use `errors.Is` / `errors.As`.
- Errors are compared with `errors.Is`, not `err.Error() == "..."`.
- Error strings are lowercase, with no trailing punctuation.
- Typed nil in an interface: a function returning a concrete nil pointer as `error` is never nil.

## context.Context
- `ctx` is the first parameter, and it is passed down, not replaced with `context.Background()` mid-stack.
- Not stored in structs.
- HTTP, DB, and external calls respect cancellation and deadlines.

## Goroutines and concurrency
- Every goroutine has an exit path. Check for `select` on `ctx.Done()` or a channel that is closed.
- The sender closes channels. Receivers do not.
- Writes to a map from multiple goroutines need a mutex or `sync.Map`.
- `sync.Mutex` or `sync.WaitGroup` is not copied. Pass pointers.
- Loop variable capture: go.mod's `go` version below 1.22 means loop variables are shared between iterations. Check goroutines and closures in loops.

## Resources and defer
- `defer` inside a loop accumulates until the function returns. Move the loop body into a function if this matters.
- `Close()` errors on writers (files, gzip, `bufio` flushes) are checked. `resp.Body.Close()` is called on every path.
- `rows.Close()` and `rows.Err()` are checked after iterating.

## Nil and zero values
- Writes to a nil map panic. Check where maps are created.
- Nil pointer dereference on optional fields returned from another package.

## Time
- `time.Now()` is injected or behind an interface where tests need control.
- Durations are `time.Duration`, not bare ints with a unit in the name.

## API design and naming
- Exported identifiers have doc comments starting with the name.
- No stutter: `user.UserService` should be `user.Service`.
- Package names are short, lowercase, no underscores.
- Receiver names are short and consistent across methods of one type.
- Interfaces are small and defined by the consumer, not the producer.

## Tooling
- `gofmt` and `go vet` clean. `golangci-lint` config respected (`.golangci.yml`).
- `go.mod` and `go.sum` updated with the code; `go mod tidy` leaves no diff.
- New dependency is necessary and maintained.
