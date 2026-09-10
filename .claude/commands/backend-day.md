# Execute Development Day

## Usage

`/backend-day <day-number>`

Example: `/backend-day 13`

## Instructions

Execute the specified development day from the project's existing development specifications.

Before making changes, read:

1. `CLAUDE.md`
2. `docs/architecture/product-architecture.md`
3. `docs/development/progress.md` (if it exists)
4. `docs/development/days/day-$ARGUMENTS.md`

Replace `XX` with the requested day number.

Then inspect the actual current implementation and determine the delta between:

* the current repository state
* the requested day's specification

Use the project's `.claude/agents/` definitions when their expertise is relevant.

## Execution rules

* Implement ONLY the requested day's scope.
* Do not implement future-day work.
* Follow the architecture and development rules defined in the project documentation.
* Do not duplicate or reinterpret those rules in this command.
* Preserve existing architecture unless the requested day requires a change.
* Add/update tests required by the day's specification.
* Create/review Alembic migrations when database changes are required.
* Never claim tests or checks passed unless they were actually run.
* Update `docs/development/progress.md` after successful completion.
* Do not automatically start the next development day.

## Before coding

Briefly report:

* current implementation state
* requested day objective
* implementation delta
* files/components expected to change
* any architectural conflict or ambiguity

If the requested day conflicts materially with the architecture or existing implementation, stop and ask for approval before making changes.

## Review (after implementation, before testing)

Using the `backend-reviewer` agent, review the implementation against `docs/architecture/product-architecture.md` and the day's spec. This is review-only — no fixes applied during this step.

Do not re-read `CLAUDE.md`, the architecture doc, `progress.md`, or the day spec — they are already loaded from the steps above.

Check:

* Strategy vs. Creation boundary is respected (Creation does not redefine strategy)
* Opportunity exists before Brief; Brief exists before Creation
* Trends/signals never directly trigger content generation
* `ContentProfile` remains the universal root — no parallel strategy engines per profile type
* `BusinessContext` remains optional and additive
* AI providers are accessed only through the Orchestrator/Router layer, never imported directly into domain services
* Domain modules are organized by responsibility, not by AI provider
* Performance/Learning logic explains *why*, not just *how much*, where applicable
* Actual implementation scope matches the day spec's claimed scope — nothing from future days implemented
* General backend quality: error handling, input validation, DB session handling, N+1 risks, missing indexes on new columns/FKs

Classify each finding as:

* **Blocking** — violates an architectural law or the day's defined scope; must be fixed before testing
* **Should-fix** — real issue, not a law violation, log it but don't block on it
* **Suggestion** — optional, log it but don't block on it

For each relevant law/check, report one line: respected or violated. Only expand on violations — do not restate law text on a pass.

If any **Blocking** issue is found: fix it now, then re-check only the affected law/scope item (not the full checklist) before proceeding.

Do not proceed to Testing until review shows no blocking issues.

## Testing (after review passes)

Run `/backend-test` to verify the implementation (tests, Ruff lint, Ruff format check, migration validation). Do not proceed to the "after coding" report until this has actually been run.

## After coding

Report:

* implementation summary
* files changed
* database/migration changes
* API changes
* AI changes, if applicable
* tests added/updated
* review result (blocking issues found/fixed, outstanding should-fix/suggestions)
* `/backend-test` result (status, actual command output per its own reporting rules)
* known issues
* confirmation that future-day scope was not implemented

Then update `docs/development/progress.md`, including any outstanding should-fix/suggestion items from review that weren't acted on, so future days can see them.