"""Statistical suggestion provider.

This is market-basket analysis, the technique behind "customers who bought X
also bought Y". Three signals are merged:

1. Curated rules (``seed``) — a small prior so the feature works on day one.
2. Global co-occurrence (``statistical``) — mined from every list in the
   database with support / confidence / lift.
3. Personal co-occurrence (``personal``) — what *this* user buys together,
   which no external model can know.

Personal signal is weighted highest, then global statistics, then the prior.
"""

from __future__ import annotations

from app.config import settings
from app.core.logging import get_logger
from app.db.pool import run_in_thread
from app.repositories import catalog as catalog_repo
from app.repositories import suggestions as suggestions_repo
from app.services.suggestions.base import Suggestion, SuggestionRequest

logger = get_logger("smartsupply.suggestions.statistical")

# Personal habits beat global averages, which beat a hand-written prior.
# "llm" is kept only to rank legacy rows already stored in the DB.
SOURCE_MULTIPLIER = {
    "personal": 1.0,
    "statistical": 0.9,
    "llm": 0.85,
    "seed": 0.8,
}


class StatisticalProvider:
    """Association-rule provider backed entirely by PostgreSQL."""

    name = "statistical"

    @property
    def model_version(self) -> str | None:
        return "stat-v1"

    @property
    def available(self) -> bool:
        return True

    async def suggest(self, request: SuggestionRequest) -> list[Suggestion]:
        return await run_in_thread(self._suggest_sync, request)

    # ------------------------------------------------------------------ impl

    def _suggest_sync(self, request: SuggestionRequest) -> list[Suggestion]:
        normalized = [name for name in request.normalized_items if name]
        if not normalized:
            return []

        # Map synonyms onto catalog keys so a rule for 'картофель' also fires
        # when the user typed 'картошка'.
        canonical = catalog_repo.canonicalize(normalized)
        antecedents = sorted({canonical.get(name, name) for name in normalized})
        origin_of = {canonical.get(name, name): name for name in normalized}

        # Nothing already in the basket should be suggested back.
        exclude = sorted(set(antecedents) | set(normalized) | set(request.exclude))
        # Over-fetch, then merge and re-rank across sources.
        fetch_limit = max(request.limit * 4, 20)

        merged: dict[str, Suggestion] = {}

        personal = suggestions_repo.get_personal_rules(
            request.user_id, antecedents, exclude=exclude, limit=fetch_limit
        )
        for row in personal:
            name = row["consequent"]
            confidence = float(row["confidence"] or 0.0)
            support = int(row["support"])
            self._merge(
                merged,
                Suggestion(
                    name=name,
                    score=confidence * SOURCE_MULTIPLIER["personal"],
                    source="personal",
                    reason=f"Вы покупали это вместе {support} раз(а)",
                    based_on=self._origin_names(request, antecedents, origin_of),
                ),
            )

        rules = suggestions_repo.get_rules_for(
            antecedents,
            exclude=exclude,
            limit=fetch_limit,
            min_weight=0.0,
        )
        for row in rules:
            source = row["source"]
            score = float(row["score"]) * SOURCE_MULTIPLIER.get(source, 0.7)
            self._merge(
                merged,
                Suggestion(
                    name=row["consequent"],
                    score=score,
                    source=source,
                    reason=row["reason"] or self._default_reason(row["antecedent"]),
                    based_on=self._origin_names(request, [row["antecedent"]], origin_of),
                ),
            )

        candidates = [s for s in merged.values() if s.score >= settings.SUGGESTIONS_MIN_SCORE]
        candidates.sort(key=lambda s: (-s.score, s.name))
        top = candidates[: request.limit]

        self._attach_catalog_info(top)
        return top

    @staticmethod
    def _merge(bucket: dict[str, Suggestion], candidate: Suggestion) -> None:
        """Keep the strongest signal per suggested item, merging origins."""
        existing = bucket.get(candidate.name)
        if existing is None:
            bucket[candidate.name] = candidate
            return

        if candidate.score > existing.score:
            merged_origins = list(dict.fromkeys(candidate.based_on + existing.based_on))
            candidate.based_on = merged_origins
            bucket[candidate.name] = candidate
        else:
            existing.based_on = list(dict.fromkeys(existing.based_on + candidate.based_on))

    @staticmethod
    def _origin_names(
        request: SuggestionRequest,
        keys: list[str],
        origin_of: dict[str, str],
    ) -> list[str]:
        """Map rule keys back to what the user actually typed."""
        typed = dict(zip(request.normalized_items, request.items, strict=False))
        result: list[str] = []
        for key in keys:
            if not key:
                continue
            normalized_origin = origin_of.get(key, key)
            result.append(typed.get(normalized_origin, normalized_origin))
        return list(dict.fromkeys(result))

    @staticmethod
    def _default_reason(antecedent: str) -> str:
        return f"Часто покупают вместе с «{antecedent}»"

    @staticmethod
    def _attach_catalog_info(suggestions: list[Suggestion]) -> None:
        """Enrich suggestions with catalog ids and categories in one query."""
        if not suggestions:
            return
        resolved = catalog_repo.resolve_many([s.name for s in suggestions])
        for suggestion in suggestions:
            match = resolved.get(suggestion.name)
            if match is not None:
                suggestion.product_id = str(match["id"])
                suggestion.category = match.get("category_name")
                # Prefer the catalog's canonical spelling.
                suggestion.name = match["name"]
