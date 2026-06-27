#!/usr/bin/env python3
"""
test_bugfixes.py — Verify bug fixes in shared.py.

Note: All legacy helpers have been removed and replaced with
declarative rules (find_cycles → has_no_cycles + exists,
find_duplicates → is_unique, validate_exists → exists,
validate_glossary_refs → exists, validate_coverage → covers_all).

Run: python3 test_bugfixes.py
"""

import sys
from pathlib import Path

# Ensure we can import shared
sys.path.insert(0, str(Path(__file__).parent))

from shared import LayerResult


def test_no_legacy_helpers():
    """Verify legacy helpers are removed."""
    legacy_funcs = [
        "find_cycles",
        "find_duplicates",
        "validate_exists",
        "validate_coverage",
        "validate_glossary_refs",
        "_validate_glossary_ref",
    ]
    for func_name in legacy_funcs:
        assert not hasattr(sys.modules["shared"], func_name), (
            f"Legacy function '{func_name}' still exists in shared.py"
        )
        print(f"  ✓ {func_name} — removed")


def test_new_rule_handlers():
    """Verify new rule handlers exist."""
    handlers = [
        "handle_non_empty",
        "handle_exists",
        "handle_unique",
        "handle_no_overlap",
        "handle_item_count",
        "handle_patterns",
        "handle_coverage",
        "handle_orphans",
        "handle_has_no_cycles",
    ]
    for handler_name in handlers:
        assert hasattr(sys.modules["shared"], handler_name), (
            f"Handler '{handler_name}' missing from shared.py"
        )
        print(f"  ✓ {handler_name} — present")


def main():
    print("Testing migration to declarative rules...")
    print()

    print("Legacy helpers removed:")
    test_no_legacy_helpers()
    print()

    print("New rule handlers present:")
    test_new_rule_handlers()
    print()

    print("All tests passed! ✓")


if __name__ == "__main__":
    main()
