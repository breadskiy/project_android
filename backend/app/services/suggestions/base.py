"""Provider contract for "bought together" suggestions.

Single table-driven implementation:

``StatisticalProvider``
    Association-rule mining over real lists plus a curated prior. No network,
    single-digit milliseconds, works offline.

Legacy ``llm``/``hybrid`` provider names are accepted by the API for backward
compatibility but resolve to the statistical engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(slots=True)
class Suggestion:
    """One recommended item."""

    name: str
    score: float
    source: str
    reason: str | None = None
    based_on: list[str] = field(default_factory=list)
    product_id: str | None = None
    category: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "score": round(min(1.0, max(0.0, self.score)), 4),
            "source": self.source,
            "reason": self.reason,
            "based_on": self.based_on,
            "product_id": self.product_id,
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "Suggestion":
        return cls(
            name=str(payload["name"]),
            score=float(payload.get("score", 0.0)),
            source=str(payload.get("source", "seed")),
            reason=payload.get("reason"),
            based_on=list(payload.get("based_on") or []),
            product_id=payload.get("product_id"),
            category=payload.get("category"),
        )


@dataclass(slots=True)
class SuggestionRequest:
    """Everything a provider needs, with no HTTP or ORM concepts."""

    user_id: str
    items: list[str]
    """Raw item names currently in the basket."""
    normalized_items: list[str]
    """Normalized keys for the same items."""
    limit: int
    list_id: str | None = None
    exclude: list[str] = field(default_factory=list)
    """Normalized names that must not be suggested (already in the basket)."""


@runtime_checkable
class SuggestionProviderProtocol(Protocol):
    """Contract every suggestion provider implements."""

    name: str
    """Provider identifier stored in the cache and returned to clients."""

    @property
    def model_version(self) -> str | None:
        """Version tag recorded with cached results, if any."""
        ...

    @property
    def available(self) -> bool:
        """False when the provider cannot serve requests (e.g. missing API key)."""
        ...

    async def suggest(self, request: SuggestionRequest) -> list[Suggestion]:
        """Return ranked suggestions, best first."""
        ...
