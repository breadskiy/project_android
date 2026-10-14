-- 004_smart_features.sql
-- Умная составляющая: дневная квота обращений к LLM и индекс для
-- предсказания пополнения запасов (replenish) по истории покупок.
--
-- llm_usage считает платные/медленные вызовы языковой модели на пользователя
-- в сутки (LLM_DAILY_REQUEST_LIMIT_PER_USER). Отдельная маленькая таблица
-- вместо агрегации по events: счётчик нужен до вызова, а не после.

CREATE TABLE IF NOT EXISTS public.llm_usage
(
    user_id uuid NOT NULL,
    day     date NOT NULL,
    count   integer NOT NULL DEFAULT 0,
    CONSTRAINT llm_usage_pkey PRIMARY KEY (user_id, day),
    CONSTRAINT llm_usage_count_non_negative CHECK (count >= 0),
    CONSTRAINT llm_usage_user_fkey FOREIGN KEY (user_id)
        REFERENCES public.users (id) ON DELETE CASCADE
);

-- История покупок одного пользователя: что и когда отмечалось купленным.
-- Используется GET /smart/replenish без какого-либо LLM.
CREATE INDEX IF NOT EXISTS idx_sli_user_purchase_history
    ON public.shopping_list_items (added_by, normalized_name, checked_at DESC)
    WHERE normalized_name IS NOT NULL AND checked_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_llm_usage_day
    ON public.llm_usage (day);
