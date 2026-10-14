"""Persistence for the recommendation engine.

Three rule sources coexist in ``product_pair_rules``:

``seed``
    A curated prior shipped with the app, so suggestions work on an empty
    database (the cold-start problem).
``statistical``
    Mined from real co-occurrence in users' lists: support, confidence, lift.
``llm``
    Legacy value only: no new rules with this source are produced, but rows
    written earlier remain readable and rank below statistical ones.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from psycopg.types.json import Json

from app.core.security import utcnow
from app.db.pool import Row, connection, execute, fetch_all, fetch_one, fetch_value

# Statistical mining thresholds. Below these, a co-occurrence is coincidence.
MIN_SUPPORT = 2
MIN_CONFIDENCE = 0.15


# ------------------------------------------------------------- rule lookup


def get_rules_for(
    antecedents: list[str],
    *,
    exclude: list[str],
    limit: int = 20,
    min_weight: float = 0.0,
) -> list[Row]:
    """Best rules triggered by any item in the basket.

    Feedback shifts the ranking: a suggestion users keep rejecting sinks,
    one they keep accepting rises. This is the learning loop that runs
    without any external service.
    """
    if not antecedents:
        return []

    return fetch_all(
        """
        WITH scored AS (
            SELECT
                r.consequent,
                r.antecedent,
                r.source,
                r.reason,
                r.consequent_id,
                r.support,
                r.confidence,
                r.lift,
                r.accepted_count,
                r.rejected_count,
                -- Feedback-adjusted weight, clamped to [0, 1].
                LEAST(
                    1.0,
                    GREATEST(
                        0.0,
                        r.weight
                        + LEAST(0.2, r.accepted_count * 0.02)
                        - LEAST(0.4, r.rejected_count * 0.05)
                    )
                ) AS score,
                row_number() OVER (
                    PARTITION BY r.consequent
                    ORDER BY r.weight DESC,
                             CASE r.source
                                 WHEN 'llm' THEN 0
                                 WHEN 'statistical' THEN 1
                                 ELSE 2
                             END
                ) AS rank_in_group
            FROM product_pair_rules r
            WHERE r.antecedent = ANY(%(antecedents)s)
              AND NOT (r.consequent = ANY(%(exclude)s))
              AND r.weight >= %(min_weight)s
        )
        SELECT consequent, antecedent, source, reason, consequent_id,
               support, confidence, lift, accepted_count, rejected_count, score
        FROM scored
        WHERE rank_in_group = 1
        ORDER BY score DESC, support DESC, consequent
        LIMIT %(limit)s
        """,
        {
            "antecedents": antecedents,
            "exclude": exclude or [""],
            "limit": limit,
            "min_weight": min_weight,
        },
    )


def get_personal_rules(
    user_id: str,
    antecedents: list[str],
    *,
    exclude: list[str],
    limit: int = 10,
) -> list[Row]:
    """What *this* user actually buys together, mined from their own lists.

    External knowledge cannot produce this; it is the part of the engine that
    is genuinely personalized.
    """
    if not antecedents:
        return []

    return fetch_all(
        """
        WITH my_lists AS (
            SELECT sl.id
            FROM shopping_lists sl
            JOIN shopping_list_members m ON m.shopping_list_id = sl.id
            WHERE m.user_id = %(user_id)s
        ),
        baskets AS (
            SELECT i.shopping_list_id AS list_id,
                   i.normalized_name  AS name
            FROM shopping_list_items i
            JOIN my_lists ON my_lists.id = i.shopping_list_id
            WHERE i.normalized_name IS NOT NULL AND i.normalized_name <> ''
            GROUP BY i.shopping_list_id, i.normalized_name
        ),
        anchors AS (
            SELECT list_id FROM baskets WHERE name = ANY(%(antecedents)s)
        ),
        co AS (
            SELECT b.name, count(DISTINCT b.list_id) AS support
            FROM baskets b
            JOIN anchors a ON a.list_id = b.list_id
            WHERE NOT (b.name = ANY(%(antecedents)s))
              AND NOT (b.name = ANY(%(exclude)s))
            GROUP BY b.name
        ),
        anchor_total AS (
            SELECT GREATEST(count(DISTINCT list_id), 1) AS total FROM anchors
        )
        SELECT co.name AS consequent,
               co.support,
               co.support::float / anchor_total.total AS confidence
        FROM co
        CROSS JOIN anchor_total
        WHERE co.support >= 2
        ORDER BY co.support DESC, co.name
        LIMIT %(limit)s
        """,
        {
            "user_id": user_id,
            "antecedents": antecedents,
            "exclude": exclude or [""],
            "limit": limit,
        },
    )


def count_rules_by_source() -> dict[str, int]:
    rows = fetch_all("SELECT source, count(*) AS c FROM product_pair_rules GROUP BY source")
    return {row["source"]: int(row["c"]) for row in rows}


def list_rules(
    *,
    antecedent: str | None = None,
    source: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Row]:
    filters: list[str] = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if antecedent:
        filters.append("antecedent = %(antecedent)s")
        params["antecedent"] = antecedent
    if source:
        filters.append("source = %(source)s")
        params["source"] = source
    where = (" WHERE " + " AND ".join(filters)) if filters else ""

    return fetch_all(
        f"""
        SELECT antecedent, consequent, source, weight, support, confidence,
               lift, reason, accepted_count, rejected_count, refreshed_at
        FROM product_pair_rules
        {where}
        ORDER BY weight DESC, support DESC, antecedent, consequent
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        params,
    )


# ------------------------------------------------------------- rule writes


def upsert_rules(rules: list[dict[str, Any]]) -> int:
    """Insert or refresh rules. Feedback counters are preserved on update."""
    if not rules:
        return 0

    written = 0
    with connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                for rule in rules:
                    cur.execute(
                        """
                        INSERT INTO product_pair_rules (
                            antecedent, consequent, antecedent_id, consequent_id,
                            source, weight, support, confidence, lift, reason,
                            model_version, refreshed_at
                        )
                        VALUES (
                            %(antecedent)s, %(consequent)s, %(antecedent_id)s,
                            %(consequent_id)s, %(source)s, %(weight)s, %(support)s,
                            %(confidence)s, %(lift)s, %(reason)s, %(model_version)s,
                            now()
                        )
                        ON CONFLICT (antecedent, consequent, source) DO UPDATE
                        SET weight        = EXCLUDED.weight,
                            support       = EXCLUDED.support,
                            confidence    = EXCLUDED.confidence,
                            lift          = EXCLUDED.lift,
                            reason        = COALESCE(EXCLUDED.reason, product_pair_rules.reason),
                            antecedent_id = COALESCE(EXCLUDED.antecedent_id, product_pair_rules.antecedent_id),
                            consequent_id = COALESCE(EXCLUDED.consequent_id, product_pair_rules.consequent_id),
                            model_version = COALESCE(EXCLUDED.model_version, product_pair_rules.model_version),
                            refreshed_at  = now()
                        """,
                        {
                            "antecedent": rule["antecedent"],
                            "consequent": rule["consequent"],
                            "antecedent_id": rule.get("antecedent_id"),
                            "consequent_id": rule.get("consequent_id"),
                            "source": rule.get("source", "seed"),
                            "weight": rule.get("weight", 0.5),
                            "support": rule.get("support", 0),
                            "confidence": rule.get("confidence"),
                            "lift": rule.get("lift"),
                            "reason": rule.get("reason"),
                            "model_version": rule.get("model_version"),
                        },
                    )
                    written += 1
    return written


def record_feedback_on_rule(*, consequent: str, accepted: bool, antecedents: list[str]) -> None:
    """Fold user feedback back into the rules that produced the suggestion."""
    column = "accepted_count" if accepted else "rejected_count"
    execute(
        f"""
        UPDATE product_pair_rules
        SET {column} = {column} + 1
        WHERE consequent = %s
          AND (%s::text[] = '{{}}' OR antecedent = ANY(%s::text[]))
        """,
        (consequent, antecedents, antecedents),
    )


def rebuild_statistical_rules(*, min_support: int = MIN_SUPPORT) -> tuple[int, int]:
    """Mine association rules from real lists.

    Classic market-basket metrics per ordered pair (A -> B):
      support(A,B)   number of lists containing both
      confidence     P(B | A) = support(A,B) / support(A)
      lift           confidence / P(B); > 1 means a real association

    Returns ``(rules_written, baskets_analyzed)``.
    """
    baskets = int(
        fetch_value(
            """
            SELECT count(*) FROM (
                SELECT shopping_list_id
                FROM shopping_list_items
                WHERE normalized_name IS NOT NULL AND normalized_name <> ''
                GROUP BY shopping_list_id
                HAVING count(DISTINCT normalized_name) >= 2
            ) AS b
            """
        )
        or 0
    )
    if baskets == 0:
        return 0, 0

    rows = fetch_all(
        """
        WITH basket_items AS (
            SELECT DISTINCT shopping_list_id AS list_id, normalized_name AS name
            FROM shopping_list_items
            WHERE normalized_name IS NOT NULL AND normalized_name <> ''
        ),
        totals AS (
            SELECT count(DISTINCT list_id)::float AS basket_count FROM basket_items
        ),
        item_support AS (
            SELECT name, count(DISTINCT list_id) AS support
            FROM basket_items
            GROUP BY name
        ),
        pairs AS (
            SELECT a.name AS antecedent,
                   b.name AS consequent,
                   count(DISTINCT a.list_id) AS support
            FROM basket_items a
            JOIN basket_items b
                ON a.list_id = b.list_id AND a.name <> b.name
            GROUP BY a.name, b.name
            HAVING count(DISTINCT a.list_id) >= %(min_support)s
        )
        SELECT p.antecedent,
               p.consequent,
               p.support,
               p.support::float / sa.support                        AS confidence,
               (p.support::float / sa.support)
                   / (sc.support::float / t.basket_count)           AS lift
        FROM pairs p
        JOIN item_support sa ON sa.name = p.antecedent
        JOIN item_support sc ON sc.name = p.consequent
        CROSS JOIN totals t
        WHERE p.support::float / sa.support >= %(min_confidence)s
        ORDER BY p.support DESC
        LIMIT 20000
        """,
        {"min_support": min_support, "min_confidence": MIN_CONFIDENCE},
    )

    rules = [
        {
            "antecedent": row["antecedent"],
            "consequent": row["consequent"],
            "source": "statistical",
            # Confidence is already a probability; keep it as the weight but
            # damp low-support rules so two coincidences cannot outrank a
            # well-established pair.
            "weight": min(1.0, float(row["confidence"]) * min(1.0, row["support"] / 5)),
            "support": int(row["support"]),
            "confidence": float(row["confidence"]),
            "lift": float(row["lift"]) if row["lift"] is not None else None,
            "reason": "Вы часто покупаете это вместе",
        }
        for row in rows
    ]

    written = upsert_rules(rules)
    return written, baskets


def prune_statistical_rules(older_than_days: int = 90) -> int:
    return execute(
        """
        DELETE FROM product_pair_rules
        WHERE source = 'statistical'
          AND refreshed_at < now() - make_interval(days => %s)
        """,
        (older_than_days,),
    )


# ------------------------------------------------------------------- cache


def get_cached(basket_hash: str, provider: str) -> Row | None:
    row = fetch_one(
        """
        UPDATE suggestion_cache
        SET hits = hits + 1
        WHERE basket_hash = %s
          AND provider = %s
          AND (expires_at IS NULL OR expires_at > now())
        RETURNING payload, model_version, created_at
        """,
        (basket_hash, provider),
    )
    return row


def store_cached(
    *,
    basket_hash: str,
    provider: str,
    payload: list[dict[str, Any]],
    model_version: str | None,
    ttl_seconds: int,
) -> None:
    expires_at = utcnow() + timedelta(seconds=ttl_seconds) if ttl_seconds > 0 else None
    execute(
        """
        INSERT INTO suggestion_cache (basket_hash, provider, payload, model_version, expires_at)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (basket_hash, provider) DO UPDATE
        SET payload = EXCLUDED.payload,
            model_version = EXCLUDED.model_version,
            expires_at = EXCLUDED.expires_at,
            created_at = now()
        """,
        (basket_hash, provider, Json(payload), model_version, expires_at),
    )


def purge_expired_cache() -> int:
    return execute("DELETE FROM suggestion_cache WHERE expires_at IS NOT NULL AND expires_at < now()")


def count_cached() -> int:
    return int(fetch_value("SELECT count(*) FROM suggestion_cache") or 0)


def invalidate_cache(provider: str | None = None) -> int:
    if provider:
        return execute("DELETE FROM suggestion_cache WHERE provider = %s", (provider,))
    return execute("DELETE FROM suggestion_cache")


# ---------------------------------------------------------------- feedback


def record_feedback(
    *,
    user_id: str,
    list_id: str | None,
    suggested_name: str,
    based_on: list[str],
    action: str,
    provider: str | None,
    model_version: str | None = None,
) -> None:
    execute(
        """
        INSERT INTO suggestion_feedback (
            user_id, shopping_list_id, suggested_name, based_on,
            action, provider, model_version
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (user_id, list_id, suggested_name, based_on, action, provider, model_version),
    )


def acceptance_stats(*, days: int = 30) -> Row:
    row = fetch_one(
        """
        SELECT
            count(*) FILTER (WHERE action = 'shown')    AS shown,
            count(*) FILTER (WHERE action = 'accepted') AS accepted,
            count(*) FILTER (WHERE action = 'rejected') AS rejected
        FROM suggestion_feedback
        WHERE created_at > now() - make_interval(days => %s)
        """,
        (days,),
    )
    return row or {"shown": 0, "accepted": 0, "rejected": 0}


# ------------------------------------------------------------------ events


def log_event(
    *,
    user_id: str | None,
    event_type: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append to the ``events`` table (the raw ML signal).

    Never raises: analytics must not be able to fail a user's request.
    """
    try:
        execute(
            """
            INSERT INTO events (user_id, event_type, entity_type, entity_id, metadata)
            VALUES (%s, %s::event_type_t, %s, %s, %s)
            """,
            (user_id, event_type, entity_type, entity_id, Json(metadata or {})),
        )
    except Exception:  # pragma: no cover - best-effort logging
        from app.core.logging import get_logger

        get_logger("smartsupply.events").debug("event logging failed", exc_info=True)
