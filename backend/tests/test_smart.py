"""Разбор ввода и пополнение: /smart/parse, /smart/replenish."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.usefixtures("seeded")


async def test_parse_preview(client: httpx.AsyncClient, user) -> None:
    response = await client.post("/smart/parse", headers=user.headers, json={"text": "2л молока"})
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "молока"
    assert str(body["quantity"]) == "2"
    assert body["unit"] == "л"


async def test_add_item_parses_quantity(client: httpx.AsyncClient, user, shopping_list) -> None:
    response = await client.post(
        f"/lists/{shopping_list['id']}/items",
        headers=user.headers,
        params={"suggest": "false"},
        json={"name": "молоко 2л"},
    )
    assert response.status_code == 201
    item = response.json()["item"]
    assert item["name"] == "молоко"
    assert str(item["quantity"]) == "2"
    assert item["unit"] == "л"


async def test_replenish_detects_due_product(client: httpx.AsyncClient, user) -> None:
    from app.db import pool as pool_module

    # Три покупки молока: 10, 6 и 3.5 дня назад (медианный интервал ~3.75 дня).
    for days_ago in (10.0, 6.0, 3.5):
        created = (
            await client.post(
                "/lists",
                headers=user.headers,
                json={"name": f"Покупки {days_ago}", "items": ["молоко"]},
            )
        ).json()
        items = (await client.get(f"/lists/{created['id']}", headers=user.headers)).json()["items"]
        milk = next(item for item in items if "молоко" in item["name"].casefold())
        await client.patch(
            f"/lists/{created['id']}/items/{milk['id']}",
            headers=user.headers,
            json={"checked": True},
        )
        pool_module.execute(
            "UPDATE shopping_list_items SET checked_at = now() - (%s || ' days')::interval WHERE id = %s",
            (days_ago, milk["id"]),
        )

    # Свежая покупка хлеба — он due быть не должен.
    created = (
        await client.post(
            "/lists", headers=user.headers, json={"name": "Свежее", "items": ["хлеб"]}
        )
    ).json()
    items = (await client.get(f"/lists/{created['id']}", headers=user.headers)).json()["items"]
    await client.patch(
        f"/lists/{created['id']}/items/{items[0]['id']}",
        headers=user.headers,
        json={"checked": True},
    )

    response = await client.get("/smart/replenish", headers=user.headers)
    assert response.status_code == 200
    names = [item["normalized_name"] for item in response.json()["items"]]
    assert "молоко" in names
