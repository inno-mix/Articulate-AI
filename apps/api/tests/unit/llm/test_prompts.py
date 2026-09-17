import jinja2
import pytest

from app.llm.prompts import render_prompt, system_template_names, user_block

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
