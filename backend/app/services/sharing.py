"""Sharing: invite codes, membership management, import links, QR codes.

Why invite codes instead of the legacy ``smartsupply://share/<list-uuid>``:
the list UUID is a durable identifier that appears in URLs, logs and client
storage. Using it as the access key means the key can never be rotated. An
invite code is revocable, can expire, can be use-limited, and revoking it does
not break the list itself. Legacy links are still accepted for compatibility.
"""

from __future__ import annotations

import io
from typing import Any
from uuid import UUID

from app.config import settings
from app.core.errors import (
    InviteInvalidError,
    LimitExceededError,
    ListNotFoundError,
    PermissionDeniedError,
    SystemListError,
    ValidationError,
)
from app.core.logging import get_logger
from app.db.pool import Row, run_in_thread
from app.repositories import invites as invites_repo
from app.repositories import lists as lists_repo
from app.repositories import suggestions as suggestions_repo
from app.services.lists import _require_membership

logger = get_logger("smartsupply.sharing")

SCHEME = "smartsupply"
JOIN_HOST = "join"
LEGACY_SHARE_HOST = "share"
LEGACY_COPY_HOST = "copy"


def build_link(code: str) -> str:
    return f"{SCHEME}://{JOIN_HOST}/{code}"


def build_qr_url(code: str) -> str:
    return f"/lists/invites/{code}/qr"


def _invite_payload(row: Row) -> dict[str, Any]:
    code = row["code"]
    return {
        **row,
        "link": build_link(code),
        "qr_svg_url": build_qr_url(code),
    }


# ------------------------------------------------------------------ invites


def _create_invite_sync(
    list_id: str,
    user_id: str,
    *,
    mode: str,
    role: str,
    expires_in_hours: int | None,
    max_uses: int | None,
) -> dict[str, Any]:
    membership = _require_membership(list_id, user_id, min_role="owner")
    if membership.get("is_system"):
        raise SystemListError("Системный список «⭐ Избранное» нельзя расшарить")

    if invites_repo.count_active(list_id) >= 20:
        raise LimitExceededError("Слишком много активных приглашений для этого списка")

    # A plain "share this list" click should keep handing out the same code
    # instead of accumulating one code per click.
    if expires_in_hours is None and max_uses is None:
        existing = invites_repo.find_reusable(list_id=list_id, mode=mode, role=role)
        if existing is not None:
            if mode == "share":
                lists_repo.set_shared(list_id, True)
            return _invite_payload(existing)

    created = invites_repo.create(
        list_id=list_id,
        created_by=user_id,
        mode=mode,
        role=role,
        expires_in_hours=expires_in_hours,
        max_uses=max_uses,
    )

    if mode == "share":
        lists_repo.set_shared(list_id, True)

    suggestions_repo.log_event(
        user_id=user_id,
        event_type="click",
        entity_type="shopping_list",
        entity_id=list_id,
        metadata={"action": "create_invite", "mode": mode, "role": role},
    )
    return _invite_payload(created)


async def create_invite(
    list_id: str,
    user_id: str,
    *,
    mode: str = "share",
    role: str = "editor",
    expires_in_hours: int | None = None,
    max_uses: int | None = None,
) -> dict[str, Any]:
    return await run_in_thread(
        _create_invite_sync,
        list_id,
        user_id,
        mode=mode,
        role=role,
        expires_in_hours=expires_in_hours,
        max_uses=max_uses,
    )


def _list_invites_sync(list_id: str, user_id: str) -> list[dict[str, Any]]:
    _require_membership(list_id, user_id, min_role="owner")
    return [_invite_payload(row) for row in invites_repo.list_for_list(list_id)]


async def list_invites(list_id: str, user_id: str) -> list[dict[str, Any]]:
    return await run_in_thread(_list_invites_sync, list_id, user_id)


def _revoke_invite_sync(list_id: str, user_id: str, code: str) -> None:
    _require_membership(list_id, user_id, min_role="owner")
    if not invites_repo.revoke(list_id, code):
        raise InviteInvalidError("Приглашение не найдено или уже отозвано")


async def revoke_invite(list_id: str, user_id: str, code: str) -> None:
    await run_in_thread(_revoke_invite_sync, list_id, user_id, code)


def _preview_sync(code: str, user_id: str) -> dict[str, Any]:
    invite = invites_repo.get_by_code(code)
    if invite is None or invite["revoked"]:
        raise InviteInvalidError()

    from app.core.security import utcnow

    if invite["expires_at"] is not None and invite["expires_at"] <= utcnow():
        raise InviteInvalidError("Срок действия приглашения истек")
    if invite["max_uses"] is not None and invite["uses"] >= invite["max_uses"]:
        raise InviteInvalidError("Приглашение уже использовано максимальное число раз")

    membership = lists_repo.get_membership(str(invite["list_id"]), user_id)

    return {
        "code": invite["code"],
        "list_name": invite["list_name"],
        "owner_name": invite["owner_name"],
        "mode": invite["mode"],
        "role": invite["role"],
        "item_count": int(invite["item_count"]),
        "member_count": int(invite["member_count"]),
        "already_member": membership is not None,
        "expires_at": invite["expires_at"],
    }


async def preview_invite(code: str, user_id: str) -> dict[str, Any]:
    return await run_in_thread(_preview_sync, code, user_id)


# -------------------------------------------------------------------- join


def _join_by_code_sync(code: str, user_id: str) -> dict[str, Any]:
    invite = invites_repo.get_by_code(code)
    if invite is None or invite["revoked"]:
        raise InviteInvalidError()

    list_id = str(invite["list_id"])

    if str(invite["owner_id"]) == user_id and invite["mode"] == "share":
        raise ValidationError("Вы владелец этого списка")

    existing = lists_repo.get_membership(list_id, user_id)
    if existing is not None and invite["mode"] == "share":
        return {
            "ok": True,
            "message": "Вы уже участник этого списка",
            "list_id": UUID(list_id),
            "mode": "share",
            "role": existing["role"],
        }

    # Atomic validate-and-increment: two people using a single-use code
    # concurrently cannot both get in.
    consumed = invites_repo.consume(code)
    if consumed is None:
        raise InviteInvalidError("Приглашение недействительно, истекло или исчерпано")

    if invite["mode"] == "copy":
        new_list_id = lists_repo.copy_list_as_new(
            source_list_id=list_id,
            user_id=user_id,
            new_name=f"{invite['list_name']} (Копия)",
        )
        suggestions_repo.log_event(
            user_id=user_id,
            event_type="add_to_cart",
            entity_type="shopping_list",
            entity_id=new_list_id,
            metadata={"action": "import_copy", "source_list_id": list_id},
        )
        return {
            "ok": True,
            "message": "Копия списка сохранена в ваши списки",
            "list_id": UUID(new_list_id),
            "mode": "copy",
            "role": "owner",
        }

    if lists_repo.count_members(list_id) >= settings.MAX_MEMBERS_PER_LIST:
        raise LimitExceededError(
            f"В списке не может быть больше {settings.MAX_MEMBERS_PER_LIST} участников"
        )

    lists_repo.add_member(
        list_id=list_id,
        user_id=user_id,
        role=invite["role"],
        invited_by=str(invite["owner_id"]),
    )
    suggestions_repo.log_event(
        user_id=user_id,
        event_type="click",
        entity_type="shopping_list",
        entity_id=list_id,
        metadata={"action": "join_shared", "role": invite["role"]},
    )

    return {
        "ok": True,
        "message": "Вы присоединились к общему списку",
        "list_id": UUID(list_id),
        "mode": "share",
        "role": invite["role"],
    }


async def join_by_code(code: str, user_id: str) -> dict[str, Any]:
    return await run_in_thread(_join_by_code_sync, code, user_id)


def parse_import_link(link: str) -> tuple[str, str]:
    """Parse an import link into ``(kind, value)``.

    ``kind`` is ``"code"`` for the current format, or ``"legacy_share"`` /
    ``"legacy_copy"`` for links produced by the CLI version.
    """
    from urllib.parse import urlparse

    parsed = urlparse(link.strip())
    if parsed.scheme != SCHEME:
        raise ValidationError("Недопустимая ссылка импорта")

    value = parsed.path.strip("/")
    if not value:
        raise ValidationError("Ссылка не содержит идентификатор")

    if parsed.netloc == JOIN_HOST:
        code = value.upper()
        if not 8 <= len(code) <= 64 or not code.isalnum():
            raise ValidationError("Некорректный код приглашения")
        return "code", code

    if parsed.netloc in (LEGACY_SHARE_HOST, LEGACY_COPY_HOST):
        try:
            list_uuid = str(UUID(value))
        except ValueError as exc:
            raise ValidationError("Некорректный идентификатор списка") from exc
        kind = "legacy_share" if parsed.netloc == LEGACY_SHARE_HOST else "legacy_copy"
        return kind, list_uuid

    raise ValidationError("Недопустимая ссылка импорта")


def _import_legacy_sync(kind: str, list_id: str, user_id: str) -> dict[str, Any]:
    """Honour links from the CLI era, where the list UUID was the key."""
    source = lists_repo.get_list_raw(list_id)
    if source is None:
        raise ListNotFoundError()

    if kind == "legacy_copy":
        new_list_id = lists_repo.copy_list_as_new(
            source_list_id=list_id,
            user_id=user_id,
            new_name=f"{source['name']} (Копия)",
        )
        return {
            "ok": True,
            "message": "Копия списка сохранена в ваши списки",
            "list_id": UUID(new_list_id),
            "mode": "copy",
            "role": "owner",
        }

    existing = lists_repo.get_membership(list_id, user_id)
    if existing is not None:
        return {
            "ok": True,
            "message": "Вы уже участник этого списка",
            "list_id": UUID(list_id),
            "mode": "share",
            "role": existing["role"],
        }

    if not source["is_shared"]:
        raise InviteInvalidError("Список не является общим")

    if lists_repo.count_members(list_id) >= settings.MAX_MEMBERS_PER_LIST:
        raise LimitExceededError(
            f"В списке не может быть больше {settings.MAX_MEMBERS_PER_LIST} участников"
        )

    lists_repo.add_member(
        list_id=list_id,
        user_id=user_id,
        role="editor",
        invited_by=str(source["owner_id"]),
    )
    return {
        "ok": True,
        "message": "Вы присоединились к общему списку",
        "list_id": UUID(list_id),
        "mode": "share",
        "role": "editor",
    }


async def import_link(link: str, user_id: str) -> dict[str, Any]:
    kind, value = parse_import_link(link)
    if kind == "code":
        return await join_by_code(value, user_id)
    return await run_in_thread(_import_legacy_sync, kind, value, user_id)


# -------------------------------------------------------------- membership


def _members_sync(list_id: str, user_id: str) -> list[dict[str, Any]]:
    membership = _require_membership(list_id, user_id)
    from app.services.lists import _members_payload

    return _members_payload(list_id, user_id, bool(membership["is_owner"]))


async def get_members(list_id: str, user_id: str) -> list[dict[str, Any]]:
    return await run_in_thread(_members_sync, list_id, user_id)


def _update_member_sync(list_id: str, owner_id: str, member_id: str, role: str) -> None:
    _require_membership(list_id, owner_id, min_role="owner")
    if member_id == owner_id:
        raise ValidationError("Нельзя изменить свою собственную роль владельца")
    if not lists_repo.update_member_role(list_id, member_id, role):
        raise ListNotFoundError("Участник не найден")


async def update_member_role(list_id: str, owner_id: str, member_id: str, role: str) -> None:
    await run_in_thread(_update_member_sync, list_id, owner_id, member_id, role)


def _remove_member_sync(list_id: str, actor_id: str, member_id: str) -> None:
    membership = _require_membership(list_id, actor_id)

    # Owners can remove anyone; a member can only remove themselves (leave).
    if not membership["is_owner"] and member_id != actor_id:
        raise PermissionDeniedError("Только владелец может удалять других участников")

    if not lists_repo.remove_member(list_id, member_id):
        raise ListNotFoundError("Участник не найден")


async def remove_member(list_id: str, actor_id: str, member_id: str) -> None:
    await run_in_thread(_remove_member_sync, list_id, actor_id, member_id)


def _unshare_sync(list_id: str, user_id: str) -> dict[str, Any]:
    _require_membership(list_id, user_id, min_role="owner")

    revoked = invites_repo.revoke_all(list_id)
    for member in lists_repo.get_members(list_id):
        if member["role"] != "owner":
            lists_repo.remove_member(list_id, str(member["user_id"]))
    lists_repo.set_shared(list_id, False)

    logger.info("List %s unshared (%d invites revoked)", list_id, revoked)
    return {
        "ok": True,
        "list_id": UUID(list_id),
        "is_shared": False,
        "member_count": lists_repo.count_members(list_id),
        "active_invites": 0,
    }


async def unshare(list_id: str, user_id: str) -> dict[str, Any]:
    return await run_in_thread(_unshare_sync, list_id, user_id)


def _share_state_sync(list_id: str, user_id: str) -> dict[str, Any]:
    _require_membership(list_id, user_id)
    row = lists_repo.get_list(list_id, user_id)
    if row is None:
        raise ListNotFoundError()
    return {
        "ok": True,
        "list_id": row["id"],
        "is_shared": row["is_shared"],
        "member_count": int(row["member_count"]),
        "active_invites": invites_repo.count_active(list_id),
    }


async def get_share_state(list_id: str, user_id: str) -> dict[str, Any]:
    return await run_in_thread(_share_state_sync, list_id, user_id)


# ------------------------------------------------------------------- QR code


def render_qr_svg(code: str) -> str:
    """Render an invite link as an SVG QR code.

    SVG is generated in pure Python by ``qrcode``, so Pillow is not required.
    """
    import qrcode
    import qrcode.image.svg

    img = qrcode.make(
        build_link(code),
        image_factory=qrcode.image.svg.SvgPathImage,
        box_size=10,
        border=2,
    )
    buffer = io.BytesIO()
    img.save(buffer)
    return buffer.getvalue().decode("utf-8")
