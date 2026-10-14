"""Sharing tests: invites, roles, member management, imports, QR."""

from __future__ import annotations

import uuid

import httpx
import pytest


async def create_invite(client: httpx.AsyncClient, user, list_id: str, **body) -> dict:
    response = await client.post(f"/lists/{list_id}/share", headers=user.headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


# ------------------------------------------------------------------ invites


async def test_share_returns_code_link_and_qr(
    client: httpx.AsyncClient, user, shopping_list
) -> None:
    invite = await create_invite(client, user, shopping_list["id"])
    assert invite["mode"] == "share"
    assert invite["role"] == "editor"
    assert invite["link"] == f"smartsupply://join/{invite['code']}"
    assert invite["qr_svg_url"].endswith("/qr")
    # The list UUID must not be the shared secret any more.
    assert shopping_list["id"] not in invite["link"]


async def test_invite_code_has_no_ambiguous_characters(
    client: httpx.AsyncClient, user, shopping_list
) -> None:
    invite = await create_invite(client, user, shopping_list["id"])
    assert not set(invite["code"]) & set("IO01")


async def test_repeated_share_reuses_code(
    client: httpx.AsyncClient, user, shopping_list
) -> None:
    first = await create_invite(client, user, shopping_list["id"])
    second = await create_invite(client, user, shopping_list["id"])
    assert first["code"] == second["code"]


async def test_limited_invite_creates_new_code(
    client: httpx.AsyncClient, user, shopping_list
) -> None:
    plain = await create_invite(client, user, shopping_list["id"])
    limited = await create_invite(client, user, shopping_list["id"], max_uses=1)
    assert plain["code"] != limited["code"]
    assert limited["max_uses"] == 1


async def test_non_owner_cannot_share(
    client: httpx.AsyncClient, other_user, shopping_list
) -> None:
    response = await client.post(
        f"/lists/{shopping_list['id']}/share", headers=other_user.headers, json={}
    )
    assert response.status_code == 404


async def test_system_list_cannot_be_shared(client: httpx.AsyncClient, user) -> None:
    favorites = (await client.get("/lists/favorites", headers=user.headers)).json()
    response = await client.post(
        f"/lists/{favorites['id']}/share", headers=user.headers, json={}
    )
    assert response.status_code == 409


async def test_owner_role_cannot_be_granted(
    client: httpx.AsyncClient, user, shopping_list
) -> None:
    response = await client.post(
        f"/lists/{shopping_list['id']}/share",
        headers=user.headers,
        json={"role": "owner"},
    )
    assert response.status_code == 422


async def test_qr_endpoint_returns_svg(client: httpx.AsyncClient, user, shopping_list) -> None:
    invite = await create_invite(client, user, shopping_list["id"])
    response = await client.get(f"/lists/invites/{invite['code']}/qr", headers=user.headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.text.lstrip().startswith("<?xml")


async def test_invite_preview_hides_contents(
    client: httpx.AsyncClient, user, other_user, shopping_list
) -> None:
    invite = await create_invite(client, user, shopping_list["id"])
    response = await client.get(f"/lists/invites/{invite['code']}", headers=other_user.headers)
    assert response.status_code == 200
    body = response.json()
    assert body["list_name"] == "Продукты"
    assert body["item_count"] == 2
    assert body["already_member"] is False
    # Item names are not disclosed before joining.
    assert "хлеб" not in response.text


# --------------------------------------------------------------------- join


async def test_join_shared_list(
    client: httpx.AsyncClient, user, other_user, shopping_list
) -> None:
    invite = await create_invite(client, user, shopping_list["id"])

    joined = await client.post(
        "/lists/join", headers=other_user.headers, json={"code": invite["code"]}
    )
    assert joined.status_code == 200
    assert joined.json()["role"] == "editor"

    visible = await client.get(f"/lists/{shopping_list['id']}", headers=other_user.headers)
    assert visible.status_code == 200
    assert visible.json()["role"] == "editor"
    assert visible.json()["is_owner"] is False


async def test_editor_can_modify_items(
    client: httpx.AsyncClient, user, other_user, shopping_list
) -> None:
    invite = await create_invite(client, user, shopping_list["id"])
    await client.post("/lists/join", headers=other_user.headers, json={"code": invite["code"]})

    added = await client.post(
        f"/lists/{shopping_list['id']}/items",
        headers=other_user.headers,
        json={"name": "сыр"},
    )
    assert added.status_code == 201

    # Both members see the same list state.
    owner_view = (
        await client.get(f"/lists/{shopping_list['id']}", headers=user.headers)
    ).json()
    assert "сыр" in [item["name"] for item in owner_view["items"]]
    assert owner_view["is_shared"] is True
    assert owner_view["member_count"] == 2


async def test_viewer_cannot_modify_items(
    client: httpx.AsyncClient, user, other_user, shopping_list
) -> None:
    invite = await create_invite(client, user, shopping_list["id"], role="viewer")
    await client.post("/lists/join", headers=other_user.headers, json={"code": invite["code"]})

    read = await client.get(f"/lists/{shopping_list['id']}", headers=other_user.headers)
    assert read.status_code == 200

    write = await client.post(
        f"/lists/{shopping_list['id']}/items",
        headers=other_user.headers,
        json={"name": "нельзя"},
    )
    assert write.status_code == 403
    assert write.json()["error"]["code"] == "permission_denied"


async def test_copy_mode_creates_independent_list(
    client: httpx.AsyncClient, user, other_user, shopping_list
) -> None:
    invite = await create_invite(client, user, shopping_list["id"], mode="copy")
    joined = await client.post(
        "/lists/join", headers=other_user.headers, json={"code": invite["code"]}
    )
    assert joined.status_code == 200
    body = joined.json()
    assert body["mode"] == "copy"
    assert body["role"] == "owner"
    new_list_id = body["list_id"]
    assert new_list_id != shopping_list["id"]

    copy = (await client.get(f"/lists/{new_list_id}", headers=other_user.headers)).json()
    assert copy["item_count"] == 2

    # Changing the copy must not touch the original.
    await client.post(
        f"/lists/{new_list_id}/items", headers=other_user.headers, json={"name": "своё"}
    )
    original = (await client.get(f"/lists/{shopping_list['id']}", headers=user.headers)).json()
    assert original["item_count"] == 2


async def test_single_use_invite_is_exhausted(
    client: httpx.AsyncClient, user, other_user, user_factory, shopping_list
) -> None:
    invite = await create_invite(client, user, shopping_list["id"], max_uses=1)
    first = await client.post(
        "/lists/join", headers=other_user.headers, json={"code": invite["code"]}
    )
    assert first.status_code == 200

    third_user = await user_factory("Третий")
    second = await client.post(
        "/lists/join", headers=third_user.headers, json={"code": invite["code"]}
    )
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "invite_invalid"


async def test_revoked_invite_rejected(
    client: httpx.AsyncClient, user, other_user, shopping_list
) -> None:
    invite = await create_invite(client, user, shopping_list["id"])
    revoked = await client.delete(
        f"/lists/{shopping_list['id']}/invites/{invite['code']}", headers=user.headers
    )
    assert revoked.status_code == 200

    response = await client.post(
        "/lists/join", headers=other_user.headers, json={"code": invite["code"]}
    )
    assert response.status_code == 400


async def test_unknown_code_rejected(client: httpx.AsyncClient, user) -> None:
    response = await client.post("/lists/join", headers=user.headers, json={"code": "ZZZZZZZZZZZZ"})
    assert response.status_code == 400


async def test_owner_cannot_join_own_list(
    client: httpx.AsyncClient, user, shopping_list
) -> None:
    invite = await create_invite(client, user, shopping_list["id"])
    response = await client.post(
        "/lists/join", headers=user.headers, json={"code": invite["code"]}
    )
    assert response.status_code == 422


async def test_joining_twice_is_idempotent(
    client: httpx.AsyncClient, user, other_user, shopping_list
) -> None:
    invite = await create_invite(client, user, shopping_list["id"])
    first = await client.post(
        "/lists/join", headers=other_user.headers, json={"code": invite["code"]}
    )
    second = await client.post(
        "/lists/join", headers=other_user.headers, json={"code": invite["code"]}
    )
    assert first.status_code == second.status_code == 200

    members = await client.get(f"/lists/{shopping_list['id']}/members", headers=user.headers)
    assert len(members.json()) == 2


# ------------------------------------------------------------- import links


async def test_import_by_join_link(
    client: httpx.AsyncClient, user, other_user, shopping_list
) -> None:
    invite = await create_invite(client, user, shopping_list["id"])
    response = await client.post(
        "/lists/import", headers=other_user.headers, json={"link": invite["link"]}
    )
    assert response.status_code == 200


async def test_legacy_share_link_still_works(
    client: httpx.AsyncClient, user, other_user, shopping_list
) -> None:
    """Links produced by the terminal version must keep working."""
    await create_invite(client, user, shopping_list["id"])  # marks the list as shared
    response = await client.post(
        "/lists/import",
        headers=other_user.headers,
        json={"link": f"smartsupply://share/{shopping_list['id']}"},
    )
    assert response.status_code == 200
    assert response.json()["mode"] == "share"


async def test_legacy_copy_link_still_works(
    client: httpx.AsyncClient, other_user, shopping_list
) -> None:
    response = await client.post(
        "/lists/import",
        headers=other_user.headers,
        json={"link": f"smartsupply://copy/{shopping_list['id']}"},
    )
    assert response.status_code == 200
    assert response.json()["mode"] == "copy"


async def test_legacy_share_link_requires_shared_list(
    client: httpx.AsyncClient, other_user, shopping_list
) -> None:
    response = await client.post(
        "/lists/import",
        headers=other_user.headers,
        json={"link": f"smartsupply://share/{shopping_list['id']}"},
    )
    assert response.status_code == 400


@pytest.mark.parametrize(
    "link",
    [
        "https://evil.example/steal",
        "smartsupply://join/short",
        "smartsupply://share/not-a-uuid",
        "smartsupply://unknown/abc",
        "javascript:alert(1)",
        "smartsupply://",
    ],
)
async def test_malformed_import_links_rejected(
    client: httpx.AsyncClient, user, link: str
) -> None:
    """The legacy version raised a 500 on 'share/not-a-uuid'."""
    response = await client.post("/lists/import", headers=user.headers, json={"link": link})
    assert response.status_code == 422


# ----------------------------------------------------------------- members


async def test_email_visible_only_to_owner(
    client: httpx.AsyncClient, user, other_user, shopping_list
) -> None:
    invite = await create_invite(client, user, shopping_list["id"])
    await client.post("/lists/join", headers=other_user.headers, json={"code": invite["code"]})

    owner_view = await client.get(
        f"/lists/{shopping_list['id']}/members", headers=user.headers
    )
    member_view = await client.get(
        f"/lists/{shopping_list['id']}/members", headers=other_user.headers
    )

    assert any(member["email"] for member in owner_view.json())
    assert all(member["email"] is None for member in member_view.json())


async def test_owner_changes_member_role(
    client: httpx.AsyncClient, user, other_user, shopping_list
) -> None:
    invite = await create_invite(client, user, shopping_list["id"])
    await client.post("/lists/join", headers=other_user.headers, json={"code": invite["code"]})

    response = await client.patch(
        f"/lists/{shopping_list['id']}/members/{other_user.user_id}",
        headers=user.headers,
        json={"role": "viewer"},
    )
    assert response.status_code == 200

    blocked = await client.post(
        f"/lists/{shopping_list['id']}/items",
        headers=other_user.headers,
        json={"name": "теперь нельзя"},
    )
    assert blocked.status_code == 403


async def test_member_cannot_change_roles(
    client: httpx.AsyncClient, user, other_user, shopping_list
) -> None:
    invite = await create_invite(client, user, shopping_list["id"])
    await client.post("/lists/join", headers=other_user.headers, json={"code": invite["code"]})

    response = await client.patch(
        f"/lists/{shopping_list['id']}/members/{user.user_id}",
        headers=other_user.headers,
        json={"role": "viewer"},
    )
    assert response.status_code == 403


async def test_owner_removes_member(
    client: httpx.AsyncClient, user, other_user, shopping_list
) -> None:
    invite = await create_invite(client, user, shopping_list["id"])
    await client.post("/lists/join", headers=other_user.headers, json={"code": invite["code"]})

    removed = await client.delete(
        f"/lists/{shopping_list['id']}/members/{other_user.user_id}", headers=user.headers
    )
    assert removed.status_code == 200
    assert (
        await client.get(f"/lists/{shopping_list['id']}", headers=other_user.headers)
    ).status_code == 404


async def test_member_leaves_by_deleting_list(
    client: httpx.AsyncClient, user, other_user, shopping_list
) -> None:
    invite = await create_invite(client, user, shopping_list["id"])
    await client.post("/lists/join", headers=other_user.headers, json={"code": invite["code"]})

    left = await client.delete(f"/lists/{shopping_list['id']}", headers=other_user.headers)
    assert left.status_code == 200
    assert left.json()["left_shared_list"] is True

    # The list itself survives for the owner.
    assert (
        await client.get(f"/lists/{shopping_list['id']}", headers=user.headers)
    ).status_code == 200


async def test_unshare_revokes_everything(
    client: httpx.AsyncClient, user, other_user, shopping_list
) -> None:
    invite = await create_invite(client, user, shopping_list["id"])
    await client.post("/lists/join", headers=other_user.headers, json={"code": invite["code"]})

    response = await client.delete(f"/lists/{shopping_list['id']}/share", headers=user.headers)
    assert response.status_code == 200
    body = response.json()
    assert body["is_shared"] is False
    assert body["member_count"] == 1
    assert body["active_invites"] == 0

    assert (
        await client.get(f"/lists/{shopping_list['id']}", headers=other_user.headers)
    ).status_code == 404
    assert (
        await client.post(
            "/lists/join", headers=other_user.headers, json={"code": invite["code"]}
        )
    ).status_code == 400


async def test_share_state(client: httpx.AsyncClient, user, shopping_list) -> None:
    await create_invite(client, user, shopping_list["id"])
    response = await client.get(f"/lists/{shopping_list['id']}/share", headers=user.headers)
    assert response.status_code == 200
    body = response.json()
    assert body["is_shared"] is True
    assert body["active_invites"] == 1
