"""Shopping list, membership and item persistence.

Access control is expressed in SQL: every read and write is scoped by a join
against ``shopping_list_members``, so a caller can never touch a list they are
not a member of, regardless of what the service layer forgets to check.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal
from uuid import uuid4

from app.core.normalization import normalize_item_name
from app.core.smart_parse import parse_item_input
from app.core.security import utcnow
from app.db.pool import Row, connection, execute, fetch_all, fetch_one, fetch_value

SYSTEM_FAVORITE = "system_favorite"
FAVORITE_NAME = "⭐ Избранное"

ROLE_RANK = {"viewer": 0, "editor": 1, "owner": 2}

LIST_SELECT = """
    SELECT
        sl.id,
        sl.name,
        sl.description,
        sl.user_id                          AS owner_id,
        owner.display_name                  AS owner_name,
        m.role                              AS role,
        (sl.user_id = m.user_id)            AS is_owner,
        sl.is_shared,
        (sl.description IS NOT NULL AND sl.description = 'system_favorite') AS is_system,
        sl.created_at,
        sl.updated_at,
        COALESCE(stats.item_count, 0)       AS item_count,
        COALESCE(stats.checked_count, 0)    AS checked_count,
        COALESCE(mc.member_count, 1)        AS member_count
    FROM shopping_lists sl
    JOIN shopping_list_members m
        ON m.shopping_list_id = sl.id AND m.user_id = %(user_id)s
    JOIN users owner
        ON owner.id = sl.user_id
    LEFT JOIN (
        SELECT shopping_list_id,
               count(*)                                        AS item_count,
               count(*) FILTER (WHERE checked)                 AS checked_count
        FROM shopping_list_items
        GROUP BY shopping_list_id
    ) stats ON stats.shopping_list_id = sl.id
    LEFT JOIN (
        SELECT shopping_list_id, count(*) AS member_count
        FROM shopping_list_members
        GROUP BY shopping_list_id
    ) mc ON mc.shopping_list_id = sl.id
"""

ITEM_SELECT = """
    SELECT
        i.id,
        i.shopping_list_id AS list_id,
        i.name,
        i.normalized_name,
        i.quantity,
        i.unit,
        i.notes,
        i.priority,
        i.checked,
        i.checked_at,
        i.checked_by,
        cb.display_name AS checked_by_name,
        i.added_by,
        ab.display_name AS added_by_name,
        i.product_id,
        i.sort_order,
        i.added_at,
        i.updated_at
    FROM shopping_list_items i
    LEFT JOIN users cb ON cb.id = i.checked_by
    LEFT JOIN users ab ON ab.id = i.added_by
"""


# ---------------------------------------------------------------- read side


def get_membership(list_id: str, user_id: str) -> Row | None:
    """The single authorization primitive: role of a user on a list."""
    return fetch_one(
        """
        SELECT m.role,
               sl.user_id AS owner_id,
               sl.description,
               sl.is_shared,
               sl.name,
               (sl.user_id = %(user_id)s) AS is_owner,
               (sl.description IS NOT NULL AND sl.description = 'system_favorite') AS is_system
        FROM shopping_list_members m
        JOIN shopping_lists sl ON sl.id = m.shopping_list_id
        WHERE m.shopping_list_id = %(list_id)s AND m.user_id = %(user_id)s
        """,
        {"list_id": list_id, "user_id": user_id},
    )


def get_list(list_id: str, user_id: str) -> Row | None:
    return fetch_one(
        LIST_SELECT + " WHERE sl.id = %(list_id)s",
        {"list_id": list_id, "user_id": user_id},
    )


def list_for_user(
    user_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
    sort: Literal["created_at", "updated_at", "name"] = "created_at",
    direction: Literal["asc", "desc"] = "desc",
    query: str | None = None,
    only_owned: bool | None = None,
) -> tuple[list[Row], int]:
    filters = []
    params: dict[str, Any] = {"user_id": user_id, "limit": limit, "offset": offset}

    if query:
        filters.append("sl.name ILIKE %(query)s")
        params["query"] = f"%{query}%"
    if only_owned is True:
        filters.append("sl.user_id = %(user_id)s")
    elif only_owned is False:
        filters.append("sl.user_id <> %(user_id)s")

    where = (" WHERE " + " AND ".join(filters)) if filters else ""

    # Sort/direction come from validated enums, never raw user strings.
    order_column = {
        "created_at": "sl.created_at",
        "updated_at": "sl.updated_at",
        "name": "sl.name",
    }[sort]
    order_dir = "ASC" if direction == "asc" else "DESC"

    rows = fetch_all(
        f"""
        {LIST_SELECT}{where}
        ORDER BY is_system DESC, {order_column} {order_dir}, sl.id
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        params,
    )

    total = fetch_value(
        f"""
        SELECT count(*)
        FROM shopping_lists sl
        JOIN shopping_list_members m
            ON m.shopping_list_id = sl.id AND m.user_id = %(user_id)s
        {where}
        """,
        params,
    )
    return rows, int(total or 0)


def get_list_raw(list_id: str) -> Row | None:
    """List row without a membership join, for legacy-link handling only."""
    return fetch_one(
        """
        SELECT id, user_id AS owner_id, name, description, is_shared
        FROM shopping_lists
        WHERE id = %s
        """,
        (list_id,),
    )


def count_owned(user_id: str) -> int:
    return int(fetch_value("SELECT count(*) FROM shopping_lists WHERE user_id = %s", (user_id,)) or 0)


def get_members(list_id: str) -> list[Row]:
    return fetch_all(
        """
        SELECT m.user_id, m.role, m.joined_at, u.display_name, u.email
        FROM shopping_list_members m
        JOIN users u ON u.id = m.user_id
        WHERE m.shopping_list_id = %s
        ORDER BY
            CASE m.role WHEN 'owner' THEN 0 WHEN 'editor' THEN 1 ELSE 2 END,
            m.joined_at
        """,
        (list_id,),
    )


def get_items(
    list_id: str,
    *,
    limit: int | None = None,
    offset: int = 0,
    item_filter: Literal["all", "pending", "checked"] = "all",
) -> list[Row]:
    condition = {
        "all": "",
        "pending": " AND i.checked = false",
        "checked": " AND i.checked = true",
    }[item_filter]

    sql_text = f"""
        {ITEM_SELECT}
        WHERE i.shopping_list_id = %(list_id)s{condition}
        ORDER BY i.checked, i.sort_order, i.added_at, i.id
    """
    params: dict[str, Any] = {"list_id": list_id}
    if limit is not None:
        sql_text += " LIMIT %(limit)s OFFSET %(offset)s"
        params.update({"limit": limit, "offset": offset})

    return fetch_all(sql_text, params)


def count_items(list_id: str, item_filter: Literal["all", "pending", "checked"] = "all") -> int:
    condition = {
        "all": "",
        "pending": " AND checked = false",
        "checked": " AND checked = true",
    }[item_filter]
    return int(
        fetch_value(
            f"SELECT count(*) FROM shopping_list_items WHERE shopping_list_id = %s{condition}",
            (list_id,),
        )
        or 0
    )


def get_item(list_id: str, item_id: str) -> Row | None:
    return fetch_one(
        f"{ITEM_SELECT} WHERE i.id = %(item_id)s AND i.shopping_list_id = %(list_id)s",
        {"item_id": item_id, "list_id": list_id},
    )


def get_item_names(list_id: str, *, only_pending: bool = False) -> list[str]:
    condition = " AND checked = false" if only_pending else ""
    rows = fetch_all(
        f"""
        SELECT name
        FROM shopping_list_items
        WHERE shopping_list_id = %s{condition}
        ORDER BY sort_order, added_at
        """,
        (list_id,),
    )
    return [row["name"] for row in rows]


# --------------------------------------------------------------- write side


def create_list(
    *,
    user_id: str,
    name: str,
    description: str | None,
    items: list[str],
) -> Row:
    """Create a list, its owner membership and initial items in one transaction."""
    list_id = str(uuid4())
    now = utcnow()

    with connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO shopping_lists (id, user_id, name, description, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (list_id, user_id, name, description, now, now),
                )
                cur.execute(
                    """
                    INSERT INTO shopping_list_members (shopping_list_id, user_id, role)
                    VALUES (%s, %s, 'owner')
                    """,
                    (list_id, user_id),
                )

                for position, item_name in enumerate(items):
                    parsed = parse_item_input(item_name)
                    cur.execute(
                        """
                        INSERT INTO shopping_list_items (
                            shopping_list_id, name, normalized_name, quantity,
                            unit, added_by, sort_order, added_at, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            list_id,
                            parsed.name,
                            normalize_item_name(parsed.name),
                            parsed.quantity,
                            parsed.unit,
                            user_id,
                            position,
                            now,
                            now,
                        ),
                    )

    row = get_list(list_id, user_id)
    assert row is not None
    return row


def update_list(list_id: str, *, name: str | None, description: str | None) -> bool:
    return (
        execute(
            """
            UPDATE shopping_lists
            SET name = COALESCE(%(name)s, name),
                description = COALESCE(%(description)s, description),
                updated_at = now()
            WHERE id = %(list_id)s
            """,
            {"list_id": list_id, "name": name, "description": description},
        )
        > 0
    )


def delete_list(list_id: str) -> bool:
    # Items and memberships disappear via ON DELETE CASCADE.
    return execute("DELETE FROM shopping_lists WHERE id = %s", (list_id,)) > 0


def leave_list(list_id: str, user_id: str) -> bool:
    """Remove a non-owner membership."""
    deleted = execute(
        """
        DELETE FROM shopping_list_members
        WHERE shopping_list_id = %s AND user_id = %s AND role <> 'owner'
        """,
        (list_id, user_id),
    )
    if deleted:
        _refresh_shared_flag(list_id)
    return deleted > 0


def ensure_favorites(user_id: str) -> str:
    """Return the id of the user's system favourites list, creating it if needed."""
    existing = fetch_value(
        """
        SELECT id FROM shopping_lists
        WHERE user_id = %s AND description = %s
        LIMIT 1
        """,
        (user_id, SYSTEM_FAVORITE),
    )
    if existing:
        return str(existing)

    now = utcnow()
    with connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO shopping_lists (user_id, name, description, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) WHERE description = 'system_favorite'
                    DO NOTHING
                    RETURNING id
                    """,
                    (user_id, FAVORITE_NAME, SYSTEM_FAVORITE, now, now),
                )
                created = cur.fetchone()
                if created is None:
                    cur.execute(
                        """
                        SELECT id FROM shopping_lists
                        WHERE user_id = %s AND description = %s
                        LIMIT 1
                        """,
                        (user_id, SYSTEM_FAVORITE),
                    )
                    created = cur.fetchone()
                    assert created is not None
                    return str(created["id"])

                list_id = str(created["id"])
                cur.execute(
                    """
                    INSERT INTO shopping_list_members (shopping_list_id, user_id, role)
                    VALUES (%s, %s, 'owner')
                    ON CONFLICT (shopping_list_id, user_id) DO NOTHING
                    """,
                    (list_id, user_id),
                )
                return list_id


def touch_list(list_id: str) -> None:
    execute("UPDATE shopping_lists SET updated_at = now() WHERE id = %s", (list_id,))


# ------------------------------------------------------------------- items


def add_item(
    *,
    list_id: str,
    user_id: str,
    name: str,
    quantity: Decimal | float | int = 1,
    unit: str | None = None,
    notes: str | None = None,
    priority: int = 1,
    product_id: str | None = None,
) -> Row:
    now = utcnow()
    with connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO shopping_list_items (
                        shopping_list_id, name, normalized_name, quantity, unit,
                        notes, priority, product_id, added_by, sort_order,
                        added_at, updated_at
                    )
                    VALUES (
                        %(list_id)s, %(name)s, %(normalized)s, %(quantity)s, %(unit)s,
                        %(notes)s, %(priority)s, %(product_id)s, %(user_id)s,
                        COALESCE(
                            (SELECT max(sort_order) + 1
                             FROM shopping_list_items
                             WHERE shopping_list_id = %(list_id)s),
                            0
                        ),
                        %(now)s, %(now)s
                    )
                    RETURNING id
                    """,
                    {
                        "list_id": list_id,
                        "name": name,
                        "normalized": normalize_item_name(name),
                        "quantity": quantity,
                        "unit": unit,
                        "notes": notes,
                        "priority": priority,
                        "product_id": product_id,
                        "user_id": user_id,
                        "now": now,
                    },
                )
                created = cur.fetchone()
                assert created is not None
                cur.execute(
                    "UPDATE shopping_lists SET updated_at = %s WHERE id = %s",
                    (now, list_id),
                )
                item_id = str(created["id"])

    row = get_item(list_id, item_id)
    assert row is not None
    return row


def add_items_bulk(
    *,
    list_id: str,
    user_id: str,
    items: list[dict[str, Any]],
) -> list[str]:
    """Insert several items in one transaction; returns the new ids."""
    now = utcnow()
    created_ids: list[str] = []

    with connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(max(sort_order) + 1, 0) AS next_order
                    FROM shopping_list_items
                    WHERE shopping_list_id = %s
                    """,
                    (list_id,),
                )
                start = int((cur.fetchone() or {"next_order": 0})["next_order"])

                for offset, item in enumerate(items):
                    cur.execute(
                        """
                        INSERT INTO shopping_list_items (
                            shopping_list_id, name, normalized_name, quantity, unit,
                            notes, priority, product_id, added_by, sort_order,
                            added_at, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            list_id,
                            item["name"],
                            normalize_item_name(item["name"]),
                            item.get("quantity", 1),
                            item.get("unit"),
                            item.get("notes"),
                            item.get("priority", 1),
                            item.get("product_id"),
                            user_id,
                            start + offset,
                            now,
                            now,
                        ),
                    )
                    row = cur.fetchone()
                    assert row is not None
                    created_ids.append(str(row["id"]))

                cur.execute(
                    "UPDATE shopping_lists SET updated_at = %s WHERE id = %s",
                    (now, list_id),
                )

    return created_ids


def update_item(
    *,
    list_id: str,
    item_id: str,
    user_id: str,
    name: str | None = None,
    quantity: Decimal | None = None,
    unit: str | None = None,
    notes: str | None = None,
    priority: int | None = None,
    checked: bool | None = None,
) -> Row | None:
    normalized = normalize_item_name(name) if name is not None else None

    with connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE shopping_list_items
                    SET name            = COALESCE(%(name)s, name),
                        normalized_name = COALESCE(%(normalized)s, normalized_name),
                        quantity        = COALESCE(%(quantity)s, quantity),
                        unit            = COALESCE(%(unit)s, unit),
                        notes           = COALESCE(%(notes)s, notes),
                        priority        = COALESCE(%(priority)s, priority),
                        checked         = COALESCE(%(checked)s, checked),
                        checked_at      = CASE
                                              WHEN %(checked)s IS NULL THEN checked_at
                                              WHEN %(checked)s THEN now()
                                              ELSE NULL
                                          END,
                        checked_by      = CASE
                                              WHEN %(checked)s IS NULL THEN checked_by
                                              WHEN %(checked)s THEN %(user_id)s::uuid
                                              ELSE NULL
                                          END,
                        updated_at      = now()
                    WHERE id = %(item_id)s AND shopping_list_id = %(list_id)s
                    RETURNING id
                    """,
                    {
                        "item_id": item_id,
                        "list_id": list_id,
                        "user_id": user_id,
                        "name": name,
                        "normalized": normalized,
                        "quantity": quantity,
                        "unit": unit,
                        "notes": notes,
                        "priority": priority,
                        "checked": checked,
                    },
                )
                if cur.fetchone() is None:
                    return None
                cur.execute(
                    "UPDATE shopping_lists SET updated_at = now() WHERE id = %s",
                    (list_id,),
                )

    return get_item(list_id, item_id)


def set_checked_bulk(
    *,
    list_id: str,
    item_ids: list[str],
    checked: bool,
    user_id: str,
) -> int:
    with connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE shopping_list_items
                    SET checked    = %(checked)s,
                        checked_at = CASE WHEN %(checked)s THEN now() ELSE NULL END,
                        checked_by = CASE WHEN %(checked)s THEN %(user_id)s::uuid ELSE NULL END,
                        updated_at = now()
                    WHERE shopping_list_id = %(list_id)s
                      AND id = ANY(%(ids)s::uuid[])
                    """,
                    {
                        "checked": checked,
                        "user_id": user_id,
                        "list_id": list_id,
                        "ids": item_ids,
                    },
                )
                affected = cur.rowcount
                cur.execute(
                    "UPDATE shopping_lists SET updated_at = now() WHERE id = %s",
                    (list_id,),
                )
    return affected


def delete_item(list_id: str, item_id: str) -> bool:
    with connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM shopping_list_items WHERE id = %s AND shopping_list_id = %s",
                    (item_id, list_id),
                )
                deleted = cur.rowcount
                if deleted:
                    cur.execute(
                        "UPDATE shopping_lists SET updated_at = now() WHERE id = %s",
                        (list_id,),
                    )
    return deleted > 0


def clear_items(list_id: str, *, only_checked: bool = False) -> int:
    condition = " AND checked = true" if only_checked else ""
    with connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM shopping_list_items WHERE shopping_list_id = %s{condition}",
                    (list_id,),
                )
                deleted = cur.rowcount
                cur.execute(
                    "UPDATE shopping_lists SET updated_at = now() WHERE id = %s",
                    (list_id,),
                )
    return deleted


def reorder_items(list_id: str, item_ids: list[str]) -> int:
    """Apply an explicit order; unlisted items keep following the listed ones."""
    with connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE shopping_list_items AS i
                    SET sort_order = ordering.position - 1,
                        updated_at = now()
                    FROM (
                        SELECT id, row_number() OVER () AS position
                        FROM unnest(%(ids)s::uuid[]) AS id
                    ) AS ordering
                    WHERE i.id = ordering.id AND i.shopping_list_id = %(list_id)s
                    """,
                    {"ids": item_ids, "list_id": list_id},
                )
                affected = cur.rowcount
                cur.execute(
                    """
                    UPDATE shopping_list_items
                    SET sort_order = sort_order + %s
                    WHERE shopping_list_id = %s AND NOT (id = ANY(%s::uuid[]))
                    """,
                    (len(item_ids), list_id, item_ids),
                )
                cur.execute(
                    "UPDATE shopping_lists SET updated_at = now() WHERE id = %s",
                    (list_id,),
                )
    return affected


def copy_items_to_lists(
    *,
    source_list_id: str,
    item_ids: list[str],
    target_list_ids: list[str],
    user_id: str,
    skip_duplicates: bool = True,
) -> tuple[int, int]:
    """Copy items into several lists atomically.

    Returns ``(copied, skipped_duplicates)``. One transaction for the whole
    operation, so a mid-way failure cannot leave a half-copied state.
    """
    copied = 0
    skipped = 0
    now = utcnow()

    with connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, name, quantity, unit, notes, priority, product_id
                    FROM shopping_list_items
                    WHERE shopping_list_id = %s AND id = ANY(%s::uuid[])
                    ORDER BY sort_order, added_at
                    """,
                    (source_list_id, item_ids),
                )
                source_items = cur.fetchall()
                if not source_items:
                    return 0, 0

                for target_id in target_list_ids:
                    cur.execute(
                        """
                        SELECT COALESCE(max(sort_order) + 1, 0) AS next_order
                        FROM shopping_list_items
                        WHERE shopping_list_id = %s
                        """,
                        (target_id,),
                    )
                    next_order = int((cur.fetchone() or {"next_order": 0})["next_order"])

                    existing: set[str] = set()
                    if skip_duplicates:
                        cur.execute(
                            """
                            SELECT normalized_name
                            FROM shopping_list_items
                            WHERE shopping_list_id = %s AND normalized_name IS NOT NULL
                            """,
                            (target_id,),
                        )
                        existing = {row["normalized_name"] for row in cur.fetchall()}

                    for item in source_items:
                        normalized = normalize_item_name(item["name"])
                        if skip_duplicates and normalized in existing:
                            skipped += 1
                            continue
                        existing.add(normalized)

                        cur.execute(
                            """
                            INSERT INTO shopping_list_items (
                                shopping_list_id, name, normalized_name, quantity,
                                unit, notes, priority, product_id, added_by,
                                sort_order, added_at, updated_at
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                target_id,
                                item["name"],
                                normalized,
                                item["quantity"],
                                item["unit"],
                                item["notes"],
                                item["priority"],
                                item["product_id"],
                                user_id,
                                next_order,
                                now,
                                now,
                            ),
                        )
                        next_order += 1
                        copied += 1

                cur.execute(
                    "UPDATE shopping_lists SET updated_at = %s WHERE id = ANY(%s::uuid[])",
                    (now, target_list_ids),
                )

    return copied, skipped


def copy_list_as_new(*, source_list_id: str, user_id: str, new_name: str) -> str:
    """Duplicate a list (name + items) into a brand-new list owned by user."""
    new_list_id = str(uuid4())
    now = utcnow()

    with connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO shopping_lists (id, user_id, name, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (new_list_id, user_id, new_name, now, now),
                )
                cur.execute(
                    """
                    INSERT INTO shopping_list_members (shopping_list_id, user_id, role)
                    VALUES (%s, %s, 'owner')
                    """,
                    (new_list_id, user_id),
                )
                cur.execute(
                    """
                    INSERT INTO shopping_list_items (
                        shopping_list_id, name, normalized_name, quantity, unit,
                        notes, priority, product_id, added_by, sort_order,
                        added_at, updated_at
                    )
                    SELECT %(new_id)s, name, normalized_name, quantity, unit,
                           notes, priority, product_id, %(user_id)s, sort_order,
                           %(now)s, %(now)s
                    FROM shopping_list_items
                    WHERE shopping_list_id = %(source_id)s
                    """,
                    {
                        "new_id": new_list_id,
                        "user_id": user_id,
                        "source_id": source_list_id,
                        "now": now,
                    },
                )

    return new_list_id


# -------------------------------------------------------------- membership


def add_member(*, list_id: str, user_id: str, role: str, invited_by: str | None) -> bool:
    with connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO shopping_list_members (shopping_list_id, user_id, role, invited_by)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (shopping_list_id, user_id) DO NOTHING
                    RETURNING id
                    """,
                    (list_id, user_id, role, invited_by),
                )
                inserted = cur.fetchone() is not None
                cur.execute(
                    "UPDATE shopping_lists SET is_shared = true, updated_at = now() WHERE id = %s",
                    (list_id,),
                )
    return inserted


def update_member_role(list_id: str, user_id: str, role: str) -> bool:
    return (
        execute(
            """
            UPDATE shopping_list_members
            SET role = %s
            WHERE shopping_list_id = %s AND user_id = %s AND role <> 'owner'
            """,
            (role, list_id, user_id),
        )
        > 0
    )


def remove_member(list_id: str, user_id: str) -> bool:
    removed = execute(
        """
        DELETE FROM shopping_list_members
        WHERE shopping_list_id = %s AND user_id = %s AND role <> 'owner'
        """,
        (list_id, user_id),
    )
    if removed:
        _refresh_shared_flag(list_id)
    return removed > 0


def set_shared(list_id: str, shared: bool) -> bool:
    return (
        execute(
            "UPDATE shopping_lists SET is_shared = %s, updated_at = now() WHERE id = %s",
            (shared, list_id),
        )
        > 0
    )


def count_members(list_id: str) -> int:
    return int(
        fetch_value(
            "SELECT count(*) FROM shopping_list_members WHERE shopping_list_id = %s",
            (list_id,),
        )
        or 0
    )


def _refresh_shared_flag(list_id: str) -> None:
    """A list stops being 'shared' once only the owner remains."""
    execute(
        """
        UPDATE shopping_lists sl
        SET is_shared = (
            SELECT count(*) > 1
            FROM shopping_list_members m
            WHERE m.shopping_list_id = sl.id
        ),
        updated_at = now()
        WHERE sl.id = %s
        """,
        (list_id,),
    )
