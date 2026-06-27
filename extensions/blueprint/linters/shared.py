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


# ── Type resolution helpers ──────────────────────────────────────────────────

def resolve_base_type(type_str: str) -> str:
    """Remove array notation from type string.

    e.g. 'string[]' → 'string', 'Entity[]' → 'Entity'
    """
    return type_str.replace("[]", "")


def build_valid_types(
    entity_names: set,
    enum_names: set,
    primitives: set | list,
) -> set:
    """Build union of all valid type names from primitives/entities/enums.

    Handles both string lists and dict lists for primitives.
    """
    if isinstance(primitives, list) and primitives and isinstance(primitives[0], dict):
        prim_set = {p.get("id", "") for p in primitives}
    else:
        prim_set = {str(p) for p in primitives}
    return entity_names | enum_names | prim_set


# ── Glossary matching helpers ────────────────────────────────────────────────

def _build_glossary_map(terms: list) -> dict[str, str]:
    """Build lowercase glossary term name → term_id map.

    Filters out terms with 3 or fewer characters (too noisy).
    """
    glossary_lower = {}
    for t in terms:
        name = t.get("name", t.get("term", ""))
        tid = t.get("id", t.get("termId", ""))
        if name and tid and len(name) > 3:
            glossary_lower[name.lower()] = tid
    return glossary_lower


def find_glossary_terms_in_text(text: str, glossary_map: dict[str, str]) -> list[str]:
    """Find glossary term IDs that appear in the given text.

    Returns list of glossary IDs (may be empty).
    """
    text_lower = text.lower()
    return [tid for term, tid in glossary_map.items()
            if term in text_lower]


def check_glossary_refs(
    text: str,
    glossary_map: dict[str, str],
    existing_refs: list | None = None,
) -> list[str]:
    """Check if text contains domain concepts without glossaryRefs.

    Args:
        text: The text to check.
        glossary_map: Pre-built glossary map from _build_glossary_map().
        existing_refs: List of glossary IDs already present on the item.

    Returns:
        List of glossary IDs referenced in text but missing from existing_refs.
        Empty list if no domain concepts found or all are covered.
    """
    if not text or not glossary_map:
        return []

    refs_set = {r for r in (existing_refs or [])}
    found = find_glossary_terms_in_text(text, glossary_map)
    return [tid for tid in found if tid not in refs_set]
