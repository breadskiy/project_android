"""Seed the product catalog and the curated "bought together" prior.

Usage:
    python scripts/seed_catalog.py                 # seed the app database
    python scripts/seed_catalog.py --dbname X      # seed another database
    python scripts/seed_catalog.py --rebuild-stats # also re-mine statistics

Idempotent: running it twice changes nothing beyond refreshing weights.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings  # noqa: E402
from app.core.normalization import normalize_item_name  # noqa: E402
from app.db import pool  # noqa: E402
from app.repositories import catalog as catalog_repo  # noqa: E402
from app.repositories import suggestions as suggestions_repo  # noqa: E402
from app.services.suggestions import seed_data  # noqa: E402


def seed_catalog() -> tuple[int, int, int]:
    """Insert categories, products and aliases. Returns the counts written."""
    categories: dict[str, str] = {}
    products = 0
    aliases = 0

    for category_name, name, unit, alias_list in seed_data.iter_products():
        if category_name not in categories:
            categories[category_name] = catalog_repo.upsert_category(category_name)

        product_id = catalog_repo.upsert_product(
            name=name,
            category_id=categories[category_name],
            default_unit=unit,
            popularity=0,
        )
        products += 1

        for alias in alias_list:
            catalog_repo.upsert_alias(product_id=product_id, alias=alias, source="seed")
            aliases += 1

    return len(categories), products, aliases


def seed_pair_rules() -> int:
    """Insert the curated prior, linking rules to catalog products when possible."""
    normalized_names: set[str] = set()
    for antecedent, consequent, _, _ in seed_data.iter_pair_rules():
        normalized_names.add(normalize_item_name(antecedent))
        normalized_names.add(normalize_item_name(consequent))

    resolved = catalog_repo.resolve_many(sorted(normalized_names))

    rules = []
    for antecedent, consequent, weight, reason in seed_data.iter_pair_rules():
        norm_antecedent = normalize_item_name(antecedent)
        norm_consequent = normalize_item_name(consequent)
        if not norm_antecedent or not norm_consequent or norm_antecedent == norm_consequent:
            continue

        antecedent_match = resolved.get(norm_antecedent)
        consequent_match = resolved.get(norm_consequent)

        rules.append(
            {
                "antecedent": norm_antecedent,
                "consequent": norm_consequent,
                "antecedent_id": str(antecedent_match["id"]) if antecedent_match else None,
                "consequent_id": str(consequent_match["id"]) if consequent_match else None,
                "source": "seed",
                "weight": weight,
                "support": 0,
                "confidence": None,
                "lift": None,
                "reason": reason,
                "model_version": "seed-v1",
            }
        )

    return suggestions_repo.upsert_rules(rules)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed catalog and suggestion rules")
    parser.add_argument("--dbname", default=None, help="Override the target database")
    parser.add_argument("--rebuild-stats", action="store_true", help="Re-mine statistical rules")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.dbname:
        settings.DB_NAME = args.dbname  # type: ignore[misc]

    def log(message: str) -> None:
        if not args.quiet:
            print(message)

    log(f"database: {settings.DB_NAME}")
    pool.init_pool()
    try:
        categories, products, aliases = seed_catalog()
        log(f"catalog: {categories} categories, {products} products, {aliases} aliases")

        rules = seed_pair_rules()
        log(f"pair rules (seed): {rules}")

        if args.rebuild_stats:
            written, baskets = suggestions_repo.rebuild_statistical_rules()
            log(f"statistical rules: {written} from {baskets} baskets")

        suggestions_repo.invalidate_cache()
        counts = suggestions_repo.count_rules_by_source()
        log(f"rules by source: {counts}")
        log(f"catalog size: {catalog_repo.count_products()} active products")
    finally:
        pool.close_pool()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
