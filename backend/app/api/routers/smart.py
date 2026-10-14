"""Умные эндпоинты: разбор ввода, пополнение запасов."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies import CurrentUserDep
from app.core.smart_parse import parse_item_input
from app.schemas.smart import (
    ParsePreviewRequest,
    ParsePreviewResponse,
    ReplenishResponse,
)
from app.services import smart as smart_service

router = APIRouter(prefix="/smart", tags=["smart"])


@router.post(
    "/parse",
    response_model=ParsePreviewResponse,
    summary="Предпросмотр умного разбора",
    description=(
        "Показывает, как строка превратится в товар: `«2л молока»` → "
        "название «молока», количество 2, единица «л». Список не изменяется."
    ),
)
async def parse_preview(payload: ParsePreviewRequest) -> ParsePreviewResponse:
    parsed = parse_item_input(payload.text)
    return ParsePreviewResponse(name=parsed.name, quantity=parsed.quantity, unit=parsed.unit)


@router.get(
    "/replenish",
    response_model=ReplenishResponse,
    summary="Что скоро закончится",
    description=(
        "По истории отметок «куплено» вычисляет периодичность покупок и "
        "возвращает товары, которые пора докупить. Работает локально, без ИИ."
    ),
)
async def replenish(current_user: CurrentUserDep) -> ReplenishResponse:
    items = await smart_service.replenish_for_user(current_user.id)
    return ReplenishResponse(items=items)  # type: ignore[arg-type]
