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

import json
import re
import sys
import argparse
from pathlib import Path
from typing import Optional, Dict, Set
from shared import BaseLinter, LayerResult, validate_spec_ids


# ── Helpers ───────────────────────────────────────────────────────────────────

PLACEHOLDER_PATTERNS = [
    "a valid", "some string", "any string", "example value",
    "placeholder", "tbd", "todo", "your ", "a user", "a product",
    "an order", "some value", "test value"
]


def has_placeholder(value) -> bool:
    if isinstance(value, str):
        vl = value.lower()
        return any(p in vl for p in PLACEHOLDER_PATTERNS)
    if isinstance(value, dict):
        return any(has_placeholder(v) for v in value.values())
    if isinstance(value, list):
        return any(has_placeholder(v) for v in value)
    return False


def expected_test_prefix(fn_id: str) -> str:
    """FN-001-createUser → TST-001-createUser, or FN-createUser → TST-createUser"""
    match = re.match(r"^FN-(\d{3})-(.+)$", fn_id)
    if match:
        return f"TST-{match.group(1)}-{match.group(2)}"
    return f"TST-{fn_id[3:]}" if fn_id.startswith("FN-") else f"TST-{fn_id}"


# ── Checks ────────────────────────────────────────────────────────────────────

def _check_duplicate_ids(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check for duplicate test IDs."""
    ids = [t["id"] for t in spec.get("tests", [])]
    seen = set()
    for tid in ids:
        if tid in seen:
            result.add("error", "duplicate_id",
                f"Duplicate test id '{tid}'.",
                hint="Each test must have a unique ID.")
        seen.add(tid)


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
    """Enforce per-category required fields."""
    for t in spec.get("tests", []):
        tid = t.get("id", "?")
        cat = t.get("category", "")

        if cat == "error-path":
            if not t.get("errorCode"):
                result.add("error", "error_path_missing_code",
                    f"Test '{tid}' (error-path): missing errorCode.",
                    hint="Every error-path test must declare the errorCode it exercises.")
            if not t.get("expectedError"):
                result.add("warning", "error_path_missing_expected",
                    f"Test '{tid}' (error-path): missing expectedError.",
                    hint="Declare what the caller receives: code, returnType, messageContains.")
            if t.get("expectedOutput") is not None:
                result.add("warning", "error_path_has_output",
                    f"Test '{tid}' (error-path): has expectedOutput — error-path tests should not assert normal output.",
                    hint="Remove expectedOutput from error-path tests.")

        elif cat in ("happy-path", "edge-case"):
            if t.get("expectedOutput") is None:
                result.add("error", "missing_expected_output",
                    f"Test '{tid}' ({cat}): missing expectedOutput.",
                    hint="Every happy-path and edge-case test must assert a concrete expected output.")
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
    """Resolve fnRefs and errorCodes against ApiSpec."""
    api = extra_specs.get("api")
    if not api:
        return

    fn_map = {fn["id"]: fn for fn in api.get("functions", [])}
    fn_ids = set(fn_map.keys())

    for t in spec.get("tests", []):
        tid = t.get("id", "?")
        fn_ref = t.get("fnRef")

        if not fn_ref:
            continue

        if fn_ref not in fn_ids:
            result.add("error", "fnref_missing",
                f"Test '{tid}': fnRef '{fn_ref}' not found in ApiSpec.",
                hint=f"Add function '{fn_ref}' to ApiSpec or correct the reference.")
            continue

        # Validate errorCode against function's documented errors
        error_code = t.get("errorCode")
        if error_code:
            fn_error_codes = {e["code"] for e in fn_map[fn_ref].get("errors", [])}
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

    # Build glossary term map (lowercase -> id)
    glossary_lower = {}
    for t in glossary.get("terms", []):
        glossary_lower[t["name"].lower()] = t["id"]

    def has_domain_concept(text: str) -> bool:
        text_lower = text.lower()
        return any(len(term) > 3 and term in text_lower for term in glossary_lower)

    def find_glossary_refs(text: str) -> list:
        text_lower = text.lower()
        return [tid for term, tid in glossary_lower.items()
                if len(term) > 3 and term in text_lower]

    # Check test cases
    for t in spec.get("tests", []):
        tid = t.get("id", "?")
        desc = t.get("description", "")
        clause = t.get("contractClause", "")
        refs = t.get("glossaryRefs", [])

        has_text = bool(desc) or bool(clause)
        if not has_text or refs:
            continue

        text_parts = [desc, clause]
        combined = " ".join(text_parts)
        if has_domain_concept(combined):
            expected = find_glossary_refs(combined)
            result.add("warning", "glossary",
                f"Test '{tid}': description/contractClause references glossary terms "
                f"({', '.join(expected)}) but has no glossaryRefs.",
                hint="Add glossaryRefs (GL-NNN) for domain concepts in this test.")

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
            if desc and has_domain_concept(desc) and not refs:
                expected = find_glossary_refs(desc)
                result.add("warning", "glossary",
                    f"functionCoverage '{fn_ref}' outOfScope #{i+1}: '{desc[:60]}...' references glossary terms "
                    f"({', '.join(expected)}) but has no glossaryRefs.",
                    hint="Add glossaryRefs (GL-NNN) for domain concepts in this outOfScope item.")


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

SEMANTIC_RULES = []


# ── Misc Checks ───────────────────────────────────────────────────────────────

MISC_CHECKS = [
    ("duplicate_ids", _check_duplicate_ids),
    ("id_fn_consistency", _check_id_fn_consistency),
    ("category_rules", _check_category_rules),
    ("placeholder_values", _check_placeholder_values),
    ("api_refs", _check_api_refs),
    ("api_coverage", _check_api_coverage),
    ("function_coverage", _check_function_coverage_summary),
    ("glossary_refs", _check_glossary_refs),
    ("lifecycle", _check_lifecycle),
]


# ── Cross-spec dependency ─────────────────────────────────────────────────────

CROSS_SPEC_DEPS = ["api", "glossary"]


# ── Linter Class ──────────────────────────────────────────────────────────────

class TestSpecLinter(BaseLinter):
    """Linter for TestSpec artifacts."""
    
    SPEC_NAME = "testspec"
    SEMANTIC_RULES = SEMANTIC_RULES
    MISC_CHECKS = MISC_CHECKS
    CROSS_SPEC_DEPS = CROSS_SPEC_DEPS


# ── Backward-compatible entry point ───────────────────────────────────────────

def run_lint(spec, schema_path, api, glossary, strict):
    """Backward-compatible entry point for lint_all.py."""
    linter = TestSpecLinter(spec, schema_path, strict)
    return linter.run(api=api, glossary=glossary)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    TestSpecLinter.main([
        ("--api", {"help": "Path to apispec JSON for cross-spec checks", "spec_name": "api"}),
        ("--glossary", {"help": "Path to glossary JSON", "spec_name": "glossary"}),
    ])
