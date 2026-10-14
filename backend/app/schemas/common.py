"""Shared schema primitives: base models, pagination, common responses."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

T = TypeVar("T")

# Reusable constrained string types.
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ItemNameStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
ListNameStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
DisplayNameStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
UnitStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]
NotesStr = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class StrictModel(BaseModel):
    """Request models: unknown fields are rejected instead of ignored."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class ResponseModel(BaseModel):
    """Response models: serialized from dicts coming out of the repositories."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class MessageResponse(ResponseModel):
    ok: bool = True
    message: str = Field(examples=["Операция выполнена"])


class ErrorDetail(ResponseModel):
    code: str = Field(examples=["list_not_found"])
    message: str = Field(examples=["Список не найден или недоступен"])
    details: dict[str, Any] | None = None


class ErrorResponse(ResponseModel):
    """The single error envelope used by every failing endpoint."""

    error: ErrorDetail


class PageMeta(ResponseModel):
    total: int = Field(ge=0, examples=[42])
    limit: int = Field(ge=1, examples=[50])
    offset: int = Field(ge=0, examples=[0])
    has_more: bool = Field(examples=[False])


class Page(ResponseModel, Generic[T]):
    items: list[T]
    meta: PageMeta


class PaginationParams(StrictModel):
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class HealthResponse(ResponseModel):
    status: str = Field(examples=["ok"])
    database: str = Field(examples=["ok"])
    version: str = Field(examples=["3.0.0"])
    environment: str = Field(examples=["development"])
    ai_suggestions: bool = Field(examples=[True])
    llm_configured: bool = Field(examples=[False])
    time: datetime


class ReadinessResponse(ResponseModel):
    status: str = Field(examples=["ready"])
    pool: dict[str, Any] = Field(
        default_factory=dict,
        description="Статистика пула соединений с БД",
    )
