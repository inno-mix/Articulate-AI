# 0015. Development-only cloud reference model for evals

- Status: Accepted
- Date: 2026-09-17
- Deciders: Owner (Micko Matamorosa)

## Context
Feedback quality is the core of the product. In Q1 the app runs on a 3–4B Ollama model (ADR-0002),
and users' own cloud keys only arrive in Phase 9. Tuning prompts and the rubric only against a small
local model would mean:
- we can't tell whether the coaching is actually good until the last phase;
- prompts may be bent around small-model quirks and not transfer to Claude/GPT/Gemini.

## Decision
- From Phase 2, the eval runner can also call **one cloud "reference" model** using the owner's own
  API key, stored as `EVAL_ANTHROPIC_API_KEY`, `EVAL_OPENAI_API_KEY` or `EVAL_GOOGLE_API_KEY` in
  `apps/api/.env`.
- These keys are used **only** by `evals/` and live tests — never by the running app. `Settings`
  rejects them when `APP_ENV=production`, and a test proves the app's LLM factory ignores them.
- The Q1 app runtime stays on Ollama.
- Quality targets (≥ 80 % in range, ≤ 5 % schema failures) are measured on the reference model.
  Ollama results are reported next to them; a documented gap is acceptable because Ollama is
  development-only.
- Prompt changes are never accepted if they lower the reference score; both runs are repeated after
  each change.
- The provider model builders (`app/llm/providers.py::build_model`) are written in Phase 2 and
  reused by Phase 9.

## Consequences
- Each reference run costs a small amount on the owner's account (the runner prints the number of
  calls and needs `CONFIRM=1`) and needs internet.
- Prompts are optimised for capable models first, which is where real users will be.
- Phase 9 gets smaller (builders and cloud evals already exist).

## Alternatives considered
- Ollama only until Phase 9 — can't judge the core product's quality for most of Q1.
- Use a cloud model as the development runtime — contradicts the owner's "Ollama for development".
- Wait for Phase 9 — quality problems would be discovered last, when they're most expensive.
