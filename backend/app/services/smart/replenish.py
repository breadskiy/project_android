"""Пополнение запасов: что скоро закончится, судя по истории покупок.

Медианный интервал между покупками устойчив к выбросам ("забыл купить —
взял два раза подряд"), поэтому предсказание не дёргается от одного сбоя.
"""

from __future__ import annotations

from datetime import UTC, datetime
from statistics import median

from app.db.pool import run_in_thread
from app.repositories import smart as smart_repo

MIN_PURCHASES = 3
DUE_RATIO = 0.8


def _compute_due(
    history: list[dict],
    pending: set[str],
    display: dict[str, str],
    *,
    now: datetime,
) -> list[dict]:
    by_product: dict[str, list[datetime]] = {}
    for row in history:
        at = row["at"]
        if at is None:
            continue
        if at.tzinfo is None:
            at = at.replace(tzinfo=UTC)
        by_product.setdefault(row["name"], []).append(at)

    due: list[dict] = []
    for name, moments in by_product.items():
        if name in pending or len(moments) < MIN_PURCHASES:
            continue
        moments.sort()
        intervals = [
            (later - earlier).total_seconds() / 86400
            for earlier, later in zip(moments, moments[1:])
            if (later - earlier).total_seconds() > 0
        ]
        if not intervals:
            continue
        avg_interval = float(median(intervals))
        if avg_interval < 1.0:
            continue
        days_since = (now - moments[-1]).total_seconds() / 86400
        if days_since < avg_interval * DUE_RATIO:
            continue
        due.append(
            {
                "name": display.get(name, name),
                "normalized_name": name,
                "purchases": len(moments),
                "avg_interval_days": round(avg_interval, 1),
                "days_since_last": round(max(0.0, days_since), 1),
            }
        )
    due.sort(key=lambda item: item["days_since_last"] / max(item["avg_interval_days"], 0.1), reverse=True)
    return due


def _replenish_sync(user_id: str) -> list[dict]:
    history = smart_repo.get_purchase_history(user_id)
    pending = smart_repo.get_pending_names(user_id)
    names = list({row["name"] for row in history})
    display = smart_repo.resolve_display_names(names)
    return _compute_due(history, pending, display, now=datetime.now(UTC))


async def replenish_for_user(user_id: str) -> list[dict]:
    """Товары, которые пора докупить. Пусто — всё в порядке."""
    return await run_in_thread(_replenish_sync, user_id)
