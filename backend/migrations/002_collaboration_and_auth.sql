-- 002_collaboration_and_auth.sql
-- Replaces the jsonb `sharing_settings` array with a proper membership table,
-- adds invite codes (so a list UUID is no longer the access key) and refresh
-- tokens (so logout and token revocation become possible).

-- ======================================================== membership ======

CREATE TABLE IF NOT EXISTS public.shopping_list_members
(
    id               uuid NOT NULL DEFAULT gen_random_uuid(),
    shopping_list_id uuid NOT NULL,
    user_id          uuid NOT NULL,
    role             text NOT NULL DEFAULT 'editor',
    invited_by       uuid,
    joined_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT shopping_list_members_pkey PRIMARY KEY (id),
    CONSTRAINT shopping_list_members_unique UNIQUE (shopping_list_id, user_id),
    CONSTRAINT shopping_list_members_role_valid
        CHECK (role IN ('owner', 'editor', 'viewer')),
    CONSTRAINT shopping_list_members_list_fkey FOREIGN KEY (shopping_list_id)
        REFERENCES public.shopping_lists (id) ON DELETE CASCADE,
    CONSTRAINT shopping_list_members_user_fkey FOREIGN KEY (user_id)
        REFERENCES public.users (id) ON DELETE CASCADE,
    CONSTRAINT shopping_list_members_invited_by_fkey FOREIGN KEY (invited_by)
        REFERENCES public.users (id) ON DELETE SET NULL
);

COMMENT ON TABLE public.shopping_list_members
    IS 'Участники общих списков с ролями (owner/editor/viewer)';

CREATE INDEX IF NOT EXISTS idx_slm_user
    ON public.shopping_list_members (user_id);

CREATE INDEX IF NOT EXISTS idx_slm_list_role
    ON public.shopping_list_members (shopping_list_id, role);

-- Every existing list owner becomes an explicit 'owner' member.
INSERT INTO public.shopping_list_members (shopping_list_id, user_id, role)
SELECT sl.id, sl.user_id, 'owner'
FROM public.shopping_lists sl
ON CONFLICT (shopping_list_id, user_id) DO NOTHING;

-- Migrate the legacy jsonb array of member ids into real rows.
INSERT INTO public.shopping_list_members (shopping_list_id, user_id, role)
SELECT sl.id, u.id, 'editor'
FROM public.shopping_lists sl
CROSS JOIN LATERAL jsonb_array_elements_text(
    CASE
        WHEN jsonb_typeof(sl.sharing_settings) = 'array' THEN sl.sharing_settings
        ELSE '[]'::jsonb
    END
) AS legacy(member_id)
JOIN public.users u ON u.id::text = legacy.member_id
ON CONFLICT (shopping_list_id, user_id) DO NOTHING;

-- =========================================================== invites ======

CREATE TABLE IF NOT EXISTS public.shopping_list_invites
(
    id               uuid NOT NULL DEFAULT gen_random_uuid(),
    shopping_list_id uuid NOT NULL,
    code             text NOT NULL,
    mode             text NOT NULL DEFAULT 'share',
    role             text NOT NULL DEFAULT 'editor',
    created_by       uuid,
    expires_at       timestamptz,
    max_uses         integer,
    uses             integer NOT NULL DEFAULT 0,
    revoked          boolean NOT NULL DEFAULT false,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT shopping_list_invites_pkey PRIMARY KEY (id),
    CONSTRAINT shopping_list_invites_code_key UNIQUE (code),
    CONSTRAINT shopping_list_invites_mode_valid CHECK (mode IN ('share', 'copy')),
    CONSTRAINT shopping_list_invites_role_valid CHECK (role IN ('editor', 'viewer')),
    CONSTRAINT shopping_list_invites_uses_valid
        CHECK (uses >= 0 AND (max_uses IS NULL OR max_uses > 0)),
    CONSTRAINT shopping_list_invites_code_len
        CHECK (length(code) BETWEEN 8 AND 64),
    CONSTRAINT shopping_list_invites_list_fkey FOREIGN KEY (shopping_list_id)
        REFERENCES public.shopping_lists (id) ON DELETE CASCADE,
    CONSTRAINT shopping_list_invites_creator_fkey FOREIGN KEY (created_by)
        REFERENCES public.users (id) ON DELETE SET NULL
);

COMMENT ON TABLE public.shopping_list_invites
    IS 'Коды приглашения: доступ к списку больше не равен знанию его UUID';

CREATE INDEX IF NOT EXISTS idx_invites_list
    ON public.shopping_list_invites (shopping_list_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_invites_active
    ON public.shopping_list_invites (code)
    WHERE revoked = false;

-- ==================================================== refresh tokens ======
-- Only the SHA-256 hash is stored, so a database dump does not hand out live
-- sessions. Rotation is tracked via replaced_by to detect token reuse.

CREATE TABLE IF NOT EXISTS public.refresh_tokens
(
    id          uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL,
    token_hash  text NOT NULL,
    issued_at   timestamptz NOT NULL DEFAULT now(),
    expires_at  timestamptz NOT NULL,
    revoked_at  timestamptz,
    replaced_by uuid,
    user_agent  text,
    ip_address  inet,
    CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id),
    CONSTRAINT refresh_tokens_hash_key UNIQUE (token_hash),
    CONSTRAINT refresh_tokens_user_fkey FOREIGN KEY (user_id)
        REFERENCES public.users (id) ON DELETE CASCADE,
    CONSTRAINT refresh_tokens_replaced_by_fkey FOREIGN KEY (replaced_by)
        REFERENCES public.refresh_tokens (id) ON DELETE SET NULL,
    CONSTRAINT refresh_tokens_ua_len CHECK (user_agent IS NULL OR length(user_agent) <= 512),
    CONSTRAINT refresh_tokens_expiry_after_issue CHECK (expires_at > issued_at)
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user
    ON public.refresh_tokens (user_id, expires_at DESC);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_active
    ON public.refresh_tokens (expires_at)
    WHERE revoked_at IS NULL;

-- ================================================== user preferences ======
-- Home of the AI suggestions toggle. The table already existed but was unused.

ALTER TABLE public.user_preferences
    ADD COLUMN IF NOT EXISTS ai_suggestions_enabled boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS suggestions_limit integer NOT NULL DEFAULT 5,
    ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

ALTER TABLE public.user_preferences
    DROP CONSTRAINT IF EXISTS user_preferences_suggestions_limit_range;

ALTER TABLE public.user_preferences
    ADD CONSTRAINT user_preferences_suggestions_limit_range
        CHECK (suggestions_limit BETWEEN 1 AND 20);
