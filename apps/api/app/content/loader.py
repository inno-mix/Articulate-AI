"""Loads and validates scenario content YAML (`content/scenarios/*.yaml`, coding-conventions §5)."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import RecommendedMode, ScenarioCategory
from app.models.scenario import Scenario
from app.schemas.json_types import Persona


class ContentError(Exception):
    """A content file failed validation. `str(error)` names the file."""

    def __init__(self, path: Path, message: str) -> None:
        self.path = path
        self.message = message
        super().__init__(f"{path.name}: {message}")


class ScenarioFile(BaseModel):
    """One `content/scenarios/<slug>.yaml` file (data-model.md `scenarios`)."""

    model_config = ConfigDict(extra="forbid")

    slug: Annotated[str, Field(pattern=r"^[a-z0-9-]{3,60}$")]
    title: Annotated[str, Field(max_length=80)]
    category: ScenarioCategory
    difficulty: Annotated[int, Field(ge=1, le=3)]
    summary: Annotated[str, Field(max_length=300)]
    persona: Persona
    user_objective: Annotated[str, Field(max_length=300)]
    opening_line: Annotated[str, Field(max_length=400)]
    success_criteria: Annotated[list[str], Field(min_length=1, max_length=5)]
    recommended_mode: RecommendedMode
    rubric_version: str = "v1"
    is_assessment: bool = False
    keyterms: Annotated[list[str], Field(max_length=20)] = []


@dataclass(frozen=True)
class UpsertReport:
    created: int
    updated: int
    unchanged: int


def load_scenario_files(directory: Path) -> list[ScenarioFile]:
    """Load and validate every `*.yaml` file in `directory`.

    Raises `ContentError` on any problem.
    """
    files: list[ScenarioFile] = []
    seen_slugs: dict[str, Path] = {}
    for path in sorted(directory.glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            raise ContentError(path, f"invalid YAML: {exc}") from exc
        try:
            scenario = ScenarioFile.model_validate(raw)
        except Exception as exc:  # pydantic ValidationError, wrapped with the file name
            raise ContentError(path, str(exc)) from exc
        if scenario.slug in seen_slugs:
            raise ContentError(
                path, f"duplicate slug {scenario.slug!r} (also in {seen_slugs[scenario.slug].name})"
            )
        seen_slugs[scenario.slug] = path
        files.append(scenario)
    return files


def scenario_content_hash(scenario: ScenarioFile) -> str:
    """sha256 of the scenario's canonical JSON (data-model.md `scenarios.content_hash`)."""
    canonical = json.dumps(scenario.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


async def upsert_scenarios(db: AsyncSession, files: list[ScenarioFile]) -> UpsertReport:
    """Insert new built-in scenarios, update changed ones (by `content_hash`), skip the rest."""
    created = updated = unchanged = 0
    for file in files:
        content_hash = scenario_content_hash(file)
        existing = await db.scalar(select(Scenario).where(Scenario.slug == file.slug))
        if existing is None:
            db.add(
                Scenario(
                    slug=file.slug,
                    title=file.title,
                    category=file.category,
                    difficulty=file.difficulty,
                    summary=file.summary,
                    persona=file.persona.model_dump(mode="json"),
                    user_objective=file.user_objective,
                    opening_line=file.opening_line,
                    success_criteria=file.success_criteria,
                    recommended_mode=file.recommended_mode,
                    keyterms=file.keyterms,
                    rubric_version=file.rubric_version,
                    is_assessment=file.is_assessment,
                    content_hash=content_hash,
                )
            )
            created += 1
        elif existing.content_hash != content_hash:
            existing.title = file.title
            existing.category = file.category
            existing.difficulty = file.difficulty
            existing.summary = file.summary
            existing.persona = file.persona.model_dump(mode="json")
            existing.user_objective = file.user_objective
            existing.opening_line = file.opening_line
            existing.success_criteria = file.success_criteria
            existing.recommended_mode = file.recommended_mode
            existing.keyterms = file.keyterms
            existing.rubric_version = file.rubric_version
            existing.is_assessment = file.is_assessment
            existing.content_hash = content_hash
            updated += 1
        else:
            unchanged += 1
    await db.flush()
    return UpsertReport(created=created, updated=updated, unchanged=unchanged)
