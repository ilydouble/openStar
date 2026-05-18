# Repository Development Guidelines

This repository should be developed with clear domain boundaries and verified changes.

## Architecture

- Follow DDD principles: keep domain concepts, infrastructure code, API adapters, and configuration concerns separated.
- Keep relational database access behind repository classes. Do not issue ad hoc SQL from API handlers.
- Database schema changes must be represented as Alembic migrations under `icore-agent/alembic/`.
- Keep configuration grouped by business domain. Preserve stable public exports when refactoring shared config.

## Environment

- Do not commit `.env` files, `dotenv/.env.{domain}` files, or real secrets.
- Keep `dotenv/.env.{domain}.example` complete and use placeholders for credentials.
- Load backend environment through `icore-agent/compose.sh` so Docker Compose receives every split domain env file.
- PostgreSQL local development uses Docker Compose and the `icore_db` named volume.

## Testing And Git

- Every code or documentation change must be committed to git immediately after the change is completed.
- Keep commits scoped to the files changed for the current task.
- Do not bundle unrelated workspace changes into the same commit.
- Every code change must include or update focused tests.
- 每次代码改动都要进行测试，并在测试通过后再交付。
- use icore-agent/.venv/bin/autopep8 to format all changes
- Run the relevant test slice before broad verification.
- Before handing off or committing, run the full applicable test suite and ensure it passes.
- Commit only after tests pass. Keep git commits scoped to the completed change.

## Code Comment
- Write comment for function declaration, explain what a function does
- Write necessary helpful comments for critical code lines
- Don't write comment for all code lines, only write for those necessary
