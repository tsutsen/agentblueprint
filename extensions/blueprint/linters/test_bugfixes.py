#!/usr/bin/env python3
"""
test_bugfixes.py — Verify bug fixes in shared.py.

Bugs fixed:
  1. find_cycles: target_label → label in f-strings
  2. _validate_glossary_ref: target_label → label in f-string
  3. validate_glossary_refs: target_label → label in f-strings
  4. _validate_glossary_ref: duplicate function removed

Note: find_duplicates and validate_exists were removed entirely.

Run: python3 test_bugfixes.py
"""

import sys
from pathlib import Path

# Ensure we can import shared
sys.path.insert(0, str(Path(__file__).parent))

from shared import (
    find_cycles,
    _validate_glossary_ref,
    validate_glossary_refs,
    LayerResult,
)

def test_find_cycles_no_cycle():
    """Bug 2: find_cycles with no cycle."""
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
    """Bug 2: find_cycles with cycle (target_label → label)."""
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
    """Bug 2: find_cycles with invalid dependency ref."""
    items = [
        {"id": "A", "deps": ["MISSING"]},
    ]
    result = LayerResult()
    find_cycles(items, "id", "deps", {"A"}, result, label="Module")
    assert len(result.errors) == 1
    assert "Module" in result.errors[0].message
    assert "MISSING" in result.errors[0].message
    print(f"  ✓ find_cycles (bad ref) — 'Module' appears: {result.errors[0].message[:60]}")


def test_validate_glossary_ref_single():
    """Bug 4: _validate_glossary_ref (target_label → label)."""
    result = LayerResult()
    _validate_glossary_ref(
        ["GL-001", "GL-999"],
        label="Component",
        name="COMP-001",
        gl_ids={"GL-001", "GL-002"},
        result=result,
    )
    assert len(result.errors) == 1
    assert "Component" in result.errors[0].message
    assert "COMP-001" in result.errors[0].message
    assert "GL-999" in result.errors[0].message
    print(f"  ✓ _validate_glossary_ref — 'Component' appears: {result.errors[0].message[:60]}")


def test_validate_glossary_refs_no_refs():
    """Bug 5: validate_glossary_refs with missing refs."""
    result = LayerResult()
    validate_glossary_refs(
        {"terms": [{"id": "GL-001", "name": "Auth"}]},
        result,
        checks=[
            ("Component", "glossaryRefs", [
                {"id": "COMP-001", "glossaryRefs": ["GL-001"]},
                {"id": "COMP-002", "glossaryRefs": []},
            ]),
        ],
    )
    assert len(result.warnings) == 1
    assert "Component" in result.warnings[0].message
    assert "COMP-002" in result.warnings[0].message
    print(f"  ✓ validate_glossary_refs (no refs) — 'Component' appears: {result.warnings[0].message[:60]}")


def test_validate_glossary_refs_bad_ref():
    """Bug 5: validate_glossary_refs with invalid ref."""
    result = LayerResult()
    validate_glossary_refs(
        {"terms": [{"id": "GL-001", "name": "Auth"}]},
        result,
        checks=[
            ("Flow", "glossaryRefs", [
                {"id": "FLW-001", "glossaryRefs": ["GL-999"]},
            ]),
        ],
    )
    assert len(result.errors) == 1
    assert "Flow" in result.errors[0].message
    assert "FLW-001" in result.errors[0].message
    print(f"  ✓ validate_glossary_refs (bad ref) — 'Flow' appears: {result.errors[0].message[:60]}")


def test_no_duplicate_function():
    """Bug 6: _validate_glossary_ref should be defined only once."""
    import inspect
    source = inspect.getsource(sys.modules["shared"])
    count = source.count("def _validate_glossary_ref(")
    assert count == 1, f"Expected 1 definition of _validate_glossary_ref, found {count}"
    print("  ✓ _validate_glossary_ref — defined exactly once (no duplicate)")


def test_no_target_label_in_legacy():
    """Verify no remaining target_label references in legacy functions."""
    import inspect
    source = inspect.getsource(sys.modules["shared"])

    # Extract legacy function bodies
    legacy_funcs = ["find_cycles",
                    "_validate_glossary_ref", "validate_glossary_refs"]
    for func_name in legacy_funcs:
        func = getattr(sys.modules["shared"], func_name)
        func_source = inspect.getsource(func)
        # Check that target_label doesn't appear in the function body
        # (it may appear in TypedDict definitions, but not in function code)
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

    print("Bug 2: _validate_glossary_ref (target_label → label)")
    test_validate_glossary_ref_single()
    print()

    print("Bug 3: validate_glossary_refs (target_label → label)")
    test_validate_glossary_refs_no_refs()
    test_validate_glossary_refs_bad_ref()
    print()

    print("Bug 4: Duplicate _validate_glossary_ref removed")
    test_no_duplicate_function()
    print()

    print("Regression: No remaining target_label in legacy functions")
    test_no_target_label_in_legacy()
    print()

    print("All tests passed! ✓")


if __name__ == "__main__":
    main()
