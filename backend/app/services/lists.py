"""Shopping list and item business rules.

Authorization model
-------------------
``owner``   full control, including delete, sharing and member management
``editor``  read and write items, rename the list
``viewer``  read only

The protected system list ("⭐ Избранное") cannot be renamed, deleted or
shared, matching the original CLI behaviour.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from app.config import settings
from app.core.errors import (
    ItemNotFoundError,
    LimitExceededError,
    ListNotFoundError,
    PermissionDeniedError,
    SystemListError,
    ValidationError,
)
from app.core.normalization import clean_display_name, normalize_item_name
from app.core.smart_parse import apply_parsed, parse_item_input
from app.db.pool import Row, run_in_thread
from app.repositories import catalog as catalog_repo
from app.repositories import invites as invites_repo
from app.repositories import lists as lists_repo
from app.repositories import suggestions as suggestions_repo

ROLE_RANK = {"viewer": 0, "editor": 1, "owner": 2}


# ------------------------------------------------------------ authorization


def _require_membership(list_id: str, user_id: str, *, min_role: str = "viewer") -> Row:
    membership = lists_repo.get_membership(list_id, user_id)
    if membership is None:
        # 404 rather than 403: an outsider must not learn that the list exists.
        raise ListNotFoundError()

    if ROLE_RANK[membership["role"]] < ROLE_RANK[min_role]:
        raise PermissionDeniedError(
            {
                "editor": "Для этого действия нужны права редактора",
                "owner": "Только владелец может выполнять эту операцию",
            }.get(min_role, "Недостаточно прав")
        )
    return membership


def _reject_system_list(membership: Row, action: str) -> None:
    if membership.get("is_system"):
        raise SystemListError(f"Системный список «⭐ Избранное» нельзя {action}")


# -------------------------------------------------------------------- lists


def _get_lists_sync(
    user_id: str,
    *,
    limit: int,
    offset: int,
    sort: str,
    direction: str,
    query: str | None,
    only_owned: bool | None,
) -> dict[str, Any]:
    lists_repo.ensure_favorites(user_id)
    rows, total = lists_repo.list_for_user(
        user_id,
        limit=limit,
        offset=offset,
        sort=sort,  # type: ignore[arg-type]
        direction=direction,  # type: ignore[arg-type]
        query=query,
        only_owned=only_owned,
    )
    return {
        "items": rows,
        "meta": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(rows) < total,
        },
    }


async def get_lists(
    user_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
    sort: str = "created_at",
    direction: str = "desc",
    query: str | None = None,
    only_owned: bool | None = None,
) -> dict[str, Any]:
    return await run_in_thread(
        _get_lists_sync,
        user_id,
        limit=limit,
        offset=offset,
        sort=sort,
        direction=direction,
        query=query,
        only_owned=only_owned,
    )


def _create_list_sync(
    user_id: str, *, name: str, description: str | None, items: list[str]
) -> Row:
    if lists_repo.count_owned(user_id) >= settings.MAX_LISTS_PER_USER:
        raise LimitExceededError(
            f"Достигнут лимит списков ({settings.MAX_LISTS_PER_USER})",
            details={"limit": settings.MAX_LISTS_PER_USER},
        )
    if len(items) > settings.MAX_ITEMS_PER_LIST:
        raise LimitExceededError(
            f"В списке не может быть больше {settings.MAX_ITEMS_PER_LIST} товаров"
        )

    clean_name = clean_display_name(name)
    if not clean_name:
        raise ValidationError("Название списка не может быть пустым")

    created = lists_repo.create_list(
        user_id=user_id,
        name=clean_name,
        description=description,
        items=[clean_display_name(item) for item in items if clean_display_name(item)],
    )

    suggestions_repo.log_event(
        user_id=user_id,
        event_type="add_to_cart",
        entity_type="shopping_list",
        entity_id=str(created["id"]),
        metadata={"action": "create_list", "item_count": len(items)},
    )
    return created


async def create_list(
    user_id: str, *, name: str, description: str | None = None, items: list[str] | None = None
) -> Row:
    return await run_in_thread(
        _create_list_sync,
        user_id,
        name=name,
        description=description,
        items=items or [],
    )


def _get_list_sync(
    list_id: str, user_id: str, *, item_filter: str, with_members: bool
) -> dict[str, Any]:
    _require_membership(list_id, user_id)
    row = lists_repo.get_list(list_id, user_id)
    if row is None:
        raise ListNotFoundError()

    detail = dict(row)
    detail["items"] = lists_repo.get_items(list_id, item_filter=item_filter)  # type: ignore[arg-type]
    detail["members"] = _members_payload(list_id, user_id, row["is_owner"]) if with_members else []
    return detail


def _members_payload(list_id: str, user_id: str, is_owner: bool) -> list[dict[str, Any]]:
    members = lists_repo.get_members(list_id)
    payload: list[dict[str, Any]] = []
    for member in members:
        entry = {
            "user_id": member["user_id"],
            "display_name": member["display_name"],
            "role": member["role"],
            "joined_at": member["joined_at"],
            "is_you": str(member["user_id"]) == user_id,
            # Email is other users' personal data: only the owner sees it.
            "email": member["email"] if is_owner else None,
        }
        payload.append(entry)
    return payload


async def get_list(
    list_id: str,
    user_id: str,
    *,
    item_filter: str = "all",
    with_members: bool = True,
) -> dict[str, Any]:
    return await run_in_thread(
        _get_list_sync,
        list_id,
        user_id,
        item_filter=item_filter,
        with_members=with_members,
    )


def _update_list_sync(
    list_id: str, user_id: str, *, name: str | None, description: str | None
) -> Row:
    membership = _require_membership(list_id, user_id, min_role="editor")
    if name is not None:
        _reject_system_list(membership, "переименовать")

    clean_name = clean_display_name(name) if name is not None else None
    if name is not None and not clean_name:
        raise ValidationError("Название списка не может быть пустым")

    if not lists_repo.update_list(list_id, name=clean_name, description=description):
        raise ListNotFoundError()

    row = lists_repo.get_list(list_id, user_id)
    assert row is not None
    return row


async def update_list(
    list_id: str, user_id: str, *, name: str | None = None, description: str | None = None
) -> Row:
    return await run_in_thread(
        _update_list_sync, list_id, user_id, name=name, description=description
    )


def _delete_list_sync(list_id: str, user_id: str) -> dict[str, Any]:
    membership = _require_membership(list_id, user_id)

    # A non-owner "deleting" a shared list simply leaves it.
    if not membership["is_owner"]:
        lists_repo.leave_list(list_id, user_id)
        return {
            "ok": True,
            "message": "Вы покинули общий список",
            "left_shared_list": True,
        }

    _reject_system_list(membership, "удалить")
    if not lists_repo.delete_list(list_id):
        raise ListNotFoundError()

    return {"ok": True, "message": "Список удален", "left_shared_list": False}


async def delete_list(list_id: str, user_id: str) -> dict[str, Any]:
    return await run_in_thread(_delete_list_sync, list_id, user_id)


# -------------------------------------------------------------------- items


def _get_items_sync(
    list_id: str, user_id: str, *, limit: int, offset: int, item_filter: str
) -> dict[str, Any]:
    _require_membership(list_id, user_id)
    rows = lists_repo.get_items(
        list_id, limit=limit, offset=offset, item_filter=item_filter  # type: ignore[arg-type]
    )
    total = lists_repo.count_items(list_id, item_filter)  # type: ignore[arg-type]
    return {
        "items": rows,
        "meta": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(rows) < total,
        },
    }


async def get_items(
    list_id: str,
    user_id: str,
    *,
    limit: int = 200,
    offset: int = 0,
    item_filter: str = "all",
) -> dict[str, Any]:
    return await run_in_thread(
        _get_items_sync, list_id, user_id, limit=limit, offset=offset, item_filter=item_filter
    )


def _add_item_sync(
    list_id: str,
    user_id: str,
    *,
    name: str,
    quantity: Decimal,
    unit: str | None,
    notes: str | None,
    priority: int,
    product_id: str | None,
) -> Row:
    _require_membership(list_id, user_id, min_role="editor")

    if lists_repo.count_items(list_id) >= settings.MAX_ITEMS_PER_LIST:
        raise LimitExceededError(
            f"В списке не может быть больше {settings.MAX_ITEMS_PER_LIST} товаров"
        )

    clean_name = clean_display_name(name)
    if not clean_name:
        raise ValidationError("Название товара не может быть пустым")

    # Умный разбор: "2л молока" -> название "молока", количество 2, единица "л".
    # Явно переданные quantity/unit всегда важнее разобранных из строки.
    smart_name, smart_quantity, smart_unit = apply_parsed(
        name=clean_name, quantity=quantity, unit=unit
    )
    clean_name = smart_name
    quantity = smart_quantity
    unit = smart_unit

    resolved_product_id = product_id
    resolved_unit = unit
    if resolved_product_id is None:
        # Link to the catalog when we recognize the name; this is what makes
        # suggestions and analytics work on structured data.
        match = catalog_repo.find_exact(normalize_item_name(clean_name))
        if match is not None:
            resolved_product_id = str(match["id"])
            resolved_unit = resolved_unit or match.get("default_unit")

    item = lists_repo.add_item(
        list_id=list_id,
        user_id=user_id,
        name=clean_name,
        quantity=quantity,
        unit=resolved_unit,
        notes=notes,
        priority=priority,
        product_id=resolved_product_id,
    )

    if resolved_product_id:
        catalog_repo.bump_popularity([resolved_product_id])

    suggestions_repo.log_event(
        user_id=user_id,
        event_type="add_to_cart",
        entity_type="shopping_list_item",
        entity_id=str(item["id"]),
        metadata={"name": clean_name, "list_id": list_id},
    )
    return item


async def add_item(
    list_id: str,
    user_id: str,
    *,
    name: str,
    quantity: Decimal = Decimal(1),
    unit: str | None = None,
    notes: str | None = None,
    priority: int = 1,
    product_id: str | None = None,
) -> Row:
    return await run_in_thread(
        _add_item_sync,
        list_id,
        user_id,
        name=name,
        quantity=quantity,
        unit=unit,
        notes=notes,
        priority=priority,
        product_id=product_id,
    )


def _add_items_bulk_sync(
    list_id: str, user_id: str, *, items: list[dict[str, Any]]
) -> list[Row]:
    _require_membership(list_id, user_id, min_role="editor")

    current = lists_repo.count_items(list_id)
    if current + len(items) > settings.MAX_ITEMS_PER_LIST:
        raise LimitExceededError(
            f"В списке не может быть больше {settings.MAX_ITEMS_PER_LIST} товаров",
            details={"current": current, "adding": len(items)},
        )

    prepared: list[dict[str, Any]] = []
    for item in items:
        clean_name = clean_display_name(item["name"])
        if not clean_name:
            continue
        entry = dict(item)
        # Умный разбор применяется только к значениям по умолчанию,
        # чтобы не затирать явно заданные количество/единицу.
        if entry.get("quantity", Decimal(1)) == Decimal(1) and not entry.get("unit"):
            parsed = parse_item_input(clean_name)
            entry["name"] = parsed.name
            entry["quantity"] = parsed.quantity
            entry["unit"] = parsed.unit
        else:
            entry["name"] = clean_name
        if entry.get("product_id") is None:
            match = catalog_repo.find_exact(normalize_item_name(clean_name))
            if match is not None:
                entry["product_id"] = str(match["id"])
                entry["unit"] = entry.get("unit") or match.get("default_unit")
        prepared.append(entry)

    if not prepared:
        raise ValidationError("Нет ни одного корректного товара")

    created_ids = lists_repo.add_items_bulk(list_id=list_id, user_id=user_id, items=prepared)
    product_ids = [str(e["product_id"]) for e in prepared if e.get("product_id")]
    if product_ids:
        catalog_repo.bump_popularity(product_ids)

    suggestions_repo.log_event(
        user_id=user_id,
        event_type="add_to_cart",
        entity_type="shopping_list",
        entity_id=list_id,
        metadata={"action": "bulk_add", "count": len(created_ids)},
    )

    return [item for item in (lists_repo.get_item(list_id, i) for i in created_ids) if item]


async def add_items_bulk(list_id: str, user_id: str, *, items: list[dict[str, Any]]) -> list[Row]:
    return await run_in_thread(_add_items_bulk_sync, list_id, user_id, items=items)


def _update_item_sync(
    list_id: str,
    item_id: str,
    user_id: str,
    *,
    name: str | None,
    quantity: Decimal | None,
    unit: str | None,
    notes: str | None,
    priority: int | None,
    checked: bool | None,
) -> Row:
    _require_membership(list_id, user_id, min_role="editor")

    clean_name = clean_display_name(name) if name is not None else None
    if name is not None and not clean_name:
        raise ValidationError("Название товара не может быть пустым")

    if clean_name is not None and quantity is None and unit is None:
        # Переименование свободным текстом ("молоко 2л") тоже разбираем.
        parsed = parse_item_input(clean_name)
        clean_name = parsed.name
        if parsed.quantity != Decimal(1) or parsed.unit is not None:
            quantity = parsed.quantity
            unit = parsed.unit

    updated = lists_repo.update_item(
        list_id=list_id,
        item_id=item_id,
        user_id=user_id,
        name=clean_name,
        quantity=quantity,
        unit=unit,
        notes=notes,
        priority=priority,
        checked=checked,
    )
    if updated is None:
        raise ItemNotFoundError()

    if checked is not None:
        suggestions_repo.log_event(
            user_id=user_id,
            event_type="purchase" if checked else "remove_from_cart",
            entity_type="shopping_list_item",
            entity_id=item_id,
            metadata={"checked": checked, "name": updated["name"]},
        )
    return updated


async def update_item(
    list_id: str,
    item_id: str,
    user_id: str,
    *,
    name: str | None = None,
    quantity: Decimal | None = None,
    unit: str | None = None,
    notes: str | None = None,
    priority: int | None = None,
    checked: bool | None = None,
) -> Row:
    return await run_in_thread(
        _update_item_sync,
        list_id,
        item_id,
        user_id,
        name=name,
        quantity=quantity,
        unit=unit,
        notes=notes,
        priority=priority,
        checked=checked,
    )


def _toggle_items_sync(
    list_id: str, user_id: str, *, item_ids: list[str], checked: bool
) -> dict[str, Any]:
    _require_membership(list_id, user_id, min_role="editor")
    updated = lists_repo.set_checked_bulk(
        list_id=list_id, item_ids=item_ids, checked=checked, user_id=user_id
    )
    if updated == 0:
        raise ItemNotFoundError("Ни один из указанных товаров не найден в списке")
    return {"ok": True, "updated": updated, "checked": checked}


async def toggle_items(
    list_id: str, user_id: str, *, item_ids: list[str], checked: bool
) -> dict[str, Any]:
    return await run_in_thread(
        _toggle_items_sync, list_id, user_id, item_ids=item_ids, checked=checked
    )


def _delete_item_sync(list_id: str, item_id: str, user_id: str) -> None:
    _require_membership(list_id, user_id, min_role="editor")
    if not lists_repo.delete_item(list_id, item_id):
        raise ItemNotFoundError()


async def delete_item(list_id: str, item_id: str, user_id: str) -> None:
    await run_in_thread(_delete_item_sync, list_id, item_id, user_id)


def _clear_items_sync(list_id: str, user_id: str, *, only_checked: bool) -> dict[str, Any]:
    _require_membership(list_id, user_id, min_role="editor")
    deleted = lists_repo.clear_items(list_id, only_checked=only_checked)
    return {"ok": True, "deleted": deleted}


async def clear_items(list_id: str, user_id: str, *, only_checked: bool = False) -> dict[str, Any]:
    return await run_in_thread(_clear_items_sync, list_id, user_id, only_checked=only_checked)


def _reorder_items_sync(list_id: str, user_id: str, *, item_ids: list[str]) -> dict[str, Any]:
    _require_membership(list_id, user_id, min_role="editor")
    updated = lists_repo.reorder_items(list_id, item_ids)
    if updated == 0:
        raise ItemNotFoundError("Ни один из указанных товаров не найден в списке")
    return {"ok": True, "updated": updated}


async def reorder_items(list_id: str, user_id: str, *, item_ids: list[str]) -> dict[str, Any]:
    return await run_in_thread(_reorder_items_sync, list_id, user_id, item_ids=item_ids)


def _copy_items_sync(
    source_list_id: str,
    user_id: str,
    *,
    item_ids: list[str],
    target_list_ids: list[str],
) -> dict[str, Any]:
    _require_membership(source_list_id, user_id)

    if source_list_id in target_list_ids:
        raise ValidationError("Нельзя копировать товары в тот же список")

    # Verify write access to *every* target before touching any of them,
    # so a partially authorized request changes nothing (IDOR prevention).
    for target_id in target_list_ids:
        _require_membership(target_id, user_id, min_role="editor")

    existing_ids = {str(row["id"]) for row in lists_repo.get_items(source_list_id)}
    missing = [item_id for item_id in item_ids if item_id not in existing_ids]
    if missing:
        raise ItemNotFoundError(
            "Один или несколько товаров не найдены в исходном списке",
            details={"missing": missing[:10]},
        )

    copied, skipped = lists_repo.copy_items_to_lists(
        source_list_id=source_list_id,
        item_ids=item_ids,
        target_list_ids=target_list_ids,
        user_id=user_id,
    )
    return {
        "ok": True,
        "copied_items": copied,
        "target_lists": len(target_list_ids),
        "skipped_duplicates": skipped,
    }


async def copy_items(
    source_list_id: str,
    user_id: str,
    *,
    item_ids: list[str],
    target_list_ids: list[str],
) -> dict[str, Any]:
    return await run_in_thread(
        _copy_items_sync,
        source_list_id,
        user_id,
        item_ids=item_ids,
        target_list_ids=target_list_ids,
    )


# ---------------------------------------------------------------- favourites


def _favorites_sync(user_id: str) -> str:
    return lists_repo.ensure_favorites(user_id)


async def get_favorites_id(user_id: str) -> str:
    return await run_in_thread(_favorites_sync, user_id)
