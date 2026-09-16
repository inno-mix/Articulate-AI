# CLAUDE.md

@AGENTS.md

## Claude Code specifics
- Library docs: use the Context7 MCP (`resolve-library-id` → `query-docs`) before writing code
  against FastAPI, SQLAlchemy, Pydantic AI, Taskiq, Deepgram, Azure Speech, Next.js, shadcn/ui,
  TanStack Query, openapi-fetch, Playwright. Pin the version from the lock file.
- Executing a phase: `superpowers:executing-plans` or `superpowers:subagent-driven-development`
  with the phase file in `docs/tasks/`. Use `superpowers:test-driven-development` per subtask and
  `superpowers:verification-before-completion` before claiming a task is done.
- UI verification: start servers with `make dev` / `make dev-fake` (or `preview_start` via
  `.claude/launch.json` once it exists), then use the built-in browser pane
  (`read_page`, `read_console_messages`, `read_network_requests`, screenshots).
- Don't commit unless the owner asked for commits in this session or the task loop they approved
  says so.
- The owner prefers plain-language summaries: say what changed, what was verified, what's next.
