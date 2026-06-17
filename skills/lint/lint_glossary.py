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
from dataclasses import dataclass, field
from typing import Optional

# Regex for GL-NNN ID format (e.g. GL-001)
GL_ID_RE = re.compile(r"^GL-\d{3}$")

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class Issue:
    severity: str
    category: str
    message: str
    hint: str = ""


@dataclass
class LintResult:
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)

    def add(self, severity: str, category: str, message: str, hint: str = ""):
        issue = Issue(severity, category, message, hint)
        if severity == "error":
            self.errors.append(issue)
        else:
            self.warnings.append(issue)

    @property
    def clean(self) -> bool:
        return len(self.errors) == 0

    @property
    def all_issues(self):
        return self.errors + self.warnings


# ── Term extraction from other specs ─────────────────────────────────────────

def extract_domain_terms(specs: dict) -> dict[str, list[str]]:
    """
    Extract named domain concepts from other specs that should have glossary entries.
    Returns {term: [source_label, ...]}
    """
    terms: dict[str, list[str]] = {}

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

def check_gl_ids(glossary: dict, result: LintResult) -> dict[str, dict]:
    """Check GL-NNN IDs are sequential and unique. Returns term_id → entry map."""
    terms = glossary.get("terms", [])
    seen_ids: dict[str, dict] = {}
    ids_found: list[int] = []

    for entry in terms:
        term_id = entry.get("id", "")
        
        # Validate ID format
        if not GL_ID_RE.match(term_id):
            term_name = entry.get("term", "unknown")
            result.add("error", "gl_id_format",
                f"Term '{term_name}': ID '{term_id}' does not match GL-NNN format.",
                hint="Use GL-NNN format (e.g., GL-001, GL-042).")
            continue
        
        # Check for duplicate IDs
        if term_id in seen_ids:
            result.add("error", "duplicate_gl_id",
                f"Duplicate GL-NNN ID '{term_id}' (used by '{seen_ids[term_id].get('term', '?')}').",
                hint="Each term must have a unique GL-NNN identifier.")
            continue
        
        seen_ids[term_id] = entry
        ids_found.append(int(term_id.split("-")[1]))

    # Check for sequential numbering gaps
    if ids_found:
        min_id = min(ids_found)
        max_id = max(ids_found)
        expected = set(range(min_id, max_id + 1))
        actual = set(ids_found)
        missing = expected - actual
        
        for gap in sorted(missing):
            result.add("warning", "gl_id_gap",
                f"Gap in GL-NNN sequence: GL-{gap:03d} is missing.",
                hint="GL-NNN IDs should be sequential with no gaps.")

    return seen_ids


def check_duplicates(glossary: dict, result: LintResult) -> dict[str, dict]:
    """Check for duplicate term names. Returns term_name → entry map."""
    terms = glossary.get("terms", [])
    seen: dict[str, dict] = {}
    for entry in terms:
        name = entry["term"]
        if name in seen:
            result.add("error", "duplicate_term",
                f"Duplicate term '{name}'.",
                hint="Each term must appear exactly once. Combine the definitions or remove one.")
        else:
            seen[name] = entry
    return seen


def check_self_reference(term_map: dict[str, dict], result: LintResult):
    """A term must not appear in its own definition."""
    for name, entry in term_map.items():
        defn = entry.get("definition", "")
        # Case-insensitive whole-word check
        import re
        pattern = re.compile(r'\b' + re.escape(name) + r'\b', re.IGNORECASE)
        if pattern.search(defn):
            result.add("warning", "self_reference",
                f"Term '{name}': definition contains the term itself.",
                hint="Definitions must not use the term being defined. Rewrite using other words.")


def check_circular_definitions(term_map: dict[str, dict], result: LintResult):
    """Detect circular definitions: A defined using B defined using A."""
    import re

    def terms_used_in(definition: str, all_terms: set[str]) -> set[str]:
        found = set()
        for t in all_terms:
            if re.search(r'\b' + re.escape(t) + r'\b', definition, re.IGNORECASE):
                found.add(t)
        return found

    all_term_names = set(term_map.keys())

    # Build usage graph: term → set of terms used in its definition
    usage_graph: dict[str, set[str]] = {}
    for name, entry in term_map.items():
        used = terms_used_in(entry.get("definition", ""), all_term_names)
        used.discard(name)  # self-reference handled separately
        usage_graph[name] = used

    # DFS cycle detection
    visited = set()
    path: list[str] = []

    def dfs(node: str) -> Optional[list[str]]:
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
    for term in term_map:
        if term not in visited:
            cycle = dfs(term)
            if cycle:
                key = frozenset(cycle)
                if key not in reported:
                    reported.add(key)
                    result.add("warning", "circular_definition",
                        f"Circular definition detected: {' → '.join(cycle + [cycle[0]])}.",
                        hint="Rewrite one definition to break the cycle.")


def check_related_terms(gl_id_map: dict[str, dict], result: LintResult):
    """All relatedTerms must be valid GL-NNN IDs that exist in the glossary."""
    for term_id, entry in gl_id_map.items():
        for related in entry.get("relatedTerms", []):
            if not GL_ID_RE.match(related):
                result.add("error", "related_term_format",
                    f"Term '{entry['term']}': relatedTerm '{related}' is not a valid GL-NNN ID.",
                    hint="Use GL-NNN format (e.g., GL-001, GL-042).")
            elif related not in gl_id_map:
                result.add("error", "related_term_missing",
                    f"Term '{entry['term']}': relatedTerm '{related}' not found in glossary.",
                    hint=f"Add GL-{related.split('-')[1]} as a glossary entry or correct the ID.")


def check_synonym_conflicts(gl_id_map: dict[str, dict], result: LintResult):
    """Synonyms must not also have their own glossary entry — that creates ambiguity."""
    for term_id, entry in gl_id_map.items():
        for syn in entry.get("synonyms", []):
            # Check if synonym text matches another term's name
            for other_id, other_entry in gl_id_map.items():
                if other_id != term_id and syn == other_entry["term"]:
                    result.add("error", "synonym_conflict",
                        f"Term '{entry['term']}': synonym '{syn}' also has its own glossary entry (GL-{other_id.split('-')[1]}).",
                        hint=f"Either remove the '{syn}' entry and keep it as a synonym, or remove it from '{entry['term']}' synonyms.")


def check_definition_quality(gl_id_map: dict[str, dict], result: LintResult):
    """Flag definitions that are suspiciously short or placeholder-like."""
    placeholder_patterns = ["tbd", "todo", "see above", "see below", "n/a", "same as"]
    vague_starters = ["a thing", "something that", "refers to", "relates to"]

    for name, entry in gl_id_map.items():
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


def check_cross_spec_coverage(
    gl_id_map: dict[str, dict],
    domain_terms: dict[str, list[str]],
    result: LintResult
):
    """
    Domain terms extracted from other specs should have glossary entries.
    Glossary entries not referenced anywhere are flagged as unused.
    """
    # Build set of all known names: terms + their synonyms
    known_names: dict[str, str] = {}  # name_lower → canonical term
    for term_id, entry in gl_id_map.items():
        known_names[entry["term"].lower()] = term_id
        for syn in entry.get("synonyms", []):
            known_names[syn.lower()] = term_id

    referenced_terms: set[str] = set()

    for term, sources in domain_terms.items():
        canonical = known_names.get(term.lower())
        if canonical:
            referenced_terms.add(canonical)
        else:
            # Only warn if the term looks like a meaningful domain noun
            # (skip single-word all-caps enum values like PENDING, PAID)
            if not (term.isupper() and "_" not in term and len(term) < 15):
                source_summary = sources[0] if sources else "unknown"
                result.add("warning", "term_undefined",
                    f"'{term}' (from {source_summary}) has no glossary entry.",
                    hint=f"Add a glossary entry for '{term}'.")

    # Unused terms
    for term_id in gl_id_map:
        if term_id not in referenced_terms:
            result.add("warning", "term_unused",
                f"Term '{gl_id_map[term_id]['term']}' (GL-{term_id.split('-')[1]}) is not referenced by any loaded spec.",
                hint="If this term appears in specs, check spelling. If it's genuinely unused, consider removing it.")


# ── Runner ────────────────────────────────────────────────────────────────────

def run_lint(
    glossary: dict,
    schema_path: Optional[Path],
    other_specs: dict,
    strict: bool
) -> LintResult:
    result = LintResult()

    # JSON Schema validation
    if schema_path and HAS_JSONSCHEMA:
        schema = json.loads(schema_path.read_text())
        for err in jsonschema.Draft7Validator(schema).iter_errors(glossary):
            result.add("error", "schema", f"{err.json_path}: {err.message}")
    elif schema_path and not HAS_JSONSCHEMA:
        result.add("warning", "schema_skipped",
            "jsonschema not installed — skipping schema validation.",
            hint="pip install jsonschema")

    # Project match — goalspec/archspec/designspec use "project"; dataspec/apispec use "module"
    for label, spec in other_specs.items():
        if not spec:
            continue
        spec_name = spec.get("project") or spec.get("module")
        if spec_name and spec_name != glossary["project"]:
            result.add("error", "project_match",
                f"Project mismatch: glossary='{glossary['project']}' {label}='{spec_name}'.",
                hint="All specs must have identical project/module values.")

    # Structural checks
    gl_id_map = check_gl_ids(glossary, result)
    term_map = {entry["term"]: entry for entry in gl_id_map.values()} if gl_id_map else {}
    if gl_id_map:  # Only run name-based checks if GL-IDs are valid
        check_self_reference(term_map, result)
        check_circular_definitions(term_map, result)
    check_related_terms(gl_id_map, result)
    check_synonym_conflicts(gl_id_map, result)
    check_definition_quality(gl_id_map, result)

    # Cross-spec coverage
    if any(other_specs.values()):
        domain_terms = extract_domain_terms(other_specs)
        check_cross_spec_coverage(term_map, domain_terms, result)

    if strict:
        for w in result.warnings:
            w.severity = "error"
            result.errors.append(w)
        result.warnings.clear()

    return result


# ── Output ────────────────────────────────────────────────────────────────────

def print_human(result: LintResult, path: str):
    print(f"\n{'─'*60}")
    print(f"  Glossary Lint Report — {path}")
    print(f"{'─'*60}")

    if not result.all_issues:
        print("  ✓ All checks passed.\n")
        return

    if result.errors:
        print(f"\n  ERRORS ({len(result.errors)}):")
        for e in result.errors:
            print(f"    ✗ [{e.category}] {e.message}")
            if e.hint:
                print(f"      → {e.hint}")

    if result.warnings:
        print(f"\n  WARNINGS ({len(result.warnings)}):")
        for w in result.warnings:
            print(f"    ⚠ [{w.category}] {w.message}")
            if w.hint:
                print(f"      → {w.hint}")

    print(f"\n  {len(result.errors)} error(s), {len(result.warnings)} warning(s).\n")


def print_json_output(result: LintResult):
    print(json.dumps({
        "clean": result.clean,
        "errors":   [{"category": e.category, "message": e.message, "hint": e.hint} for e in result.errors],
        "warnings": [{"category": w.category, "message": w.message, "hint": w.hint} for w in result.warnings]
    }, indent=2))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Lint a Glossary JSON.")
    parser.add_argument("input",     help="Path to glossary JSON")
    parser.add_argument("--schema",  help="Path to glossary.schema.json")
    parser.add_argument("--goal",    help="Path to goalspec JSON")
    parser.add_argument("--arch",    help="Path to archspec JSON")
    parser.add_argument("--data",    help="Path to dataspec JSON")
    parser.add_argument("--api",     help="Path to apispec JSON")
    parser.add_argument("--strict",  action="store_true")
    parser.add_argument("--json",    action="store_true")
    args = parser.parse_args()

    glossary = json.loads(Path(args.input).read_text())
    schema_path = Path(args.schema) if args.schema else None

    other_specs = {
        "goalspec":  json.loads(Path(args.goal).read_text()) if args.goal else None,
        "archspec":  json.loads(Path(args.arch).read_text()) if args.arch else None,
        "dataspec":  json.loads(Path(args.data).read_text()) if args.data else None,
        "apispec":   json.loads(Path(args.api).read_text())  if args.api  else None,
    }

    result = run_lint(glossary, schema_path, other_specs, args.strict)

    if args.json:
        print_json_output(result)
    else:
        print_human(result, args.input)

    sys.exit(0 if result.clean else 1)


if __name__ == "__main__":
    main()
