---
name: go-code
description: Write canonical Go with idiomatic naming, contract comments, wrapped errors, small interfaces, and table-driven tests. Use when writing, changing, or reviewing Go code.
---

# go-code

Writes Go the way the standard library and the Go team write it. Apply this when adding, changing, or refactoring Go code. The repo wins; when the repo is silent, these opinions decide.

Read `references/conventions.md` before anything beyond a trivial edit. It holds the full rules, examples, and canonical sources.

## Non-negotiables

- **Format with the tool, not by hand.** `gofmt` (or `goimports`) and `go vet` must be clean. Do not argue style in review; the formatter decides.
- **Name for the reader.** `MixedCaps`, canonical initialisms (`URL`, `ID`, `HTTP`), short names in short scopes, descriptive names at package scope. Package names are short, lowercase, and do not stutter (`user.Service`, not `user.UserService`). No `Get` prefix.
- **Comment the contract, never the mechanics.** Every exported identifier gets a doc comment that starts with its name and ends with a period. A comment earns its place by stating behaviour a reader cannot infer: units, ownership, nil handling, concurrency safety, error conditions, or why a surprising choice was made. Delete comments that restate the code.
- **Return errors; do not panic for expected failures.** Handle every error, wrap with `%w` and context, keep error strings lowercase without punctuation, and compare with `errors.Is` / `errors.As`.
- **Keep interfaces small and consumer-owned.** Accept interfaces, return concrete types. Do not define an interface until a second implementation or a real dependency boundary exists.
- **Test behaviour with table-driven tests.** Named cases, `t.Run`, `got`/`want`, and failure messages that include the input. Test the public API unless internals are the point.

## Order of work

1. **Read the package first.** Match its layout, naming, error style, and test helpers. Consistency beats this skill.
2. **Design the API surface.** Decide what is exported, what the zero value means, and which errors callers must distinguish.
3. **Write the smallest correct implementation.** Return early, keep nesting shallow, and avoid package-level mutable state.
4. **Name and comment as you go.** Retrofitted comments are usually restatements.
5. **Write the table test** with the success path, boundaries, and error cases. Add a regression case for a bug fix.
6. **Verify** with the commands below and fix every finding.

## Verify

```
gofmt -l .
go vet ./...
go test ./...
go test -race ./...     # any concurrent code
```

For test layout, runners, fuzzing, and integration tags, use `../test-write/references/go.md`. To run or target tests, use `../test-write/SKILL.md`.

## Review checklist

- [ ] `gofmt` and `go vet` clean; `go mod tidy` leaves no diff.
- [ ] Exported names documented; comments explain why or contract, not what.
- [ ] Initialisms correct; no stutter; no `Get` prefix; receiver names short and consistent.
- [ ] Every error handled or explicitly justified; wrapped with `%w`; lowercase message.
- [ ] Interfaces small and defined by the consumer; concrete types returned.
- [ ] Goroutines have an exit path; channels closed by the sender; race detector clean.
- [ ] Table tests name their cases and print useful failures.

## Output

When writing code, report the files changed, the exported surface added or changed, and the verification commands with their result. Do not commit unless the user asks; then use `../git-commit/SKILL.md` with `--type feat`, `fix`, or `refactor` as appropriate.
