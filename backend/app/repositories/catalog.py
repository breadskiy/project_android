"""Product catalog persistence: fuzzy search, aliases, categories."""

from __future__ import annotations

from typing import Any

from app.core.normalization import normalize_item_name
from app.db.pool import Row, connection, execute, fetch_all, fetch_one, fetch_value

# Trigram similarity below this is noise for short Russian product names.
DEFAULT_SIMILARITY_THRESHOLD = 0.35


def search(
    query: str,
    *,
    limit: int = 10,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[Row]:
    """Prefix + trigram search over product names and aliases.

    Exact and prefix matches rank first; trigram similarity then catches typos
    ('малоко' -> 'молоко').
    """
    normalized = normalize_item_name(query)
    if not normalized:
        return []

    return fetch_all(
        """
        WITH direct AS (
            SELECT p.id,
                   p.name,
                   p.normalized_name,
                   p.category_id,
                   p.default_unit,
                   p.popularity,
                   NULL::text AS matched_alias,
                   CASE
                       WHEN p.normalized_name = %(q)s THEN 1.0
                       WHEN p.normalized_name LIKE %(prefix)s THEN 0.9
                       ELSE similarity(p.normalized_name, %(q)s)
                   END AS score
            FROM products p
            WHERE p.is_active
              AND (
                  p.normalized_name = %(q)s
                  OR p.normalized_name LIKE %(prefix)s
                  OR similarity(p.normalized_name, %(q)s) >= %(threshold)s
              )
        ),
        via_alias AS (
            SELECT p.id,
                   p.name,
                   p.normalized_name,
                   p.category_id,
                   p.default_unit,
                   p.popularity,
                   a.alias AS matched_alias,
                   CASE
                       WHEN a.alias = %(q)s THEN 0.95
                       WHEN a.alias LIKE %(prefix)s THEN 0.85
                       ELSE similarity(a.alias, %(q)s)
                   END AS score
            FROM product_aliases a
            JOIN products p ON p.id = a.product_id
            WHERE p.is_active
              AND (
                  a.alias = %(q)s
                  OR a.alias LIKE %(prefix)s
                  OR similarity(a.alias, %(q)s) >= %(threshold)s
              )
        ),
        merged AS (
            SELECT * FROM direct
            UNION ALL
            SELECT * FROM via_alias
        ),
        best AS (
            SELECT DISTINCT ON (id)
                   id, name, normalized_name, category_id, default_unit,
                   popularity, matched_alias, score
            FROM merged
            ORDER BY id, score DESC
        )
        SELECT b.*, c.name AS category_name
        FROM best b
        LEFT JOIN categories c ON c.id = b.category_id
        ORDER BY b.score DESC, b.popularity DESC, b.name
        LIMIT %(limit)s
        """,
        {
            "q": normalized,
            "prefix": f"{normalized}%",
            "threshold": threshold,
            "limit": limit,
        },
    )
    if any(float(r["score"]) >= 0.85 for r in rows):
        rows = [r for r in rows if float(r["score"]) >= 0.6]
    return rows


def find_exact(normalized_name: str) -> Row | None:
    """Resolve a normalized name to a product, following aliases."""
    if not normalized_name:
        return None
    return fetch_one(
        """
        SELECT p.id, p.name, p.normalized_name, p.category_id,
               p.default_unit, p.popularity, c.name AS category_name
        FROM products p
        LEFT JOIN categories c ON c.id = p.category_id
        WHERE p.is_active AND p.normalized_name = %(q)s
        UNION ALL
        SELECT p.id, p.name, p.normalized_name, p.category_id,
               p.default_unit, p.popularity, c.name AS category_name
        FROM product_aliases a
        JOIN products p ON p.id = a.product_id
        LEFT JOIN categories c ON c.id = p.category_id
        WHERE p.is_active AND a.alias = %(q)s
        LIMIT 1
        """,
        {"q": normalized_name},
    )


def resolve_many(normalized_names: list[str]) -> dict[str, Row]:
    """Batch variant of :func:`find_exact`; one query for a whole basket."""
    if not normalized_names:
        return {}

    rows = fetch_all(
        """
        SELECT key, id, name, normalized_name, category_id, category_name, default_unit
        FROM (
            SELECT p.normalized_name AS key, p.id, p.name, p.normalized_name,
                   p.category_id, c.name AS category_name, p.default_unit,
                   1 AS priority
            FROM products p
            LEFT JOIN categories c ON c.id = p.category_id
            WHERE p.is_active AND p.normalized_name = ANY(%(names)s)
            UNION ALL
            SELECT a.alias AS key, p.id, p.name, p.normalized_name,
                   p.category_id, c.name AS category_name, p.default_unit,
                   2 AS priority
            FROM product_aliases a
            JOIN products p ON p.id = a.product_id
            LEFT JOIN categories c ON c.id = p.category_id
            WHERE p.is_active AND a.alias = ANY(%(names)s)
        ) matches
        ORDER BY key, priority
        """,
        {"names": normalized_names},
    )

    resolved: dict[str, Row] = {}
    for row in rows:
        resolved.setdefault(row["key"], row)
    return resolved


def canonicalize(
    normalized_names: list[str],
    *,
    fuzzy_threshold: float = 0.3,
    prefix_length: int = 4,
) -> dict[str, str]:
    """Map normalized user input onto canonical catalog keys.

    Exact names and aliases resolve first ('картоха' -> 'картофель'). Whatever
    is left falls back to a guarded trigram match: the input must both start
    with the product's first few characters *and* be similar enough. Requiring
    both keeps inflected forms working ('молока' -> 'молоко', 'картошечка' ->
    'картофель') without matching unrelated words that merely share letters.

    Without this step a rule written for 'молоко' would never fire for the very
    common input "2 л молока".
    """
    if not normalized_names:
        return {}

    mapping: dict[str, str] = {}
    for key, row in resolve_many(normalized_names).items():
        if row.get("normalized_name"):
            mapping[key] = row["normalized_name"]

    unresolved = [name for name in normalized_names if name and name not in mapping]
    if not unresolved:
        return mapping

    rows = fetch_all(
        """
        SELECT DISTINCT ON (needle.name)
               needle.name        AS key,
               p.normalized_name  AS canonical
        FROM unnest(%(names)s::text[]) AS needle(name)
        JOIN products p
            ON p.is_active
           AND p.normalized_name IS NOT NULL
           AND length(p.normalized_name) >= %(prefix_length)s
           AND needle.name LIKE left(p.normalized_name, %(prefix_length)s) || '%%'
           AND similarity(p.normalized_name, needle.name) >= %(threshold)s
        ORDER BY needle.name,
                 similarity(p.normalized_name, needle.name) DESC,
                 p.popularity DESC
        """,
        {"names": unresolved, "threshold": fuzzy_threshold, "prefix_length": prefix_length},
    )
    for row in rows:
        mapping[row["key"]] = row["canonical"]

    return mapping


def list_products(
    *,
    limit: int = 50,
    offset: int = 0,
    category_id: str | None = None,
) -> tuple[list[Row], int]:
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    where = "WHERE p.is_active"
    if category_id:
        where += " AND p.category_id = %(category_id)s"
        params["category_id"] = category_id

    rows = fetch_all(
        f"""
        SELECT p.id, p.name, p.normalized_name, p.category_id,
               c.name AS category_name, p.default_unit, p.popularity
        FROM products p
        LEFT JOIN categories c ON c.id = p.category_id
        {where}
        ORDER BY p.popularity DESC, p.name
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        params,
    )
    total = fetch_value(f"SELECT count(*) FROM products p {where}", params)
    return rows, int(total or 0)


def list_categories() -> list[Row]:
    return fetch_all(
        """
        SELECT c.id, c.name, c.parent_id,
               count(p.id) FILTER (WHERE p.is_active) AS product_count
        FROM categories c
        LEFT JOIN products p ON p.category_id = c.id
        GROUP BY c.id, c.name, c.parent_id
        ORDER BY c.name
        """
    )


def bump_popularity(product_ids: list[str]) -> None:
    if not product_ids:
        return
    execute(
        "UPDATE products SET popularity = popularity + 1 WHERE id = ANY(%s::uuid[])",
        (product_ids,),
    )


def count_products() -> int:
    return int(fetch_value("SELECT count(*) FROM products WHERE is_active") or 0)


# ------------------------------------------------------------------ seeding


def upsert_category(name: str) -> str:
    row = fetch_one(
        """
        INSERT INTO categories (name)
        VALUES (%s)
        ON CONFLICT (lower(name)) DO UPDATE SET name = EXCLUDED.name
        RETURNING id
        """,
        (name,),
    )
    assert row is not None
    return str(row["id"])


def upsert_product(
    *,
    name: str,
    category_id: str | None,
    default_unit: str | None,
    popularity: int = 0,
) -> str:
    normalized = normalize_item_name(name)
    row = fetch_one(
        """
        INSERT INTO products (name, normalized_name, category_id, default_unit, popularity)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (normalized_name) WHERE normalized_name IS NOT NULL
        DO UPDATE SET
            name = EXCLUDED.name,
            category_id = COALESCE(EXCLUDED.category_id, products.category_id),
            default_unit = COALESCE(EXCLUDED.default_unit, products.default_unit),
            popularity = GREATEST(products.popularity, EXCLUDED.popularity),
            updated_at = now()
        RETURNING id
        """,
        (name, normalized, category_id, default_unit, popularity),
    )
    assert row is not None
    return str(row["id"])


def upsert_alias(*, product_id: str, alias: str, source: str = "seed") -> None:
    normalized_alias = normalize_item_name(alias)
    if not normalized_alias:
        return
    execute(
        """
        INSERT INTO product_aliases (product_id, alias, source)
        VALUES (%s, %s, %s)
        ON CONFLICT (alias) DO UPDATE
        SET product_id = EXCLUDED.product_id
        """,
        (product_id, normalized_alias, source),
    )
