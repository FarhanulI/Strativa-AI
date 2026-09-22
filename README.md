# AI Content Studio API

Backend API for AI Content Studio, built as a FastAPI modular monolith.

## Requirements

- Python 3.12+
- uv
- PostgreSQL
- pgvector
- Redis

## Setup

```bash
uv sync
```

Create a local `.env` file from `.env.example` and set values for your machine:

```bash
DATABASE_URL=postgresql+asyncpg://contentstudio:password@localhost:5432/contentstudio
REDIS_URL=redis://localhost:6379
```

Start PostgreSQL and Redis using your operating system's service manager or installed local services. PostgreSQL must have pgvector available; migrations enable the extension for the configured database.

Run migrations:

```bash
uv run alembic upgrade head
```

Run the API:

```bash
uv run uvicorn app.main:app --reload --port 8000
```

## Checks

```bash
uv run pytest
uv run ruff check .
```

## API

Root endpoints:

- `GET /` - Returns API name and version
- `GET /api/v1/health` - Health check endpoint
- Swagger UI: `/docs`

### Workspaces

Workspaces are the foundational multi-tenant containers for all content data.

- `POST /api/v1/workspaces` - Create workspace
- `GET /api/v1/workspaces` - List all workspaces
- `GET /api/v1/workspaces/{workspace_id}` - Get workspace
- `PATCH /api/v1/workspaces/{workspace_id}` - Update workspace
- `DELETE /api/v1/workspaces/{workspace_id}` - Delete workspace

### Content Profiles

Content profiles belong to a workspace and are the universal strategic root for both creators and businesses.

- `POST /api/v1/profiles?workspace_id=<uuid>` - Create profile (`type`: `creator` or `business`)
- `GET /api/v1/profiles?workspace_id=<uuid>` - List profiles in workspace
- `GET /api/v1/profiles/{profile_id}?workspace_id=<uuid>` - Get profile
- `PATCH /api/v1/profiles/{profile_id}?workspace_id=<uuid>` - Update profile
- `DELETE /api/v1/profiles/{profile_id}?workspace_id=<uuid>` - Delete profile

### Brand Profiles

Each content profile can have at most one brand profile.

- `POST /api/v1/profiles/{profile_id}/brand?workspace_id=<uuid>` - Create brand profile
- `GET /api/v1/profiles/{profile_id}/brand?workspace_id=<uuid>` - Get brand profile
- `PATCH /api/v1/profiles/{profile_id}/brand?workspace_id=<uuid>` - Update brand profile
- `DELETE /api/v1/profiles/{profile_id}/brand?workspace_id=<uuid>` - Delete brand profile

**Note:** `workspace_id` query parameter is temporary and required for tenant isolation during development. Once authentication is implemented with Clerk, `workspace_id` will be derived from the authenticated user's workspace membership.

## Architecture

### Day 2: Workspace → ContentProfile Foundation

This is the foundational multi-tenant layer that establishes:

1. **Workspace** - Container for all tenant-scoped data
2. **WorkspaceMember** - User membership with roles (owner, admin, member)
3. **ContentProfile** - Universal root entity (`creator` and `business`) belonging to exactly one workspace
4. **Brand** - Optional one-to-one profile attached to a content profile

### Design Patterns

- **Modular Monolith**: FastAPI + SQLAlchemy in a single deployable unit
- **Async/Await**: All database operations are async
- **Dependency Injection**: Services and repositories injected via FastAPI dependencies
- **Tenant Isolation**: All profile and brand queries scoped by workspace_id
- **Type Safety**: Full Python type hints with Pydantic v2
- **Declarative ORM**: SQLAlchemy 2.x typed declarative mappings

### Data Flow

```
API Route (request validation)
  ↓
Service (business logic, transactions)
  ↓
Repository (database access only)
  ↓
SQLAlchemy ORM
  ↓
PostgreSQL
```

## Future Foundation

This Day 2/3 foundation enables:

- **Day 3+**: Brand Intelligence, Audience Intelligence, Market Intelligence, Performance Intelligence
- **Authentication**: Clerk integration (derive workspace from authenticated user)
- **Advanced Features**: Content Strategy, Content Intelligence, Publishing, etc.

---


<!-- Set up this Neon project in the current working directory.

1. `npm i -g neon@latest && neon login`
2. `neon skills -y`
3. `neon mcp -y`
4. `neon link --project-id withered-sunset-12594016 --branch production -y`
5. `neon config init`
6. Update `neon.ts`:

```ts
import { defineConfig } from "@neon/config/v1";

export default defineConfig({
  preview: {
    // Upgrade to a paid plan to enable AI Gateway for your project.
    // aiGateway: true,
    functions: {
      api: { name: "api", source: "./hello.ts" },
    },
  },
});
```

and `hello.ts`:

```ts
export default async function hello(): Promise<Response> {
  return new Response("Hello from Neon Functions");
}
```

7. `neon deploy` -->