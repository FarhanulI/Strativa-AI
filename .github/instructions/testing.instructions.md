# Backend Testing Rules

## Testing Philosophy

Tests must verify both functionality and architecture.

A feature is not complete merely because its happy path works.

## Required Test Categories

For domain features test:

1. creation
2. retrieval
3. listing
4. update
5. deletion
6. validation
7. ownership
8. relationships
9. filtering
10. sorting where applicable

## Workspace Isolation

Every workspace-scoped feature should include a test proving:

Workspace A cannot access Workspace B's resource.

Expected API behavior:

404 Not Found

Do not expose whether the resource exists.

## Parent Validation

When creating a child resource:

* verify parent exists
* verify parent belongs to current workspace
* verify related resources belong to the same ownership boundary

## Database Behavior

Test important cascade behavior.

Test nullable foreign keys with SET NULL behavior when used.

Test unique constraints.

Test score/range constraints.

## API Tests

Test:

* status codes
* response structure
* validation errors
* authorization boundaries

Do not test implementation details when behavior is sufficient.

## Service Tests

Test business rules independently from HTTP.

Important calculations should have deterministic tests.

## Regression

Before completing a development day:

run the complete existing test suite.

Do not only run newly created tests.

## Definition of Done

No development task is complete with failing tests.

Do not disable tests to make the suite pass.
