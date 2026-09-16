# Agent Workflow

> How an AI coding agent (Claude Code or any other) works on this repo.
> Goal: correct, verified, small steps — no guessing.

## 1. Before you start any work

1. Read `AGENTS.md` (root).
2. Open `docs/tasks/README.md` → find the **first phase whose status is not `Done`** and, inside
   it, the first unchecked task. Work on that task only, unless the owner told you otherwise.
3. Read the task's **"Read before starting"** list — every linked section, not just the titles.
4. Check the task's **Depends on** — if a dependency is unchecked, stop and say so.
5. Run `git status` — the tree should be clean. If not, ask before touching unrelated changes.
   Make sure you're on the phase branch (see §2a); create it if the phase is just starting.
6. Run `make check` (from Phase 0 onwards) to confirm the baseline is green. If it's red before you
   change anything, report that first.

## 2a. Branches

- One branch per phase, created from an up-to-date `main`: `phase-<NN>-<slug>`
  (e.g. `phase-01-text-practice`). Spikes live on the phase branch too.
- Commit per subtask on that branch; never commit directly to `main`.
- At phase end the owner reviews the branch, then it's merged with `git merge --ff-only` (or via a
  pull request once a GitHub remote exists). Only merge when the owner says so.
- Commit only when the owner has approved committing for this session (Claude Code: see
  `CLAUDE.md`).

## 2. The task loop

For each subtask, in order:

1. **Understand** — restate (to yourself) the expected behaviour and the files involved.
2. **Look up APIs** — for any third-party library call you are not 100 % sure about, query
   Context7 (`resolve-library-id` → `query-docs`) with the version from the lock file. Record
   non-obvious findings in the task's "Notes" in the completion log.
3. **Red** — write the failing test(s) listed in the subtask. Run the exact command. Confirm it
   fails **for the expected reason** (not an import error from a typo).
4. **Green** — write the minimal code to pass. Match `coding-conventions.md`.
5. **Verify** — run the subtask's command, then `make check` (or the narrower command the subtask
   gives while iterating; always `make check` before committing).
6. **Refactor** — only while green; re-run tests.
7. **Commit** — one Conventional Commit per subtask (or per tightly coupled pair). Never commit
   `.env`, secrets, generated eval results, or unrelated changes.
8. **Tick** — change `- [ ]` to `- [x]` for the subtask in the phase file, in the same commit.

When all subtasks of a task are ticked, check the task's **Acceptance criteria** one by one, then
append an entry to the phase file's **Completion log**:
```
- 2026-10-02 · Task 1.3 · commits abc1234..def5678 · `make check` ✅ (142 passed) ·
  Notes: Pydantic AI v2 `run_stream` needs `async with`; used NativeOutput for Ollama.
```

When all tasks of a phase are done: run the **Phase verification** section, `make test-e2e`,
update the status table in `docs/tasks/README.md`, and summarise to the owner.

## 3. Hard rules

| # | Rule |
|---|---|
| A1 | **Never guess an external API.** Look it up (Context7 / official docs). If docs contradict these docs, trust the official docs, then update our docs in the same change and mention it. |
| A2 | **Contracts are binding.** Don't change an endpoint, schema, DB column, WS message or env var name unless the task says so. If you must, update `api-contract.md` / `data-model.md` / `voice-and-pronunciation.md` / `local-development.md` in the same commit and run `make gen-client`. |
| A3 | **No new dependencies** beyond those named in the task or `docs/architecture/*` without asking the owner. |
| A4 | **Evidence before claims.** Never say "done", "fixed" or "passing" without having run the command in this session and seen the output. Quote the result. |
| A5 | **Don't weaken tests** to make them pass (no deleting assertions, no broad `skip`, no `except: pass`). |
| A6 | **Secrets:** never print, log, echo or commit key values. Refer to them by env var name. You cannot create accounts or keys — ask the owner. |
| A7 | **Scope:** do only the current task. Note unrelated problems in the completion log ("Follow-ups") instead of fixing them. |
| A8 | **Paths contain a space.** Quote `"…/Articulate AI/…"` in every shell command and script. |
| A9 | **Local resources are limited (8 GB).** Don't start extra Ollama models; stop dev servers you started when you're done; prefer `make dev-fake` for UI work. |
| A10 | **Spikes are throwaway.** Spike code lives in `apps/api/spikes/` (or `apps/web/spikes/`), is never imported by the app, and its findings go into a new ADR in `docs/decisions/`. |
| A11 | **Docs stay true.** If implementation reveals a doc is wrong or incomplete, fix the doc in the same change. |
| A12 | **Ask, don't assume,** when: a requirement is ambiguous; a spike contradicts the plan; a test can't pass without changing a contract; an external account/key/payment is needed; a destructive action is required (dropping data, force-push, deleting files you didn't create). |

## 4. Verification toolbox

| Need | Command / tool |
|---|---|
| Everything before commit | `make check` |
| One backend test | `cd "apps/api" && uv run pytest tests/path/test_x.py::test_name -vv` |
| One frontend test | `pnpm --filter web test -- tests/path/x.test.tsx` |
| Type/lint only | `make lint` |
| API manually | `curl -s http://localhost:8000/api/v1/health \| python -m json.tool` |
| SSE manually | `curl -N -X POST http://localhost:8000/api/v1/sessions/<id>/messages -H 'Content-Type: application/json' -d '{"content":"hi"}'` |
| UI manually | Claude Code: use the built-in browser pane (`preview_start` / `navigate`, `read_page`, `read_console_messages`, screenshots). Check the console for errors and the network panel for failed requests. |
| DB state | `docker compose -f infra/docker-compose.yml exec postgres psql -U articulate -d articulate -c "…"` |
| Worker jobs | worker terminal output (`make dev` prefixes lines with `[worker]`) |
| LLM quality | `make eval` (Ollama); `make eval-cloud PROVIDER=… MODEL=… CONFIRM=1` (reference model — ask the owner first, it costs money) |
| Real providers | `make test-live` (tell the owner first — Deepgram/Azure usage costs money) |

## 5. Using Claude Code skills (if available)

- Executing a phase: `superpowers:executing-plans` (inline) or
  `superpowers:subagent-driven-development` (one fresh subagent per task + review).
- Each code step: `superpowers:test-driven-development`.
- Before claiming completion: `superpowers:verification-before-completion`.
- Bugs: `superpowers:systematic-debugging`.
- Phase end: `code-review` skill on the phase diff; Phase 10: `security-auditor`.
- Schema work: `database-designer` for review of migrations.

## 6. Definition of Done (every task)

- [ ] All subtasks ticked, each with a passing test that failed first.
- [ ] Acceptance criteria verified and evidence recorded in the completion log.
- [ ] `make check` passes.
- [ ] No contract drift (or docs + generated client updated in the same change).
- [ ] No secrets, debug prints, commented-out code, or stray files.
- [ ] User-facing text is clear, kind and free of internal jargon.
- [ ] Errors are handled with the documented codes and show a retry path in the UI.
- [ ] Commits follow Conventional Commits.

## 7. Writing a new task (for humans or agents extending the plan)

Use the template in `docs/tasks/README.md` §4. A good subtask:
- names exact files,
- names the exact test(s) and what they assert,
- gives the exact command and the expected result,
- takes 2–15 minutes,
- leaves the codebase green.
