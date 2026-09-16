# 0005. PostgreSQL + SQLAlchemy 2 (async) + Alembic

- Status: Accepted
- Date: 2026-09-17

## Context
Relational data (users, sessions, messages, scores) with JSON documents (reports, speech data).
Async FastAPI.

## Decision
PostgreSQL 17 (Docker locally), SQLAlchemy 2 typed ORM with `asyncpg`, Alembic autogenerate
(reviewed by hand), JSONB for document-shaped data validated by Pydantic, enums as TEXT + CHECK.

## Consequences
- Tests use a real Postgres (`articulate_test`) with per-test SAVEPOINT rollback.
- JSONB shapes must be versioned carefully (Pydantic models are the schema).

## Alternatives considered
- SQLModel — thinner docs for async + Alembic edge cases.
- Prisma (Python client) — not first-class for Python.
- MongoDB — relational queries (progress, ownership) fit SQL better.
