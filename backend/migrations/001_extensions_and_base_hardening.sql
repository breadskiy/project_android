-- 001_extensions_and_base_hardening.sql
-- Enables the text-search extensions used by catalog search and tightens the
-- constraints that the original pgAdmin-generated schema left open.
--
-- Style note: PostgreSQL has no "ADD CONSTRAINT IF NOT EXISTS", so every
-- constraint is dropped first. That keeps each migration safely re-runnable.

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- ============================================================== users =====

-- Emails must be unique case-insensitively: 'User@x.ru' and 'user@x.ru' are
-- the same account. The original schema only had a plain UNIQUE(email).
UPDATE public.users SET email = lower(btrim(email)) WHERE email <> lower(btrim(email));

CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower_key
    ON public.users (lower(email));

-- Backfill before tightening, otherwise SET NOT NULL fails on existing rows.
UPDATE public.users
SET display_name = 'Пользователь'
WHERE display_name IS NULL OR length(btrim(display_name)) = 0;

ALTER TABLE public.users
    ALTER COLUMN display_name SET NOT NULL;

ALTER TABLE public.users DROP CONSTRAINT IF EXISTS users_email_not_blank;
ALTER TABLE public.users DROP CONSTRAINT IF EXISTS users_display_name_not_blank;
ALTER TABLE public.users DROP CONSTRAINT IF EXISTS users_password_hash_present;
ALTER TABLE public.users DROP CONSTRAINT IF EXISTS users_email_max_len;

ALTER TABLE public.users
    ADD CONSTRAINT users_email_not_blank CHECK (length(btrim(email)) > 0),
    ADD CONSTRAINT users_email_max_len CHECK (length(email) <= 254),
    ADD CONSTRAINT users_display_name_not_blank CHECK (length(btrim(display_name)) > 0),
    ADD CONSTRAINT users_password_hash_present CHECK (password_hash IS NOT NULL);

CREATE INDEX IF NOT EXISTS idx_users_active
    ON public.users (is_active)
    WHERE is_active = true;

-- ===================================================== shopping_lists =====

ALTER TABLE public.shopping_lists DROP CONSTRAINT IF EXISTS shopping_lists_name_not_blank;
ALTER TABLE public.shopping_lists DROP CONSTRAINT IF EXISTS shopping_lists_name_max_len;

ALTER TABLE public.shopping_lists
    ADD CONSTRAINT shopping_lists_name_not_blank CHECK (length(btrim(name)) > 0),
    ADD CONSTRAINT shopping_lists_name_max_len CHECK (length(name) <= 200);

CREATE INDEX IF NOT EXISTS idx_shopping_lists_owner_created
    ON public.shopping_lists (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_shopping_lists_updated
    ON public.shopping_lists (updated_at DESC);

-- At most one system favourites list per user.
-- Duplicates from the CLI era are collapsed before the index is created.
WITH ranked AS (
    SELECT id,
           row_number() OVER (PARTITION BY user_id ORDER BY created_at) AS rn
    FROM public.shopping_lists
    WHERE description = 'system_favorite'
)
UPDATE public.shopping_lists sl
SET description = 'system_favorite_duplicate'
FROM ranked
WHERE sl.id = ranked.id AND ranked.rn > 1;

CREATE UNIQUE INDEX IF NOT EXISTS uq_shopping_lists_system_favorite
    ON public.shopping_lists (user_id)
    WHERE description = 'system_favorite';

COMMENT ON COLUMN public.shopping_lists.sharing_settings
    IS 'DEPRECATED: заменено таблицей shopping_list_members (миграция 002)';

-- ================================================ shopping_list_items =====

ALTER TABLE public.shopping_list_items
    ADD COLUMN IF NOT EXISTS checked_at       timestamptz,
    ADD COLUMN IF NOT EXISTS checked_by       uuid,
    ADD COLUMN IF NOT EXISTS added_by         uuid,
    ADD COLUMN IF NOT EXISTS normalized_name  text,
    ADD COLUMN IF NOT EXISTS sort_order       integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS updated_at       timestamptz NOT NULL DEFAULT now();

ALTER TABLE public.shopping_list_items DROP CONSTRAINT IF EXISTS sli_name_not_blank;
ALTER TABLE public.shopping_list_items DROP CONSTRAINT IF EXISTS sli_name_max_len;
ALTER TABLE public.shopping_list_items DROP CONSTRAINT IF EXISTS sli_quantity_positive;
ALTER TABLE public.shopping_list_items DROP CONSTRAINT IF EXISTS sli_priority_range;
ALTER TABLE public.shopping_list_items DROP CONSTRAINT IF EXISTS sli_notes_max_len;
ALTER TABLE public.shopping_list_items DROP CONSTRAINT IF EXISTS sli_unit_max_len;
ALTER TABLE public.shopping_list_items DROP CONSTRAINT IF EXISTS sli_checked_consistency;
ALTER TABLE public.shopping_list_items DROP CONSTRAINT IF EXISTS sli_checked_by_fkey;
ALTER TABLE public.shopping_list_items DROP CONSTRAINT IF EXISTS sli_added_by_fkey;

ALTER TABLE public.shopping_list_items
    ADD CONSTRAINT sli_name_not_blank CHECK (length(btrim(name)) > 0),
    ADD CONSTRAINT sli_name_max_len CHECK (length(name) <= 300),
    ADD CONSTRAINT sli_quantity_positive CHECK (quantity > 0 AND quantity <= 100000),
    ADD CONSTRAINT sli_priority_range CHECK (priority BETWEEN 0 AND 3),
    ADD CONSTRAINT sli_notes_max_len CHECK (notes IS NULL OR length(notes) <= 1000),
    ADD CONSTRAINT sli_unit_max_len CHECK (unit IS NULL OR length(unit) <= 32),
    -- An unchecked item must not carry a "checked at" timestamp.
    ADD CONSTRAINT sli_checked_consistency
        CHECK (checked = true OR checked_at IS NULL),
    ADD CONSTRAINT sli_checked_by_fkey FOREIGN KEY (checked_by)
        REFERENCES public.users (id) ON DELETE SET NULL,
    ADD CONSTRAINT sli_added_by_fkey FOREIGN KEY (added_by)
        REFERENCES public.users (id) ON DELETE SET NULL;

-- The hot path is "all items of one list, in display order".
CREATE INDEX IF NOT EXISTS idx_sli_list_order
    ON public.shopping_list_items (shopping_list_id, sort_order, added_at);

CREATE INDEX IF NOT EXISTS idx_sli_product
    ON public.shopping_list_items (product_id)
    WHERE product_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_sli_normalized
    ON public.shopping_list_items (normalized_name)
    WHERE normalized_name IS NOT NULL;

-- ============================================================= events =====
-- Events are the raw signal the recommendation statistics are built from.

CREATE INDEX IF NOT EXISTS idx_events_user_created
    ON public.events (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_events_type_created
    ON public.events (event_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_events_entity
    ON public.events (entity_type, entity_id);
