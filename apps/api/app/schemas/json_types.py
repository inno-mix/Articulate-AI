"""Pydantic models for JSONB columns (data-model.md)."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class Persona(BaseModel):
    """The AI character in a practice scenario (`scenarios.persona`)."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(max_length=40)]
    role: Annotated[str, Field(max_length=80)]
    personality: Annotated[str, Field(max_length=200)]
    goals: Annotated[str, Field(max_length=200)]
