"""Схемы умных эндпоинтов: разбор ввода, пополнение."""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from app.schemas.common import ItemNameStr, ResponseModel, StrictModel


class ParsePreviewRequest(StrictModel):
    text: ItemNameStr = Field(examples=["2л молока"])


class ParsePreviewResponse(ResponseModel):
    name: str = Field(examples=["молока"])
    quantity: Decimal = Field(examples=[2])
    unit: str | None = Field(default=None, examples=["л"])


class ReplenishItem(ResponseModel):
    name: str = Field(description="Название товара из каталога или как покупали")
    normalized_name: str
    purchases: int = Field(ge=3, description="Сколько покупок легло в основу прогноза")
    avg_interval_days: float = Field(ge=1.0, description="Медианный интервал между покупками")
    days_since_last: float = Field(ge=0.0, description="Дней с последней покупки")


class ReplenishResponse(ResponseModel):
    items: list[ReplenishItem] = Field(description="Что пора докупить, сначала срочное")
