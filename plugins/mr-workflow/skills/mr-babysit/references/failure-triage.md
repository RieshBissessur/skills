# Failure triage

Read this when classifying failures. Commands are in `../SKILL.md`.

## Categories

| Category | Signals in the log | Action |
|----------|--------------------|--------|
| **Lint / format** | `eslint`, `prettier --check`, `ruff`, `black --check`, `golangci-lint`, "would reformat" | Run auto-fixes only on failed/changed files, then review the diff. Commit with type `style`. |
| **Type error** | `tsc`, `mypy`, "not assignable", `pyright` | Fix the types. Add `any` or `type: ignore` only with a specific justification; existing suppressions are not a reason. |
| **Test failure** | `FAIL`, `AssertionError`, `expected ... received`, `Traceback`, `--- FAIL:` | Read the test. Fix the code if it is wrong. Update the test only if it is clearly outdated, and say why. If unclear, ask. |
| **Build error** | `compilation failed`, `Module not found`, `cannot find symbol`, `error TS` during build | Fix the import, dependency, or code error. |
| **Dependency** | `ERESOLVE`, `version solving failed`, lockfile out of date | Update the lockfile with the package manager. Commit with type `build`. |
| **Warning** | Annotation `level: warning`, deprecation notices, GitLab `allow_failure` jobs | Fix if small and in the diff. Otherwise report it. |
| **Infra / flake** | `timeout`, `connection reset`, `502`, `rate limit`, runner offline, passes on rerun | Rerun. Do not change code. |
| **Config / CI** | YAML syntax, unknown keyword, missing variable or secret, registry permission denied | Fix YAML syntax or keywords (type `ci`). Missing secrets or permissions need a human. |
| **Needs human** | Needs a secret, external access, a product decision, or an unclear expected result | Stop and ask. |

## Fix approach

1. Reproduce with the same command the job runs. Check the CI config if unsure.
2. Fix the smallest thing that makes the job pass.
3. Rerun the local command until it passes.
4. Run the nearest related check too (for example the whole test file), so one failure is not traded for another.

## Warnings

Warnings do not fail the pipeline, but they are work to do:

- Fix a warning when the fix is local and small.
- Leave it and report it when the fix is large, in unrelated code, or a deliberate choice.

## Stop and ask when

- The same job fails the same way after a fix.
- The fix would disable a check, delete a test, or change a threshold.
- The failure depends on something outside the repo (secrets, external services, cloud permissions).
- The expected behaviour is unclear from the code or the MR description.

## Final report

Follow the output contract in `../SKILL.md`: concise per-round actions and one final status line. Do not paste full logs.
