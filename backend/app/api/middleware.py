"""Security headers, body-size limit and global rate limiting."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.errors import error_body
from app.config import settings
from app.core.rate_limit import RateLimiter

request_limiter = RateLimiter(
    settings.RATE_LIMIT_REQUESTS,
    settings.RATE_LIMIT_WINDOW,
    name="requests",
)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}

# Swagger UI loads its assets from a CDN, so /docs cannot use the strict CSP.
DOCS_PATHS = frozenset({"/docs", "/redoc", "/docs/oauth2-redirect", "/openapi.json"})
STRICT_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)

        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)

        if request.url.path not in DOCS_PATHS:
            response.headers.setdefault("Content-Security-Policy", STRICT_CSP)

        # API responses are user-specific; never let a shared cache keep them.
        response.headers.setdefault("Cache-Control", "no-store")

        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized payloads before they are parsed."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                declared = int(content_length)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content=error_body("bad_request", "Некорректный заголовок Content-Length"),
                )
            if declared > settings.MAX_BODY_BYTES:
                return JSONResponse(
                    status_code=413,
                    content=error_body(
                        "payload_too_large",
                        "Тело запроса слишком большое",
                        {"max_bytes": settings.MAX_BODY_BYTES},
                    ),
                )
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Coarse per-IP limit for every endpoint."""

    EXEMPT_PATHS = frozenset({"/health", "/health/live", "/health/ready"})

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method == "OPTIONS" or request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        from app.api.dependencies import client_ip

        allowed, retry_after = await request_limiter.check(client_ip(request))
        if not allowed:
            return JSONResponse(
                status_code=429,
                content=error_body(
                    "rate_limited",
                    "Слишком много запросов, попробуйте позже",
                    {"retry_after": retry_after},
                ),
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)


def register_middleware(app: FastAPI) -> None:
    # Registered outermost-last: rate limiting runs before body checks.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(RateLimitMiddleware)
