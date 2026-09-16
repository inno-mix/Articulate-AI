# Data Model

> PostgreSQL 17 · SQLAlchemy 2 (async, typed `Mapped[...]`) · Alembic migrations.
> Tables are created in the phase listed. **Changing a column = update this doc in the same commit.**

## Conventions

- Primary keys: `id UUID` generated in Python with `uuid.uuid4()` (`default=uuid4`).
- Timestamps: `TIMESTAMPTZ`, stored in UTC. `created_at` default `now()`; `updated_at` set by the ORM
  on update (`onupdate=func.now()`).
- Enums: stored as `TEXT` with a `CHECK` constraint (via SQLAlchemy `Enum(..., native_enum=False,
  create_constraint=True, length=32)`) so adding values only needs a constraint migration.
- JSON: `JSONB`. Every JSONB column has a Pydantic model that validates it on write
  (see "JSON shapes" below).
- Foreign keys to `users.id` use `ON DELETE CASCADE` (deleting a user deletes all their data).
- Naming: tables plural snake_case; indexes `ix_<table>_<cols>`; unique `uq_<table>_<cols>`;
  constraint naming convention set on `MetaData` so Alembic autogenerate is stable.
- Scores: LLM dimension scores are integers 1–5. Everything shown on charts is normalised to
  0–100 in `skill_scores` using `score_100 = (score_5 - 1) * 25`.

## Dimension keys (shared everywhere)

`clarity`, `conciseness`, `structure`, `audience_fit`, `tone`, `confidence`,
`grammar_vocabulary` (LLM-scored) · `fluency` (voice only, computed) · `pronunciation`
(from Azure attempts). Defined once in `app/domain/dimensions.py` as a `StrEnum`.

---

## Q1 tables

### `users` (Phase 0)
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | Local user id is fixed: `00000000-0000-0000-0000-000000000001` |
| email | TEXT NOT NULL | stored lower-cased; `uq_users_email` |
| password_hash | TEXT NULL | NULL for the local user (Phase 7 fills it for real users) |
| email_verified_at | TIMESTAMPTZ NULL | |
| is_local | BOOLEAN NOT NULL DEFAULT false | true only for the built-in local user |
| created_at / updated_at | TIMESTAMPTZ | |

Local user email: `local@articulate.localhost`.

### `profiles` (Phase 0)
| Column | Type | Notes |
|---|---|---|
| user_id | UUID PK FK→users | |
| display_name | TEXT NOT NULL DEFAULT 'You' | ≤ 60 chars |
| seniority | TEXT enum | `junior` \| `mid` \| `senior` \| `staff_plus` \| `manager`; default `mid` |
| native_language | TEXT NULL | free text, ≤ 40 chars; stored but not used by prompts in Q1 (spec D23) |
| english_level | TEXT enum | `A2` \| `B1` \| `B2` \| `C1` \| `C2`; default `B2` |
| goals | TEXT[] NOT NULL DEFAULT '{}' | values from `interviews`, `meetings`, `stakeholders`, `code_review`, `presentations`, `writing` |
| focus_areas | TEXT[] NOT NULL DEFAULT '{}' | dimension keys |
| timezone | TEXT NOT NULL DEFAULT 'UTC' | IANA name, validated with `zoneinfo` |
| onboarding_completed_at | TIMESTAMPTZ NULL | used from Phase 7 |
| created_at / updated_at | TIMESTAMPTZ | |

### `user_settings` (Phase 0)
| Column | Type | Notes |
|---|---|---|
| user_id | UUID PK FK→users | |
| default_mode | TEXT enum `text` \| `voice` | default `text` |
| voice_input_mode | TEXT enum `push_to_talk` \| `hands_free` | default `push_to_talk` |
| tts_voice | TEXT NOT NULL | default from `DEEPGRAM_TTS_VOICE` |
| reminders_enabled | BOOLEAN NOT NULL DEFAULT false | Phase 8 |
| reminder_time | TIME NULL | local time, Phase 8 |
| weekly_summary_enabled | BOOLEAN NOT NULL DEFAULT false | Phase 8 |
| created_at / updated_at | TIMESTAMPTZ | |

### `scenarios` (Phase 1)
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| slug | TEXT NOT NULL | `uq_scenarios_slug` (custom scenarios get `custom-<8 hex>`) |
| title | TEXT NOT NULL | ≤ 80 |
| category | TEXT enum | see spec F1 |
| difficulty | SMALLINT NOT NULL | CHECK 1–3 |
| summary | TEXT NOT NULL | ≤ 300 |
| persona | JSONB NOT NULL | `Persona` |
| user_objective | TEXT NOT NULL | ≤ 300 |
| opening_line | TEXT NOT NULL | ≤ 400 |
| success_criteria | JSONB NOT NULL | `list[str]`, 1–5 items |
| recommended_mode | TEXT enum `text` \| `voice` \| `either` | |
| keyterms | JSONB NOT NULL DEFAULT '[]' | `list[str]` ≤ 20 technical terms for Deepgram keyterm prompting |
| rubric_version | TEXT NOT NULL DEFAULT 'v1' | |
| is_assessment | BOOLEAN NOT NULL DEFAULT false | |
| is_custom | BOOLEAN NOT NULL DEFAULT false | |
| owner_user_id | UUID NULL FK→users | required when `is_custom`; CHECK `(is_custom = (owner_user_id IS NOT NULL))` |
| content_hash | TEXT NULL | sha256 of the YAML entry; seed updates rows when it changes |
| created_at / updated_at | TIMESTAMPTZ | |

Index: `ix_scenarios_owner_user_id`.

### `practice_sessions` (Phase 1)
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK→users | `ix_practice_sessions_user_id_started_at` (user_id, started_at DESC) |
| scenario_id | UUID FK→scenarios ON DELETE CASCADE | |
| mode | TEXT enum `text` \| `voice` | |
| purpose | TEXT enum `practice` \| `assessment` | default `practice` |
| status | TEXT enum `active` \| `ended` \| `abandoned` | |
| safety_flag | BOOLEAN NOT NULL DEFAULT false | |
| user_turns | SMALLINT NOT NULL DEFAULT 0 | incremented per user message |
| llm_provider | TEXT NOT NULL | e.g. `ollama` |
| llm_model | TEXT NOT NULL | e.g. `llama3.2:latest` |
| started_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| ended_at | TIMESTAMPTZ NULL | |
| assessment_id | UUID NULL FK→assessments ON DELETE SET NULL | Phase 5 migration adds it |

### `messages` (Phase 1)
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| session_id | UUID FK→practice_sessions ON DELETE CASCADE | |
| seq | INTEGER NOT NULL | 0-based order; `uq_messages_session_id_seq` |
| role | TEXT enum `assistant` \| `user` | |
| content | TEXT NOT NULL | |
| source | TEXT enum `text` \| `voice` \| `system` | `system` = fixed safety message |
| speech | JSONB NULL | `SpeechData` for voice user turns (Phase 3) |
| created_at | TIMESTAMPTZ | |

### `feedback_reports` (Phase 2)
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| session_id | UUID FK→practice_sessions ON DELETE CASCADE | `uq_feedback_reports_session_id` |
| user_id | UUID FK→users | denormalised for ownership filters |
| status | TEXT enum `pending` \| `running` \| `ready` \| `failed` | |
| attempts | SMALLINT NOT NULL DEFAULT 0 | |
| overall_score | SMALLINT NULL | 0–100 |
| objective_met | BOOLEAN NULL | |
| summary | TEXT NULL | |
| dimension_scores | JSONB NULL | `list[DimensionScoreOut]` |
| strengths | JSONB NULL | `list[str]` |
| improvements | JSONB NULL | `list[str]` |
| highlights | JSONB NULL | `list[Highlight]` |
| grammar_fixes | JSONB NULL | `list[GrammarFix]` |
| voice_metrics | JSONB NULL | `VoiceMetrics` (voice sessions only) |
| rubric_version | TEXT NOT NULL | |
| prompt_version | TEXT NOT NULL | |
| llm_provider / llm_model | TEXT NULL | set when generated |
| error_code | TEXT NULL | e.g. `llm_unavailable`, `llm_invalid_output` |
| created_at / updated_at | TIMESTAMPTZ | `updated_at` is used to detect stuck `running` reports |
| completed_at | TIMESTAMPTZ NULL | |

### `skill_scores` (Phase 2)
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK→users | `ix_skill_scores_user_id_dimension_recorded_at` |
| dimension | TEXT NOT NULL | dimension key |
| score | SMALLINT NOT NULL | 0–100 |
| source | TEXT enum `session` \| `pronunciation` \| `drill` | |
| purpose | TEXT enum `practice` \| `assessment` | |
| session_id | UUID NULL FK→practice_sessions ON DELETE CASCADE | |
| pronunciation_attempt_id | UUID NULL FK→pronunciation_attempts ON DELETE CASCADE | Phase 4 migration adds it |
| drill_id | UUID NULL FK→drills ON DELETE CASCADE | Phase 6 migration adds it |
| scorer | TEXT NOT NULL | what produced the score: `<provider>:<model>` for LLM dimensions (e.g. `ollama:qwen3:4b`), `metrics:v1` for fluency, `<assessor>:pronunciation` (e.g. `azure:pronunciation`) for pronunciation |
| rubric_version | TEXT NULL | set for LLM-scored dimensions |
| recorded_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |

Rules: scores are only compared within the same `scorer` (see Phase 5). Pronunciation attempts made
for a drill (`purpose=drill`) do **not** write their own row — the drill writes one row when it is
completed — so nothing is counted twice. Attempts with `purpose=assessment` write rows with
`purpose=assessment`.

### `pronunciation_sets` / `pronunciation_sentences` (Phase 4)
`pronunciation_sets`: `id`, `slug` (unique), `title`, `description`, `difficulty` (1–3),
`position` (display order), `content_hash`, timestamps.

`pronunciation_sentences`: `id`, `set_id` FK (cascade), `position` (1-based, YAML order; unique with set_id),
`text` (≤ 200 chars), `focus_words` `TEXT[]`, timestamps.

### `pronunciation_attempts` (Phase 4)
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK→users | `ix_pronunciation_attempts_user_id_created_at` |
| sentence_id | UUID FK→pronunciation_sentences ON DELETE CASCADE | |
| purpose | TEXT enum `practice` \| `assessment` \| `drill` | |
| pron_score / accuracy / fluency / completeness | NUMERIC(5,2) NOT NULL | 0–100 |
| words | JSONB NOT NULL | `list[WordAssessment]` |
| duration_ms | INTEGER NOT NULL | |
| provider | TEXT NOT NULL | `azure` \| `fake` |
| assessment_id | UUID NULL FK→assessments ON DELETE SET NULL | Phase 5 |
| created_at | TIMESTAMPTZ | |

### `assessments` (Phase 5)
`id`, `user_id` FK, `status` (`in_progress` \| `completed`), `started_at`, `completed_at`.
The newest `completed` assessment is the baseline.

### `coach_notes` (Phase 5)
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK→users | `ix_coach_notes_user_id_is_active` |
| dimension | TEXT NOT NULL | dimension key |
| note | TEXT NOT NULL | ≤ 160 |
| evidence | TEXT NULL | quote ≤ 200 |
| times_seen | INTEGER NOT NULL DEFAULT 1 | |
| is_active | BOOLEAN NOT NULL DEFAULT true | |
| dismissed_by_user | BOOLEAN NOT NULL DEFAULT false | |
| last_session_id | UUID NULL FK→practice_sessions ON DELETE SET NULL | |
| created_at / updated_at | TIMESTAMPTZ | |

Business rule: at most 8 rows with `is_active = true` per user.

### `drills` (Phase 6)
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK→users | |
| drill_date | DATE NOT NULL | user's local date |
| position | SMALLINT NOT NULL | 0–2; `uq_drills_user_id_drill_date_position` |
| kind | TEXT enum `explain_concept` \| `rephrase` \| `pronunciation` \| `filler_free_minute` | |
| answer_mode | TEXT enum `text` \| `voice` \| `pronunciation` | |
| title | TEXT NOT NULL | |
| prompt | TEXT NOT NULL | |
| target_dimension | TEXT NOT NULL | |
| payload | JSONB NOT NULL DEFAULT '{}' | kind-specific (e.g. sentence ids, original sentence) |
| coach_note_id | UUID NULL FK→coach_notes ON DELETE SET NULL | |
| status | TEXT enum `pending` \| `completed` \| `skipped` | |
| response_text | TEXT NULL | |
| response_speech | JSONB NULL | `SpeechData` |
| result | JSONB NULL | `DrillResult` |
| completed_at | TIMESTAMPTZ NULL | |
| created_at | TIMESTAMPTZ | |

### `writing_rewrites` (Phase 6)
`id`, `user_id` FK, `channel` enum (`slack`,`email`,`pr_description`,`other`), `goal` enum
(`clearer`,`shorter`,`more_polite`,`more_assertive`), `context` TEXT NULL, `input_text`,
`output_text`, `changes` JSONB (`list[RewriteChange]`), `tone_note` TEXT, `llm_provider`,
`llm_model`, `created_at`. Index `(user_id, created_at DESC)`.

### `usage_events` (Phase 1, extended later)
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK→users | `ix_usage_events_user_id_created_at` |
| kind | TEXT enum `llm` \| `stt` \| `tts` \| `pronunciation` | |
| feature | TEXT NOT NULL | e.g. `roleplay`, `hint`, `feedback`, `memory`, `rewrite`, `custom_scenario`, `drill` |
| provider / model | TEXT NOT NULL | |
| input_tokens / output_tokens | INTEGER NULL | llm |
| audio_seconds | NUMERIC(10,2) NULL | stt / pronunciation |
| characters | INTEGER NULL | tts |
| latency_ms | INTEGER NULL | |
| created_at | TIMESTAMPTZ | |

---

## Q2 tables

### `auth_tokens` (Phase 7)
`id`, `user_id` FK, `kind` enum (`refresh`,`email_verification`,`password_reset`),
`token_hash` TEXT unique (sha256 of the random token),
`family_id` UUID NULL (refresh-token rotation family), `expires_at`, `used_at` NULL,
`revoked_at` NULL, `created_at`. Index `(user_id, kind)`. Unsubscribe links use signed,
stateless tokens and are not stored here.

### `email_deliveries` (Phase 7 creates, Phase 8 uses heavily)
`id`, `user_id` FK, `kind` enum (`verify_email`,`password_reset`,`practice_reminder`,
`weekly_summary`), `dedupe_key` TEXT unique (e.g. `practice_reminder:<user>:<local-date>`),
`status` enum (`sent`,`failed`), `error` TEXT NULL, `created_at`.

### `llm_credentials` (Phase 9)
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK→users | `uq_llm_credentials_user_id_provider` |
| provider | TEXT enum `anthropic` \| `openai` \| `google` | |
| encrypted_key | BYTEA NOT NULL | AES-256-GCM ciphertext+tag |
| nonce | BYTEA NOT NULL | 12 bytes |
| key_version | SMALLINT NOT NULL | which master key encrypted it |
| key_last4 | TEXT NOT NULL | |
| model | TEXT NOT NULL | from allowlist |
| is_active | BOOLEAN NOT NULL DEFAULT false | at most one active per user (partial unique index) |
| validated_at | TIMESTAMPTZ NULL | |
| last_error_code | TEXT NULL | |
| created_at / updated_at | TIMESTAMPTZ | |

Partial unique index: `uq_llm_credentials_user_id_active ON (user_id) WHERE is_active`.

---

## JSON shapes (Pydantic models in `app/schemas/json_types.py`)

```python
class Persona(BaseModel):
    name: str            # ≤ 40
    role: str            # ≤ 80, e.g. "Product manager"
    personality: str     # ≤ 200
    goals: str           # ≤ 200, what the persona wants from the conversation

class SpeechWord(BaseModel):
    word: str
    start: float         # seconds from turn start
    end: float
    confidence: float    # 0..1
    is_filler: bool

class SpeechData(BaseModel):
    words: list[SpeechWord]
    duration_s: float    # last.end - first.start
    stt_model: str

class DimensionScoreOut(BaseModel):
    dimension: str       # dimension key
    score: int           # 1..5
    reason: str

class Highlight(BaseModel):
    message_id: UUID | None   # resolved by matching the quote
    quote: str
    issue: str
    better_version: str

class GrammarFix(BaseModel):
    original: str
    corrected: str
    explanation: str

class VoiceMetrics(BaseModel):
    speaking_seconds: float
    words: int                 # excluding fillers
    wpm: float                 # 0 when pace_measured is false
    pace_measured: bool        # false when no turn had ≥ 3 non-filler words
    filler_count: int
    filler_rate_per_100: float
    filler_examples: list[str]      # ≤ 5 distinct
    long_pause_count: int           # gaps > 2.0 s inside a turn
    long_pauses_per_min: float
    hard_to_catch_words: list[str]  # confidence < 0.60, non-filler, ≤ 10 distinct
    fluency_score: int              # 1..5

class PhonemeAssessment(BaseModel):
    phoneme: str
    accuracy: float
    heard_as: str | None = None     # only if provider returns N-best phonemes

class WordAssessment(BaseModel):
    word: str
    accuracy: float
    error_type: Literal["None", "Omission", "Insertion", "Mispronunciation",
                        "UnexpectedBreak", "MissingBreak", "Monotone", "Other"]
    # the parser maps any value Azure returns that isn't listed to "Other" (never fails on it)
    phonemes: list[PhonemeAssessment]

class DrillResult(BaseModel):
    score: int                 # 1..5
    feedback: str              # ≤ 300
    better_version: str | None = None
    metrics: VoiceMetrics | None = None
    pronunciation_attempt_ids: list[UUID] = []

class RewriteChange(BaseModel):
    what: str
    why: str
```

## Entity relationships

```
users 1─1 profiles
users 1─1 user_settings
users 1─* practice_sessions *─1 scenarios (built-in or custom owned by user)
practice_sessions 1─* messages
practice_sessions 1─0..1 feedback_reports
users 1─* skill_scores  (from sessions, pronunciation attempts, drills)
pronunciation_sets 1─* pronunciation_sentences 1─* pronunciation_attempts *─1 users
users 1─* assessments 1─* practice_sessions / pronunciation_attempts
users 1─* coach_notes, drills, writing_rewrites, usage_events
users 1─* auth_tokens, email_deliveries, llm_credentials   (Q2)
```
