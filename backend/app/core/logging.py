"""Logging configuration."""

from __future__ import annotations

import logging
import sys

from app.config import settings

_CONFIGURED = False

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging() -> None:
    """Configure root logging once, aligning uvicorn loggers with our level."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = getattr(logging, settings.LOG_LEVEL, logging.INFO)

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
        logger.setLevel(level)

    # psycopg's pool logs every checkout/return at INFO, which buries the
    # application's own messages. Only warnings are useful in practice.
    logging.getLogger("psycopg").setLevel(max(level, logging.WARNING))
    logging.getLogger("psycopg.pool").setLevel(max(level, logging.WARNING))

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
