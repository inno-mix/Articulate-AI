"""Scenario visibility: built-in (non-assessment) scenarios + the caller's own custom scenarios."""

from typing import Literal
from uuid import UUID

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.domain.enums import RecommendedMode, ScenarioCategory
from app.models.scenario import Scenario
from app.schemas.scenario import ScenarioDetail, ScenarioSummary

Owner = Literal["builtin", "mine", "all"]


def _is_visible(scenario: Scenario, user_id: UUID) -> bool:
    return not scenario.is_custom or scenario.owner_user_id == user_id


async def list_scenarios(
    db: AsyncSession,
    user_id: UUID,
    *,
    category: ScenarioCategory | None,
    difficulty: int | None,
    mode: RecommendedMode | None,
    owner: Owner = "all",
) -> list[ScenarioSummary]:
    conditions: list[ColumnElement[bool]] = [Scenario.is_assessment.is_(False)]
    if owner == "builtin":
        conditions.append(Scenario.is_custom.is_(False))
    elif owner == "mine":
        conditions.append(Scenario.is_custom.is_(True))
        conditions.append(Scenario.owner_user_id == user_id)
    else:
        conditions.append(or_(Scenario.is_custom.is_(False), Scenario.owner_user_id == user_id))
    if category is not None:
        conditions.append(Scenario.category == category)
    if difficulty is not None:
        conditions.append(Scenario.difficulty == difficulty)
    if mode is not None:
        conditions.append(Scenario.recommended_mode.in_([mode, RecommendedMode.EITHER]))

    rows = await db.scalars(
        select(Scenario).where(*conditions).order_by(Scenario.difficulty, Scenario.title)
    )
    return [ScenarioSummary.model_validate(row) for row in rows]


async def get_scenario_by_slug(db: AsyncSession, user_id: UUID, slug: str) -> ScenarioDetail:
    scenario = await db.scalar(select(Scenario).where(Scenario.slug == slug))
    if scenario is None or not _is_visible(scenario, user_id):
        raise NotFoundError()
    return ScenarioDetail.model_validate(scenario)


async def get_scenario_by_id(db: AsyncSession, user_id: UUID, scenario_id: UUID) -> Scenario:
    """ORM instance (not a response schema) — used by session creation."""
    scenario = await db.get(Scenario, scenario_id)
    if scenario is None or not _is_visible(scenario, user_id):
        raise NotFoundError()
    return scenario
