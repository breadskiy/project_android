"""Product catalog endpoints (autocomplete and browsing)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentUserDep, PaginationDep
from app.schemas.catalog import (
    CategoryListResponse,
    ProductPage,
    ProductSearchResponse,
)
from app.services import catalog as catalog_service

router = APIRouter(prefix="/products", tags=["catalog"])


@router.get(
    "/search",
    response_model=ProductSearchResponse,
    summary="Поиск товаров с учетом опечаток",
    description=(
        "Триграммный поиск по названиям и синонимам: «малоко» находит «молоко», "
        "«картоха» — «картофель». Используется для автодополнения при вводе."
    ),
)
async def search_products(
    current_user: CurrentUserDep,
    q: Annotated[str, Query(min_length=1, max_length=300, description="Поисковый запрос")],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> ProductSearchResponse:
    result = await catalog_service.search(q, limit=limit)
    return ProductSearchResponse(**result)


@router.get(
    "",
    response_model=ProductPage,
    summary="Каталог товаров",
)
async def list_products(
    current_user: CurrentUserDep,
    pagination: PaginationDep,
    category_id: Annotated[UUID | None, Query(description="Фильтр по категории")] = None,
) -> ProductPage:
    result = await catalog_service.list_products(
        limit=pagination.limit,
        offset=pagination.offset,
        category_id=str(category_id) if category_id else None,
    )
    return ProductPage(**result)


@router.get(
    "/categories",
    response_model=CategoryListResponse,
    summary="Категории товаров",
)
async def list_categories(current_user: CurrentUserDep) -> CategoryListResponse:
    items = await catalog_service.list_categories()
    return CategoryListResponse(items=items)  # type: ignore[arg-type]
