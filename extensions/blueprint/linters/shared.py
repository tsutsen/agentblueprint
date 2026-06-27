#!/usr/bin/env python3
"""
shared.py — Canonical types, output formatting, and linter infrastructure.

All linters should import from this module.

Module layout (internal):
    linter_types.py — Issue, LayerResult, Resolved, CompletenessGate, CompletenessScore
    path.py         — resolve_path, _normalize_ref
    output.py       — print_human, print_json_output
    id_validation.py — ID validation helpers
    linter.py       — BaseLinter, _apply_strict_mode
    check.py        — CheckDef abstract base + shared check functions
    rules.py        — Rule schemas, handlers, registry, dispatch (imports from check)
    gates.py        — Gate schemas, handlers, registry, dispatch (imports from check)

Usage in a linter:
    from shared import Issue, LayerResult, BaseLinter, print_human
    from rules import SemanticRule, _run_new_semantic_rules
    from gates import GateDef, run_gates  # for per-spec completeness
"""

# ── Re-exports (single import point) ──────────────────────────────────────────

from linter_types import (
    Issue,
    LayerResult,
    Resolved,
    CompletenessGate,
    CompletenessScore,
    gate,
)
from path import (
    _normalize_ref,
    resolve_path,
)
from output import (
    print_human,
    print_json_output,
)
from id_validation import (
    validate_spec_ids,
    validate_sequential,
    validate_project_and_version,
    _validate_all_ids,
)
from linter import (
    BaseLinter,
    _apply_strict_mode,
)


# ── Suite-level helpers ───────────────────────────────────────────────────────

def suite_completeness_pct(scores: list[CompletenessScore]) -> int:
    """Compute overall suite completeness as average of individual scores."""
    if not scores:
        return 0
    return sum(s.score_pct for s in scores) // len(scores)


SPEC_ORDER = ["goalspec", "glossary", "designspec", "archspec",
              "dataspec", "apispec", "testspec", "plan", "issues"]
