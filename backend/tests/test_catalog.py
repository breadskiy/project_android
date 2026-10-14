"""Product catalog tests: fuzzy search, aliases, autocomplete."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.usefixtures("seeded")


async def test_exact_search(client: httpx.AsyncClient, user) -> None:
    response = await client.get("/products/search?q=молоко", headers=user.headers)
    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["name"] == "молоко"
    assert body["items"][0]["similarity"] == pytest.approx(1.0)
    assert body["normalized_query"] == "молоко"


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("малоко", "молоко"),
        ("картоха", "картофель"),
        ("хлеп", "хлеб"),
        ("макарони", "макароны"),
        ("помидори", "помидоры"),
    ],
)
async def test_typo_tolerant_search(
    client: httpx.AsyncClient, user, query: str, expected: str
) -> None:
    response = await client.get(f"/products/search?q={query}", headers=user.headers)
    names = [item["name"] for item in response.json()["items"]]
    assert expected in names, f"{query!r} did not find {expected!r}: {names}"


async def test_alias_search_reports_matched_alias(client: httpx.AsyncClient, user) -> None:
    response = await client.get("/products/search?q=картоха", headers=user.headers)
    match = next(item for item in response.json()["items"] if item["name"] == "картофель")
    assert match["matched_alias"] == "картоха"


async def test_prefix_search_for_autocomplete(client: httpx.AsyncClient, user) -> None:
    response = await client.get("/products/search?q=мол", headers=user.headers)
    names = [item["name"] for item in response.json()["items"]]
    assert "молоко" in names


async def test_search_ignores_quantities(client: httpx.AsyncClient, user) -> None:
    response = await client.get("/products/search?q=2 л молока", headers=user.headers)
    assert response.json()["normalized_query"] == "молока"
    assert "молоко" in [item["name"] for item in response.json()["items"]]


async def test_search_returns_empty_for_nonsense(client: httpx.AsyncClient, user) -> None:
    response = await client.get("/products/search?q=щщщщщщ", headers=user.headers)
    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_search_requires_query(client: httpx.AsyncClient, user) -> None:
    assert (await client.get("/products/search?q=", headers=user.headers)).status_code == 422


async def test_search_requires_auth(client: httpx.AsyncClient) -> None:
    assert (await client.get("/products/search?q=молоко")).status_code == 401


async def test_catalog_listing_is_paginated(client: httpx.AsyncClient, user) -> None:
    response = await client.get("/products?limit=10", headers=user.headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 10
    assert body["meta"]["total"] > 100
    assert body["meta"]["has_more"] is True


async def test_categories_have_products(client: httpx.AsyncClient, user) -> None:
    response = await client.get("/products/categories", headers=user.headers)
    assert response.status_code == 200
    categories = response.json()["items"]
    assert len(categories) >= 10
    assert all(category["product_count"] > 0 for category in categories)

    names = {category["name"] for category in categories}
    assert "Молочные продукты" in names


async def test_category_filter(client: httpx.AsyncClient, user) -> None:
    categories = (await client.get("/products/categories", headers=user.headers)).json()["items"]
    dairy = next(c for c in categories if c["name"] == "Молочные продукты")

    response = await client.get(
        f"/products?category_id={dairy['id']}&limit=100", headers=user.headers
    )
    assert response.json()["meta"]["total"] == dairy["product_count"]
    assert all(item["category_name"] == "Молочные продукты" for item in response.json()["items"])


async def test_added_item_links_to_catalog(client: httpx.AsyncClient, user) -> None:
    """Recognized names get a product_id, which is what powers analytics."""
    created = (
        await client.post("/lists", headers=user.headers, json={"name": "Тест"})
    ).json()

    response = await client.post(
        f"/lists/{created['id']}/items", headers=user.headers, json={"name": "молоко"}
    )
    item = response.json()["item"]
    assert item["product_id"] is not None
    # The catalog's default unit is applied when the user did not specify one.
    assert item["unit"] == "л"


async def test_unknown_item_has_no_product_link(client: httpx.AsyncClient, user) -> None:
    created = (
        await client.post("/lists", headers=user.headers, json={"name": "Тест"})
    ).json()
    response = await client.post(
        f"/lists/{created['id']}/items",
        headers=user.headers,
        json={"name": "какой-то особенный товар"},
    )
    assert response.json()["item"]["product_id"] is None
