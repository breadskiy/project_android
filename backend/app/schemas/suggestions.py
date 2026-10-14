"""Suggestion ("часто покупают вместе") schemas.

The provider abstraction is visible in the API on purpose: clients can tell
whether a suggestion came from the statistical engine, from the curated
prior, or from personal history. Values ``llm``/``hybrid`` are kept for
backward compatibility and resolve to the statistical engine.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator

from app.schemas.common import ItemNameStr, ResponseModel, StrictModel


class SuggestionSource(StrEnum):
    SEED = "seed"
    STATISTICAL = "statistical"
    # Legacy: kept so old rows/payloads still validate; never produced now.
    LLM = "llm"
    PERSONAL = "personal"


class SuggestionProvider(StrEnum):
    STATISTICAL = "statistical"
    # Legacy: accepted for compatibility, resolve to statistical.
    LLM = "llm"
    HYBRID = "hybrid"


class FeedbackAction(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SHOWN = "shown"


class ItemSuggestion(ResponseModel):
    name: str = Field(description="Название предлагаемого товара", examples=["сыр"])
    score: float = Field(ge=0.0, le=1.0, description="Уверенность 0..1", examples=[0.72])
    source: SuggestionSource = Field(examples=[SuggestionSource.SEED])
    reason: str | None = Field(
        default=None,
        description="Человекочитаемое объяснение подсказки",
        examples=["Часто покупают вместе с хлебом"],
    )
    based_on: list[str] = Field(
        default_factory=list,
        description="Товары из корзины, на основе которых построена подсказка",
        examples=[["хлеб"]],
    )
    product_id: UUID | None = None
    category: str | None = None


class SuggestionsResponse(ResponseModel):
    items: list[ItemSuggestion]
    provider: SuggestionProvider
    model_version: str | None = None
    cached: bool = Field(default=False, description="Ответ отдан из кеша")
    enabled: bool = Field(default=True, description="false — подсказки отключены пользователем")
    took_ms: int = Field(ge=0, examples=[3])
    basket_size: int = Field(ge=0)


class SuggestionFeedbackRequest(StrictModel):
    suggested_name: ItemNameStr
    action: FeedbackAction
    list_id: UUID | None = None
    based_on: list[ItemNameStr] = Field(default_factory=list, max_length=50)
    provider: SuggestionProvider | None = None

    @field_validator("based_on")
    @classmethod
    def drop_blanks(cls, value: list[str]) -> list[str]:
        return [item for item in (v.strip() for v in value) if item]


class SuggestionFeedbackResponse(ResponseModel):
    ok: bool = True
    message: str = Field(default="Спасибо, подсказки станут точнее")


class PairRuleResponse(ResponseModel):
    antecedent: str
    consequent: str
    source: str
    weight: float
    support: int
    confidence: float | None = None
    lift: float | None = None
    reason: str | None = None
    accepted_count: int
    rejected_count: int
    refreshed_at: datetime


class RebuildStatsResponse(ResponseModel):
    ok: bool = True
    rules_written: int = Field(ge=0)
    baskets_analyzed: int = Field(ge=0)
    took_ms: int = Field(ge=0)


class SuggestionEngineStatus(ResponseModel):
    provider: SuggestionProvider
    globally_enabled: bool
    # Legacy compatibility fields: LLM removed, always False/None.
    llm_configured: bool = Field(
        description="Legacy, всегда false: внешняя языковая модель не используется",
    )
    llm_model: str | None = None
    seed_rules: int = Field(ge=0)
    statistical_rules: int = Field(ge=0)
    # Legacy: число ранее сохранённых строк source='llm' (новые не создаются).
    llm_rules: int = Field(ge=0)
    cached_baskets: int = Field(ge=0)
    catalog_products: int = Field(ge=0)


QueryItemName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
