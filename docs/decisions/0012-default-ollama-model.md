# 0012. Default Ollama model for feedback generation

- Status: Accepted
- Date: 2026-09-21
- Deciders: Owner (Micko Matamorosa)

## Context

Phase 2 needed a default `OLLAMA_MODEL` for the feedback-report worker, chosen with evidence rather
than a guess (ADR-0015). The eval suite (`apps/api/evals/`) scored 26 hand-written cases — covering
excellent answers, ESL grammar, rambling, rude/defensive tone, hedging, jargon, unstructured
interview answers, a very short session, a prompt-injection attempt, spoken-style filler, mixed
signals, and code-switched (Tagalog/English) input — against two Ollama candidates and one cloud
reference model, using the exact same prompts and rubric the app uses in production
(`app.services.feedback.build_feedback_prompts`).

## Reference run (target: in-range ≥ 80%, schema failure ≤ 5%)

**Provider/model:** Google, `gemini-3.7-flash` (current model id verified against Pydantic AI's
docs at run time; picked by the owner from EVAL_GOOGLE_API_KEY being the configured eval key).

| Metric | Result |
|---|---|
| in_range_rate | 94.2% |
| schema_failure_rate | 0.0% |
| objective_accuracy | 100% |
| english_ok_rate | 100% (see note below) |
| p50 / p95 latency | 8.6 s / 20.7 s |

**Target met** on the first run — no prompt/rubric changes were needed.

**Note — a scoring bug, not a model or prompt problem:** the first run reported
`english_ok_rate: 0.0%`; the one case it flagged
(`foreign-language-code-review-01`) turned out to be a false positive in the eval harness, not the
model. The model's actual output was excellent: it wrote entirely in English, correctly identified
that the user's message was in Tagalog/Taglish, and named it as such. The case's `foreign_words`
list included the 2-letter Tagalog word "mo", and the harness's original substring check matched it
*inside* the English word "**Mo**st" (as in "Most of the response is in Tagalog/Taglish rather than
English.") — `english_ok` used a plain substring test, so a 2-letter foreign word can collide with
common English words. Fixed by (1) switching `evals/scoring.py`'s check to
word-boundary regex matching (`\bword\b`) and (2) dropping the two collision-prone short words
("mo", "may") from that case's `foreign_words` list, keeping the five longer, unambiguous ones.
Verified by re-scoring the actual captured model output offline with the fix — it correctly comes
back `english_ok: True` — so this needed no further reference spend to confirm.

## Ollama candidates (reported next to the reference; a gap is acceptable — ADR-0015)

| Model | in_range_rate | schema_failure_rate | p50 / p95 latency |
|---|---|---|---|
| `llama3.2:latest` | 80.9% | 3.8% (1/26) | 40.1 s / 67.7 s |
| `qwen3:4b` | 0.0% | 100% (26/26, all timeouts) | ≥120 s (timed out) |

**`llama3.2:latest` wins outright** on the decision rule (higher in-range rate; the tie-break
columns don't even come into play).

### Why qwen3:4b failed completely

qwen3 models "think" by default (ai-layer.md §3), which was expected to cost some latency. In
practice it made the model *unusable* for this feature on this 8 GB machine:

1. **First run** used the app's default 30 s timeout (a bug in the eval runner, since fixed —
   feedback generation is a background job, never a live request) and failed 69% of cases —
   almost all from that timeout, not genuine model failures.
2. **Second run**, with the runner's timeout raised to 120 s, still failed 100% of cases. p50/p95
   latency sat right at 120,000-120,343 ms — every single call was still hitting the timeout.
3. Added proper thinking-disable support: `PydanticAILLMService(disable_thinking=...)`, auto-detected
   for any model name containing `"qwen3"` (`app/llm/pydantic_ai_service.py::thinks_by_default`),
   verified empirically against real Ollama (a trivial call dropped from 120 s+ to ~10 s with
   `thinking=False`). Re-ran qwen3:4b with thinking disabled: **still 100% timeouts** at 120 s.
4. Diagnosed further: a *trivial* structured call (`NativeOutput`, thinking disabled) completed in
   12.7 s. The full `FeedbackAnalysis` schema — 7 dimension scores each with a reasoned
   explanation, a summary, strengths, improvements, up to 5 highlights and up to 8 grammar fixes,
   generated under `NativeOutput`'s grammar-constrained decoding — did not complete even with a
   240 s budget (nearly 4×  qwen3's already-poor p95). The bottleneck is the combination of a
   large structured schema with grammar-constrained decoding on a 4B model on this hardware, not
   the "thinking" setting specifically (already ruled out) and not a fixable eval-runner bug.

This was pursued to the point of real diagnosis (not abandoned at the first failure) precisely
because ai-layer.md §3 anticipated the thinking issue and asked for it to be checked — the
thinking-disable fix is real, generally useful infrastructure now in `PydanticAILLMService`, and
would matter if a *smaller-schema* feature (e.g. a future qwen3 use for `hint` or `roleplay`) were
ever considered. It just doesn't rescue qwen3:4b for feedback generation specifically.

## Decision

- **Default `OLLAMA_MODEL` stays `llama3.2:latest`** (the existing default) — validated with
  evidence, not changed.
- **Reference model: Google `gemini-3.7-flash`**, owner's key, development-only (ADR-0015).
- No prompt or rubric changes were made — the reference run met its target on the first attempt,
  and the one apparent quality gap (`english_ok`) was a scoring bug, not a real prompt issue.
- `PydanticAILLMService.disable_thinking` / `thinks_by_default()` are now part of the LLM layer,
  auto-applied whenever a qwen3-family model is selected, for any future use of that model family.

## Consequences

- The gap between `llama3.2:latest` (80.9% in-range) and the reference model (94.2% in-range) is
  documented and accepted (ADR-0015) — Ollama is development-only, users never see it in
  production.
- `qwen3:4b` is not a viable candidate for feedback generation on an 8 GB development machine as
  currently speced; revisit only if the `FeedbackAnalysis` schema shrinks significantly or the dev
  machine's hardware changes. Not worth re-testing with the same schema.
- Eval case authors should avoid `foreign_words` entries shorter than ~4 characters, or entries
  that are common substrings of English words, even though the scorer now uses word-boundary
  matching (belt-and-braces — word-boundary matching still permits exact short-word collisions,
  e.g. a foreign word that is itself also a common English word).

## Alternatives considered

- Keep chasing qwen3:4b (smaller prompt, `output_mode="tool"` instead of `"native"`, trimming the
  rubric) — rejected for now: `llama3.2:latest` already clears its bar with a healthy margin, and
  the reference model's numbers are strong, so there's no pressing quality problem this would
  solve; revisit only if `llama3.2:latest`'s real-world quality proves insufficient.
- A different Gemini tier (e.g. a "pro" model) as reference — `gemini-3.7-flash` already cleared
  both targets comfortably at low latency and cost; a heavier model wasn't needed.
