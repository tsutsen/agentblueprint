#!/usr/bin/env python3
"""
lint_testspec.py — Validate a TestSpec JSON against its schema and semantic rules.
Optionally cross-checks against ApiSpec for fnRef and errorCode resolution.

What this catches beyond JSON Schema:
  - Duplicate test IDs
  - Test ID format inconsistent with fnRef (TST-NNN-testName must ref FN-NNN-testName)
  - Test IDs not following TST-NNN-testName pattern
  - error-path tests missing errorCode
  - happy-path / edge-case tests missing expectedOutput
  - fnRefs that don't exist in ApiSpec
  - errorCodes that don't exist on the referenced function in ApiSpec
  - Functions in ApiSpec with no tests
  - Error conditions in ApiSpec with no error-path test
  - functionCoverage entries that don't match actual test counts
  - functionCoverage missing entries for functions that have tests
  - verificationStatus = pending at confirmed status
  - Placeholder detection in input values and descriptions

Usage:
    python lint_testspec.py <testspec.json> [--schema testspec.schema.json]
                            [--api apispec.json] [--strict] [--json]
"""

import re
import argparse
from typing import Dict, Set
from shared import BaseLinter, CompletenessGate, LayerResult, validate_spec_ids, _build_glossary_map, check_glossary_refs
from rules import SemanticRule


# ── Helpers ───────────────────────────────────────────────────────────────────

PLACEHOLDER_PATTERNS = [
    "a valid", "some string", "any string", "example value",
    "placeholder", "tbd", "todo", "your ", "a user", "a product",
    "an order", "some value", "test value"
]


def has_placeholder(value, _depth: int = 0) -> bool:
    """Check if a value contains placeholder text.

    Args:
        value: The value to check (str, dict, or list).
        _depth: Internal recursion depth counter (default: 0).

    Returns:
        True if placeholder text is found, False otherwise.

    Note:
        Maximum recursion depth is 20 to prevent stack overflow
        on deeply nested structures.
    """
    if _depth > 20:
        return False
    if isinstance(value, str):
        vl = value.lower()
        return any(p in vl for p in PLACEHOLDER_PATTERNS)
    if isinstance(value, dict):
        return any(has_placeholder(v, _depth + 1) for v in value.values())
    if isinstance(value, list):
        return any(has_placeholder(v, _depth + 1) for v in value)
    return False


def expected_test_prefix(fn_id: str) -> str:
    """ENDP-001-CreateUser → TST-001-CreateUser, or FN-001-createUser → TST-001-createUser"""
    match = re.match(r"^(?:ENDP|FN)-(\d{3})-(.+)$", fn_id)
    if match:
        return f"TST-{match.group(1)}-{match.group(2)}"
    return f"TST-{fn_id.split('-', 1)[1]}" if '-' in fn_id else f"TST-{fn_id}"


# ── Checks ────────────────────────────────────────────────────────────────────

def _check_id_fn_consistency(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Test ID prefix must match its fnRef."""
    for t in spec.get("tests", []):
        tid = t.get("id", "")
        fn_ref = t.get("fnRef", "")
        if fn_ref:
            expected = expected_test_prefix(fn_ref)
            if tid and not tid.startswith(expected + "-"):
                result.add("error", "id_fn_mismatch",
                    f"Test '{tid}': ID prefix does not match fnRef '{fn_ref}' (expected '{expected}-NNN').",
                    hint=f"Rename to '{expected}-NNN' to keep IDs traceable to their function.")


def _check_category_rules(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Enforce per-category conditional rules."""
    for t in spec.get("tests", []):
        tid = t.get("id", "?")
        cat = t.get("category", "")

        if cat == "error-path":
            if not t.get("expectedError"):
                result.add("warning", "error_path_missing_expected",
                    f"Test '{tid}' (error-path): missing expectedError.",
                    hint="Declare what the caller receives: code, returnType, messageContains.")
            if not t.get("errorCode"):
                result.add("warning", "error_path_missing_code",
                    f"Test '{tid}' (error-path): missing errorCode.",
                    hint="Declare the errorCode this test exercises.")
            if t.get("expectedOutput") is not None:
                result.add("warning", "error_path_has_output",
                    f"Test '{tid}' (error-path): has expectedOutput — error-path tests should not assert normal output.",
                    hint="Remove expectedOutput from error-path tests.")

        elif cat in ("happy-path", "edge-case"):
            if t.get("errorCode"):
                result.add("warning", "non_error_has_error_code",
                    f"Test '{tid}' ({cat}): has errorCode — only error-path tests should declare error codes.",
                    hint="Remove errorCode or change category to error-path.")


def _check_placeholder_values(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Detect placeholder input values."""
    for t in spec.get("tests", []):
        tid = t.get("id", "?")
        inp = t.get("input", {})
        for param, val in inp.items():
            if has_placeholder(val):
                result.add("warning", "placeholder_input",
                    f"Test '{tid}': input '{param}' may contain a placeholder value ('{str(val)[:40]}').",
                    hint="Use concrete, specific values — not 'a valid userId' but 'usr_48291'.")
        desc = t.get("description", "")
        desc_placeholders = ["tbd", "todo", "placeholder", "some test", "a test"]
        if any(desc.lower().startswith(p) or desc.lower() == p for p in desc_placeholders):
            result.add("warning", "placeholder_description",
                f"Test '{tid}': description appears to be a placeholder ('{desc[:60]}').",
                hint="Describe the specific scenario being tested.")


def _check_api_refs(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Validate errorCode against ApiSpec function errors."""
    api = extra_specs.get("api")
    if not api:
        return

    fn_map = {fn["id"]: fn for fn in api.get("functions", [])}

    for t in spec.get("tests", []):
        tid = t.get("id", "?")
        fn_ref = t.get("fnRef")
        error_code = t.get("errorCode")

        if not fn_ref or not error_code:
            continue

        fn_error_codes = {e["code"] for e in fn_map.get(fn_ref, {}).get("errors", [])}
        if error_code not in fn_error_codes:
            result.add("error", "error_code_undocumented",
                f"Test '{tid}': errorCode '{error_code}' is not documented on '{fn_ref}' in ApiSpec.",
                hint=f"Add error code '{error_code}' to '{fn_ref}' in ApiSpec or correct the test.")


def _check_api_coverage(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Every ApiSpec function must have tests; every error code must have an error-path test."""
    api = extra_specs.get("api")
    if not api:
        return

    tests = spec.get("tests", [])
    tested_fns = {t["fnRef"] for t in tests if t.get("fnRef")}
    tested_errors: Dict[str, Set[str]] = {}
    for t in tests:
        if t.get("fnRef") and t.get("errorCode"):
            tested_errors.setdefault(t["fnRef"], set()).add(t["errorCode"])

    for fn in api.get("functions", []):
        fn_id = fn["id"]

        if fn_id not in tested_fns:
            result.add("error", "function_untested",
                f"Function '{fn_id}' has no tests.",
                hint=f"Add at least one test with fnRef='{fn_id}'.")
            continue

        for err in fn.get("errors", []):
            code = err["code"]
            if code not in tested_errors.get(fn_id, set()):
                result.add("error", "error_code_untested",
                    f"Function '{fn_id}': error code '{code}' has no error-path test.",
                    hint=f"Add a test with fnRef='{fn_id}', category='error-path', errorCode='{code}'.")


def _check_function_coverage_summary(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Validate functionCoverage entries match actual test counts."""
    tests = spec.get("tests", [])
    coverage_entries = spec.get("functionCoverage", [])

    if not coverage_entries:
        result.add("warning", "no_coverage_summary",
            "No functionCoverage summary present.",
            hint="Add a functionCoverage entry per function summarising test counts and out-of-scope items.")
        return

    # Count actual tests per function per category
    actual: Dict[str, Dict[str, int]] = {}
    for t in tests:
        fn = t.get("fnRef")
        cat = t.get("category")
        if fn and cat:
            actual.setdefault(fn, {"happy-path": 0, "edge-case": 0, "error-path": 0})
            actual[fn][cat] = actual[fn].get(cat, 0) + 1

    coverage_fns = set()
    for entry in coverage_entries:
        fn = entry["fnRef"]
        coverage_fns.add(fn)
        counts = actual.get(fn, {})

        declared_happy = entry.get("happyPathCount", 0)
        declared_edge = entry.get("edgeCaseCount", 0)
        declared_error = entry.get("errorPathCount", 0)

        actual_happy = counts.get("happy-path", 0)
        actual_edge = counts.get("edge-case", 0)
        actual_error = counts.get("error-path", 0)

        if declared_happy != actual_happy:
            result.add("warning", "coverage_count_mismatch",
                f"functionCoverage '{fn}': happyPathCount={declared_happy} but {actual_happy} happy-path tests found.",
                hint="Update the count to match actual tests.")
        if declared_edge != actual_edge:
            result.add("warning", "coverage_count_mismatch",
                f"functionCoverage '{fn}': edgeCaseCount={declared_edge} but {actual_edge} edge-case tests found.",
                hint="Update the count to match actual tests.")
        if declared_error != actual_error:
            result.add("warning", "coverage_count_mismatch",
                f"functionCoverage '{fn}': errorPathCount={declared_error} but {actual_error} error-path tests found.",
                hint="Update the count to match actual tests.")

    # Functions with tests but no coverage entry
    for fn in actual:
        if fn not in coverage_fns:
            result.add("warning", "coverage_entry_missing",
                f"Function '{fn}' has tests but no functionCoverage entry.",
                hint=f"Add a functionCoverage entry for '{fn}' with out-of-scope declarations.")


def _check_glossary_refs(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """WARN: Check that test descriptions, contract clauses, and out-of-scope items have glossaryRefs."""
    glossary = extra_specs.get("glossary")
    if not glossary:
        return

    glossary_map = _build_glossary_map(glossary.get("terms", []))

    def _warn(text: str, refs: list, ctx: str) -> None:
        """Helper to warn about missing glossaryRefs."""
        missing = check_glossary_refs(text, glossary_map, refs)
        if missing:
            result.add("warning", "glossary",
                f"{ctx} references glossary terms ({', '.join(missing)}) but has no glossaryRefs.",
                hint="Add glossaryRefs (GL-NNN) for domain concepts.")

    # Check test cases
    for t in spec.get("tests", []):
        tid = t.get("id", "?")
        desc = t.get("description", "")
        clause = t.get("contractClause", "")
        refs = t.get("glossaryRefs", [])

        has_text = bool(desc) or bool(clause)
        if not has_text or refs:
            continue

        combined = f"{desc} {clause}".strip()
        _warn(combined, refs, f"Test '{tid}' description/contractClause")

    # Check outOfScope items in functionCoverage
    for fc in spec.get("functionCoverage", []):
        fn_ref = fc.get("fnRef", "?")
        for i, item in enumerate(fc.get("outOfScope", [])):
            if isinstance(item, dict):
                desc = item.get("description", "")
                refs = item.get("glossaryRefs", [])
            else:
                desc = str(item)
                refs = []
            if desc and not refs:
                _warn(desc, [],
                    f"functionCoverage '{fn_ref}' outOfScope #{i+1}: '{desc[:60]}...'")


def _check_lifecycle(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Status-aware completeness checks."""
    status = spec.get("status", "draft")
    verification = spec.get("verificationStatus", "pending")

    if status == "confirmed":
        if verification == "pending":
            result.add("error", "verification_pending",
                "TestSpec status is 'confirmed' but verificationStatus is 'pending'.",
                hint="Run the independent clean-context verification step before confirming.")
        if not spec.get("apiSpecVersion"):
            result.add("error", "missing_api_version",
                "TestSpec status is 'confirmed' but apiSpecVersion is not set.",
                hint="Set apiSpecVersion to pin which ApiSpec version these tests cover.")

    if status in ("review", "confirmed"):
        if not spec.get("functionCoverage"):
            result.add("warning", "no_coverage_at_review",
                f"TestSpec status is '{status}' but functionCoverage summary is absent.",
                hint="Add a functionCoverage entry for every function before review.")


# ── Semantic Rules ────────────────────────────────────────────────────────────

SEMANTIC_RULES: list[SemanticRule] = [
    # Test IDs must be unique
    {
        "target": "tests.id",
        "check": "is_unique",
        "target_label": "Test",
        "category": "duplicate_id",
        "hint": "Each test must have a unique ID.",
    },
    # fnRefs must exist in ApiSpec
    {
        "target": "tests.fnRef",
        "check": "exists",
        "inside": "api:functions.id",
        "target_label": "Test",
        "ref_label": "ApiSpec function",
        "category": "fnref_missing",
        "hint": "Add the function to ApiSpec or correct the reference.",
    },
    # Every ApiSpec function must have tests
    {
        "target": "tests.fnRef",
        "check": "covers_all",
        "should_cover_all": "api:functions",
        "covered_label": "ApiSpec function",
        "target_label": "Test",
        "category": "function_untested",
        "hint": "Add at least one test with fnRef set to this function.",
    },
]


# ── Misc Checks ───────────────────────────────────────────────────────────────

MISC_CHECKS = [
    _check_id_fn_consistency,
    _check_category_rules,
    _check_placeholder_values,
    _check_api_refs,
    _check_function_coverage_summary,
    _check_glossary_refs,
    _check_lifecycle,
]


# ── Cross-spec dependency ─────────────────────────────────────────────────────

CROSS_SPEC_DEPS = ["api", "glossary"]


# ── Completeness Gates ────────────────────────────────────────────────────────

COMPLETENESS_GATES: list = [
    {
        "target": "tests",
        "check": "has_count",
        "count": 1,
        "target_label": "test",
        "category": "completeness",
        "required_at": "draft",
        "description": "Has at least one test",
    },
    {
        "target": "functionCoverage",
        "check": "has_count",
        "count": 1,
        "target_label": "functionCoverage entry",
        "category": "completeness",
        "required_at": "draft",
        "description": "Has functionCoverage summary",
    },
    {
        "target": "apiSpecVersion",
        "check": "value_check",
        "expected": "truthy",
        "target_label": "apiSpecVersion",
        "category": "completeness",
        "required_at": "review",
        "description": "apiSpecVersion is set",
    },
    {
        "target": "verificationStatus",
        "check": "value_check",
        "expected": "confirmed",
        "target_label": "verificationStatus",
        "category": "completeness",
        "required_at": "confirmed",
        "description": "Independent verification completed",
    },
]


# ── Misc Completeness Gates ───────────────────────────────────────────────────

def _gate_expected_output(spec: dict, extra_specs: dict) -> CompletenessGate:
    """Happy-path/edge-case tests have expectedOutput (error-path excluded)."""
    tests = spec.get("tests", [])
    non_error = [t for t in tests if t.get("category") in ("happy-path", "edge-case")]
    missing = [t["id"] for t in non_error if not t.get("expectedOutput")]
    return CompletenessGate(
        description="All non-error-path tests have expectedOutput",
        passed=len(missing) == 0, required_at="review",
        detail=f"Missing expectedOutput: {missing}" if missing else "",
    )


def _gate_error_path_tests(spec: dict, extra_specs: dict) -> CompletenessGate:
    """Has error-path tests."""
    tests = spec.get("tests", [])
    error_tests = [t for t in tests if t.get("category") == "error-path"]
    return CompletenessGate(
        description="Has error-path tests",
        passed=len(error_tests) >= 1, required_at="review",
        detail="No error-path tests found" if not error_tests else "",
    )


def _gate_api_function_coverage(spec: dict, extra_specs: dict) -> CompletenessGate:
    """All ApiSpec functions have tests (cross-spec)."""
    api = extra_specs.get("api")
    if not api:
        return CompletenessGate(
            description="All ApiSpec functions have tests",
            passed=True, required_at="review",
            detail="No ApiSpec available for cross-check",
        )
    tests = spec.get("tests", [])
    fn_ids = {fn["id"] for fn in api.get("functions", [])}
    tested_fns = {t["fnRef"] for t in tests if t.get("fnRef")}
    untested = fn_ids - tested_fns
    return CompletenessGate(
        description="All ApiSpec functions have tests",
        passed=len(untested) == 0, required_at="review",
        detail=f"Untested: {untested}" if untested else "",
    )


def _gate_out_of_scope_declarations(spec: dict, extra_specs: dict) -> CompletenessGate:
    """All functions have outOfScope declarations."""
    coverage = spec.get("functionCoverage", [])
    all_oos = all(c.get("outOfScope") for c in coverage)
    return CompletenessGate(
        description="All functions have out-of-scope declarations",
        passed=all_oos, required_at="review",
        detail="Some functionCoverage entries missing outOfScope" if not all_oos else "",
    )


def _gate_coverage_completeness(spec: dict, extra_specs: dict) -> CompletenessGate:
    """functionCoverage covers all tested functions."""
    tests = spec.get("tests", [])
    coverage = spec.get("functionCoverage", [])
    tested_fns = {t["fnRef"] for t in tests if t.get("fnRef")}
    coverage_fns = {c["fnRef"] for c in coverage}
    missing_cov = tested_fns - coverage_fns
    return CompletenessGate(
        description="functionCoverage covers all tested functions",
        passed=len(missing_cov) == 0, required_at="review",
        detail=f"Missing: {missing_cov}" if missing_cov else "",
    )


# ── Linter Class ──────────────────────────────────────────────────────────────

class TestSpecLinter(BaseLinter):
    """Linter for TestSpec artifacts."""

    SPEC_NAME = "testspec"
    SPEC_KEY = "testspec"
    SEMANTIC_RULES = SEMANTIC_RULES
    COMPLETENESS_GATES = COMPLETENESS_GATES
    MISC_GATES = [
        _gate_expected_output,
        _gate_error_path_tests,
        _gate_api_function_coverage,
        _gate_out_of_scope_declarations,
        _gate_coverage_completeness,
    ]
    MISC_CHECKS = MISC_CHECKS
    CROSS_SPEC_DEPS = CROSS_SPEC_DEPS


# Canonical linter class for lint_all.py
LinterClass = TestSpecLinter


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    TestSpecLinter.main()
