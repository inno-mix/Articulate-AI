from uuid import UUID

from app.domain.enums import RecommendedMode, ScenarioCategory
from app.schemas.common import ResponseModel
from app.schemas.json_types import Persona


class ScenarioSummary(ResponseModel):
    id: UUID
    slug: str
    title: str
    category: ScenarioCategory
    difficulty: int
    summary: str
    recommended_mode: RecommendedMode
    is_custom: bool


class ScenarioDetail(ScenarioSummary):
    persona: Persona
    user_objective: str
    opening_line: str
    success_criteria: list[str]
