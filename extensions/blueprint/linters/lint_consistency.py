#!/usr/bin/env python3
"""
lint_consistency.py — Check consistency between Markdown and JSON spec files.

Compares entity, enum, and relationship names between the Markdown and JSON
versions of each spec file. Warns about any drift.

Usage:
    python lint_consistency.py <spec-dir> --specs goal,design,data,api,test
"""

import json
import sys
import argparse
import re
from pathlib import Path
from typing import Optional, Set, Dict, Any
from shared import Issue, LayerResult, print_human, print_json_output


# ── Markdown parsing ──────────────────────────────────────────────────────────

def parse_markdown_entities(content: str) -> Set[str]:
    """Extract entity names from Markdown tables."""
    entities = set()
    # Match Table lines in DBML-style or Markdown table headers
    for match in re.finditer(r"Table\s+(\w+)", content):
        entities.add(match.group(1))
    return entities


def parse_markdown_enums(content: str) -> Set[str]:
    """Extract enum names from Markdown."""
    enums = set()
    for match in re.finditer(r"Enum\s+(\w+)", content):
        enums.add(match.group(1))
    return enums


def parse_markdown_relationships(content: str) -> Set[str]:
    """Extract relationship pairs from Markdown."""
    rels = set()
    for match in re.finditer(r"Ref:\s+(\w+)\.\w+\s*<\s*(\w+)\.\w+", content):
        rels.add((match.group(1), match.group(2)))
    return rels


def parse_markdown_functions(content: str) -> Set[str]:
    """Extract function IDs from Markdown."""
    fns = set()
    for match in re.finditer(r"FN-[A-Za-z][A-Za-z0-9]*", content):
        fns.add(match.group(0))
    return fns


# ── Spec comparison helpers ───────────────────────────────────────────────────

def extract_json_entities(spec: dict) -> Set[str]:
    return {e["name"] for e in spec.get("entities", [])}


def extract_json_enums(spec: dict) -> Set[str]:
    return {e["name"] for e in spec.get("enums", [])}


def extract_json_relationships(spec: dict) -> Set[tuple]:
    rels = set()
    for r in spec.get("relationships", []):
        rels.add((r.get("from", ""), r.get("to", "")))
    return rels


def extract_json_functions(spec: dict) -> Set[str]:
    return {f["id"] for f in spec.get("functions", [])}


# ── Consistency checks ────────────────────────────────────────────────────────

def check_entity_consistency(md_entities: Set[str], json_entities: Set[str],
                             spec_name: str, result: LayerResult):
    """Check that entity names match between Markdown and JSON."""
    only_md = md_entities - json_entities
    only_json = json_entities - md_entities

    if only_md:
        result.add("warning", "entity_only_markdown",
            f"[{spec_name}] Entity in Markdown but not JSON: {sorted(only_md)}",
            hint="Add these entities to the JSON spec or remove from Markdown.")

    if only_json:
        result.add("warning", "entity_only_json",
            f"[{spec_name}] Entity in JSON but not Markdown: {sorted(only_json)}",
            hint="Add these entities to the Markdown spec or remove from JSON.")


def check_enum_consistency(md_enums: Set[str], json_enums: Set[str],
                           spec_name: str, result: LayerResult):
    """Check that enum names match between Markdown and JSON."""
    only_md = md_enums - json_enums
    only_json = json_enums - md_enums

    if only_md:
        result.add("warning", "enum_only_markdown",
            f"[{spec_name}] Enum in Markdown but not JSON: {sorted(only_md)}",
            hint="Add these enums to the JSON spec or remove from Markdown.")

    if only_json:
        result.add("warning", "enum_only_json",
            f"[{spec_name}] Enum in JSON but not Markdown: {sorted(only_json)}",
            hint="Add these enums to the Markdown spec or remove from JSON.")


def check_relationship_consistency(md_rels: Set[tuple], json_rels: Set[tuple],
                                   spec_name: str, result: LayerResult):
    """Check that relationships match between Markdown and JSON."""
    only_md = md_rels - json_rels
    only_json = json_rels - md_rels

    if only_md:
        result.add("warning", "rel_only_markdown",
            f"[{spec_name}] Relationship in Markdown but not JSON: {sorted(only_md)}",
            hint="Add these relationships to the JSON spec or remove from Markdown.")

    if only_json:
        result.add("warning", "rel_only_json",
            f"[{spec_name}] Relationship in JSON but not Markdown: {sorted(only_json)}",
            hint="Add these relationships to the Markdown spec or remove from JSON.")


def check_function_consistency(md_fns: Set[str], json_fns: Set[str],
                               spec_name: str, result: LayerResult):
    """Check that function IDs match between Markdown and JSON."""
    only_md = md_fns - json_fns
    only_json = json_fns - md_fns

    if only_md:
        result.add("warning", "fn_only_markdown",
            f"[{spec_name}] Function in Markdown but not JSON: {sorted(only_md)}",
            hint="Add these functions to the JSON spec or remove from Markdown.")

    if only_json:
        result.add("warning", "fn_only_json",
            f"[{spec_name}] Function in JSON but not Markdown: {sorted(only_json)}",
            hint="Add these functions to the Markdown spec or remove from JSON.")


# ── Runner ────────────────────────────────────────────────────────────────────

def run_lint(spec_dir: Path, specs: list[str]) -> LayerResult:
    result = LayerResult()

    for spec_type in specs:
        md_path = spec_dir / f"{spec_type.title()}.md"
        json_path = spec_dir / f"{spec_type.title()}.json"

        if not md_path.exists() or not json_path.exists():
            result.add("warning", "file_missing",
                f"Skipping {spec_type}: missing {md_path.name} or {json_path.name}")
            continue

        md_content = md_path.read_text()
        json_spec = json.loads(json_path.read_text())

        md_entities = parse_markdown_entities(md_content)
        json_entities = extract_json_entities(json_spec)
        check_entity_consistency(md_entities, json_entities, spec_type, result)

        md_enums = parse_markdown_enums(md_content)
        json_enums = extract_json_enums(json_spec)
        check_enum_consistency(md_enums, json_enums, spec_type, result)

        md_rels = parse_markdown_relationships(md_content)
        json_rels = extract_json_relationships(json_spec)
        check_relationship_consistency(md_rels, json_rels, spec_type, result)

        # ApiSpec functions
        if spec_type == "api":
            md_fns = parse_markdown_functions(md_content)
            json_fns = extract_json_functions(json_spec)
            check_function_consistency(md_fns, json_fns, spec_type, result)

    return result


# ── Output
# Uses shared.print_human and shared.print_json_output


def main():
    parser = argparse.ArgumentParser(description="Check Markdown/JSON consistency.")
    parser.add_argument("spec_dir", help="Directory containing spec files")
    parser.add_argument("--specs", default="goal,design,data,api,test",
                        help="Comma-separated list of specs to check (default: all)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    spec_dir = Path(args.spec_dir)
    specs = [s.strip() for s in args.specs.split(",")]

    result = run_lint(spec_dir, specs)

    if args.json:
        print_json_output(result)
    else:
        print_human(result)

    sys.exit(0 if result.clean else 1)


if __name__ == "__main__":
    main()
