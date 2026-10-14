"""Suggestion service: the single entry point routers use.

Responsibilities:
  * honour the user's AI toggle and the global switch
  * normalize the basket and build the cache key
  * serve from cache, otherwise ask the provider
  * write results back to the cache and log what was shown

Only the table-driven statistical engine is used (``product_pair_rules``).
Values ``llm``/``hybrid`` in ``SUGGESTIONS_PROVIDER`` are accepted for
backward compatibility but resolve to the statistical engine.
"""

from __future__ import annotations

import hashlib
from time import perf_counter
from typing import Any

from app.config import settings
from app.core.errors import PermissionDeniedError
from app.core.logging import get_logger
from app.core.normalization import normalize_item_name
from app.db.pool import run_in_thread
from app.repositories import catalog as catalog_repo
from app.repositories import lists as lists_repo
from app.repositories import suggestions as suggestions_repo
from app.repositories import users as users_repo
from app.services.suggestions.base import Suggestion, SuggestionRequest
from app.services.suggestions.statistical import StatisticalProvider

logger = get_logger("smartsupply.suggestions")

_statistical_provider = StatisticalProvider()


def _get_provider(configured: str) -> Any:
    """Resolve the active provider.

    Table-only engine. Legacy values ``llm``/``hybrid`` fall back to the
    statistical provider so old configs keep working without external calls.
    """
    if configured in ("llm", "hybrid"):
        logger.info(
            "Suggestions provider %r is legacy; using statistical engine", configured
        )
    return _statistical_provider


def basket_hash(normalized_items: list[str], limit: int) -> str:
    """Stable, order-independent cache key for a basket."""
    payload = "|".join(sorted(set(normalized_items))) + f"#{limit}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _empty_response(*, enabled: bool, provider: str, basket_size: int = 0) -> dict[str, Any]:
    return {
        "items": [],
        "provider": provider,
        "model_version": None,
        "cached": False,
        "enabled": enabled,
        "took_ms": 0,
        "basket_size": basket_size,
    }


def _load_preferences(user_id: str) -> dict[str, Any]:
    return dict(users_repo.get_preferences(user_id))


async def suggest_for_items(
    *,
    user_id: str,
    items: list[str],
    limit: int | None = None,
    list_id: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Suggestions for an explicit basket of item names."""
    started = perf_counter()
    provider_name = settings.SUGGESTIONS_PROVIDER

    if not settings.AI_SUGGESTIONS_ENABLED and not force:
        return _empty_response(enabled=False, provider=provider_name)

    prefs = await run_in_thread(_load_preferences, user_id)
    if not prefs.get("ai_suggestions_enabled", True) and not force:
        # The user switched suggestions off: nothing is computed locally.
        return _empty_response(enabled=False, provider=provider_name)

    effective_limit = min(
        limit or int(prefs.get("suggestions_limit") or settings.SUGGESTIONS_DEFAULT_LIMIT),
        settings.SUGGESTIONS_MAX_LIMIT,
    )

    normalized = [normalize_item_name(name) for name in items]
    pairs = [(raw, norm) for raw, norm in zip(items, normalized, strict=True) if norm]
    if not pairs:
        return _empty_response(enabled=True, provider=provider_name)

    raw_items = [raw for raw, _ in pairs]
    normalized_items = [norm for _, norm in pairs]

    provider = _get_provider(provider_name)
    cache_key = basket_hash(normalized_items, effective_limit)

    cached = await run_in_thread(suggestions_repo.get_cached, cache_key, provider.name)
    if cached is not None:
        payload = [Suggestion.from_dict(entry) for entry in cached["payload"]]
        return {
            "items": [s.to_dict() for s in payload],
            "provider": provider.name,
            "model_version": cached.get("model_version"),
            "cached": True,
            "enabled": True,
            "took_ms": int((perf_counter() - started) * 1000),
            "basket_size": len(normalized_items),
        }

    request = SuggestionRequest(
        user_id=user_id,
        items=raw_items,
        normalized_items=normalized_items,
        limit=effective_limit,
        list_id=list_id,
        exclude=normalized_items,
    )

    try:
        suggestions = await provider.suggest(request)
    except Exception:
        logger.exception("Suggestion provider %s failed", provider.name)
        if provider is not _statistical_provider:
            suggestions = await _statistical_provider.suggest(request)
        else:
            suggestions = []

    payload = [s.to_dict() for s in suggestions]

    if payload:
        await run_in_thread(
            suggestions_repo.store_cached,
            basket_hash=cache_key,
            provider=provider.name,
            payload=payload,
            model_version=provider.model_version,
            ttl_seconds=settings.SUGGESTIONS_CACHE_TTL_SECONDS,
        )
        await run_in_thread(
            _log_shown,
            user_id=user_id,
            list_id=list_id,
            suggestions=payload,
            based_on=raw_items,
            provider=provider.name,
            model_version=provider.model_version,
        )

    return {
        "items": payload,
        "provider": provider.name,
        "model_version": provider.model_version,
        "cached": False,
        "enabled": True,
        "took_ms": int((perf_counter() - started) * 1000),
        "basket_size": len(normalized_items),
    }


def _log_shown(
    *,
    user_id: str,
    list_id: str | None,
    suggestions: list[dict[str, Any]],
    based_on: list[str],
    provider: str,
    model_version: str | None,
) -> None:
    """Record impressions so acceptance rate can be measured later."""
    for suggestion in suggestions[:10]:
        suggestions_repo.record_feedback(
            user_id=user_id,
            list_id=list_id,
            suggested_name=suggestion["name"],
            based_on=based_on[:20],
            action="shown",
            provider=provider,
            model_version=model_version,
        )


async def suggest_for_list(
    *,
    user_id: str,
    list_id: str,
    limit: int | None = None,
    only_pending: bool = True,
) -> dict[str, Any]:
    """Suggestions for everything currently in a list the user can read."""
    membership = await run_in_thread(lists_repo.get_membership, list_id, user_id)
    if membership is None:
        from app.core.errors import ListNotFoundError

        raise ListNotFoundError()

    names = await run_in_thread(lists_repo.get_item_names, list_id, only_pending=only_pending)
    if not names:
        return _empty_response(enabled=True, provider=settings.SUGGESTIONS_PROVIDER)

    return await suggest_for_items(
        user_id=user_id, items=names, limit=limit, list_id=list_id
    )


async def suggestions_enabled_for(user_id: str) -> bool:
    """Whether suggestions should be computed for this user at all."""
    if not settings.AI_SUGGESTIONS_ENABLED:
        return False
    prefs = await run_in_thread(_load_preferences, user_id)
    return bool(prefs.get("ai_suggestions_enabled", True))


# ---------------------------------------------------------------- feedback


def _record_feedback_sync(
    *,
    user_id: str,
    suggested_name: str,
    action: str,
    list_id: str | None,
    based_on: list[str],
    provider: str | None,
) -> None:
    normalized_name = normalize_item_name(suggested_name)
    normalized_based_on = [normalize_item_name(name) for name in based_on]
    normalized_based_on = [name for name in normalized_based_on if name]

    suggestions_repo.record_feedback(
        user_id=user_id,
        list_id=list_id,
        suggested_name=suggested_name,
        based_on=based_on,
        action=action,
        provider=provider,
    )

    if action in ("accepted", "rejected") and normalized_name:
        # Feed the signal back into the rules that produced the suggestion.
        suggestions_repo.record_feedback_on_rule(
            consequent=normalized_name,
            accepted=action == "accepted",
            antecedents=normalized_based_on,
        )
        # A changed ranking must not keep being served from cache.
        suggestions_repo.invalidate_cache()

    suggestions_repo.log_event(
        user_id=user_id,
        event_type="click" if action != "accepted" else "add_to_cart",
        entity_type="suggestion",
        metadata={
            "suggested_name": suggested_name,
            "action": action,
            "based_on": based_on[:20],
        },
    )


async def record_feedback(
    *,
    user_id: str,
    suggested_name: str,
    action: str,
    list_id: str | None = None,
    based_on: list[str] | None = None,
    provider: str | None = None,
) -> None:
    await run_in_thread(
        _record_feedback_sync,
        user_id=user_id,
        suggested_name=suggested_name,
        action=action,
        list_id=list_id,
        based_on=based_on or [],
        provider=provider,
    )


# ------------------------------------------------------------- maintenance


def _rebuild_sync() -> dict[str, Any]:
    started = perf_counter()
    written, baskets = suggestions_repo.rebuild_statistical_rules()
    suggestions_repo.invalidate_cache()
    return {
        "ok": True,
        "rules_written": written,
        "baskets_analyzed": baskets,
        "took_ms": int((perf_counter() - started) * 1000),
    }


async def rebuild_statistics() -> dict[str, Any]:
    """Re-mine association rules from current data."""
    return await run_in_thread(_rebuild_sync)


def _status_sync() -> dict[str, Any]:
    counts = suggestions_repo.count_rules_by_source()
    return {
        "provider": settings.SUGGESTIONS_PROVIDER,
        "globally_enabled": settings.AI_SUGGESTIONS_ENABLED,
        "llm_configured": settings.llm_configured,
        "llm_model": None,
        "seed_rules": counts.get("seed", 0),
        "statistical_rules": counts.get("statistical", 0),
        "llm_rules": counts.get("llm", 0),
        "cached_baskets": suggestions_repo.count_cached(),
        "catalog_products": catalog_repo.count_products(),
    }


async def get_engine_status() -> dict[str, Any]:
    return await run_in_thread(_status_sync)
