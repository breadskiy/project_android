-- database/database.sql
-- Базовая схема Smart Supply Lists.
--
-- Этот файл создаёт таблицы, которые миграции 001-003 только ужесточают
-- (constraints/индексы) и дополняют (members/invites/catalog/suggestions).
-- Идемпотентен: можно безопасно выполнять на существующей базе.
--
-- Порядок важен из-за внешних ключей: users -> lists/items, categories ->
-- products -> items.

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Тип событий для таблицы events. Миграции его не создают, поэтому он здесь.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'event_type_t') THEN
        CREATE TYPE event_type_t AS ENUM (
            'view',
            'click',
            'add_to_cart',
            'remove_from_cart',
            'purchase',
            'llm_request'
        );
    END IF;
END
$$;

-- ============================================================== users =====

CREATE TABLE IF NOT EXISTS public.users
(
    id               uuid        NOT NULL DEFAULT gen_random_uuid(),
    email            text        NOT NULL,
    password_hash    text        NOT NULL,
    display_name     text        NOT NULL DEFAULT 'Пользователь',
    phone            text        NOT NULL DEFAULT '',
    locale           text        NOT NULL DEFAULT 'ru-RU',
    timezone         text        NOT NULL DEFAULT 'Europe/Moscow',
    profile          jsonb       NOT NULL DEFAULT '{}'::jsonb,
    preferred_store_id uuid,
    is_active        boolean     NOT NULL DEFAULT true,
    email_verified   boolean     NOT NULL DEFAULT false,
    created_at       timestamptz NOT NULL DEFAULT now(),
    last_login       timestamptz,
    CONSTRAINT users_pkey PRIMARY KEY (id),
    CONSTRAINT users_email_key UNIQUE (email)
);

CREATE TABLE IF NOT EXISTS public.user_preferences
(
    user_id                uuid        NOT NULL,
    ai_suggestions_enabled boolean     NOT NULL DEFAULT true,
    suggestions_limit      integer     NOT NULL DEFAULT 5,
    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT user_preferences_pkey PRIMARY KEY (user_id),
    CONSTRAINT user_preferences_user_fkey FOREIGN KEY (user_id)
        REFERENCES public.users (id) ON DELETE CASCADE
);

-- ===================================================== shopping_lists =====

CREATE TABLE IF NOT EXISTS public.shopping_lists
(
    id               uuid        NOT NULL DEFAULT gen_random_uuid(),
    user_id          uuid        NOT NULL,
    name             text        NOT NULL,
    description      text,
    is_shared        boolean     NOT NULL DEFAULT false,
    sharing_settings jsonb       NOT NULL DEFAULT '[]'::jsonb,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT shopping_lists_pkey PRIMARY KEY (id),
    CONSTRAINT shopping_lists_user_fkey FOREIGN KEY (user_id)
        REFERENCES public.users (id) ON DELETE CASCADE
);

-- ========================================================== categories =====

CREATE TABLE IF NOT EXISTS public.categories
(
    id         uuid        NOT NULL DEFAULT gen_random_uuid(),
    name       text        NOT NULL,
    parent_id  uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT categories_pkey PRIMARY KEY (id),
    CONSTRAINT categories_parent_fkey FOREIGN KEY (parent_id)
        REFERENCES public.categories (id) ON DELETE SET NULL
);

-- ============================================================ products =====

CREATE TABLE IF NOT EXISTS public.products
(
    id              uuid        NOT NULL DEFAULT gen_random_uuid(),
    name            text        NOT NULL,
    normalized_name text,
    category_id     uuid,
    default_unit    text,
    popularity      integer     NOT NULL DEFAULT 0,
    is_active       boolean     NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT products_pkey PRIMARY KEY (id),
    CONSTRAINT products_category_fkey FOREIGN KEY (category_id)
        REFERENCES public.categories (id) ON DELETE SET NULL
);

-- ================================================ shopping_list_items =====

CREATE TABLE IF NOT EXISTS public.shopping_list_items
(
    id               uuid        NOT NULL DEFAULT gen_random_uuid(),
    shopping_list_id uuid        NOT NULL,
    name             text        NOT NULL,
    normalized_name  text,
    quantity         numeric     NOT NULL DEFAULT 1,
    unit             text,
    notes            text,
    priority         integer     NOT NULL DEFAULT 1,
    checked          boolean     NOT NULL DEFAULT false,
    checked_at       timestamptz,
    checked_by       uuid,
    added_by         uuid,
    product_id       uuid,
    sort_order       integer     NOT NULL DEFAULT 0,
    added_at         timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT shopping_list_items_pkey PRIMARY KEY (id),
    CONSTRAINT sli_list_fkey FOREIGN KEY (shopping_list_id)
        REFERENCES public.shopping_lists (id) ON DELETE CASCADE,
    CONSTRAINT sli_checked_by_fkey FOREIGN KEY (checked_by)
        REFERENCES public.users (id) ON DELETE SET NULL,
    CONSTRAINT sli_added_by_fkey FOREIGN KEY (added_by)
        REFERENCES public.users (id) ON DELETE SET NULL,
    CONSTRAINT sli_product_fkey FOREIGN KEY (product_id)
        REFERENCES public.products (id) ON DELETE SET NULL
);

-- ============================================================= events =====
-- Сырой сигнал для статистики и ML: покупки, клики, обращения к LLM.

CREATE TABLE IF NOT EXISTS public.events
(
    id          uuid        NOT NULL DEFAULT gen_random_uuid(),
    user_id     uuid,
    event_type  event_type_t NOT NULL,
    entity_type text,
    entity_id   text,
    metadata    jsonb       NOT NULL DEFAULT '{}'::jsonb,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT events_pkey PRIMARY KEY (id),
    CONSTRAINT events_user_fkey FOREIGN KEY (user_id)
        REFERENCES public.users (id) ON DELETE CASCADE
);

-- ==================================================== recommendations =====
-- Зарезервировано под персональные рекомендации; индексы добавляет 003.

CREATE TABLE IF NOT EXISTS public.recommendations
(
    id         uuid        NOT NULL DEFAULT gen_random_uuid(),
    user_id    uuid        NOT NULL,
    product_id uuid        NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT recommendations_pkey PRIMARY KEY (id),
    CONSTRAINT recommendations_user_fkey FOREIGN KEY (user_id)
        REFERENCES public.users (id) ON DELETE CASCADE,
    CONSTRAINT recommendations_product_fkey FOREIGN KEY (product_id)
        REFERENCES public.products (id) ON DELETE CASCADE
);
