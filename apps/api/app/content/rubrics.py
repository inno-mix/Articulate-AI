"""Versioned feedback rubric (ai-layer.md §6), loaded from YAML and cached."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

from app.content.loader import ContentError
from app.llm.outputs import LLMDimension

RUBRICS_DIR = Path(__file__).resolve().parent.parent.parent / "content" / "rubrics"


class RubricAnchor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: Literal[1, 3, 5]
    text: str


class RubricDimension(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: LLMDimension
    label: str
    description: str
    anchors: list[RubricAnchor]


class Rubric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    dimensions: list[RubricDimension]


@lru_cache
def get_rubric(version: str) -> Rubric:
    """Load and validate `content/rubrics/<version>.yaml`. Raises `ContentError` if unknown."""
    path = RUBRICS_DIR / f"{version}.yaml"
    if not path.exists():
        raise ContentError(path, f"unknown rubric version {version!r}")
    raw = yaml.safe_load(path.read_text())
    try:
        return Rubric.model_validate(raw)
    except Exception as exc:
        raise ContentError(path, str(exc)) from exc
