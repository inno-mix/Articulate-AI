"""Feedback report generation (ai-layer.md §4.2, §7; overview.md §4.2).

Prompt building only in Task 2.1; report generation is added in Task 2.3.
"""

from app.content.rubrics import Rubric
from app.llm.prompts import RenderedPrompt, render_prompt
from app.models import Profile, Scenario


def _scenario_context(scenario: Scenario) -> dict[str, object]:
    return {
        "title": scenario.title,
        "user_objective": scenario.user_objective,
        "success_criteria": scenario.success_criteria,
    }


def _learner_context(profile: Profile) -> dict[str, str]:
    return {
        "seniority": profile.seniority.value,
        "english_level": profile.english_level.value,
    }


def build_feedback_prompts(
    *,
    scenario: Scenario,
    profile: Profile,
    rubric: Rubric,
    transcript_text: str,
    speaking_summary: str | None,
) -> tuple[RenderedPrompt, RenderedPrompt]:
    system = render_prompt("feedback_system", learner=_learner_context(profile), rubric=rubric)
    user = render_prompt(
        "feedback_user",
        scenario=_scenario_context(scenario),
        transcript_text=transcript_text,
        speaking_summary=speaking_summary,
    )
    return system, user
