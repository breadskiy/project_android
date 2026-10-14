"""Shopping list item endpoints, including live suggestions on add."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.dependencies import CurrentUserDep, PaginationDep
from app.schemas.common import ErrorResponse, MessageResponse
from app.schemas.lists import (
    BulkCreateItemsRequest,
    BulkItemsResponse,
    ClearItemsResponse,
    CopyItemsRequest,
    CopyItemsResponse,
    CreateItemRequest,
    ItemCreatedResponse,
    ItemFilter,
    ItemPage,
    ItemResponse,
    ReorderItemsRequest,
    ToggleItemsRequest,
    ToggleItemsResponse,
    UpdateItemRequest,
)
from app.services import lists as lists_service
from app.services import suggestions as suggestions_service

router = APIRouter(prefix="/lists/{list_id}/items", tags=["items"])

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Список или товар не найден"}}
FORBIDDEN = {403: {"model": ErrorResponse, "description": "Нужны права редактора"}}


@router.get(
    "",
    response_model=ItemPage,
    summary="Товары списка",
    responses={**NOT_FOUND},
)
async def get_items(
    list_id: UUID,
    current_user: CurrentUserDep,
    pagination: PaginationDep,
    filter: Annotated[ItemFilter, Query(description="all / pending / checked")] = ItemFilter.ALL,
) -> ItemPage:
    result = await lists_service.get_items(
        str(list_id),
        current_user.id,
        limit=pagination.limit,
        offset=pagination.offset,
        item_filter=filter.value,
    )
    return ItemPage(**result)


@router.post(
    "",
    response_model=ItemCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить товар (с подсказками «часто покупают вместе»)",
    description=(
        "Добавляет товар и сразу возвращает подсказки «часто покупают вместе» "
        "для блока саджеста. Отдельно вписывать что-то для подсказок не нужно. "
        "Подсказки можно отключить параметром `suggest=false` или в настройках "
        "профиля (`ai_suggestions_enabled`)."
    ),
    responses={**NOT_FOUND, **FORBIDDEN, 409: {"model": ErrorResponse, "description": "Лимит товаров"}},
)
async def add_item(
    list_id: UUID,
    payload: CreateItemRequest,
    current_user: CurrentUserDep,
    suggest: Annotated[bool, Query(description="Возвращать подсказки «часто покупают вместе»")] = True,
) -> ItemCreatedResponse:
    item = await lists_service.add_item(
        str(list_id),
        current_user.id,
        name=payload.name,
        quantity=payload.quantity,
        unit=payload.unit,
        notes=payload.notes,
        priority=payload.priority,
        product_id=str(payload.product_id) if payload.product_id else None,
    )

    suggestions: list[dict] = []
    if suggest:
        # Suggestions are advisory: a failure here must not fail the write that
        # already succeeded.
        result = await suggestions_service.suggest_for_list(
            user_id=current_user.id, list_id=str(list_id)
        )
        suggestions = result["items"]

    return ItemCreatedResponse(item=ItemResponse(**item), suggestions=suggestions)  # type: ignore[arg-type]


@router.post(
    "/bulk",
    response_model=BulkItemsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить несколько товаров за один запрос",
    responses={**NOT_FOUND, **FORBIDDEN, 409: {"model": ErrorResponse, "description": "Лимит товаров"}},
)
async def add_items_bulk(
    list_id: UUID,
    payload: BulkCreateItemsRequest,
    current_user: CurrentUserDep,
    suggest: Annotated[bool, Query(description="Возвращать подсказки «часто покупают вместе»")] = True,
) -> BulkItemsResponse:
    items = await lists_service.add_items_bulk(
        str(list_id),
        current_user.id,
        items=[
            {
                "name": item.name,
                "quantity": item.quantity,
                "unit": item.unit,
                "notes": item.notes,
                "priority": item.priority,
                "product_id": str(item.product_id) if item.product_id else None,
            }
            for item in payload.items
        ],
    )

    suggestions: list[dict] = []
    if suggest:
        result = await suggestions_service.suggest_for_list(
            user_id=current_user.id, list_id=str(list_id)
        )
        suggestions = result["items"]

    return BulkItemsResponse(
        created=len(items),
        items=[ItemResponse(**item) for item in items],  # type: ignore[arg-type]
        suggestions=suggestions,  # type: ignore[arg-type]
    )


@router.patch(
    "/{item_id}",
    response_model=ItemResponse,
    summary="Изменить товар (название, количество, отметка «куплено»)",
    responses={**NOT_FOUND, **FORBIDDEN},
)
async def update_item(
    list_id: UUID,
    item_id: UUID,
    payload: UpdateItemRequest,
    current_user: CurrentUserDep,
) -> ItemResponse:
    updated = await lists_service.update_item(
        str(list_id),
        str(item_id),
        current_user.id,
        name=payload.name,
        quantity=payload.quantity,
        unit=payload.unit,
        notes=payload.notes,
        priority=payload.priority,
        checked=payload.checked,
    )
    return ItemResponse(**updated)


@router.post(
    "/toggle",
    response_model=ToggleItemsResponse,
    summary="Отметить несколько товаров купленными или снять отметку",
    responses={**NOT_FOUND, **FORBIDDEN},
)
async def toggle_items(
    list_id: UUID, payload: ToggleItemsRequest, current_user: CurrentUserDep
) -> ToggleItemsResponse:
    result = await lists_service.toggle_items(
        str(list_id),
        current_user.id,
        item_ids=[str(item_id) for item_id in payload.item_ids],
        checked=payload.checked,
    )
    return ToggleItemsResponse(**result)


@router.post(
    "/reorder",
    response_model=MessageResponse,
    summary="Изменить порядок товаров",
    responses={**NOT_FOUND, **FORBIDDEN},
)
async def reorder_items(
    list_id: UUID, payload: ReorderItemsRequest, current_user: CurrentUserDep
) -> MessageResponse:
    result = await lists_service.reorder_items(
        str(list_id), current_user.id, item_ids=[str(i) for i in payload.item_ids]
    )
    return MessageResponse(message=f"Порядок обновлен для {result['updated']} товаров")


@router.post(
    "/copy",
    response_model=CopyItemsResponse,
    summary="Копировать товары в другие списки",
    description=(
        "Права на запись проверяются для всех целевых списков до начала записи, "
        "операция выполняется одной транзакцией. Дубликаты пропускаются."
    ),
    responses={**NOT_FOUND, **FORBIDDEN},
)
async def copy_items(
    list_id: UUID, payload: CopyItemsRequest, current_user: CurrentUserDep
) -> CopyItemsResponse:
    result = await lists_service.copy_items(
        str(list_id),
        current_user.id,
        item_ids=[str(i) for i in payload.item_ids],
        target_list_ids=[str(i) for i in payload.target_list_ids],
    )
    return CopyItemsResponse(**result)


@router.delete(
    "/{item_id}",
    response_model=MessageResponse,
    summary="Удалить товар",
    responses={**NOT_FOUND, **FORBIDDEN},
)
async def delete_item(
    list_id: UUID, item_id: UUID, current_user: CurrentUserDep
) -> MessageResponse:
    await lists_service.delete_item(str(list_id), str(item_id), current_user.id)
    return MessageResponse(message="Товар удален")


@router.delete(
    "",
    response_model=ClearItemsResponse,
    summary="Очистить список",
    description="`checked_only=true` удаляет только купленные товары.",
    responses={**NOT_FOUND, **FORBIDDEN},
)
async def clear_items(
    list_id: UUID,
    current_user: CurrentUserDep,
    checked_only: Annotated[bool, Query(description="Удалить только купленные")] = False,
) -> ClearItemsResponse:
    result = await lists_service.clear_items(
        str(list_id), current_user.id, only_checked=checked_only
    )
    return ClearItemsResponse(**result)
