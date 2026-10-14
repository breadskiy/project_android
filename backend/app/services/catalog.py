"""Product catalog service: search, autocomplete, categories."""

from __future__ import annotations

from typing import Any

from app.core.normalization import normalize_item_name
from app.db.pool import run_in_thread
from app.repositories import catalog as catalog_repo


def _search_sync(query: str, *, limit: int) -> dict[str, Any]:
    normalized = normalize_item_name(query)
    rows = catalog_repo.search(query, limit=limit)
    return {
        "items": [
            {
                "id": row["id"],
                "name": row["name"],
                "normalized_name": row["normalized_name"],
                "category_id": row["category_id"],
                "category_name": row.get("category_name"),
                "default_unit": row["default_unit"],
                "popularity": int(row["popularity"]),
                "similarity": round(float(row["score"]), 4),
                "matched_alias": row.get("matched_alias"),
            }
            for row in rows
        ],
        "query": query,
        "normalized_query": normalized,
    }


async def search(query: str, *, limit: int = 10) -> dict[str, Any]:
    return await run_in_thread(_search_sync, query, limit=limit)


def _list_sync(*, limit: int, offset: int, category_id: str | None) -> dict[str, Any]:
    rows, total = catalog_repo.list_products(limit=limit, offset=offset, category_id=category_id)
    return {
        "items": rows,
        "meta": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(rows) < total,
        },
    }


async def list_products(
    *, limit: int = 50, offset: int = 0, category_id: str | None = None
) -> dict[str, Any]:
    return await run_in_thread(_list_sync, limit=limit, offset=offset, category_id=category_id)


def _categories_sync() -> list[dict[str, Any]]:
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "parent_id": row["parent_id"],
            "product_count": int(row["product_count"]),
        }
        for row in catalog_repo.list_categories()
    ]


async def list_categories() -> list[dict[str, Any]]:
    return await run_in_thread(_categories_sync)
