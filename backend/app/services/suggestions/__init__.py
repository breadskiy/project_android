"""Suggestion engine: providers, scoring and the public service API."""

from __future__ import annotations

from app.services.suggestions.base import Suggestion, SuggestionProviderProtocol
from app.services.suggestions.service import (
    get_engine_status,
    rebuild_statistics,
    record_feedback,
    suggest_for_items,
    suggest_for_list,
    suggestions_enabled_for,
)

__all__ = [
    "Suggestion",
    "SuggestionProviderProtocol",
    "get_engine_status",
    "rebuild_statistics",
    "record_feedback",
    "suggest_for_items",
    "suggest_for_list",
    "suggestions_enabled_for",
]
