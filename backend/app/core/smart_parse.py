"""Умный разбор свободного ввода товара.

Пользователь пишет "2л молока", "молоко 1.5 литра", "3 шт яйца", "2х500г макароны".
Сервис списков хранит количество и единицу отдельно, поэтому разбор извлекает
их из строки, а в названии оставляет только сам товар.

Чистая функция без обращений к БД: привязка к каталогу происходит позже
в ``app.services.lists`` через ``catalog_repo``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.core.normalization import clean_display_name

# Каноническая единица -> варианты написания.
_UNIT_ALIASES: dict[str, tuple[str, ...]] = {
    "г": ("г", "гр", "грамм", "грамма", "граммов", "граммы"),
    "кг": ("кг", "килограмм", "килограмма", "килограммов", "кило"),
    "мг": ("мг", "миллиграмм"),
    "л": ("л", "литр", "литра", "литров", "литры"),
    "мл": ("мл", "миллилитр", "миллилитра"),
    "шт": ("шт", "штук", "штука", "штуки", "штучка"),
    "уп": ("уп", "упак", "упаковка", "упаковки", "упаковок", "набор"),
    "пачка": ("пач", "пачка", "пачки", "пачек"),
    "бутылка": ("бут", "бутылка", "бутылки", "бутылок"),
    "банка": ("банка", "банки", "банок"),
    "пакет": ("пакет", "пакета", "пакетов"),
    "коробка": ("кор", "коробка", "коробки", "коробок"),
}

_ALIAS_TO_CANONICAL: dict[str, str] = {
    alias: canonical for canonical, aliases in _UNIT_ALIASES.items() for alias in aliases
}

_UNIT_PATTERN = "|".join(
    sorted((_alias for aliases in _UNIT_ALIASES.values() for _alias in aliases), key=len, reverse=True)
)

_PERCENT_RE = re.compile(r"\d+(?:[.,]\d+)?\s*%")
# Мультиупаковка: "2х500г", "2 x 500 г", "3х1л". Количеством считается число
# упаковок (первое число); единица берётся из хвоста, если она там есть.
# Без \b на конце осознанно: в "2х500г" между "500" и "г" границы слова нет.
_MULTIPLIER_RE = re.compile(
    rf"(?P<packs>\d+(?:[.,]\d+)?)\s*[xх]\s*\d+(?:[.,]\d+)?\s*(?P<unit>{_UNIT_PATTERN})?",
    re.IGNORECASE,
)
_QTY_UNIT_RE = re.compile(
    rf"(?P<qty>\d+(?:[.,]\d+)?)\s*(?P<unit>{_UNIT_PATTERN})\b",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"(?P<qty>\d+(?:[.,]\d+)?)")
_WHITESPACE_RE = re.compile(r"\s+")

MAX_QUANTITY = Decimal(100000)


@dataclass(slots=True)
class ParsedItem:
    """Результат разбора: чистое название + количество + единица."""

    name: str
    quantity: Decimal
    unit: str | None


def _to_decimal(raw: str) -> Decimal | None:
    try:
        value = Decimal(raw.replace(",", "."))
    except InvalidOperation:
        return None
    if value <= 0 or value > MAX_QUANTITY:
        return None
    # Нормализуем 2.0 -> 2, но не плодим длинных хвостов.
    return +value


def parse_item_input(raw: str) -> ParsedItem:
    """Разобрать ``2л молока`` -> (``молока``, 2, ``л``).

    Возвращает исходное название (почищенное), если количества в строке нет.
    Никогда не бросает исключений на пользовательских данных.
    """
    cleaned = clean_display_name(raw)
    if not cleaned:
        return ParsedItem(name="", quantity=Decimal(1), unit=None)

    text = unicodedata.normalize("NFKC", cleaned)
    text = _PERCENT_RE.sub(" ", text)

    quantity: Decimal | None = None
    unit: str | None = None

    multiplier = _MULTIPLIER_RE.search(text)
    if multiplier is not None:
        # "2х500г" -> 2 упаковки; "500г" из середины выкидываем целиком,
        # иначе остаток "г" прилипнет к названию.
        quantity = _to_decimal(multiplier.group("packs"))
        if quantity is not None and multiplier.group("unit"):
            unit = _ALIAS_TO_CANONICAL.get(multiplier.group("unit").casefold())
        text = text[: multiplier.start()] + " " + text[multiplier.end():]

    if quantity is None:
        qty_unit = _QTY_UNIT_RE.search(text)
        if qty_unit is not None:
            quantity = _to_decimal(qty_unit.group("qty"))
            if quantity is not None:
                unit = _ALIAS_TO_CANONICAL.get(qty_unit.group("unit").casefold())
            text = text[: qty_unit.start()] + " " + text[qty_unit.end():]

    # Отдельно стоящее число в начале или конце ("2 молока", "молоко 2").
    if quantity is None:
        stripped = text.strip()
        for pattern in (rf"^{_NUMBER_RE.pattern}\b", rf"\b{_NUMBER_RE.pattern}$"):
            match = re.search(pattern, stripped)
            if match is not None:
                parsed = _to_decimal(match.group("qty"))
                if parsed is not None:
                    quantity = parsed
                    stripped = (stripped[: match.start()] + " " + stripped[match.end():]).strip()
                    break
        text = stripped

    name = _WHITESPACE_RE.sub(" ", text).strip(" -")
    if not name:
        # Строка состояла из одного количества ("2 л") — оставляем как есть,
        # чтобы не создавать товар с пустым названием.
        return ParsedItem(name=cleaned, quantity=Decimal(1), unit=None)

    return ParsedItem(name=name, quantity=quantity or Decimal(1), unit=unit)


def apply_parsed(
    *,
    name: str,
    quantity: Decimal,
    unit: str | None,
) -> tuple[str, Decimal, str | None]:
    """Применить разбор, только если количество/единица не заданы явно.

    Возвращает (name, quantity, unit). Явно переданные значения всегда
    приоритетнее разобранных из строки.
    """
    if quantity != Decimal(1) or unit is not None:
        return clean_display_name(name), quantity, unit
    parsed = parse_item_input(name)
    return parsed.name, parsed.quantity, parsed.unit
