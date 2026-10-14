"""FastAPI API for SmartSupply.

The existing db.py functions are kept as the persistence/business layer.
This module replaces the interactive CLI with authenticated HTTP endpoints.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass
from time import monotonic
from typing import Any, Awaitable, Callable, Deque, TypeVar
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from db import (
    add_item_to_list,
    clear_list_items,
    copy_list,
    create_shopping_list,
    delete_item_from_list,
    delete_shopping_list,
    ensure_favorites_list,
    get_list_items,
    get_shopping_lists,
    join_shared_list,
    login_user,
    make_list_shared,
    register_user,
    rename_item,
    rename_shopping_list,
    verify_token,
)

logger = logging.getLogger("smartsupply.api")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_BODY_BYTES = int(os.getenv("MAX_BODY_BYTES", "1048576"))  # 1 MiB
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "120"))
AUTH_RATE_LIMIT_REQUESTS = int(os.getenv("AUTH_RATE_LIMIT_REQUESTS", "10"))

EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _csv_env(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


ALLOWED_ORIGINS = _csv_env("CORS_ORIGINS", "http://localhost:3000")


# ---------------------------------------------------------------------------
# Small in-process rate limiter.
# For multiple workers / multiple instances, put rate limiting at the reverse
# proxy/API gateway or use a shared store such as Redis.
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class _Bucket:
    timestamps: Deque[float]


class RateLimiter:
    def __init__(self, limit: int, window: int) -> None:
        self.limit = limit
        self.window = window
        self._buckets: dict[str, _Bucket] = defaultdict(lambda: _Bucket(deque()))
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        now = monotonic()
        async with self._lock:
            bucket = self._buckets[key]
            cutoff = now - self.window
            while bucket.timestamps and bucket.timestamps[0] <= cutoff:
                bucket.timestamps.popleft()
            if len(bucket.timestamps) >= self.limit:
                return False
            bucket.timestamps.append(now)
            # Avoid unbounded growth of inactive keys.
            if len(self._buckets) > 10_000:
                stale = [k for k, b in self._buckets.items() if not b.timestamps or b.timestamps[-1] <= cutoff]
                for stale_key in stale[:2_000]:
                    self._buckets.pop(stale_key, None)
            return True


request_limiter = RateLimiter(RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW)
auth_limiter = RateLimiter(AUTH_RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW)

T = TypeVar("T")


async def run_db(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run the synchronous db.py layer without blocking the event loop."""
    return await asyncio.to_thread(func, *args, **kwargs)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RegisterRequest(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_RE.fullmatch(value):
            raise ValueError("Некорректный email")
        return value

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Имя не может быть пустым")
        return value


class LoginRequest(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_RE.fullmatch(value):
            raise ValueError("Некорректный email")
        return value


class CreateListRequest(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    items: list[str] = Field(default_factory=list, max_length=500)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Название списка не может быть пустым")
        return value

    @field_validator("items")
    @classmethod
    def validate_items(cls, value: list[str]) -> list[str]:
        cleaned = []
        for item in value:
            item = item.strip()
            if not item:
                continue
            if len(item) > 300:
                raise ValueError("Название товара не может быть длиннее 300 символов")
            cleaned.append(item)
        return cleaned


class ItemRequest(StrictModel):
    name: str = Field(min_length=1, max_length=300)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Название товара не может быть пустым")
        return value


class CopyItemsRequest(StrictModel):
    item_ids: list[str] = Field(min_length=1, max_length=500)
    target_list_ids: list[str] = Field(min_length=1, max_length=100)

    @field_validator("item_ids", "target_list_ids")
    @classmethod
    def validate_ids(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("ID не должны повторяться")
        for item_id in value:
            if not ID_RE.fullmatch(item_id):
                raise ValueError("Некорректный ID")
        return value


class ImportLinkRequest(StrictModel):
    link: str = Field(min_length=1, max_length=512)


# ---------------------------------------------------------------------------
# Authentication / authorization helpers
# ---------------------------------------------------------------------------


def _extract_bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, credentials = header.partition(" ")
    if scheme.lower() != "bearer" or not credentials.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется Bearer-токен",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.strip()
    # Never accept arbitrarily large auth headers.
    if len(token) > 4096:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Некорректный токен")
    return token


async def get_current_auth(request: Request) -> dict[str, Any]:
    token = _extract_bearer_token(request)
    auth = await run_db(verify_token, token)
    if not isinstance(auth, dict) or not auth.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(auth or {}).get("message", "Недействительный токен"),
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = str(auth.get("user_id", ""))
    if not user_id or len(user_id) > 128:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Некорректные данные авторизации")
    return {**auth, "user_id": user_id, "token": token}


def _normalize_list(row: tuple[Any, ...], user_id: str) -> dict[str, Any]:
    """Map legacy db tuple shape to a stable JSON representation."""
    l_id, l_name, l_count, is_shared, members, owner_name, owner_id = row
    return {
        "id": str(l_id),
        "name": str(l_name),
        "item_count": int(l_count),
        "is_shared": bool(is_shared),
        "members": [str(x) for x in (members or []) if x],
        "owner_name": owner_name,
        "owner_id": str(owner_id),
        "access": "owned" if str(owner_id) == user_id else "member",
    }


async def _get_user_lists(user_id: str) -> list[tuple[Any, ...]]:
    rows = await run_db(get_shopping_lists, user_id)
    if not isinstance(rows, list):
        return []
    return rows


async def _get_user_list_or_404(user_id: str, list_id: str) -> tuple[Any, ...]:
    if not ID_RE.fullmatch(list_id):
        raise HTTPException(status_code=400, detail="Некорректный ID списка")
    rows = await _get_user_lists(user_id)
    for row in rows:
        if str(row[0]) == list_id:
            return row
    raise HTTPException(status_code=404, detail="Список не найден или недоступен")


async def _require_owned_list(user_id: str, list_id: str) -> tuple[Any, ...]:
    row = await _get_user_list_or_404(user_id, list_id)
    if str(row[6]) != user_id:
        raise HTTPException(status_code=403, detail="Только владелец может выполнять эту операцию")
    return row


async def _get_item_or_404(list_id: str, item_id: str) -> tuple[Any, ...]:
    if not ID_RE.fullmatch(item_id):
        raise HTTPException(status_code=400, detail="Некорректный ID товара")
    items = await run_db(get_list_items, list_id)
    for item in items or []:
        if str(item[0]) == item_id:
            return item
    raise HTTPException(status_code=404, detail="Товар не найден")


# ---------------------------------------------------------------------------
# App + middleware
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("SmartSupply API started")
    yield
    logger.info("SmartSupply API stopped")


app = FastAPI(
    title="SmartSupply API",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_and_limits(request: Request, call_next: Callable[[Request], Awaitable[JSONResponse]]):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_BODY_BYTES:
                return JSONResponse(status_code=413, content={"detail": "Request body too large"})
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length"})

    client_host = request.client.host if request.client else "unknown"
    if not await request_limiter.allow(client_host):
        return JSONResponse(status_code=429, content={"detail": "Слишком много запросов"})

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-XSS-Protection"] = "0"
    return response


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {
        "name": "Smart Supply Lists API",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
    }

@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/register", status_code=status.HTTP_201_CREATED, tags=["auth"])
async def register(payload: RegisterRequest, request: Request) -> dict[str, Any]:
    key = f"register:{request.client.host if request.client else 'unknown'}"
    if not await auth_limiter.allow(key):
        raise HTTPException(status_code=429, detail="Слишком много попыток регистрации")

    try:
        result = await run_db(
            register_user,
            email=payload.email,
            password=payload.password,
            display_name=payload.display_name,
        )
    except Exception:
        logger.exception("Registration failed")
        raise HTTPException(status_code=500, detail="Ошибка регистрации") from None

    if not isinstance(result, dict):
        raise HTTPException(status_code=500, detail="Некорректный ответ слоя данных")
    if result.get("ok") is False:
        raise HTTPException(status_code=400, detail=str(result.get("message", "Регистрация не выполнена")))
    return result


@app.post("/auth/login", tags=["auth"])
async def login(payload: LoginRequest, request: Request) -> dict[str, Any]:
    key = f"login:{request.client.host if request.client else 'unknown'}:{payload.email}"
    if not await auth_limiter.allow(key):
        raise HTTPException(status_code=429, detail="Слишком много попыток входа")

    try:
        result = await run_db(login_user, payload.email, payload.password)
    except Exception:
        logger.exception("Login failed")
        # Do not leak DB/authentication internals.
        raise HTTPException(status_code=500, detail="Ошибка авторизации") from None

    if not isinstance(result, dict) or not result.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверные учетные данные",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return result


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------

@app.get("/me", tags=["account"])
async def me(auth: dict[str, Any] = Depends(get_current_auth)) -> dict[str, Any]:
    return {
        "user_id": auth["user_id"],
        "display_name": auth.get("display_name"),
        "email": auth.get("email"),
    }


@app.get("/lists", tags=["lists"])
async def list_my_lists(auth: dict[str, Any] = Depends(get_current_auth)) -> dict[str, Any]:
    await run_db(ensure_favorites_list, auth["user_id"])
    rows = await _get_user_lists(auth["user_id"])
    return {"items": [_normalize_list(row, auth["user_id"]) for row in rows]}


@app.post("/lists", status_code=status.HTTP_201_CREATED, tags=["lists"])
async def create_list(payload: CreateListRequest, auth: dict[str, Any] = Depends(get_current_auth)) -> dict[str, Any]:
    try:
        result = await run_db(create_shopping_list, auth["user_id"], payload.name, payload.items)
    except Exception:
        logger.exception("Create list failed")
        raise HTTPException(status_code=500, detail="Не удалось создать список") from None
    return {"result": result, "name": payload.name}


@app.get("/lists/{list_id}", tags=["lists"])
async def get_list(list_id: str, auth: dict[str, Any] = Depends(get_current_auth)) -> dict[str, Any]:
    row = await _get_user_list_or_404(auth["user_id"], list_id)
    items = await run_db(get_list_items, list_id)
    normalized = _normalize_list(row, auth["user_id"])
    normalized["items"] = [{"id": str(i[0]), "name": str(i[1])} for i in (items or [])]
    return normalized


@app.patch("/lists/{list_id}", tags=["lists"])
async def rename_list(
    list_id: str,
    payload: ItemRequest,
    auth: dict[str, Any] = Depends(get_current_auth),
) -> dict[str, Any]:
    await _get_user_list_or_404(auth["user_id"], list_id)
    ok, message = await run_db(rename_shopping_list, list_id, payload.name)
    if not ok:
        raise HTTPException(status_code=400, detail=str(message))
    return {"ok": True, "message": str(message)}


@app.delete("/lists/{list_id}", tags=["lists"])
async def delete_list(list_id: str, auth: dict[str, Any] = Depends(get_current_auth)) -> dict[str, Any]:
    await _get_user_list_or_404(auth["user_id"], list_id)
    ok, message = await run_db(delete_shopping_list, auth["user_id"], list_id)
    if not ok:
        raise HTTPException(status_code=400, detail=str(message))
    return {"ok": True, "message": str(message)}


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------

@app.post("/lists/{list_id}/items", status_code=status.HTTP_201_CREATED, tags=["items"])
async def add_item(
    list_id: str,
    payload: ItemRequest,
    auth: dict[str, Any] = Depends(get_current_auth),
) -> dict[str, Any]:
    await _get_user_list_or_404(auth["user_id"], list_id)
    result = await run_db(add_item_to_list, list_id, payload.name)
    return {"result": result}


@app.patch("/lists/{list_id}/items/{item_id}", tags=["items"])
async def edit_item(
    list_id: str,
    item_id: str,
    payload: ItemRequest,
    auth: dict[str, Any] = Depends(get_current_auth),
) -> dict[str, Any]:
    await _get_user_list_or_404(auth["user_id"], list_id)
    await _get_item_or_404(list_id, item_id)
    ok = await run_db(rename_item, item_id, payload.name)
    if not ok:
        raise HTTPException(status_code=400, detail="Не удалось изменить товар")
    return {"ok": True}


@app.delete("/lists/{list_id}/items/{item_id}", tags=["items"])
async def delete_item(
    list_id: str,
    item_id: str,
    auth: dict[str, Any] = Depends(get_current_auth),
) -> dict[str, Any]:
    await _get_user_list_or_404(auth["user_id"], list_id)
    await _get_item_or_404(list_id, item_id)
    result = await run_db(delete_item_from_list, item_id)
    return {"result": result}


@app.delete("/lists/{list_id}/items", tags=["items"])
async def clear_items(list_id: str, auth: dict[str, Any] = Depends(get_current_auth)) -> dict[str, Any]:
    await _get_user_list_or_404(auth["user_id"], list_id)
    ok = await run_db(clear_list_items, list_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Не удалось очистить список")
    return {"ok": True}


@app.post("/lists/{list_id}/items/copy", tags=["items"])
async def copy_items(
    list_id: str,
    payload: CopyItemsRequest,
    auth: dict[str, Any] = Depends(get_current_auth),
) -> dict[str, Any]:
    await _get_user_list_or_404(auth["user_id"], list_id)

    source_items = await run_db(get_list_items, list_id)
    source_by_id = {str(item[0]): str(item[1]) for item in (source_items or [])}
    missing_items = [item_id for item_id in payload.item_ids if item_id not in source_by_id]
    if missing_items:
        raise HTTPException(status_code=404, detail="Один или несколько товаров недоступны")

    # Target authorization is checked before any write to prevent IDOR.
    user_rows = await _get_user_lists(auth["user_id"])
    allowed_targets = {str(row[0]) for row in user_rows}
    invalid_targets = [target for target in payload.target_list_ids if target not in allowed_targets or target == list_id]
    if invalid_targets:
        raise HTTPException(status_code=403, detail="Один или несколько целевых списков недоступны")

    copied = 0
    for target_id in payload.target_list_ids:
        for item_name in (source_by_id[item_id] for item_id in payload.item_ids):
            await run_db(add_item_to_list, target_id, item_name)
            copied += 1
    return {"ok": True, "copied_items": copied, "target_lists": len(payload.target_list_ids)}


# ---------------------------------------------------------------------------
# Sharing / importing
# ---------------------------------------------------------------------------

@app.post("/lists/{list_id}/share", tags=["sharing"])
async def share_list(list_id: str, auth: dict[str, Any] = Depends(get_current_auth)) -> dict[str, Any]:
    await _require_owned_list(auth["user_id"], list_id)
    result = await run_db(make_list_shared, list_id)
    return {"ok": True, "share_link": f"smartsupply://share/{list_id}", "result": result}


@app.post("/lists/{list_id}/copy-link", tags=["sharing"])
async def get_copy_link(list_id: str, auth: dict[str, Any] = Depends(get_current_auth)) -> dict[str, str]:
    await _get_user_list_or_404(auth["user_id"], list_id)
    return {"copy_link": f"smartsupply://copy/{list_id}"}


@app.post("/lists/import", tags=["sharing"])
async def import_list(payload: ImportLinkRequest, auth: dict[str, Any] = Depends(get_current_auth)) -> dict[str, Any]:
    parsed = urlparse(payload.link)
    if parsed.scheme != "smartsupply" or parsed.netloc not in {"share", "copy"}:
        raise HTTPException(status_code=400, detail="Недопустимая ссылка импорта")

    list_id = parsed.path.strip("/")
    if not ID_RE.fullmatch(list_id):
        raise HTTPException(status_code=400, detail="Некорректный ID списка")

    if parsed.netloc == "share":
        ok, message = await run_db(join_shared_list, auth["user_id"], list_id)
    else:
        ok, message = await run_db(copy_list, auth["user_id"], list_id)

    if not ok:
        raise HTTPException(status_code=400, detail=str(message))
    return {"ok": True, "message": str(message), "list_id": list_id, "mode": parsed.netloc}


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Внутренняя ошибка сервера"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("UVICORN_RELOAD", "false").lower() == "true",
        proxy_headers=os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true",
    )
