"""Product catalog schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from app.schemas.common import PageMeta, ResponseModel


class ProductResponse(ResponseModel):
    id: UUID
    name: str = Field(examples=["молоко"])
    normalized_name: str | None = None
    category_id: UUID | None = None
    category_name: str | None = Field(default=None, examples=["Молочные продукты"])
    default_unit: str | None = Field(default=None, examples=["л"])
    popularity: int = Field(ge=0)


class ProductSearchResult(ProductResponse):
    similarity: float = Field(
        ge=0.0,
        le=1.0,
        description="Схожесть с поисковым запросом (триграммы)",
        examples=[0.83],
    )
    matched_alias: str | None = Field(
        default=None,
        description="Синоним, по которому найден товар",
        examples=["картоха"],
    )


class ProductPage(ResponseModel):
    items: list[ProductResponse]
    meta: PageMeta


class ProductSearchResponse(ResponseModel):
    items: list[ProductSearchResult]
    query: str
    normalized_query: str


class CategoryResponse(ResponseModel):
    id: UUID
    name: str
    parent_id: UUID | None = None
    product_count: int = Field(ge=0)


class CategoryListResponse(ResponseModel):
    items: list[CategoryResponse]
