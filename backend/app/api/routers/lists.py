"""Shopping list endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.dependencies import CurrentUserDep, PaginationDep
from app.schemas.common import ErrorResponse
from app.schemas.lists import (
    CreateListRequest,
    DeleteListResponse,
    ItemFilter,
    ListDetail,
    ListPage,
    ListSortField,
    ListSummary,
    SortDirection,
    UpdateListRequest,
)
from app.services import lists as lists_service

router = APIRouter(prefix="/lists", tags=["lists"])

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Список не найден или недоступен"}}
FORBIDDEN = {403: {"model": ErrorResponse, "description": "Недостаточно прав"}}


@router.get(
    "",
    response_model=ListPage,
    summary="Мои списки покупок",
    description=(
        "Возвращает списки, где вы владелец или участник. "
        "Системный список «⭐ Избранное» создается автоматически и идет первым."
    ),
)
async def get_lists(
    current_user: CurrentUserDep,
    pagination: PaginationDep,
    sort: Annotated[ListSortField, Query(description="Поле сортировки")] = ListSortField.CREATED_AT,
    direction: Annotated[SortDirection, Query(description="Направление")] = SortDirection.DESC,
    q: Annotated[str | None, Query(max_length=200, description="Поиск по названию")] = None,
    owned: Annotated[
        bool | None,
        Query(description="true — только мои, false — только общие от других"),
    ] = None,
) -> ListPage:
    result = await lists_service.get_lists(
        current_user.id,
        limit=pagination.limit,
        offset=pagination.offset,
        sort=sort.value,
        direction=direction.value,
        query=q,
        only_owned=owned,
    )
    return ListPage(**result)


@router.post(
    "",
    response_model=ListSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Создать список покупок",
    responses={409: {"model": ErrorResponse, "description": "Превышен лимит списков"}},
)
async def create_list(payload: CreateListRequest, current_user: CurrentUserDep) -> ListSummary:
    created = await lists_service.create_list(
        current_user.id,
        name=payload.name,
        description=payload.description,
        items=payload.items,
    )
    return ListSummary(**created)


@router.get(
    "/favorites",
    response_model=ListDetail,
    summary="Системный список «⭐ Избранное»",
    description="Создает список при первом обращении и возвращает его содержимое.",
)
async def get_favorites(current_user: CurrentUserDep) -> ListDetail:
    list_id = await lists_service.get_favorites_id(current_user.id)
    detail = await lists_service.get_list(list_id, current_user.id)
    return ListDetail(**detail)


@router.get(
    "/{list_id}",
    response_model=ListDetail,
    summary="Список с товарами и участниками",
    responses={**NOT_FOUND},
)
async def get_list(
    list_id: UUID,
    current_user: CurrentUserDep,
    items: Annotated[ItemFilter, Query(description="Фильтр товаров")] = ItemFilter.ALL,
) -> ListDetail:
    detail = await lists_service.get_list(
        str(list_id), current_user.id, item_filter=items.value
    )
    return ListDetail(**detail)


@router.patch(
    "/{list_id}",
    response_model=ListSummary,
    summary="Переименовать список или изменить описание",
    description="Требуются права редактора. Системный список переименовать нельзя.",
    responses={**NOT_FOUND, **FORBIDDEN, 409: {"model": ErrorResponse, "description": "Системный список"}},
)
async def update_list(
    list_id: UUID, payload: UpdateListRequest, current_user: CurrentUserDep
) -> ListSummary:
    updated = await lists_service.update_list(
        str(list_id),
        current_user.id,
        name=payload.name,
        description=payload.description,
    )
    return ListSummary(**updated)


@router.delete(
    "/{list_id}",
    response_model=DeleteListResponse,
    summary="Удалить список или покинуть общий",
    description=(
        "Владелец удаляет список полностью. Участник — покидает его, "
        "список остается у остальных."
    ),
    responses={**NOT_FOUND, 409: {"model": ErrorResponse, "description": "Системный список"}},
)
async def delete_list(list_id: UUID, current_user: CurrentUserDep) -> DeleteListResponse:
    result = await lists_service.delete_list(str(list_id), current_user.id)
    return DeleteListResponse(**result)
