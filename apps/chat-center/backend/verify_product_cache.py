#!/usr/bin/env python3
"""Verification script for Product Cache implementation.

Run this to verify:
1. All imports work
2. Functions are callable
3. Basic logic is correct
"""

import sys


def verify_imports():
    """Verify all imports work."""
    print("✓ Verifying imports...")

    try:
        from app.models.product_cache import ProductCache
        print("  ✓ ProductCache model imported")
    except ImportError as e:
        print(f"  ✗ Failed to import ProductCache: {e}")
        return False

    try:
        from app.services.product_cache_service import (
            get_basket_number,
            build_card_url,
            fetch_product_from_cdn,
            get_or_fetch_product,
            get_product_context_for_draft,
            CACHE_TTL_HOURS,
            CDN_TIMEOUT_SECONDS,
        )
        print("  ✓ All service functions imported")
    except ImportError as e:
        print(f"  ✗ Failed to import service functions: {e}")
        return False

    return True


def verify_basket_number():
    """Verify basket number calculation."""
    print("\n✓ Verifying basket number calculation...")

    from app.services.product_cache_service import get_basket_number

    test_cases = [
        (14300000, "01"),   # vol=143 → 01
        (14400000, "02"),   # vol=144 → 02
        (28700000, "02"),   # vol=287 → 02
        (28800000, "03"),   # vol=288 → 03
        (348500000, "20"),  # vol=3485 → 20
        (348600000, "21"),  # vol=3486 → 21
        (456500000, "25"),  # vol=4565 → 25
        (456600000, "26"),  # vol=4566 → 26
        (500000000, "26"),  # vol=5000 → 26
    ]

    for nm_id, expected in test_cases:
        result = get_basket_number(nm_id)
        if result == expected:
            print(f"  ✓ nm_id={nm_id} → basket={result}")
        else:
            print(f"  ✗ nm_id={nm_id}: expected {expected}, got {result}")
            return False

    return True


def verify_url_builder():
    """Verify URL builder."""
    print("\n✓ Verifying URL builder...")

    from app.services.product_cache_service import build_card_url

    nm_id = 12345678
    url = build_card_url(nm_id)
    expected = "https://basket-03.wbbasket.ru/vol123/part12345/12345678/info/ru/card.json"

    if url == expected:
        print(f"  ✓ URL correctly formatted")
        print(f"    {url}")
    else:
        print(f"  ✗ URL mismatch")
        print(f"    Expected: {expected}")
        print(f"    Got:      {url}")
        return False

    return True


def verify_context_formatter():
    """Verify context string formatter."""
    print("\n✓ Verifying context formatter...")

    from app.models.product_cache import ProductCache
    from app.services.product_cache_service import get_product_context_for_draft

    # Test with full product
    product = ProductCache(
        nm_id="12345678",
        name="Nike Air Max 90",
        brand="Nike",
        category="Кроссовки",
        options=[
            {"name": "Размер", "value": "42"},
            {"name": "Цвет", "value": "Черный"},
        ],
    )

    context = get_product_context_for_draft(product)

    required_parts = [
        "Товар: Nike Air Max 90",
        "Бренд: Nike",
        "Категория: Кроссовки",
        "Характеристики: Размер: 42, Цвет: Черный",
    ]

    for part in required_parts:
        if part in context:
            print(f"  ✓ Contains: {part}")
        else:
            print(f"  ✗ Missing: {part}")
            print(f"    Full context: {context}")
            return False

    # Test with None
    context_none = get_product_context_for_draft(None)
    if context_none == "":
        print("  ✓ Returns empty string for None")
    else:
        print(f"  ✗ Expected empty string for None, got: {context_none}")
        return False

    return True


def verify_migration():
    """Verify migration file exists and is valid."""
    print("\n✓ Verifying migration file...")

    import os

    migration_path = "alembic/versions/2026_02_15_0003-0003_add_product_cache.py"

    if not os.path.exists(migration_path):
        print(f"  ✗ Migration file not found: {migration_path}")
        return False

    print(f"  ✓ Migration file exists: {migration_path}")

    # Check migration has required functions
    with open(migration_path, 'r') as f:
        content = f.read()

    if "def upgrade()" in content and "def downgrade()" in content:
        print("  ✓ Migration has upgrade() and downgrade()")
    else:
        print("  ✗ Migration missing required functions")
        return False

    if "op.create_table('product_cache'" in content:
        print("  ✓ Migration creates product_cache table")
    else:
        print("  ✗ Migration doesn't create product_cache table")
        return False

    return True


def main():
    """Run all verifications."""
    print("=" * 60)
    print("Product Cache Implementation Verification")
    print("=" * 60)

    checks = [
        ("Imports", verify_imports),
        ("Basket Number", verify_basket_number),
        ("URL Builder", verify_url_builder),
        ("Context Formatter", verify_context_formatter),
        ("Migration", verify_migration),
    ]

    passed = 0
    failed = 0

    for name, check_fn in checks:
        try:
            if check_fn():
                passed += 1
            else:
                failed += 1
                print(f"\n✗ {name} check FAILED")
        except Exception as e:
            failed += 1
            print(f"\n✗ {name} check FAILED with exception: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
