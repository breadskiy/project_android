"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_error_handlers
from app.api.middleware import register_middleware
from app.api.routers import auth as auth_router
from app.api.routers import catalog as catalog_router
from app.api.routers import items as items_router
from app.api.routers import lists as lists_router
from app.api.routers import sharing as sharing_router
from app.api.routers import smart as smart_router
from app.api.routers import suggestions as suggestions_router
from app.api.routers import system as system_router
from app.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.migrator import run_migrations
from app.db.pool import close_pool, init_pool

logger = get_logger("smartsupply")

DESCRIPTION = """
Бэкенд приложения **«Умный список покупок»**.

Возможности:

* личные списки покупок с товарами, количеством и отметкой «куплено»;
* совместная работа над списком: приглашения по коду, роли участников, QR-код;
* подсказки «часто покупают вместе» с возможностью полного отключения;
* каталог товаров с поиском по опечаткам для автодополнения.

**Авторизация.** Получите токены через `POST /auth/login`, затем нажмите
«Authorize» и вставьте `access_token`. Access-токен живет
{access} минут, refresh-токен — {refresh} дней и обновляется через
`POST /auth/refresh`.

**Подсказки.** Управляются флагом `ai_suggestions_enabled` в
`PATCH /me/settings`. При выключении подсказки не вычисляются.
Внешних вызовов нет: всё считается локально по таблицам БД.
""".format(
    access=settings.JWT_EXPIRE_MINUTES,
    refresh=settings.REFRESH_TOKEN_EXPIRE_DAYS,
)

TAGS_METADATA = [
    {"name": "system", "description": "Служебные эндпоинты: состояние сервиса."},
    {"name": "auth", "description": "Регистрация, вход, токены, сессии."},
    {"name": "account", "description": "Профиль и настройки, включая переключатель ИИ."},
    {"name": "lists", "description": "Списки покупок."},
    {"name": "items", "description": "Товары внутри списков."},
    {"name": "sharing", "description": "Совместный доступ: приглашения, участники, импорт."},
    {"name": "suggestions", "description": "Подсказки «часто покупают вместе»."},
    {"name": "smart", "description": "Разбор ввода («2л молока» → товар) и пополнение («что скоро закончится»)."},
    {"name": "catalog", "description": "Каталог товаров и поиск для автодополнения."},
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    init_pool()

    if settings.RUN_MIGRATIONS_ON_STARTUP:
        try:
            run_migrations()
        except Exception:
            logger.exception("Migrations failed on startup")
            raise

    logger.info(
        "%s %s started (env=%s, ai_suggestions=%s, provider=%s)",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.ENVIRONMENT,
        settings.AI_SUGGESTIONS_ENABLED,
        settings.SUGGESTIONS_PROVIDER,
    )
    try:
        yield
    finally:
        close_pool()
        logger.info("%s stopped", settings.APP_NAME)


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=DESCRIPTION,
        openapi_tags=TAGS_METADATA,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        swagger_ui_parameters={"persistAuthorization": True, "displayRequestDuration": True},
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )
    register_middleware(app)
    register_error_handlers(app)

    app.include_router(system_router.router)
    app.include_router(auth_router.router)
    app.include_router(auth_router.account_router)
    # Sharing before lists: /lists/join and /lists/invites/{code} must not be
    # captured by /lists/{list_id}.
    app.include_router(sharing_router.router)
    app.include_router(lists_router.router)
    app.include_router(items_router.router)
    app.include_router(suggestions_router.router)
    app.include_router(smart_router.router)
    app.include_router(catalog_router.router)

    return app


app = create_app()
