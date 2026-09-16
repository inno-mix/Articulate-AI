# 0006. Taskiq + Redis for background jobs

- Status: Accepted
- Date: 2026-09-17

## Context
Feedback reports take 10–90 s on a local model; coach-memory updates and (Q2) scheduled emails also
need a worker. ARQ was the first idea but is in maintenance-only mode (checked 2026-09).

## Decision
Taskiq with `taskiq-redis` (`ListQueueBroker`), `taskiq-fastapi` for dependency reuse, and
`TaskiqScheduler` + `LabelScheduleSource` for cron jobs (Q2). Tests use `InMemoryBroker`.
Worker: `taskiq worker app.worker.broker:broker app.worker.tasks` (explicit module list; `app/worker/tasks/__init__.py` imports every task module).

## Consequences
- Redis is required locally (also used for rate limiting).
- Tasks must be idempotent (a report task checks status before working).

## Alternatives considered
- ARQ — maintenance-only.
- Celery — heavy, sync-first.
- SAQ — viable; smaller ecosystem.
- FastAPI `BackgroundTasks` — lost on restart, no retries, no scheduling.
