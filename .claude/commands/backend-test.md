# Backend Test

## Usage

`/backend-test`

## Instructions

Run the backend verification suite for the current implementation: tests, Ruff lint, formatting checks, and migration validation.

Read:

1. `CLAUDE.md`
2. `docs/development/progress.md`

Inspect the repository to determine the configured test framework, lint/format tooling, and migration setup.

## Workflow

### Tests

1. Identify the appropriate test commands.
2. Run the test suite.
3. If tests are organized into separate categories, run the relevant categories.
4. If tests fail, diagnose the failures.
5. Fix a failure only when it is clearly caused by the implementation being tested and the fix is within the current development scope.
6. Re-run affected tests after a fix.

### Lint and formatting

7. Run `ruff check .` and report violations exactly as returned (file:line, rule code).
8. Run `ruff format --check .` and report which files, if any, would be reformatted.
9. Fix a lint or formatting violation only when it is clearly caused by the implementation being tested and the fix is within the current development scope. Do not auto-apply fixes for pre-existing violations outside that scope.
10. Re-run the affected check after a fix.

### Migration validation

11. Confirm the current Alembic head matches what's on disk.
12. If new migration files exist in the current diff, verify they apply cleanly (`alembic upgrade head`) against a clean/test database and were generated against the current models, not hand-written from scratch unless intentional.
13. Report actual command output — do not infer migration correctness from the model diff alone.

### Reporting

14. Report the actual results for all four areas.

## Report

Provide:

* commands executed
* total tests
* passed
* failed
* skipped
* errors
* failing tests
* failure causes
* ruff lint result (clean / violations listed)
* ruff format result (clean / files listed)
* migration validation result (clean / issues found)
* files changed, if fixes were required
* final status

Use:
`PASS` — all relevant tests passed and lint, format, and migration checks are clean
`FAIL` — one or more tests failed, or lint/format/migration checks found issues
`BLOCKED` — checks could not run because of an environment/configuration/dependency problem

## Important

This command is verification-focused.

Do not:

* perform a separate architecture review
* implement a development day
* add speculative features
* perform unrelated refactoring
* create unrelated migrations
* fix pre-existing lint/format violations outside the current implementation's scope
* claim tests, lint, format, or migration checks passed without actually running them