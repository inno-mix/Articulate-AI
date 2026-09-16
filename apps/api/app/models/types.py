"""Shared column types."""

from enum import StrEnum

from sqlalchemy import Enum


def text_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    """Enum stored as TEXT with a CHECK constraint (data-model.md conventions)."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda members: [m.value for m in members],
    )
