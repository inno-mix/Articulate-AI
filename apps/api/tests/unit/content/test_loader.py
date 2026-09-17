from pathlib import Path

import pytest
from pydantic import ValidationError

from app.content.loader import ContentError, load_scenario_files, scenario_content_hash

REPO_SCENARIOS_DIR = Path(__file__).resolve().parents[3] / "content" / "scenarios"


def test_loads_all_repository_scenarios() -> None:
    files = load_scenario_files(REPO_SCENARIOS_DIR)

    assert len(files) == 17
    assert sum(1 for f in files if f.is_assessment) == 2
    slugs = {f.slug for f in files}
    assert slugs == {f.stem for f in REPO_SCENARIOS_DIR.glob("*.yaml")}


def test_rejects_unknown_key_with_file_name_in_error(tmp_path: Path) -> None:
    bad = tmp_path / "bogus.yaml"
    bad.write_text(
        "slug: bogus\ntitle: Bogus\ncategory: meetings\ndifficulty: 1\n"
        "summary: x\npersona: {name: A, role: B, personality: C, goals: D}\n"
        "user_objective: x\nopening_line: x\nsuccess_criteria: [x]\n"
        "recommended_mode: text\nunknown_field: surprise\n"
    )

    with pytest.raises(ContentError) as exc_info:
        load_scenario_files(tmp_path)

    assert "bogus.yaml" in str(exc_info.value)


def test_rejects_invalid_difficulty(tmp_path: Path) -> None:
    bad = tmp_path / "bad-difficulty.yaml"
    bad.write_text(
        "slug: bad-difficulty\ntitle: Bad\ncategory: meetings\ndifficulty: 9\n"
        "summary: x\npersona: {name: A, role: B, personality: C, goals: D}\n"
        "user_objective: x\nopening_line: x\nsuccess_criteria: [x]\n"
        "recommended_mode: text\n"
    )

    with pytest.raises(ContentError) as exc_info:
        load_scenario_files(tmp_path)

    assert "bad-difficulty.yaml" in str(exc_info.value)


def test_rejects_duplicate_slugs(tmp_path: Path) -> None:
    body = (
        "slug: dupe\ntitle: Dupe\ncategory: meetings\ndifficulty: 1\n"
        "summary: x\npersona: {name: A, role: B, personality: C, goals: D}\n"
        "user_objective: x\nopening_line: x\nsuccess_criteria: [x]\n"
        "recommended_mode: text\n"
    )
    (tmp_path / "one.yaml").write_text(body)
    (tmp_path / "two.yaml").write_text(body)

    with pytest.raises(ContentError, match="duplicate slug"):
        load_scenario_files(tmp_path)


def test_content_hash_is_stable_and_changes_with_content() -> None:
    files = load_scenario_files(REPO_SCENARIOS_DIR)
    first = next(f for f in files if f.slug == "standup-update")

    hash_a = scenario_content_hash(first)
    hash_b = scenario_content_hash(first)
    changed = first.model_copy(update={"title": first.title + " (changed)"})

    assert hash_a == hash_b
    assert scenario_content_hash(changed) != hash_a


def test_persona_rejects_unknown_key() -> None:
    from app.content.loader import ScenarioFile

    with pytest.raises(ValidationError):
        ScenarioFile.model_validate(
            {
                "slug": "x",
                "title": "X",
                "category": "meetings",
                "difficulty": 1,
                "summary": "x",
                "persona": {"name": "A", "role": "B", "personality": "C", "goals": "D", "extra": 1},
                "user_objective": "x",
                "opening_line": "x",
                "success_criteria": ["x"],
                "recommended_mode": "text",
            }
        )
