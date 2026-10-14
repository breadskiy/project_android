"""Suggestion endpoints — the "часто покупают вместе" feature."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentUserDep
from app.schemas.common import ErrorResponse
from app.schemas.suggestions import (
    SuggestionEngineStatus,
    SuggestionFeedbackRequest,
    SuggestionFeedbackResponse,
    SuggestionsResponse,
)
from app.services import suggestions as suggestions_service

router = APIRouter(tags=["suggestions"])

LIMIT_QUERY = Annotated[int | None, Query(ge=1, le=20, description="Сколько подсказок вернуть")]


@router.get(
    "/suggestions",
    response_model=SuggestionsResponse,
    summary="Подсказки по одному или нескольким товарам",
    description=(
        "Например `?item=хлеб` вернет «масло», «сыр», «колбаса». "
        "Параметр можно повторять: `?item=хлеб&item=картофель`.\n\n"
        "Если подсказки отключены в настройках профиля, ответ содержит "
        "`enabled=false` и пустой список."
    ),
)
async def suggestions_for_items(
    current_user: CurrentUserDep,
    item: Annotated[
        list[str],
        Query(min_length=1, max_length=300, description="Название товара (можно несколько)"),
    ],
    limit: LIMIT_QUERY = None,
) -> SuggestionsResponse:
    result = await suggestions_service.suggest_for_items(
        user_id=current_user.id,
        items=item[:50],
        limit=limit,
    )
    return SuggestionsResponse(**result)


@router.get(
    "/lists/{list_id}/suggestions",
    response_model=SuggestionsResponse,
    summary="Подсказки по всему списку",
    description=(
        "Анализирует корзину целиком и предлагает то, что обычно покупают "
        "вместе с её содержимым. Уже добавленные товары не предлагаются."
    ),
    responses={404: {"model": ErrorResponse, "description": "Список не найден или недоступен"}},
)
async def suggestions_for_list(
    list_id: UUID,
    current_user: CurrentUserDep,
    limit: LIMIT_QUERY = None,
    include_checked: Annotated[
        bool, Query(description="Учитывать купленные товары в анализе")
    ] = False,
) -> SuggestionsResponse:
    result = await suggestions_service.suggest_for_list(
        user_id=current_user.id,
        list_id=str(list_id),
        limit=limit,
        only_pending=not include_checked,
    )
    return SuggestionsResponse(**result)


@router.post(
    "/suggestions/feedback",
    response_model=SuggestionFeedbackResponse,
    summary="Обратная связь по подсказке",
    description=(
        "Сообщает, принял пользователь подсказку или отклонил. "
        "Это влияет на ранжирование: отклоняемые подсказки опускаются, "
        "принимаемые поднимаются."
    ),
)
async def suggestion_feedback(
    payload: SuggestionFeedbackRequest, current_user: CurrentUserDep
) -> SuggestionFeedbackResponse:
    await suggestions_service.record_feedback(
        user_id=current_user.id,
        suggested_name=payload.suggested_name,
        action=payload.action.value,
        list_id=str(payload.list_id) if payload.list_id else None,
        based_on=payload.based_on,
        provider=payload.provider.value if payload.provider else None,
    )
    return SuggestionFeedbackResponse()


@router.get(
    "/suggestions/status",
    response_model=SuggestionEngineStatus,
    summary="Состояние движка подсказок",
    description=(
        "Показывает активный провайдер и объем базы правил. "
        "Поля llm_* оставлены для совместимости и всегда пустые."
    ),
)
async def engine_status(current_user: CurrentUserDep) -> SuggestionEngineStatus:
    status_payload = await suggestions_service.get_engine_status()
    return SuggestionEngineStatus(**status_payload)
