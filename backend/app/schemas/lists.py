"""Shopping list and item schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator, model_validator

from app.schemas.common import (
    ItemNameStr,
    ListNameStr,
    NotesStr,
    PageMeta,
    ResponseModel,
    StrictModel,
    UnitStr,
)


class ListRole(StrEnum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class ListSortField(StrEnum):
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    NAME = "name"


class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


class ItemFilter(StrEnum):
    ALL = "all"
    PENDING = "pending"
    CHECKED = "checked"


QuantityField = Annotated[Decimal, Field(gt=0, le=100000, decimal_places=3)]


# --------------------------------------------------------------- requests


class CreateListRequest(StrictModel):
    name: ListNameStr = Field(examples=["Продукты на неделю"])
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None
    items: list[str] = Field(
        default_factory=list,
        max_length=500,
        examples=[["хлеб", "молоко", "картофель"]],
        description="Пустые строки и дубликаты отбрасываются автоматически",
    )

    @field_validator("items")
    @classmethod
    def clean_items(cls, value: list[str]) -> list[str]:
        # Blanks and duplicates are dropped rather than rejected: pasting a
        # comma-separated list routinely produces both.
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in value:
            item = item.strip()
            if not item:
                continue
            if len(item) > 300:
                raise ValueError("Название товара не может быть длиннее 300 символов")
            key = item.casefold()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(item)
        return cleaned

    @field_validator("description")
    @classmethod
    def reject_system_description(cls, value: str | None) -> str | None:
        # 'system_favorite' marks the protected list; it must not be forgeable.
        if value and value.strip().startswith("system_"):
            raise ValueError("Описание не может начинаться с 'system_'")
        return value


class UpdateListRequest(StrictModel):
    name: ListNameStr | None = None
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UpdateListRequest":
        if self.name is None and self.description is None:
            raise ValueError("Укажите хотя бы одно поле для изменения")
        return self

    @field_validator("description")
    @classmethod
    def reject_system_description(cls, value: str | None) -> str | None:
        if value and value.strip().startswith("system_"):
            raise ValueError("Описание не может начинаться с 'system_'")
        return value


class CreateItemRequest(StrictModel):
    name: ItemNameStr = Field(examples=["молоко 3.2%"])
    quantity: QuantityField = Field(default=Decimal(1), examples=[2])
    unit: UnitStr | None = Field(default=None, examples=["л"])
    notes: NotesStr | None = Field(default=None, examples=["любой производитель"])
    priority: int = Field(default=1, ge=0, le=3, examples=[1])
    product_id: UUID | None = Field(
        default=None,
        description="Товар каталога, если клиент выбрал подсказку автодополнения",
    )


class BulkCreateItemsRequest(StrictModel):
    items: list[CreateItemRequest] = Field(min_length=1, max_length=200)


class UpdateItemRequest(StrictModel):
    name: ItemNameStr | None = None
    quantity: QuantityField | None = None
    unit: UnitStr | None = None
    notes: NotesStr | None = None
    priority: int | None = Field(default=None, ge=0, le=3)
    checked: bool | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UpdateItemRequest":
        if all(
            getattr(self, field) is None
            for field in ("name", "quantity", "unit", "notes", "priority", "checked")
        ):
            raise ValueError("Укажите хотя бы одно поле для изменения")
        return self


class ToggleItemsRequest(StrictModel):
    item_ids: list[UUID] = Field(min_length=1, max_length=500)
    checked: bool

    @field_validator("item_ids")
    @classmethod
    def unique_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("ID товаров не должны повторяться")
        return value


class CopyItemsRequest(StrictModel):
    item_ids: list[UUID] = Field(min_length=1, max_length=500)
    target_list_ids: list[UUID] = Field(min_length=1, max_length=50)

    @field_validator("item_ids", "target_list_ids")
    @classmethod
    def unique_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("ID не должны повторяться")
        return value


class ReorderItemsRequest(StrictModel):
    item_ids: list[UUID] = Field(
        min_length=1,
        max_length=1000,
        description="Полный или частичный порядок товаров; перечисленные идут первыми",
    )

    @field_validator("item_ids")
    @classmethod
    def unique_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("ID товаров не должны повторяться")
        return value


# -------------------------------------------------------------- responses


class ItemResponse(ResponseModel):
    id: UUID
    list_id: UUID
    name: str
    normalized_name: str | None = None
    quantity: Decimal
    unit: str | None = None
    notes: str | None = None
    priority: int
    checked: bool
    checked_at: datetime | None = None
    checked_by: UUID | None = None
    checked_by_name: str | None = None
    added_by: UUID | None = None
    added_by_name: str | None = None
    product_id: UUID | None = None
    sort_order: int
    added_at: datetime
    updated_at: datetime


class MemberResponse(ResponseModel):
    user_id: UUID
    display_name: str
    email: str | None = Field(
        default=None,
        description="Показывается только владельцу списка",
    )
    role: ListRole
    joined_at: datetime
    is_you: bool = False


class ListSummary(ResponseModel):
    id: UUID
    name: str
    description: str | None = None
    owner_id: UUID
    owner_name: str | None = None
    role: ListRole = Field(description="Ваша роль в этом списке")
    is_owner: bool
    is_shared: bool
    is_system: bool = Field(description="Системный список «⭐ Избранное»")
    item_count: int = Field(ge=0)
    checked_count: int = Field(ge=0)
    member_count: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime


class ListDetail(ListSummary):
    items: list[ItemResponse] = Field(default_factory=list)
    members: list[MemberResponse] = Field(default_factory=list)


class ListPage(ResponseModel):
    items: list[ListSummary]
    meta: PageMeta


class ItemPage(ResponseModel):
    items: list[ItemResponse]
    meta: PageMeta


class ItemCreatedResponse(ResponseModel):
    ok: bool = True
    item: ItemResponse
    suggestions: list["ItemSuggestion"] = Field(
        default_factory=list,
        description="Подсказки «часто покупают вместе»; пусто, если ИИ отключён",
    )


class BulkItemsResponse(ResponseModel):
    ok: bool = True
    created: int = Field(ge=0)
    items: list[ItemResponse]
    suggestions: list["ItemSuggestion"] = Field(default_factory=list)


class CopyItemsResponse(ResponseModel):
    ok: bool = True
    copied_items: int = Field(ge=0)
    target_lists: int = Field(ge=0)
    skipped_duplicates: int = Field(ge=0)


class ToggleItemsResponse(ResponseModel):
    ok: bool = True
    updated: int = Field(ge=0)
    checked: bool


class ClearItemsResponse(ResponseModel):
    ok: bool = True
    deleted: int = Field(ge=0)


class DeleteListResponse(ResponseModel):
    ok: bool = True
    message: str
    left_shared_list: bool = Field(
        default=False,
        description="true — вы покинули общий список, сам список не удалён",
    )


from app.schemas.suggestions import ItemSuggestion  # noqa: E402  (circular by design)

ItemCreatedResponse.model_rebuild()
BulkItemsResponse.model_rebuild()
