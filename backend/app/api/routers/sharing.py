"""Sharing endpoints: invites, members, import, QR codes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Query, status
from fastapi.responses import Response

from app.api.dependencies import CurrentUserDep
from app.schemas.common import ErrorResponse, MessageResponse
from app.schemas.lists import MemberResponse
from app.schemas.sharing import (
    CreateInviteRequest,
    ImportLinkRequest,
    InviteListResponse,
    InvitePreview,
    InviteResponse,
    JoinByCodeRequest,
    JoinResponse,
    ShareStateResponse,
    UpdateMemberRequest,
)
from app.services import sharing as sharing_service

router = APIRouter(prefix="/lists", tags=["sharing"])

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Список не найден или недоступен"}}
OWNER_ONLY = {403: {"model": ErrorResponse, "description": "Только владелец"}}

InviteCodePath = Annotated[
    str,
    Path(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9]+$", description="Код приглашения"),
]


# ------------------------------------------------------------------ invites


@router.post(
    "/{list_id}/share",
    response_model=InviteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Поделиться списком (создать приглашение)",
    description=(
        "`mode=share` — совместное редактирование, `mode=copy` — получатель "
        "получает независимую копию. Возвращается код, ссылка и URL с QR-кодом. "
        "Повторный вызов без ограничений переиспользует существующий код."
    ),
    responses={**NOT_FOUND, **OWNER_ONLY, 409: {"model": ErrorResponse, "description": "Системный список"}},
)
async def share_list(
    list_id: UUID, payload: CreateInviteRequest, current_user: CurrentUserDep
) -> InviteResponse:
    invite = await sharing_service.create_invite(
        str(list_id),
        current_user.id,
        mode=payload.mode.value,
        role=payload.role.value,
        expires_in_hours=payload.expires_in_hours,
        max_uses=payload.max_uses,
    )
    return InviteResponse(**invite)


@router.get(
    "/{list_id}/invites",
    response_model=InviteListResponse,
    summary="Активные приглашения списка",
    responses={**NOT_FOUND, **OWNER_ONLY},
)
async def list_invites(list_id: UUID, current_user: CurrentUserDep) -> InviteListResponse:
    invites = await sharing_service.list_invites(str(list_id), current_user.id)
    return InviteListResponse(items=invites)  # type: ignore[arg-type]


@router.delete(
    "/{list_id}/invites/{code}",
    response_model=MessageResponse,
    summary="Отозвать приглашение",
    responses={**NOT_FOUND, **OWNER_ONLY},
)
async def revoke_invite(
    list_id: UUID, code: InviteCodePath, current_user: CurrentUserDep
) -> MessageResponse:
    await sharing_service.revoke_invite(str(list_id), current_user.id, code.upper())
    return MessageResponse(message="Приглашение отозвано")


@router.get(
    "/invites/{code}",
    response_model=InvitePreview,
    summary="Информация о приглашении до присоединения",
    description="Показывает название списка и число товаров, но не их содержимое.",
    responses={400: {"model": ErrorResponse, "description": "Приглашение недействительно"}},
)
async def preview_invite(code: InviteCodePath, current_user: CurrentUserDep) -> InvitePreview:
    preview = await sharing_service.preview_invite(code.upper(), current_user.id)
    return InvitePreview(**preview)


@router.get(
    "/invites/{code}/qr",
    summary="QR-код приглашения (SVG)",
    description="Возвращает SVG-изображение для сканирования; аналог QR из CLI-версии.",
    response_class=Response,
    responses={
        200: {"content": {"image/svg+xml": {}}, "description": "SVG с QR-кодом"},
        400: {"model": ErrorResponse, "description": "Приглашение недействительно"},
    },
)
async def invite_qr(code: InviteCodePath, current_user: CurrentUserDep) -> Response:
    # Validate the code (and the caller's right to see it) before rendering.
    await sharing_service.preview_invite(code.upper(), current_user.id)
    svg = sharing_service.render_qr_svg(code.upper())
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-store"},
    )


# --------------------------------------------------------------------- join


@router.post(
    "/join",
    response_model=JoinResponse,
    summary="Присоединиться к списку по коду",
    responses={400: {"model": ErrorResponse, "description": "Код недействителен"}},
)
async def join_by_code(payload: JoinByCodeRequest, current_user: CurrentUserDep) -> JoinResponse:
    result = await sharing_service.join_by_code(payload.code, current_user.id)
    return JoinResponse(**result)


@router.post(
    "/import",
    response_model=JoinResponse,
    summary="Импорт списка по ссылке",
    description=(
        "Принимает `smartsupply://join/<код>`, а также legacy-ссылки "
        "`smartsupply://share/<uuid>` и `smartsupply://copy/<uuid>` из "
        "терминальной версии приложения."
    ),
    responses={400: {"model": ErrorResponse, "description": "Некорректная ссылка"}, **NOT_FOUND},
)
async def import_link(payload: ImportLinkRequest, current_user: CurrentUserDep) -> JoinResponse:
    result = await sharing_service.import_link(payload.link, current_user.id)
    return JoinResponse(**result)


# ---------------------------------------------------------------- members


@router.get(
    "/{list_id}/members",
    response_model=list[MemberResponse],
    summary="Участники списка",
    description="Email участников виден только владельцу списка.",
    responses={**NOT_FOUND},
)
async def get_members(list_id: UUID, current_user: CurrentUserDep) -> list[MemberResponse]:
    members = await sharing_service.get_members(str(list_id), current_user.id)
    return [MemberResponse(**member) for member in members]


@router.patch(
    "/{list_id}/members/{member_id}",
    response_model=MessageResponse,
    summary="Изменить роль участника",
    responses={**NOT_FOUND, **OWNER_ONLY},
)
async def update_member(
    list_id: UUID,
    member_id: UUID,
    payload: UpdateMemberRequest,
    current_user: CurrentUserDep,
) -> MessageResponse:
    await sharing_service.update_member_role(
        str(list_id), current_user.id, str(member_id), payload.role.value
    )
    return MessageResponse(message=f"Роль изменена на {payload.role.value}")


@router.delete(
    "/{list_id}/members/{member_id}",
    response_model=MessageResponse,
    summary="Удалить участника (или выйти самому)",
    description="Владелец может удалить любого участника; участник — только себя.",
    responses={**NOT_FOUND, 403: {"model": ErrorResponse, "description": "Недостаточно прав"}},
)
async def remove_member(
    list_id: UUID, member_id: UUID, current_user: CurrentUserDep
) -> MessageResponse:
    await sharing_service.remove_member(str(list_id), current_user.id, str(member_id))
    return MessageResponse(message="Участник удален из списка")


# ------------------------------------------------------------- share state


@router.get(
    "/{list_id}/share",
    response_model=ShareStateResponse,
    summary="Состояние шаринга списка",
    responses={**NOT_FOUND},
)
async def share_state(list_id: UUID, current_user: CurrentUserDep) -> ShareStateResponse:
    state = await sharing_service.get_share_state(str(list_id), current_user.id)
    return ShareStateResponse(**state)


@router.delete(
    "/{list_id}/share",
    response_model=ShareStateResponse,
    summary="Прекратить совместный доступ",
    description="Отзывает все приглашения и удаляет всех участников кроме владельца.",
    responses={**NOT_FOUND, **OWNER_ONLY},
)
async def unshare(list_id: UUID, current_user: CurrentUserDep) -> ShareStateResponse:
    state = await sharing_service.unshare(str(list_id), current_user.id)
    return ShareStateResponse(**state)
