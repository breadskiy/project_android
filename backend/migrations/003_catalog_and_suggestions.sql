-- 003_catalog_and_suggestions.sql
-- Product catalog support (fuzzy search, aliases, normalized names) and the
-- storage that the recommendation engine reads and writes.

-- =========================================================== catalog ======

ALTER TABLE public.products
    ADD COLUMN IF NOT EXISTS normalized_name text,
    ADD COLUMN IF NOT EXISTS popularity integer NOT NULL DEFAULT 0;

ALTER TABLE public.products DROP CONSTRAINT IF EXISTS products_name_not_blank;
ALTER TABLE public.products DROP CONSTRAINT IF EXISTS products_popularity_non_negative;

ALTER TABLE public.products
    ADD CONSTRAINT products_name_not_blank CHECK (length(btrim(name)) > 0),
    ADD CONSTRAINT products_popularity_non_negative CHECK (popularity >= 0);

UPDATE public.products
SET normalized_name = lower(btrim(name))
WHERE normalized_name IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_products_normalized_name
    ON public.products (normalized_name)
    WHERE normalized_name IS NOT NULL;

-- Trigram indexes power fuzzy search: 'малоко' still finds 'молоко'.
CREATE INDEX IF NOT EXISTS idx_products_name_trgm
    ON public.products USING gin (name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_products_normalized_trgm
    ON public.products USING gin (normalized_name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_products_category
    ON public.products (category_id)
    WHERE category_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_products_popularity
    ON public.products (popularity DESC);

ALTER TABLE public.categories DROP CONSTRAINT IF EXISTS categories_name_not_blank;

ALTER TABLE public.categories
    ADD CONSTRAINT categories_name_not_blank CHECK (length(btrim(name)) > 0);

CREATE UNIQUE INDEX IF NOT EXISTS uq_categories_name_lower
    ON public.categories (lower(name));

-- Aliases map what users type onto catalog products ('картоха' -> 'картофель').
CREATE TABLE IF NOT EXISTS public.product_aliases
(
    id         uuid NOT NULL DEFAULT gen_random_uuid(),
    product_id uuid NOT NULL,
    alias      text NOT NULL,
    source     text NOT NULL DEFAULT 'seed',
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT product_aliases_pkey PRIMARY KEY (id),
    CONSTRAINT product_aliases_alias_key UNIQUE (alias),
    CONSTRAINT product_aliases_alias_not_blank CHECK (length(btrim(alias)) > 0),
    CONSTRAINT product_aliases_alias_max_len CHECK (length(alias) <= 200),
    CONSTRAINT product_aliases_source_valid CHECK (source IN ('seed', 'llm', 'user')),
    CONSTRAINT product_aliases_product_fkey FOREIGN KEY (product_id)
        REFERENCES public.products (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_product_aliases_product
    ON public.product_aliases (product_id);

CREATE INDEX IF NOT EXISTS idx_product_aliases_alias_trgm
    ON public.product_aliases USING gin (alias gin_trgm_ops);

-- ======================================================== pair rules ======
-- "Bought together" rules keyed by normalized item names, so they also work
-- for items that are not linked to a catalog product yet.
--
--   seed        curated prior; makes the feature work on an empty database
--   statistical mined from real co-occurrence in users' lists
--   llm         produced by the language model (stage 8)

CREATE TABLE IF NOT EXISTS public.product_pair_rules
(
    id             uuid NOT NULL DEFAULT gen_random_uuid(),
    antecedent     text NOT NULL,
    consequent     text NOT NULL,
    antecedent_id  uuid,
    consequent_id  uuid,
    source         text NOT NULL DEFAULT 'seed',
    weight         double precision NOT NULL DEFAULT 0.5,
    support        integer NOT NULL DEFAULT 0,
    confidence     double precision,
    lift           double precision,
    reason         text,
    model_version  text,
    accepted_count integer NOT NULL DEFAULT 0,
    rejected_count integer NOT NULL DEFAULT 0,
    refreshed_at   timestamptz NOT NULL DEFAULT now(),
    created_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT product_pair_rules_pkey PRIMARY KEY (id),
    CONSTRAINT product_pair_rules_unique UNIQUE (antecedent, consequent, source),
    CONSTRAINT product_pair_rules_distinct CHECK (antecedent <> consequent),
    CONSTRAINT product_pair_rules_not_blank
        CHECK (length(btrim(antecedent)) > 0 AND length(btrim(consequent)) > 0),
    CONSTRAINT product_pair_rules_source_valid
        CHECK (source IN ('seed', 'statistical', 'llm')),
    CONSTRAINT product_pair_rules_weight_range CHECK (weight >= 0 AND weight <= 1),
    CONSTRAINT product_pair_rules_counts_non_negative
        CHECK (support >= 0 AND accepted_count >= 0 AND rejected_count >= 0),
    CONSTRAINT product_pair_rules_antecedent_fkey FOREIGN KEY (antecedent_id)
        REFERENCES public.products (id) ON DELETE SET NULL,
    CONSTRAINT product_pair_rules_consequent_fkey FOREIGN KEY (consequent_id)
        REFERENCES public.products (id) ON DELETE SET NULL
);

COMMENT ON TABLE public.product_pair_rules
    IS 'Правила "часто покупают вместе": курируемые, статистические и от LLM';

CREATE INDEX IF NOT EXISTS idx_pair_rules_antecedent
    ON public.product_pair_rules (antecedent, weight DESC);

CREATE INDEX IF NOT EXISTS idx_pair_rules_consequent
    ON public.product_pair_rules (consequent);

CREATE INDEX IF NOT EXISTS idx_pair_rules_source
    ON public.product_pair_rules (source, refreshed_at DESC);

-- ============================================== suggestion cache & log ====
-- Cache keyed by a hash of the normalized basket, so a repeated basket is one
-- indexed lookup instead of a recomputation or a paid LLM call.

CREATE TABLE IF NOT EXISTS public.suggestion_cache
(
    id            uuid NOT NULL DEFAULT gen_random_uuid(),
    basket_hash   text NOT NULL,
    provider      text NOT NULL,
    payload       jsonb NOT NULL,
    model_version text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    expires_at    timestamptz,
    hits          integer NOT NULL DEFAULT 0,
    CONSTRAINT suggestion_cache_pkey PRIMARY KEY (id),
    CONSTRAINT suggestion_cache_unique UNIQUE (basket_hash, provider),
    CONSTRAINT suggestion_cache_provider_valid
        CHECK (provider IN ('statistical', 'llm', 'hybrid')),
    CONSTRAINT suggestion_cache_hash_len CHECK (length(basket_hash) BETWEEN 16 AND 128),
    CONSTRAINT suggestion_cache_hits_non_negative CHECK (hits >= 0)
);

CREATE INDEX IF NOT EXISTS idx_suggestion_cache_expires
    ON public.suggestion_cache (expires_at)
    WHERE expires_at IS NOT NULL;

-- Explicit user feedback: the signal that lets suggestions improve over time.
CREATE TABLE IF NOT EXISTS public.suggestion_feedback
(
    id               uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id          uuid NOT NULL,
    shopping_list_id uuid,
    suggested_name   text NOT NULL,
    based_on         text[],
    action           text NOT NULL,
    provider         text,
    model_version    text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT suggestion_feedback_pkey PRIMARY KEY (id),
    CONSTRAINT suggestion_feedback_action_valid
        CHECK (action IN ('accepted', 'rejected', 'shown')),
    CONSTRAINT suggestion_feedback_name_len
        CHECK (length(btrim(suggested_name)) > 0 AND length(suggested_name) <= 300),
    CONSTRAINT suggestion_feedback_user_fkey FOREIGN KEY (user_id)
        REFERENCES public.users (id) ON DELETE CASCADE,
    CONSTRAINT suggestion_feedback_list_fkey FOREIGN KEY (shopping_list_id)
        REFERENCES public.shopping_lists (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_suggestion_feedback_user
    ON public.suggestion_feedback (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_suggestion_feedback_name
    ON public.suggestion_feedback (suggested_name, action);

-- The pre-existing recommendations table finally gets its indexes.
CREATE INDEX IF NOT EXISTS idx_recommendations_user_created
    ON public.recommendations (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_recommendations_product
    ON public.recommendations (product_id);
