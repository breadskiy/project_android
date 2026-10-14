"""Entry point for the Smart Supply Lists API.

Run with:
    python main.py
    # or
    uvicorn main:app --reload

The application itself lives in the ``app`` package; this module only wires up
the ASGI object and the development server.
"""

from __future__ import annotations

from app.config import settings
from app.main import app

__all__ = ["app"]


def main() -> None:
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.UVICORN_RELOAD,
        proxy_headers=settings.TRUST_PROXY_HEADERS,
        forwarded_allow_ips="*" if settings.TRUST_PROXY_HEADERS else None,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
