from pydantic import BaseModel, ConfigDict


class RequestModel(BaseModel):
    """Base for request bodies: unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    """A cursor page (api-contract.md §1)."""

    items: list[T]
    next_cursor: str | None
