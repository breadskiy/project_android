"""Text normalization for item names, catalog matching and suggestions.

Users type "2 л Молока 3.2%", the catalog stores "молоко". Normalization maps
both onto the same key so pair rules and catalog lookups actually match.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final

# Units and packaging words that carry no product identity.
_UNIT_WORDS: Final = frozenset(
    {
        "г", "гр", "грамм", "граммов", "кг", "килограмм", "килограмма",
        "мг", "л", "литр", "литра", "литров", "мл", "шт", "штук", "штуки",
        "уп", "упак", "упаковка", "упаковки", "пач", "пачка", "пачки",
        "бут", "бутылка", "бутылки", "банка", "банки", "пакет", "пакета",
        "кор", "коробка", "коробки", "ящик", "ведро", "рулон", "рулонов",
        "пара", "пары", "набор", "порция", "порций", "дюжина",
    }
)

# Words that describe a purchase, not a product.
_NOISE_WORDS: Final = frozenset(
    {
        "купить", "взять", "надо", "нужно", "срочно", "ещё", "еще",
        "штучка", "чуть", "немного", "побольше", "поменьше", "любой",
        "свежий", "свежая", "свежее", "любое",
    }
)

_QUANTITY_RE: Final = re.compile(r"^\d+(?:[.,]\d+)?$")
_PERCENT_RE: Final = re.compile(r"\d+(?:[.,]\d+)?\s*%")
_MULTIPLIER_RE: Final = re.compile(r"\b[xх]\s*\d+\b", re.IGNORECASE)
_NUMBER_WITH_UNIT_RE: Final = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:г|гр|кг|мг|л|мл|шт|уп|пач)\b",
    re.IGNORECASE,
)
_PUNCT_RE: Final = re.compile(r"[^\w\s\-]+", re.UNICODE)
_WHITESPACE_RE: Final = re.compile(r"\s+")

MAX_NORMALIZED_LENGTH: Final = 300


def clean_display_name(value: str) -> str:
    """Tidy a user-supplied name while keeping it human-readable."""
    text = unicodedata.normalize("NFKC", value)
    # Turn tabs/newlines into spaces *before* dropping control characters,
    # otherwise "Мой\tсписок" would collapse into "Мойсписок".
    text = _WHITESPACE_RE.sub(" ", text)
    text = "".join(ch for ch in text if ch.isprintable())
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text[:MAX_NORMALIZED_LENGTH]


def normalize_item_name(value: str) -> str:
    """Reduce a free-form item name to a stable matching key.

    >>> normalize_item_name("2 л Молока 3.2%")
    'молока'
    >>> normalize_item_name("  ХЛЕБ   Бородинский  ")
    'хлеб бородинский'
    """
    text = unicodedata.normalize("NFKC", value).casefold()
    text = text.replace("ё", "е")

    text = _PERCENT_RE.sub(" ", text)
    text = _NUMBER_WITH_UNIT_RE.sub(" ", text)
    text = _MULTIPLIER_RE.sub(" ", text)
    text = _PUNCT_RE.sub(" ", text)

    tokens: list[str] = []
    for token in _WHITESPACE_RE.split(text):
        token = token.strip("-")
        if not token:
            continue
        if _QUANTITY_RE.match(token):
            continue
        if token in _UNIT_WORDS or token in _NOISE_WORDS:
            continue
        tokens.append(token)

    if not tokens:
        # Everything was stripped (e.g. the name was just "2 л"); fall back to
        # a whitespace-collapsed version so the key is never empty.
        fallback = _WHITESPACE_RE.sub(" ", text).strip()
        return fallback[:MAX_NORMALIZED_LENGTH]

    return " ".join(tokens)[:MAX_NORMALIZED_LENGTH]


def head_noun(value: str) -> str:
    """First meaningful token: 'молоко простоквашино' -> 'молоко'."""
    normalized = normalize_item_name(value)
    return normalized.split(" ", 1)[0] if normalized else ""


def basket_key(names: list[str]) -> str:
    """Order-independent key for a set of items, used for cache lookups."""
    unique = sorted({normalize_item_name(name) for name in names if name.strip()})
    return "|".join(unique)
