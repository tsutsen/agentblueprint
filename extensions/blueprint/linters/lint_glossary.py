#!/usr/bin/env python3
"""
lint_glossary.py — Validate a Glossary JSON against its schema and semantic rules.
Optionally cross-checks all other specs to find undefined terms and unused entries.

What this catches beyond JSON Schema:
  - Duplicate term names
  - Circular definitions (term A defined using term B defined using term A)
  - Self-referential definitions (term used in its own definition)
  - relatedTerms referencing terms not in the glossary
  - synonyms that also have their own glossary entry (conflict)
  - Domain terms from other specs missing from the glossary
  - Glossary terms never referenced in any spec (unused)
  - Definition smell: too short, too vague, or placeholder-like

Usage:
    python lint_glossary.py <glossary.json> [--schema glossary.schema.json]
                            [--goal goalspec.json] [--arch archspec.json]
                            [--data dataspec.json] [--api apispec.json]
                            [--strict] [--json]
"""

import re
import argparse
from typing import Optional, Dict
from shared import BaseLinter, CompletenessGate, LayerResult, validate_spec_ids
from rules import SemanticRule
from id_patterns import ID_PATTERNS


# ── Term extraction from other specs ─────────────────────────────────────────

def extract_domain_terms(specs: dict) -> Dict[str, list]:
    """
    Extract named domain concepts from other specs that should have glossary entries.
    Returns {term: [source_label, ...]}
    """
    terms: Dict[str, list] = {}

    def add(term: str, source: str):
        terms.setdefault(term, []).append(source)

    goal = specs.get("goal")
    if goal:
        for fr in goal.get("functionalRequirements", []):
            add(fr["actor"], f"GoalSpec FR {fr['id']} actor")
        for us in goal.get("userStories", []):
            add(us["actor"], f"GoalSpec {us['id']} actor")

    arch = specs.get("arch")
    if arch:
        for comp in arch.get("components", []):
            add(comp["name"], f"ArchSpec component '{comp['id']}'")

    data = specs.get("data")
    if data:
        for entity in data.get("entities", []):
            add(entity["name"], f"DataSpec entity")
        for enum in data.get("enums", []):
            add(enum["name"], f"DataSpec enum")
            for v in enum.get("values", []):
                add(v["name"], f"DataSpec enum value in {enum['name']}")

    api = specs.get("api")
    if api:
        for fn in api.get("functions", []):
            if fn.get("entity"):
                add(fn["entity"], f"ApiSpec function '{fn['id']}' entity")

    return terms


# ── Checks ────────────────────────────────────────────────────────────────────

def _check_related_terms(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """All relatedTerms must be valid GL-NNN IDs that exist in the glossary."""
    terms = spec.get("terms", [])
    valid_ids = {t["id"] for t in terms}
    
    for entry in terms:
        for related in entry.get("relatedTerms", []):
            # Check format
            gl_pattern = ID_PATTERNS["gl"]["pattern"]
            if not re.match(gl_pattern, related):
                result.add("error", "related_term_format",
                    f"Term '{entry['name']}': relatedTerm '{related}' is not a valid GL-NNN-TermName ID.",
                    hint=f"Use GL-NNN-TermName format (e.g., GL-001-Authentication).")
            elif related not in valid_ids:
                result.add("error", "related_term_missing",
                    f"Term '{entry['name']}': relatedTerm '{related}' not found in glossary.",
                    hint=f"Add GL-{related.split('-')[1]} as a glossary entry or correct the ID.")


def _check_synonym_conflicts(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Synonyms must not also have their own glossary entry."""
    terms = spec.get("terms", [])
    term_names = {t["name"] for t in terms}
    
    for entry in terms:
        for syn in entry.get("synonyms", []):
            if syn in term_names and syn != entry["name"]:
                other = next((t for t in terms if t["name"] == syn), None)
                if other:
                    result.add("error", "synonym_conflict",
                        f"Term '{entry['name']}': synonym '{syn}' also has its own glossary entry (GL-{other['id'].split('-')[1]}).",
                        hint=f"Either remove the '{syn}' entry and keep it as a synonym, or remove it from '{entry['name']}' synonyms.")


def _check_definition_quality(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Flag definitions that are suspiciously short or placeholder-like."""
    placeholder_patterns = ["tbd", "todo", "see above", "see below", "n/a", "same as"]
    vague_starters = ["a thing", "something that", "refers to", "relates to"]

    for entry in spec.get("terms", []):
        name = entry.get("name", "")
        defn = entry.get("definition", "")
        defn_lower = defn.lower().strip()

        for p in placeholder_patterns:
            if defn_lower.startswith(p) or defn_lower == p:
                result.add("error", "definition_placeholder",
                    f"Term '{name}': definition appears to be a placeholder ('{defn[:30]}').",
                    hint="Write a complete, precise definition.")

        for v in vague_starters:
            if defn_lower.startswith(v):
                result.add("warning", "definition_vague",
                    f"Term '{name}': definition starts with vague phrasing ('{v}...').",
                    hint="Start with what the term IS, not how it relates to other things.")

        if len(defn.split()) < 5:
            result.add("warning", "definition_too_short",
                f"Term '{name}': definition is very short ({len(defn.split())} words).",
                hint="Definitions should be precise and complete — aim for at least one full sentence.")


def _check_self_reference(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """A term must not appear in its own definition."""
    for entry in spec.get("terms", []):
        name = entry.get("name", "")
        defn = entry.get("definition", "")
        pattern = re.compile(r'\b' + re.escape(name) + r'\b', re.IGNORECASE)
        if pattern.search(defn):
            result.add("warning", "self_reference",
                f"Term '{name}': definition contains the term itself.",
                hint="Definitions must not use the term being defined. Rewrite using other words.")


def _check_circular_definitions(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Detect circular definitions: A defined using B defined using A."""
    terms = spec.get("terms", [])
    all_term_names = {t["name"] for t in terms}
    
    def terms_used_in(definition: str, term_names: set) -> set:
        found = set()
        for t in term_names:
            if re.search(r'\b' + re.escape(t) + r'\b', definition, re.IGNORECASE):
                found.add(t)
        return found

    # Build usage graph
    usage_graph = {}
    for entry in terms:
        name = entry["name"]
        used = terms_used_in(entry.get("definition", ""), all_term_names)
        used.discard(name)  # self-reference handled separately
        usage_graph[name] = used

    # DFS cycle detection using 3-color algorithm
    # WHITE=0 unvisited, GRAY=1 in current path, BLACK=2 fully explored
    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {t["name"]: WHITE for t in terms}
    path: list[str] = []
    reported: set[frozenset] = set()

    def dfs(node: str) -> None:
        color[node] = GRAY
        path.append(node)
        for dep in usage_graph.get(node, set()):
            if dep not in color:
                continue
            if color[dep] == GRAY:
                # Found a cycle
                cycle = path[path.index(dep):] + [dep]
                key = frozenset(cycle[:-1])
                if key not in reported:
                    reported.add(key)
                    result.add("warning", "circular_definition",
                        f"Circular definition detected: {' → '.join(cycle)}.",
                        hint="Rewrite one definition to break the cycle.")
            elif color[dep] == WHITE:
                dfs(dep)
        path.pop()
        color[node] = BLACK

    for term in terms:
        name = term["name"]
        if color[name] == WHITE:
            dfs(name)


def _check_cross_spec_coverage(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """
    Domain terms extracted from other specs should have glossary entries.
    Glossary entries not referenced anywhere are flagged as unused.
    """
    # Only run if other specs are loaded
    if not any(extra_specs.values()):
        return

    domain_terms = extract_domain_terms(extra_specs)
    
    # Build set of all known names: terms + their synonyms
    known_names = {}  # name_lower → canonical term
    for entry in spec.get("terms", []):
        known_names[entry["name"].lower()] = entry["id"]
        for syn in entry.get("synonyms", []):
            known_names[syn.lower()] = entry["id"]

    referenced_terms = set()

    for term, sources in domain_terms.items():
        canonical = known_names.get(term.lower())
        if canonical:
            referenced_terms.add(canonical)
        else:
            # Only warn if the term looks like a meaningful domain noun
            if not (term.isupper() and "_" not in term and len(term) < 15):
                source_summary = sources[0] if sources else "unknown"
                result.add("warning", "term_undefined",
                    f"'{term}' (from {source_summary}) has no glossary entry.",
                    hint=f"Add a glossary entry for '{term}'.")

    # Unused terms
    for entry in spec.get("terms", []):
        term_id = entry["id"]
        if term_id not in referenced_terms:
            result.add("warning", "term_unused",
                f"Term '{entry['name']}' (GL-{term_id.split('-')[1]}) is not referenced by any loaded spec.",
                hint="If this term appears in specs, check spelling. If it's genuinely unused, consider removing it.")


# ── Semantic Rules ────────────────────────────────────────────────────────────

SEMANTIC_RULES: list[SemanticRule] = [
    # Related terms must reference existing glossary terms
    {
        "target": "terms.relatedTerms",
        "check": "exists",
        "inside": "terms.id",
        "target_label": "Term",
        "ref_label": "Glossary term",
        "category": "related_term_missing",
        "hint": "Add the referenced term to the glossary or correct the ID.",
    },
]


# ── Misc Checks ───────────────────────────────────────────────────────────────

MISC_CHECKS = [
    _check_related_terms,
    _check_synonym_conflicts,
    _check_definition_quality,
    _check_self_reference,
    _check_circular_definitions,
    _check_cross_spec_coverage,
]


# ── Cross-spec dependency ─────────────────────────────────────────────────────

CROSS_SPEC_DEPS = ["goal", "arch", "data", "api"]


# ── Completeness Gates ────────────────────────────────────────────────────────

COMPLETENESS_GATES: list = [
    {
        "target": "terms",
        "check": "has_count",
        "count": 3,
        "target_label": "term",
        "category": "completeness",
        "required_at": "draft",
        "description": "Has at least 3 terms",
    },
    {
        "target": "terms",
        "check": "all_have",
        "field": "definition",
        "min_length": 10,
        "target_label": "term",
        "category": "completeness",
        "required_at": "draft",
        "description": "All terms have definitions >= 10 chars",
    },
    {
        "target": "terms",
        "check": "has_count",
        "count": 5,
        "target_label": "term",
        "category": "completeness",
        "required_at": "review",
        "description": "Has at least 5 terms",
    },
]


# ── Misc Completeness Gates ───────────────────────────────────────────────────

def _gate_terms_examples_or_related(spec: dict, extra_specs: dict) -> CompletenessGate:
    """All terms have examples or related terms."""
    terms = spec.get("terms", [])
    has_examples_or_related = all(
        t.get("examples") or t.get("relatedTerms") for t in terms
    )
    return CompletenessGate(
        description="All terms have examples or related terms",
        passed=has_examples_or_related, required_at="confirmed",
        detail="Some terms missing examples and relatedTerms" if not has_examples_or_related else "",
    )


# ── Linter Class ──────────────────────────────────────────────────────────────

class GlossaryLinter(BaseLinter):
    """Linter for Glossary artifacts."""

    SPEC_NAME = "glossary"
    SPEC_KEY = "glossary"
    SEMANTIC_RULES = SEMANTIC_RULES
    COMPLETENESS_GATES = COMPLETENESS_GATES
    MISC_GATES = [_gate_terms_examples_or_related]
    MISC_CHECKS = MISC_CHECKS
    CROSS_SPEC_DEPS = CROSS_SPEC_DEPS


# Canonical linter class for lint_all.py
LinterClass = GlossaryLinter


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    GlossaryLinter.main()
