import jinja2
import pytest

from app.content.rubrics import get_rubric
from app.llm.prompts import render_prompt, system_template_names, user_block

RUBRIC = get_rubric("v1")

PERSONA = {
    "name": "Dana",
    "role": "Product manager",
    "personality": "Friendly.",
    "goals": "Ship.",
}
SCENARIO = {
    "title": "Explain tech debt",
    "summary": "Fragile module.",
    "user_objective": "Ask for time.",
}
LEARNER = {"seniority": "mid", "english_level": "B2"}


def _roleplay_context(**overrides: object) -> dict[str, object]:
    context = {
        "persona": PERSONA,
        "scenario": SCENARIO,
        "learner": LEARNER,
        "mode": "text",
        "coach_notes": [],
        "rubric": RUBRIC,
    }
    context.update(overrides)
    return context


def test_render_roleplay_includes_persona_and_rules() -> None:
    rendered = render_prompt("roleplay_system", **_roleplay_context())

    assert "Dana" in rendered.text
    assert "Product manager" in rendered.text
    assert "Stay in character" in rendered.text


def test_every_template_includes_the_english_language_rule() -> None:
    for name in system_template_names():
        rendered = render_prompt(
            name, **_roleplay_context(recent_transcript=[{"speaker": "user", "text": "hi"}])
        )
        assert "English" in rendered.text, f"{name} is missing the language rule"


def test_user_block_wraps_text_in_delimiters() -> None:
    result = user_block(prompt="hello world")

    assert "<user_text>" in result
    assert "hello world" in result
    assert "</user_text>" in result


def test_user_text_is_wrapped_in_delimiters() -> None:
    transcript = "USER: line one\nPERSONA: line two"

    result = user_block(recent_transcript=transcript)

    assert result == f"<user_text>\n{transcript}\n</user_text>"


def test_prompts_never_receive_native_language() -> None:
    learner_with_native_language = {**LEARNER, "native_language": "Tagalog"}

    rendered = render_prompt(
        "roleplay_system", **_roleplay_context(learner=learner_with_native_language)
    )

    assert "Tagalog" not in rendered.text


def test_render_voice_mode_includes_no_markdown_rule() -> None:
    voice = render_prompt("roleplay_system", **_roleplay_context(mode="voice"))
    text_mode = render_prompt("roleplay_system", **_roleplay_context(mode="text"))

    assert "no markdown" in voice.text.lower()
    assert "no markdown" not in text_mode.text.lower()


def test_missing_variable_raises() -> None:
    with pytest.raises(jinja2.UndefinedError):
        render_prompt("roleplay_system", persona=PERSONA)


def test_version_is_parsed_from_header() -> None:
    rendered = render_prompt("roleplay_system", **_roleplay_context())

    assert rendered.version == "roleplay-v1"


def test_hint_template_stays_under_30_words_instruction() -> None:
    rendered = render_prompt("hint", persona=PERSONA, scenario=SCENARIO, learner=LEARNER)

    assert "30 words" in rendered.text


def test_feedback_system_contains_all_rubric_anchors() -> None:
    rendered = render_prompt("feedback_system", learner=LEARNER, rubric=RUBRIC)

    for dimension in RUBRIC.dimensions:
        for anchor in dimension.anchors:
            assert anchor.text in rendered.text, f"missing anchor for {dimension.key}"


def test_feedback_system_requires_english_output() -> None:
    rendered = render_prompt("feedback_system", learner=LEARNER, rubric=RUBRIC)

    assert "English" in rendered.text


def test_feedback_system_instructs_exact_quotes_from_user_lines() -> None:
    rendered = render_prompt("feedback_system", learner=LEARNER, rubric=RUBRIC)

    assert "exactly" in rendered.text.lower()
    assert "USER:" in rendered.text


def test_feedback_user_contains_transcript_and_success_criteria() -> None:
    rendered = render_prompt(
        "feedback_user",
        scenario={
            "title": "Give code review feedback",
            "user_objective": "Explain two problems kindly.",
            "success_criteria": ["Names both problems", "Uses a kind tone"],
        },
        transcript_text="[0] PERSONA (Sam): Hi!\n[1] USER: Hi Sam, thanks for the PR.",
        speaking_summary=None,
        is_voice_session=False,
    )

    assert "Hi Sam, thanks for the PR." in rendered.text
    assert "Names both problems" in rendered.text
    assert "Uses a kind tone" in rendered.text


def test_feedback_user_voice_session_notes_transcription_errors() -> None:
    rendered = render_prompt(
        "feedback_user",
        scenario={
            "title": "Give code review feedback",
            "user_objective": "Explain two problems kindly.",
            "success_criteria": ["Names both problems"],
        },
        transcript_text="[0] PERSONA (Sam): Hi!\n[1] USER: Hi Sam, thanks for the PR.",
        speaking_summary=None,
        is_voice_session=True,
    )

    assert "transcribed from speech" in rendered.text
