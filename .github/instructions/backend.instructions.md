# FastAPI Backend Development Rules

## Stack

Python
FastAPI
SQLAlchemy
PostgreSQL
Alembic
Pydantic
uv
pytest
Ruff

## FastAPI

Use dependency injection for:

* database sessions
* authenticated user/workspace context
* shared infrastructure

Keep routers thin.

Use appropriate HTTP status codes.

Validate request payloads with Pydantic.

Do not expose SQLAlchemy ORM objects as an accidental API contract.

## SQLAlchemy

Use SQLAlchemy ORM consistently with the existing project style.

Use explicit relationships.

Avoid N+1 queries.

Use eager loading only when it is actually required.

Keep database queries inside repositories.

Do not put raw SQL into routers or services unless there is a demonstrated requirement.

## Services

Services own:

* domain validation
* authorization
* ownership
* orchestration
* calculations
* business rules

Services should not become generic utility dumping grounds.

## Repositories

Repositories own persistence.

Examples:

* create
* get
* list
* update
* delete
* filtering
* sorting

Repositories should not decide whether the current user is allowed to access a resource.

## Pydantic

Use explicit schemas.

Separate create/update/response schemas when appropriate.

Do not allow clients to submit server-controlled values such as:

* workspace_id
* calculated scores
* system timestamps
* ownership fields

unless explicitly required.

## Errors

Use consistent application error handling.

Do not expose:

* SQL errors
* stack traces
* internal implementation details

to API clients.

## Testing

Every new domain feature should have:

* service tests
* API tests where appropriate
* validation tests
* ownership tests
* relationship tests
* migration validation where relevant

Test both successful and failure paths.

## Code Quality

Use:

`uv run pytest`

`uv run ruff check .`

`uv run ruff format --check .`

Fix errors rather than suppressing them.

Keep functions focused.

Avoid unnecessary abstractions.

Prefer readable code over clever code.
