"""Sharing, invite and import schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator

from app.schemas.common import ResponseModel, StrictModel
from app.schemas.lists import ListRole

InviteCodeStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_upper=True, min_length=8, max_length=64),
]


class ShareMode(StrEnum):
    SHARE = "share"
    COPY = "copy"


class CreateInviteRequest(StrictModel):
    mode: ShareMode = Field(
        default=ShareMode.SHARE,
        description="share — совместное редактирование; copy — независимая копия",
    )
    role: ListRole = Field(
        default=ListRole.EDITOR,
        description="Роль присоединившегося (для mode=share)",
    )
    expires_in_hours: int | None = Field(default=None, ge=1, le=8760)
    max_uses: int | None = Field(default=None, ge=1, le=1000)

    @field_validator("role")
    @classmethod
    def owner_role_not_allowed(cls, value: ListRole) -> ListRole:
        if value is ListRole.OWNER:
            raise ValueError("Роль 'owner' нельзя выдать по приглашению")
        return value


class InviteResponse(ResponseModel):
    id: UUID
    list_id: UUID
    code: str = Field(examples=["K7M2QXJ4TB9P"])
    mode: ShareMode
    role: ListRole
    link: str = Field(
        description="Ссылка для импорта",
        examples=["smartsupply://join/K7M2QXJ4TB9P"],
    )
    qr_svg_url: str = Field(
        description="Относительный URL с QR-кодом в формате SVG",
        examples=["/lists/invites/K7M2QXJ4TB9P/qr"],
    )
    expires_at: datetime | None = None
    max_uses: int | None = None
    uses: int = Field(ge=0)
    revoked: bool = False
    created_at: datetime


class InviteListResponse(ResponseModel):
    items: list[InviteResponse]


class InvitePreview(ResponseModel):
    """Safe, pre-join view of an invite: no list contents are exposed."""

    code: str
    list_name: str
    owner_name: str | None = None
    mode: ShareMode
    role: ListRole
    item_count: int = Field(ge=0)
    member_count: int = Field(ge=1)
    already_member: bool = False
    expires_at: datetime | None = None


class JoinByCodeRequest(StrictModel):
    code: InviteCodeStr


class ImportLinkRequest(StrictModel):
    link: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)] = Field(
        examples=["smartsupply://join/K7M2QXJ4TB9P"],
        description=(
            "Поддерживаются smartsupply://join/<код>, а также legacy-ссылки "
            "smartsupply://share/<uuid> и smartsupply://copy/<uuid>"
        ),
    )


class JoinResponse(ResponseModel):
    ok: bool = True
    message: str
    list_id: UUID
    mode: ShareMode
    role: ListRole


class UpdateMemberRequest(StrictModel):
    role: ListRole

    @field_validator("role")
    @classmethod
    def owner_role_not_transferable(cls, value: ListRole) -> ListRole:
        if value is ListRole.OWNER:
            raise ValueError("Передача владения не поддерживается")
        return value


class ShareStateResponse(ResponseModel):
    ok: bool = True
    list_id: UUID
    is_shared: bool
    member_count: int = Field(ge=1)
    active_invites: int = Field(ge=0)
