#!/usr/bin/env python3
"""
test_bugfixes.py — Verify bug fixes in shared.py.

Bugs fixed:
  1. find_cycles: target_label → label in f-strings

Note: find_duplicates, validate_exists, and validate_glossary_refs
were removed entirely and replaced with declarative rules.

Run: python3 test_bugfixes.py
"""

import sys
from pathlib import Path

# Ensure we can import shared
sys.path.insert(0, str(Path(__file__).parent))

from shared import (
    find_cycles,
    LayerResult,
)


def test_find_cycles_no_cycle():
    """find_cycles with no cycle."""
    items = [
        {"id": "A", "deps": ["B"]},
        {"id": "B", "deps": []},
    ]
    result = LayerResult()
    found = find_cycles(items, "id", "deps", {"A", "B"}, result, label="Node")
    assert not found
    assert not result.errors
    print("  ✓ find_cycles (no cycle) — no errors")


def test_find_cycles_with_cycle():
    """find_cycles with cycle (target_label → label)."""
    items = [
        {"id": "A", "deps": ["B"]},
        {"id": "B", "deps": ["A"]},
    ]
    result = LayerResult()
    found = find_cycles(items, "id", "deps", {"A", "B"}, result, label="Node")
    assert found
    assert len(result.errors) == 1
    assert "node" in result.errors[0].message.lower(), f"Message should contain 'node': {result.errors[0].message}"
    print(f"  ✓ find_cycles (with cycle) — 'node' appears: {result.errors[0].message[:60]}")


def test_find_cycles_bad_ref():
    """find_cycles with invalid dependency ref."""
    items = [
        {"id": "A", "deps": ["MISSING"]},
    ]
    result = LayerResult()
    find_cycles(items, "id", "deps", {"A"}, result, label="Module")
    assert len(result.errors) == 1
    assert "Module" in result.errors[0].message
    assert "MISSING" in result.errors[0].message
    print(f"  ✓ find_cycles (bad ref) — 'Module' appears: {result.errors[0].message[:60]}")


def test_no_target_label_in_legacy():
    """Verify no remaining target_label references in legacy functions."""
    import inspect
    legacy_funcs = ["find_cycles"]
    for func_name in legacy_funcs:
        func = getattr(sys.modules["shared"], func_name)
        func_source = inspect.getsource(func)
        assert "target_label" not in func_source, (
            f"{func_name} still references 'target_label' — should use 'label'"
        )
        print(f"  ✓ {func_name} — no 'target_label' references")


def main():
    print("Testing bug fixes in shared.py...")
    print()

    print("Bug 1: find_cycles (target_label → label)")
    test_find_cycles_no_cycle()
    test_find_cycles_with_cycle()
    test_find_cycles_bad_ref()
    print()

    print("Regression: No remaining target_label in legacy functions")
    test_no_target_label_in_legacy()
    print()

    print("All tests passed! ✓")


if __name__ == "__main__":
    main()
