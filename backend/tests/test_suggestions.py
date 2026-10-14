"""Suggestion engine tests: the "часто покупают вместе" feature."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.usefixtures("seeded")


# --------------------------------------------------------- basic behaviour


async def test_bread_suggests_butter_cheese_sausage(client: httpx.AsyncClient, user) -> None:
    """The example from the project brief: хлеб -> масло, сыр, колбаса."""
    response = await client.get("/suggestions?item=хлеб", headers=user.headers)
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True

    names = [item["name"] for item in body["items"]]
    assert "масло сливочное" in names
    assert "сыр" in names
    assert "колбаса" in names


async def test_potato_suggests_oil_and_onion(client: httpx.AsyncClient, user) -> None:
    """The other brief example: картошка -> масло."""
    response = await client.get("/suggestions?item=картошка", headers=user.headers)
    names = [item["name"] for item in response.json()["items"]]
    assert "масло растительное" in names
    assert "лук" in names


async def test_suggestions_carry_score_source_and_reason(
    client: httpx.AsyncClient, user
) -> None:
    response = await client.get("/suggestions?item=макароны", headers=user.headers)
    first = response.json()["items"][0]
    assert 0.0 < first["score"] <= 1.0
    assert first["source"] in {"seed", "statistical", "personal", "llm"}
    assert first["reason"]
    assert first["based_on"]


async def test_suggestions_are_ranked_descending(client: httpx.AsyncClient, user) -> None:
    response = await client.get("/suggestions?item=хлеб", headers=user.headers)
    scores = [item["score"] for item in response.json()["items"]]
    assert scores == sorted(scores, reverse=True)


async def test_declined_words_are_matched(client: httpx.AsyncClient, user) -> None:
    """"2 л молока" must resolve to the rules written for "молоко"."""
    response = await client.get("/suggestions?item=2 л молока", headers=user.headers)
    assert response.json()["items"], "inflected input produced no suggestions"


async def test_synonyms_are_matched(client: httpx.AsyncClient, user) -> None:
    via_alias = await client.get("/suggestions?item=картоха", headers=user.headers)
    canonical = await client.get("/suggestions?item=картофель", headers=user.headers)
    assert [item["name"] for item in via_alias.json()["items"]] == [
        item["name"] for item in canonical.json()["items"]
    ]


async def test_multiple_items_merge_suggestions(client: httpx.AsyncClient, user) -> None:
    response = await client.get(
        "/suggestions?item=хлеб&item=макароны", headers=user.headers
    )
    names = [item["name"] for item in response.json()["items"]]
    assert len(names) == len(set(names)), "duplicate suggestions returned"
    assert response.json()["basket_size"] == 2


async def test_unknown_item_returns_empty_not_error(client: httpx.AsyncClient, user) -> None:
    response = await client.get(
        "/suggestions?item=совершенно неизвестный предмет", headers=user.headers
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_limit_is_respected(client: httpx.AsyncClient, user) -> None:
    response = await client.get("/suggestions?item=хлеб&limit=2", headers=user.headers)
    assert len(response.json()["items"]) <= 2


async def test_limit_bounds_enforced(client: httpx.AsyncClient, user) -> None:
    assert (
        await client.get("/suggestions?item=хлеб&limit=0", headers=user.headers)
    ).status_code == 422
    assert (
        await client.get("/suggestions?item=хлеб&limit=999", headers=user.headers)
    ).status_code == 422


async def test_suggestions_require_auth(client: httpx.AsyncClient) -> None:
    assert (await client.get("/suggestions?item=хлеб")).status_code == 401


# ------------------------------------------------------------------ caching


async def test_second_identical_request_is_cached(client: httpx.AsyncClient, user) -> None:
    first = await client.get("/suggestions?item=хлеб", headers=user.headers)
    second = await client.get("/suggestions?item=хлеб", headers=user.headers)
    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    assert first.json()["items"] == second.json()["items"]


async def test_cache_key_is_order_independent(client: httpx.AsyncClient, user) -> None:
    await client.get("/suggestions?item=хлеб&item=сыр", headers=user.headers)
    reordered = await client.get("/suggestions?item=сыр&item=хлеб", headers=user.headers)
    assert reordered.json()["cached"] is True


# ------------------------------------------------------------- list context


async def test_list_suggestions_exclude_present_items(
    client: httpx.AsyncClient, user
) -> None:
    created = (
        await client.post(
            "/lists",
            headers=user.headers,
            json={"name": "Завтрак", "items": ["хлеб", "масло сливочное"]},
        )
    ).json()

    response = await client.get(f"/lists/{created['id']}/suggestions", headers=user.headers)
    assert response.status_code == 200
    names = [item["name"] for item in response.json()["items"]]
    # Already in the basket, so it must not be suggested again.
    assert "масло сливочное" not in names
    assert "хлеб" not in names


async def test_list_suggestions_ignore_checked_by_default(
    client: httpx.AsyncClient, user
) -> None:
    created = (
        await client.post("/lists", headers=user.headers, json={"name": "Тест", "items": ["хлеб"]})
    ).json()
    items = (await client.get(f"/lists/{created['id']}", headers=user.headers)).json()["items"]
    await client.patch(
        f"/lists/{created['id']}/items/{items[0]['id']}",
        headers=user.headers,
        json={"checked": True},
    )

    default = await client.get(f"/lists/{created['id']}/suggestions", headers=user.headers)
    including = await client.get(
        f"/lists/{created['id']}/suggestions?include_checked=true", headers=user.headers
    )
    assert default.json()["items"] == []
    assert including.json()["items"]


async def test_list_suggestions_require_membership(
    client: httpx.AsyncClient, other_user, shopping_list
) -> None:
    response = await client.get(
        f"/lists/{shopping_list['id']}/suggestions", headers=other_user.headers
    )
    assert response.status_code == 404


async def test_add_item_returns_suggestions_inline(client: httpx.AsyncClient, user) -> None:
    """Real-time behaviour: adding an item immediately returns companions."""
    created = (
        await client.post("/lists", headers=user.headers, json={"name": "Ужин"})
    ).json()

    response = await client.post(
        f"/lists/{created['id']}/items", headers=user.headers, json={"name": "макароны"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["item"]["name"] == "макароны"
    names = [item["name"] for item in body["suggestions"]]
    assert "сыр" in names or "томатная паста" in names


async def test_suggest_false_skips_suggestions(client: httpx.AsyncClient, user) -> None:
    created = (
        await client.post("/lists", headers=user.headers, json={"name": "Без подсказок"})
    ).json()
    response = await client.post(
        f"/lists/{created['id']}/items?suggest=false",
        headers=user.headers,
        json={"name": "хлеб"},
    )
    assert response.status_code == 201
    assert response.json()["suggestions"] == []


# ------------------------------------------------------------------- toggle


async def test_user_can_disable_suggestions(client: httpx.AsyncClient, user) -> None:
    disabled = await client.patch(
        "/me/settings", headers=user.headers, json={"ai_suggestions_enabled": False}
    )
    assert disabled.status_code == 200
    assert disabled.json()["ai_suggestions_enabled"] is False

    response = await client.get("/suggestions?item=хлеб", headers=user.headers)
    body = response.json()
    assert body["enabled"] is False
    assert body["items"] == []


async def test_disabled_suggestions_also_apply_to_add_item(
    client: httpx.AsyncClient, user
) -> None:
    await client.patch(
        "/me/settings", headers=user.headers, json={"ai_suggestions_enabled": False}
    )
    created = (
        await client.post("/lists", headers=user.headers, json={"name": "Список"})
    ).json()
    response = await client.post(
        f"/lists/{created['id']}/items", headers=user.headers, json={"name": "хлеб"}
    )
    assert response.status_code == 201
    assert response.json()["suggestions"] == []


async def test_suggestions_can_be_re_enabled(client: httpx.AsyncClient, user) -> None:
    await client.patch(
        "/me/settings", headers=user.headers, json={"ai_suggestions_enabled": False}
    )
    await client.patch(
        "/me/settings", headers=user.headers, json={"ai_suggestions_enabled": True}
    )
    response = await client.get("/suggestions?item=хлеб", headers=user.headers)
    assert response.json()["enabled"] is True
    assert response.json()["items"]


async def test_toggle_is_per_user(client: httpx.AsyncClient, user, other_user) -> None:
    await client.patch(
        "/me/settings", headers=user.headers, json={"ai_suggestions_enabled": False}
    )
    response = await client.get("/suggestions?item=хлеб", headers=other_user.headers)
    assert response.json()["enabled"] is True


async def test_default_limit_from_settings(client: httpx.AsyncClient, user) -> None:
    await client.patch("/me/settings", headers=user.headers, json={"suggestions_limit": 2})
    response = await client.get("/suggestions?item=хлеб", headers=user.headers)
    assert len(response.json()["items"]) <= 2


# ----------------------------------------------------------------- feedback


async def test_rejecting_a_suggestion_lowers_its_rank(client: httpx.AsyncClient, user) -> None:
    before = await client.get("/suggestions?item=хлеб", headers=user.headers)
    target = before.json()["items"][0]

    for _ in range(5):
        response = await client.post(
            "/suggestions/feedback",
            headers=user.headers,
            json={
                "suggested_name": target["name"],
                "action": "rejected",
                "based_on": ["хлеб"],
            },
        )
        assert response.status_code == 200

    after = await client.get("/suggestions?item=хлеб", headers=user.headers)
    after_items = {item["name"]: item["score"] for item in after.json()["items"]}
    assert after_items.get(target["name"], 0.0) < target["score"]


async def test_accepting_a_suggestion_raises_its_rank(client: httpx.AsyncClient, user) -> None:
    before = await client.get("/suggestions?item=чай", headers=user.headers)
    items = before.json()["items"]
    target = items[-1]

    for _ in range(5):
        await client.post(
            "/suggestions/feedback",
            headers=user.headers,
            json={
                "suggested_name": target["name"],
                "action": "accepted",
                "based_on": ["чай"],
            },
        )

    after = await client.get("/suggestions?item=чай", headers=user.headers)
    after_items = {item["name"]: item["score"] for item in after.json()["items"]}
    assert after_items.get(target["name"], 0.0) > target["score"]


async def test_feedback_validation(client: httpx.AsyncClient, user) -> None:
    response = await client.post(
        "/suggestions/feedback",
        headers=user.headers,
        json={"suggested_name": "сыр", "action": "маybe"},
    )
    assert response.status_code == 422


# --------------------------------------------------- personal statistics


async def test_personal_history_produces_suggestions(client: httpx.AsyncClient, user) -> None:
    """A pair the user repeats must be learned even without a curated rule."""
    for index in range(3):
        await client.post(
            "/lists",
            headers=user.headers,
            json={
                "name": f"Покупки {index}",
                "items": ["батарейки", "лампочка"],
            },
        )

    response = await client.get("/suggestions?item=батарейки", headers=user.headers)
    names = [item["name"] for item in response.json()["items"]]
    assert "лампочка" in names

    personal = [
        item for item in response.json()["items"] if item["source"] == "personal"
    ]
    assert personal, "personal co-occurrence signal missing"


async def test_personal_data_does_not_leak_between_users(
    client: httpx.AsyncClient, user, other_user
) -> None:
    for index in range(3):
        await client.post(
            "/lists",
            headers=user.headers,
            json={"name": f"Личное {index}", "items": ["спички", "свечи"]},
        )

    response = await client.get("/suggestions?item=спички", headers=other_user.headers)
    names = [item["name"] for item in response.json()["items"]]
    assert "свечи" not in names


# ------------------------------------------------------------------- status


async def test_engine_status_reports_llm_absence(client: httpx.AsyncClient, user) -> None:
    response = await client.get("/suggestions/status", headers=user.headers)
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "statistical"
    assert body["globally_enabled"] is True
    # No API key configured yet, so the statistical engine is in charge.
    assert body["llm_configured"] is False
    assert body["llm_model"] is None
    assert body["seed_rules"] > 100
    assert body["catalog_products"] > 100
