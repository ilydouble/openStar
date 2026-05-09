# Repository Development Guidelines

This repository should be developed with clear domain boundaries and verified changes.

## Architecture

- Follow DDD principles: keep domain concepts, infrastructure code, API adapters, and configuration concerns separated.
- Keep relational database access behind repository classes. Do not issue ad hoc SQL from API handlers.
- Database schema changes must be represented as Alembic migrations under `icore-agent/alembic/`.
- Keep configuration grouped by business domain. Preserve stable public exports when refactoring shared config.

## Environment

- Do not commit `.env` files or real secrets.
- Keep `.env.example` complete but use placeholders for credentials.
- PostgreSQL local development uses Docker Compose and the `icore_db` named volume.

## Testing And Git

- Every code change must include or update focused tests.
- 每次代码改动都要进行测试，并在测试通过后再交付。
- Run the relevant test slice before broad verification.
- Before handing off or committing, run the full applicable test suite and ensure it passes.
- Commit only after tests pass. Keep git commits scoped to the completed change.
