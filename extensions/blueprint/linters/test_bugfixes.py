#!/usr/bin/env python3
"""
test_bugfixes.py — Verify the refactored linter framework.

Checks:
  - Legacy helpers are removed from shared.py
  - Rule handlers exist (now auto-generated from _RULE_DEFS)
  - Pure check functions exist in check.py
  - New module structure (types, path, output, id_validation, linter)
  - Backward-compatible imports via shared.py re-exports

Run: python3 test_bugfixes.py
"""

import importlib
import sys
from pathlib import Path

# Ensure we can import from the linters directory
sys.path.insert(0, str(Path(__file__).parent))

import check
import rules
import gates
import shared
import linter_types
import path
import output
import id_validation
import linter
import linter_types


def test_no_legacy_helpers():
    """Verify legacy helpers and centralized assessors are removed from shared.py."""
    legacy_funcs = [
        "find_cycles",
        "find_duplicates",
        "validate_exists",
        "validate_coverage",
        "validate_glossary_refs",
        "_validate_glossary_ref",
        # assess_* moved to lint_*.py
        "assess", "assess_goalspec", "assess_archspec", "assess_dataspec",
        "assess_apispec", "assess_testspec", "assess_taskplan",
        "assess_designspec", "assess_glossary", "assess_glossary_full",
    ]
    for func_name in legacy_funcs:
        assert not hasattr(shared, func_name), (
            f"Legacy function '{func_name}' still exists in shared"
        )
        print(f"  ✓ {func_name} — removed from shared")


def test_new_rule_handlers():
    """Verify rule handlers exist (auto-generated from _RULE_DEFS)."""
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
        assert hasattr(rules, handler_name), (
            f"Handler '{handler_name}' missing from rules"
        )
        print(f"  ✓ {handler_name} — present in rules")


def test_pure_check_functions():
    """Verify pure check functions exist in check.py."""
    check_funcs = [
        "check_non_empty",
        "check_count",
        "check_coverage",
        "check_all_have",
        "check_none_match",
        "check_value",
        # Newly extracted
        "check_exists",
        "check_unique",
        "check_no_overlap",
        "check_item_count",
        "check_patterns",
        "check_orphans",
        "check_has_no_cycles",
    ]
    for func_name in check_funcs:
        assert hasattr(check, func_name), (
            f"Check function '{func_name}' missing from check"
        )
        print(f"  ✓ {func_name} — present in check")


def test_check_registry():
    """Verify _CHECK_REGISTRY contains all check functions."""
    expected_keys = {
        "non_empty", "count", "coverage", "all_have", "none_match", "value",
        "exists", "unique", "no_overlap", "item_count", "patterns",
        "orphans", "has_no_cycles",
    }
    actual_keys = set(check._CHECK_REGISTRY.keys())
    missing = expected_keys - actual_keys
    assert not missing, f"Missing from _CHECK_REGISTRY: {missing}"
    print(f"  ✓ _CHECK_REGISTRY has {len(actual_keys)} entries")


def test_rule_defs():
    """Verify _RULE_DEFS contains all rule types."""
    expected_types = {
        "non_empty", "exists", "is_unique", "not_shared", "has_item_count",
        "contains_patterns", "covers_all", "not_orphan", "has_no_cycles",
    }
    actual_types = set(rules._RULE_DEFS.keys())
    missing = expected_types - actual_types
    assert not missing, f"Missing from _RULE_DEFS: {missing}"
    print(f"  ✓ _RULE_DEFS has {len(actual_types)} rule types")


def test_gate_defs():
    """Verify _GATE_DEFS contains all gate types."""
    expected_types = {
        "non_empty", "has_count", "covers_all", "all_have", "none_match", "value_check",
    }
    actual_types = set(gates._GATE_DEFS.keys())
    missing = expected_types - actual_types
    assert not missing, f"Missing from _GATE_DEFS: {missing}"
    print(f"  ✓ _GATE_DEFS has {len(actual_types)} gate types")


def test_new_modules():
    """Verify new module structure exists and is importable."""
    modules = {
        "linter_types": ["Issue", "LayerResult", "Resolved", "CompletenessGate", "CompletenessScore", "gate"],
        "path": ["resolve_path", "_normalize_ref"],
        "output": ["print_human", "print_json_output"],
        "id_validation": ["validate_spec_ids", "validate_sequential", "validate_project_and_version"],
        "linter": ["BaseLinter"],
    }
    for mod_name, attrs in modules.items():
        mod = sys.modules[mod_name]
        for attr in attrs:
            assert hasattr(mod, attr), f"{mod_name}.{attr} missing"
        print(f"  ✓ {mod_name} — {len(attrs)} exports")


def test_shared_reexports():
    """Verify shared.py re-exports everything for backward compatibility."""
    reexports = [
        "Issue", "LayerResult", "Resolved",
        "CompletenessGate", "CompletenessScore", "gate",
        "resolve_path", "_normalize_ref",
        "print_human", "print_json_output",
        "validate_spec_ids", "validate_sequential", "validate_project_and_version",
        "BaseLinter",
        "suite_completeness_pct", "SPEC_ORDER",
    ]
    for name in reexports:
        assert hasattr(shared, name), f"shared.{name} missing"
    # assess_* functions are now in lint_*.py, not shared.py
    for name in ["assess", "assess_goalspec", "assess_archspec", "assess_dataspec",
                 "assess_apispec", "assess_testspec", "assess_taskplan",
                 "assess_designspec", "assess_glossary"]:
        assert not hasattr(shared, name), f"shared.{name} should be removed"
    print(f"  ✓ shared.py — {len(reexports)} re-exports (assess_* moved to lint_*.py)")


def test_linter_classes_and_gates():
    """Verify each lint module has COMPLETENESS_GATES, LinterClass, and no module-level run_completeness."""
    lint_modules = [
        "lint_goalspec", "lint_glossary", "lint_dataspec", "lint_apispec",
        "lint_testspec", "lint_designspec", "lint_archspec", "lint_taskplan",
    ]
    for mod_name in lint_modules:
        mod = importlib.import_module(mod_name)
        assert hasattr(mod, "COMPLETENESS_GATES"), f"{mod_name} missing COMPLETENESS_GATES"
        assert hasattr(mod, "LinterClass"), f"{mod_name} missing LinterClass"
        assert callable(mod.LinterClass), f"{mod_name}.LinterClass not callable"
        # run_completeness is on the class (via BaseLinter), not the module
        assert hasattr(mod.LinterClass, "run_completeness"), \
            f"{mod_name}.LinterClass missing run_completeness method"
        print(f"  ✓ {mod_name}: {len(mod.COMPLETENESS_GATES)} gates, LinterClass.run_completeness()")


def test_check_functions_are_pure():
    """Verify check functions return expected types."""
    # check_non_empty
    result = check.check_non_empty([None, "", [1]], ["a", "b", "c"])
    assert isinstance(result, list)
    assert len(result) == 2  # None and empty string

    # check_exists
    result = check.check_exists(["x", "y", "z"], ["a", "b", "c"], {"x", "z"})
    assert isinstance(result, list)
    assert len(result) == 1  # only "y" is missing

    # check_unique
    result = check.check_unique(["a", "b", "a"], ["1", "2", "3"])
    assert isinstance(result, list)
    assert len(result) == 1  # "a" appears twice

    # check_coverage
    result = check.check_coverage({"x", "y"}, ["x", "y", "z"])
    assert isinstance(result, list)
    assert result == ["z"]

    # check_all_have
    result = check.check_all_have([{"id": "1"}, {"id": "2", "name": "b"}], "name")
    assert isinstance(result, list)
    assert len(result) == 1

    # check_has_no_cycles
    items = [
        {"id": "a", "dependencies": ["b"]},
        {"id": "b", "dependencies": ["c"]},
        {"id": "c", "dependencies": []},
    ]
    cycles = check.check_has_no_cycles(items)
    assert cycles == []

    items_with_cycle = [
        {"id": "a", "dependencies": ["b"]},
        {"id": "b", "dependencies": ["a"]},
    ]
    cycles = check.check_has_no_cycles(items_with_cycle)
    assert len(cycles) >= 1

    print("  ✓ All check functions return expected types")


def test_rule_schema_validation():
    """Verify _validate_rule catches schema errors."""
    errors = rules._validate_rule({"check": "non_empty"})
    assert any("target" in e for e in errors), f"Should flag missing target: {errors}"

    errors = rules._validate_rule({"check": "non_empty", "target": "x", "category": "c", "unknown": 1})
    assert any("unknown" in e for e in errors), f"Should flag unknown field: {errors}"

    errors = rules._validate_rule({"check": "non_empty", "target": "x", "category": "c"})
    assert errors == [], f"Valid rule should have no errors: {errors}"

    print("  ✓ Rule schema validation works correctly")


def test_dispatch_check():
    """Verify dispatch_check invokes the correct function."""
    # dispatch_check signature: dispatch_check(check_name, *args, values=..., parent_ids=...)
    # *args are passed to the check function; values/parent_ids are for CheckResult wrapper
    cr = check.dispatch_check("non_empty", [None, "ok"], ["a", "b"],
                              values=[None, "ok"], parent_ids=["a", "b"])
    assert cr.fn == check.check_non_empty
    assert len(cr.results) == 1
    assert cr.results[0][0] == "a"

    print("  ✓ dispatch_check invokes correct function")


def main():
    print("=== Linter Refactoring Tests ===\n")
    tests = [
        ("Legacy helpers removed", test_no_legacy_helpers),
        ("Rule handlers present", test_new_rule_handlers),
        ("Pure check functions present", test_pure_check_functions),
        ("Check registry complete", test_check_registry),
        ("Rule definitions complete", test_rule_defs),
        ("Gate definitions complete", test_gate_defs),
        ("New modules importable", test_new_modules),
        ("Shared re-exports work", test_shared_reexports),
        ("Linter classes & gates", test_linter_classes_and_gates),
        ("Check functions are pure", test_check_functions_are_pure),
        ("Rule schema validation", test_rule_schema_validation),
        ("Dispatch check works", test_dispatch_check),
    ]

    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ✅ {name}\n")
            passed += 1
        except Exception as e:
            print(f"  ❌ {name}: {e}\n")
            failed += 1

    print(f"=== Results: {passed} passed, {failed} failed ===")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
