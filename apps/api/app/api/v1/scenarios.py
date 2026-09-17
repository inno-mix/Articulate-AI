from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.deps import CurrentUser, DbDep
from app.domain.enums import RecommendedMode, ScenarioCategory
from app.schemas.scenario import ScenarioDetail, ScenarioSummary
from app.services import scenarios as scenarios_service

router = APIRouter(tags=["scenarios"])


@router.get("/scenarios")
async def list_scenarios(
    user: CurrentUser,
    db: DbDep,
    category: ScenarioCategory | None = None,
    difficulty: Annotated[int | None, Query(ge=1, le=3)] = None,
    mode: RecommendedMode | None = None,
    owner: Literal["builtin", "mine", "all"] = "all",
) -> list[ScenarioSummary]:
    return await scenarios_service.list_scenarios(
        db, user.id, category=category, difficulty=difficulty, mode=mode, owner=owner
    )


@router.get("/scenarios/{slug}")
async def get_scenario(slug: str, user: CurrentUser, db: DbDep) -> ScenarioDetail:
    return await scenarios_service.get_scenario_by_slug(db, user.id, slug)
