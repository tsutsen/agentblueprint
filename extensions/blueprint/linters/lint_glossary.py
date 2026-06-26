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

import json
import re
import sys
import argparse
from pathlib import Path
from typing import Optional, Dict
from shared import BaseLinter, LayerResult, validate_spec_ids


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
            if not re.match(r"^GL-\d{3,}$", related):
                result.add("error", "related_term_format",
                    f"Term '{entry['name']}': relatedTerm '{related}' is not a valid GL-NNN ID.",
                    hint="Use GL-NNN format (e.g., GL-001, GL-042).")
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

    # DFS cycle detection
    visited = set()
    path = []

    def dfs(node: str) -> Optional[list]:
        if node in path:
            return path[path.index(node):]
        if node in visited:
            return None
        visited.add(node)
        path.append(node)
        for dep in usage_graph.get(node, set()):
            cycle = dfs(dep)
            if cycle:
                return cycle
        path.pop()
        return None

    reported = set()
    for term in terms:
        name = term["name"]
        if name not in visited:
            cycle = dfs(name)
            if cycle:
                key = frozenset(cycle)
                if key not in reported:
                    reported.add(key)
                    result.add("warning", "circular_definition",
                        f"Circular definition detected: {' → '.join(cycle + [cycle[0]])}.",
                        hint="Rewrite one definition to break the cycle.")


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

SEMANTIC_RULES = [
    # Related terms must reference existing glossary terms
    {
        "type": "exists",
        "section": "terms",
        "key": "relatedTerms",
        "valid_section": "terms",
        "valid_key": "id",
        "label": "Term",
        "ref_label": "Glossary term",
        "category": "related_term_missing",
        "hint": "Add the referenced term to the glossary or correct the ID.",
    },
]


# ── Misc Checks ───────────────────────────────────────────────────────────────

MISC_CHECKS = [
    ("related_terms_format", _check_related_terms),
    ("synonym_conflicts", _check_synonym_conflicts),
    ("definition_quality", _check_definition_quality),
    ("self_reference", _check_self_reference),
    ("circular_definitions", _check_circular_definitions),
    ("cross_spec_coverage", _check_cross_spec_coverage),
]


# ── Cross-spec dependency ─────────────────────────────────────────────────────

CROSS_SPEC_DEPS = ["goal", "arch", "data", "api"]


# ── Linter Class ──────────────────────────────────────────────────────────────

class GlossaryLinter(BaseLinter):
    """Linter for Glossary artifacts."""
    
    SPEC_NAME = "glossary"
    SEMANTIC_RULES = SEMANTIC_RULES
    MISC_CHECKS = MISC_CHECKS
    CROSS_SPEC_DEPS = CROSS_SPEC_DEPS


# ── Backward-compatible entry point ───────────────────────────────────────────

def run_lint(glossary, schema_path, other_specs, strict):
    """Backward-compatible entry point for lint_all.py."""
    linter = GlossaryLinter(glossary, schema_path, strict)
    return linter.run(**other_specs)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    GlossaryLinter.main([
        ("--goal", {"help": "Path to goalspec JSON", "spec_name": "goal"}),
        ("--arch", {"help": "Path to archspec JSON", "spec_name": "arch"}),
        ("--data", {"help": "Path to dataspec JSON", "spec_name": "data"}),
        ("--api", {"help": "Path to apispec JSON", "spec_name": "api"}),
    ])
