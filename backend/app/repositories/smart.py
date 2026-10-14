"""История покупок пользователя для предсказания пополнения.

Чистый SQL + арифметика, никакого LLM: "молоко покупаешь каждые ~3 дня,
последний раз 4 дня назад — пора докупить".
"""

from __future__ import annotations

from app.db.pool import fetch_all


def get_purchase_history(user_id: str) -> list[dict]:
    """Все отметки «куплено» пользователя, новые первыми."""
    return fetch_all(
        """
        SELECT i.normalized_name AS name, i.checked_at AS at
        FROM shopping_list_items i
        JOIN shopping_list_members m ON m.shopping_list_id = i.shopping_list_id
        WHERE m.user_id = %(user_id)s
          AND i.checked_at IS NOT NULL
          AND i.normalized_name IS NOT NULL
          AND i.normalized_name <> ''
        ORDER BY i.checked_at DESC
        LIMIT 5000
        """,
        {"user_id": user_id},
    )


def get_pending_names(user_id: str) -> set[str]:
    """Товары, уже лежащие в списках пользователя (их не предлагаем)."""
    rows = fetch_all(
        """
        SELECT DISTINCT i.normalized_name AS name
        FROM shopping_list_items i
        JOIN shopping_list_members m ON m.shopping_list_id = i.shopping_list_id
        WHERE m.user_id = %(user_id)s
          AND i.checked = false
          AND i.normalized_name IS NOT NULL
          AND i.normalized_name <> ''
        """,
        {"user_id": user_id},
    )
    return {row["name"] for row in rows}


def resolve_display_names(names: list[str]) -> dict[str, str]:
    """Нормализованное имя -> красивое название из каталога (если есть)."""
    if not names:
        return {}
    rows = fetch_all(
        """
        SELECT p.normalized_name AS key, p.name AS display
        FROM products p
        WHERE p.is_active AND p.normalized_name = ANY(%(names)s)
        """,
        {"names": names},
    )
    return {row["key"]: row["display"] for row in rows}
