"""Shopping list and item tests, including access isolation between users."""

from __future__ import annotations

import uuid

import httpx
import pytest


# ------------------------------------------------------------------- lists


async def test_favorites_created_automatically(client: httpx.AsyncClient, user) -> None:
    response = await client.get("/lists", headers=user.headers)
    assert response.status_code == 200
    items = response.json()["items"]
    favorites = [item for item in items if item["is_system"]]
    assert len(favorites) == 1
    assert favorites[0]["name"] == "⭐ Избранное"
    assert favorites[0]["role"] == "owner"


async def test_favorites_endpoint_is_idempotent(client: httpx.AsyncClient, user) -> None:
    first = await client.get("/lists/favorites", headers=user.headers)
    second = await client.get("/lists/favorites", headers=user.headers)
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


async def test_create_list_with_items(client: httpx.AsyncClient, user) -> None:
    response = await client.post(
        "/lists",
        headers=user.headers,
        json={"name": "  Продукты на неделю  ", "items": ["хлеб", "молоко", "хлеб", "  "]},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Продукты на неделю"
    # Blanks dropped, duplicates collapsed.
    assert body["item_count"] == 2
    assert body["role"] == "owner"
    assert body["is_owner"] is True
    assert body["member_count"] == 1


async def test_list_detail_contains_items_and_members(
    client: httpx.AsyncClient, user, shopping_list
) -> None:
    response = await client.get(f"/lists/{shopping_list['id']}", headers=user.headers)
    assert response.status_code == 200
    body = response.json()
    assert [item["name"] for item in body["items"]] == ["хлеб", "молоко"]
    assert len(body["members"]) == 1
    assert body["members"][0]["is_you"] is True


async def test_other_user_cannot_see_list(
    client: httpx.AsyncClient, other_user, shopping_list
) -> None:
    """A stranger gets 404, not 403: existence itself is not disclosed."""
    response = await client.get(f"/lists/{shopping_list['id']}", headers=other_user.headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "list_not_found"


async def test_unknown_list_id_returns_404(client: httpx.AsyncClient, user) -> None:
    response = await client.get(f"/lists/{uuid.uuid4()}", headers=user.headers)
    assert response.status_code == 404


async def test_malformed_list_id_returns_422_not_500(client: httpx.AsyncClient, user) -> None:
    """The legacy version raised a 500 here (invalid uuid reached PostgreSQL)."""
    response = await client.get("/lists/not-a-uuid", headers=user.headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_rename_list(client: httpx.AsyncClient, user, shopping_list) -> None:
    response = await client.patch(
        f"/lists/{shopping_list['id']}",
        headers=user.headers,
        json={"name": "Новое название"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Новое название"


async def test_system_list_cannot_be_renamed(client: httpx.AsyncClient, user) -> None:
    favorites = (await client.get("/lists/favorites", headers=user.headers)).json()
    response = await client.patch(
        f"/lists/{favorites['id']}", headers=user.headers, json={"name": "Не избранное"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "system_list_protected"


async def test_system_list_cannot_be_deleted(client: httpx.AsyncClient, user) -> None:
    favorites = (await client.get("/lists/favorites", headers=user.headers)).json()
    response = await client.delete(f"/lists/{favorites['id']}", headers=user.headers)
    assert response.status_code == 409


async def test_update_list_requires_a_field(client: httpx.AsyncClient, user, shopping_list) -> None:
    response = await client.patch(
        f"/lists/{shopping_list['id']}", headers=user.headers, json={}
    )
    assert response.status_code == 422


async def test_system_description_cannot_be_forged(client: httpx.AsyncClient, user) -> None:
    """Creating a fake system list would make it undeletable."""
    response = await client.post(
        "/lists",
        headers=user.headers,
        json={"name": "Подделка", "description": "system_favorite"},
    )
    assert response.status_code == 422


async def test_delete_list(client: httpx.AsyncClient, user, shopping_list) -> None:
    response = await client.delete(f"/lists/{shopping_list['id']}", headers=user.headers)
    assert response.status_code == 200
    assert response.json()["left_shared_list"] is False
    assert (
        await client.get(f"/lists/{shopping_list['id']}", headers=user.headers)
    ).status_code == 404


async def test_list_pagination_and_search(client: httpx.AsyncClient, user) -> None:
    for index in range(5):
        await client.post("/lists", headers=user.headers, json={"name": f"Список {index}"})

    page = await client.get("/lists?limit=2&offset=0", headers=user.headers)
    assert page.status_code == 200
    body = page.json()
    assert len(body["items"]) == 2
    assert body["meta"]["total"] == 6  # 5 + favorites
    assert body["meta"]["has_more"] is True

    found = await client.get("/lists?q=Список 3", headers=user.headers)
    assert found.json()["meta"]["total"] == 1


# ------------------------------------------------------------------- items


async def test_add_item_with_quantity_and_unit(
    client: httpx.AsyncClient, user, shopping_list
) -> None:
    response = await client.post(
        f"/lists/{shopping_list['id']}/items",
        headers=user.headers,
        json={"name": "молоко 3.2%", "quantity": 2, "unit": "л", "notes": "любое"},
    )
    assert response.status_code == 201
    item = response.json()["item"]
    assert item["name"] == "молоко 3.2%"
    assert float(item["quantity"]) == 2.0
    assert item["unit"] == "л"
    assert item["notes"] == "любое"
    assert item["added_by_name"] == "Первый пользователь"
    # Normalization strips volume and percentage.
    assert item["normalized_name"] == "молоко"


async def test_add_item_rejects_bad_quantity(
    client: httpx.AsyncClient, user, shopping_list
) -> None:
    for quantity in (0, -1, 1_000_000):
        response = await client.post(
            f"/lists/{shopping_list['id']}/items",
            headers=user.headers,
            json={"name": "тест", "quantity": quantity},
        )
        assert response.status_code == 422


async def test_check_item_records_who_and_when(
    client: httpx.AsyncClient, user, shopping_list
) -> None:
    items = (await client.get(f"/lists/{shopping_list['id']}", headers=user.headers)).json()[
        "items"
    ]
    item_id = items[0]["id"]

    checked = await client.patch(
        f"/lists/{shopping_list['id']}/items/{item_id}",
        headers=user.headers,
        json={"checked": True},
    )
    assert checked.status_code == 200
    body = checked.json()
    assert body["checked"] is True
    assert body["checked_at"] is not None
    assert body["checked_by_name"] == "Первый пользователь"

    unchecked = await client.patch(
        f"/lists/{shopping_list['id']}/items/{item_id}",
        headers=user.headers,
        json={"checked": False},
    )
    assert unchecked.json()["checked_at"] is None
    assert unchecked.json()["checked_by"] is None


async def test_item_filter(client: httpx.AsyncClient, user, shopping_list) -> None:
    items = (await client.get(f"/lists/{shopping_list['id']}", headers=user.headers)).json()[
        "items"
    ]
    await client.patch(
        f"/lists/{shopping_list['id']}/items/{items[0]['id']}",
        headers=user.headers,
        json={"checked": True},
    )

    pending = await client.get(
        f"/lists/{shopping_list['id']}/items?filter=pending", headers=user.headers
    )
    checked = await client.get(
        f"/lists/{shopping_list['id']}/items?filter=checked", headers=user.headers
    )
    assert pending.json()["meta"]["total"] == 1
    assert checked.json()["meta"]["total"] == 1


async def test_toggle_multiple_items(client: httpx.AsyncClient, user, shopping_list) -> None:
    items = (await client.get(f"/lists/{shopping_list['id']}", headers=user.headers)).json()[
        "items"
    ]
    response = await client.post(
        f"/lists/{shopping_list['id']}/items/toggle",
        headers=user.headers,
        json={"item_ids": [item["id"] for item in items], "checked": True},
    )
    assert response.status_code == 200
    assert response.json()["updated"] == 2


async def test_bulk_add_items(client: httpx.AsyncClient, user, shopping_list) -> None:
    response = await client.post(
        f"/lists/{shopping_list['id']}/items/bulk",
        headers=user.headers,
        json={"items": [{"name": "сыр"}, {"name": "колбаса", "quantity": 3}]},
    )
    assert response.status_code == 201
    assert response.json()["created"] == 2


async def test_reorder_items(client: httpx.AsyncClient, user, shopping_list) -> None:
    items = (await client.get(f"/lists/{shopping_list['id']}", headers=user.headers)).json()[
        "items"
    ]
    reversed_ids = [item["id"] for item in reversed(items)]

    response = await client.post(
        f"/lists/{shopping_list['id']}/items/reorder",
        headers=user.headers,
        json={"item_ids": reversed_ids},
    )
    assert response.status_code == 200

    after = (await client.get(f"/lists/{shopping_list['id']}", headers=user.headers)).json()
    assert [item["id"] for item in after["items"]] == reversed_ids


async def test_delete_and_clear_items(client: httpx.AsyncClient, user, shopping_list) -> None:
    list_id = shopping_list["id"]
    items = (await client.get(f"/lists/{list_id}", headers=user.headers)).json()["items"]

    deleted = await client.delete(
        f"/lists/{list_id}/items/{items[0]['id']}", headers=user.headers
    )
    assert deleted.status_code == 200

    cleared = await client.delete(f"/lists/{list_id}/items", headers=user.headers)
    assert cleared.status_code == 200
    assert cleared.json()["deleted"] == 1


async def test_clear_only_checked_items(client: httpx.AsyncClient, user, shopping_list) -> None:
    list_id = shopping_list["id"]
    items = (await client.get(f"/lists/{list_id}", headers=user.headers)).json()["items"]
    await client.patch(
        f"/lists/{list_id}/items/{items[0]['id']}", headers=user.headers, json={"checked": True}
    )

    response = await client.delete(
        f"/lists/{list_id}/items?checked_only=true", headers=user.headers
    )
    assert response.json()["deleted"] == 1

    remaining = (await client.get(f"/lists/{list_id}", headers=user.headers)).json()
    assert remaining["item_count"] == 1


async def test_missing_item_returns_404(client: httpx.AsyncClient, user, shopping_list) -> None:
    response = await client.patch(
        f"/lists/{shopping_list['id']}/items/{uuid.uuid4()}",
        headers=user.headers,
        json={"name": "нет такого"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "item_not_found"


async def test_other_user_cannot_add_items(
    client: httpx.AsyncClient, other_user, shopping_list
) -> None:
    response = await client.post(
        f"/lists/{shopping_list['id']}/items",
        headers=other_user.headers,
        json={"name": "чужой товар"},
    )
    assert response.status_code == 404


# ------------------------------------------------------------ copying items


async def test_copy_items_between_own_lists(
    client: httpx.AsyncClient, user, shopping_list
) -> None:
    target = (
        await client.post("/lists", headers=user.headers, json={"name": "Цель"})
    ).json()
    items = (await client.get(f"/lists/{shopping_list['id']}", headers=user.headers)).json()[
        "items"
    ]

    response = await client.post(
        f"/lists/{shopping_list['id']}/items/copy",
        headers=user.headers,
        json={
            "item_ids": [item["id"] for item in items],
            "target_list_ids": [target["id"]],
        },
    )
    assert response.status_code == 200
    assert response.json()["copied_items"] == 2

    # A second copy skips duplicates instead of piling them up.
    again = await client.post(
        f"/lists/{shopping_list['id']}/items/copy",
        headers=user.headers,
        json={
            "item_ids": [item["id"] for item in items],
            "target_list_ids": [target["id"]],
        },
    )
    assert again.json() == {
        "ok": True,
        "copied_items": 0,
        "target_lists": 1,
        "skipped_duplicates": 2,
    }


async def test_copy_to_foreign_list_is_blocked(
    client: httpx.AsyncClient, user, other_user, shopping_list
) -> None:
    """IDOR guard: an unauthorized target must abort the whole operation."""
    foreign = (
        await client.post("/lists", headers=other_user.headers, json={"name": "Чужой"})
    ).json()
    mine = (
        await client.post("/lists", headers=user.headers, json={"name": "Мой второй"})
    ).json()
    items = (await client.get(f"/lists/{shopping_list['id']}", headers=user.headers)).json()[
        "items"
    ]

    response = await client.post(
        f"/lists/{shopping_list['id']}/items/copy",
        headers=user.headers,
        json={
            "item_ids": [items[0]["id"]],
            "target_list_ids": [mine["id"], foreign["id"]],
        },
    )
    assert response.status_code == 404

    # Nothing was written to the authorized target either.
    unchanged = (await client.get(f"/lists/{mine['id']}", headers=user.headers)).json()
    assert unchanged["item_count"] == 0


async def test_copy_into_same_list_rejected(
    client: httpx.AsyncClient, user, shopping_list
) -> None:
    items = (await client.get(f"/lists/{shopping_list['id']}", headers=user.headers)).json()[
        "items"
    ]
    response = await client.post(
        f"/lists/{shopping_list['id']}/items/copy",
        headers=user.headers,
        json={
            "item_ids": [items[0]["id"]],
            "target_list_ids": [shopping_list["id"]],
        },
    )
    assert response.status_code == 422
