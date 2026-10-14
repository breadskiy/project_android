"""Умный разбор ввода: чистая функция, без БД."""

from __future__ import annotations

from decimal import Decimal

from app.core.smart_parse import apply_parsed, parse_item_input


def test_plain_name_untouched() -> None:
    parsed = parse_item_input("хлеб")
    assert parsed.name == "хлеб"
    assert parsed.quantity == Decimal(1)
    assert parsed.unit is None


def test_quantity_unit_prefix() -> None:
    parsed = parse_item_input("2л молока")
    assert parsed.name == "молока"
    assert parsed.quantity == Decimal(2)
    assert parsed.unit == "л"


def test_quantity_unit_suffix_with_decimal_comma() -> None:
    parsed = parse_item_input("сок 0,5л")
    assert parsed.name == "сок"
    assert parsed.quantity == Decimal("0.5")
    assert parsed.unit == "л"


def test_unit_alias_canonicalized() -> None:
    parsed = parse_item_input("Мука 2 КГ")
    assert parsed.name == "Мука"
    assert parsed.quantity == Decimal(2)
    assert parsed.unit == "кг"


def test_piece_count() -> None:
    parsed = parse_item_input("3 шт яйца")
    assert parsed.name == "яйца"
    assert parsed.quantity == Decimal(3)
    assert parsed.unit == "шт"


def test_multipack() -> None:
    parsed = parse_item_input("2х500г макароны")
    assert parsed.name == "макароны"
    assert parsed.quantity == Decimal(2)
    assert parsed.unit == "г"


def test_percent_removed() -> None:
    parsed = parse_item_input("молоко 3.2% 1л")
    assert parsed.name == "молоко"
    assert parsed.quantity == Decimal(1)
    assert parsed.unit == "л"


def test_bare_quantity_is_not_a_name() -> None:
    parsed = parse_item_input("2 л")
    assert parsed.quantity == Decimal(1)
    assert parsed.unit is None


def test_apply_parsed_respects_explicit_values() -> None:
    name, quantity, unit = apply_parsed(name="молоко", quantity=Decimal(5), unit=None)
    assert (name, quantity, unit) == ("молоко", Decimal(5), None)

    name, quantity, unit = apply_parsed(name="2л молока", quantity=Decimal(1), unit=None)
    assert (name, quantity, unit) == ("молока", Decimal(2), "л")
