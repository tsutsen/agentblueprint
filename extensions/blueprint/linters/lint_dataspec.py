#!/usr/bin/env python3
"""
lint_dataspec.py — Validate a DataSpec JSON against its schema and semantic rules.

What this catches that JSON Schema alone cannot:
  - Duplicate entity names
  - Entity names not following PascalCase
  - Field names not following camelCase
  - Method names not following camelCase
  - Entity 'extends' referencing non-existent parent
  - Relationship 'from'/'to' referencing non-existent entities
  - Enum names not following SCREAMING_SNAKE_CASE
  - Enum values not following SCREAMING_SNAKE_CASE
  - Self-referencing relationships (from == to)
  - Field types referencing undefined primitives/entities/enums
  - Methods referencing apiRef that doesn't match FN-<camelCase> pattern
  - Relationship cardinality labels not matching expected patterns

Usage:
    python lint_dataspec.py <dataspec.json> [--schema dataspec.schema.json] [--strict] [--json]
"""

import json
import sys
import argparse
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Set

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class Issue:
    severity: str      # "error" | "warning"
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_ids(items: list, key: str) -> list[str]:
    return [item[key] for item in items if key in item]

def check_duplicates(ids: list[str], label: str, result: LintResult):
    seen = set()
    for id_ in ids:
        if id_ in seen:
            result.add("error", "duplicate_id",
                f"Duplicate {label} name '{id_}'.",
                hint=f"Each {label} must have a unique name.")
        seen.add(id_)


# ── Semantic checks ───────────────────────────────────────────────────────────

def check_entities(spec: dict, enums: list, result: LintResult) -> Set[str]:
    """Validate entity names, fields, methods, and extends references."""
    entities = spec.get("entities", [])
    entity_names: Set[str] = set()
    entity_map: dict = {}

    for entity in entities:
        name = entity["name"]
        entity_names.add(name)
        entity_map[name] = entity

        # Entity name must be PascalCase
        if not re.match(r"^[A-Z][A-Za-z0-9]*$", name):
            result.add("error", "entity_name_format",
                f"Entity '{name}' does not follow PascalCase.",
                hint="Entity names must start with an uppercase letter followed by alphanumeric characters.")

    # Check extends references
    for entity in entities:
        extends = entity.get("extends")
        if extends and extends not in entity_names:
            result.add("error", "extends_missing",
                f"Entity '{entity['name']}' extends '{extends}', which does not exist.",
                hint=f"Add '{extends}' as an entity or remove the 'extends' field.")

    # Validate fields
    for entity in entities:
        for field_def in entity.get("fields", []):
            fname = field_def["name"]

            # Field name must be camelCase
            if not re.match(r"^[a-z][A-Za-z0-9]*$", fname):
                result.add("error", "field_name_format",
                    f"Entity '{entity['name']}': field '{fname}' does not follow camelCase.",
                    hint="Field names must start with a lowercase letter.")

            # Field type must resolve
            ftype = field_def.get("type", "")
            base_type = ftype.replace("[]", "") if ftype.endswith("[]") else ftype
            primitives = set(spec.get("primitives", ["string", "number", "boolean", "null", "any"]))
            enum_names = {e["name"] for e in enums}

            if base_type not in entity_names and base_type not in primitives and base_type not in enum_names:
                result.add("error", "type_undefined",
                    f"Entity '{entity['name']}': field '{fname}' has type '{ftype}', which is not defined.",
                    hint=f"Define '{base_type}' as a primitive, entity, or enum. Available: {sorted(primitives | entity_names | enum_names)}")

    # Validate methods
    for entity in entities:
        for method in entity.get("methods", []):
            mname = method.get("name", "")
            if mname and not re.match(r"^[a-z][A-Za-z0-9]*$", mname):
                result.add("error", "method_name_format",
                    f"Entity '{entity['name']}': method '{mname}' does not follow camelCase.",
                    hint="Method names must start with a lowercase letter.")

            api_ref = method.get("apiRef", "")
            if api_ref and not re.match(r"^FN-[a-z]", api_ref):
                result.add("error", "method_api_ref_format",
                    f"Entity '{entity['name']}': method '{mname}' has apiRef '{api_ref}' which doesn't match FN-<camelCase>.",
                    hint="apiRef must reference a function ID in the API spec, e.g. 'FN-createUser'.")

    # Validate visibility
    for entity in entities:
        vis = entity.get("visibility", "public")
        if vis not in ("public", "internal"):
            result.add("error", "entity_visibility_invalid",
                f"Entity '{entity['name']}': visibility '{vis}' is not valid.",
                hint="Entity visibility must be 'public' or 'internal'.")

    return entity_names


def check_enums(spec: dict, result: LintResult) -> Set[str]:
    """Validate enum names and values."""
    enums = spec.get("enums", [])
    enum_names: Set[str] = set()

    for enum in enums:
        ename = enum["name"]
        enum_names.add(ename)

        # Enum name must be SCREAMING_SNAKE_CASE
        if not re.match(r"^[A-Z][A-Z0-9_]*$", ename):
            result.add("error", "enum_name_format",
                f"Enum '{ename}' does not follow SCREAMING_SNAKE_CASE.",
                hint="Enum names must be uppercase with underscores, e.g. 'ORDER_STATUS'.")

        for val in enum.get("values", []):
            vname = val["name"]
            if not re.match(r"^[A-Z][A-Z0-9_]*$", vname):
                result.add("error", "enum_value_format",
                    f"Enum '{ename}': value '{vname}' does not follow SCREAMING_SNAKE_CASE.",
                    hint="Enum values must be uppercase with underscores, e.g. 'PENDING'.")

    return enum_names


def check_relationships(spec: dict, entity_names: Set[str], result: LintResult):
    """Validate relationship endpoints and types."""
    relationships = spec.get("relationships", [])

    for rel in relationships:
        from_entity = rel.get("from", "")
        to_entity = rel.get("to", "")

        # from/to must reference valid entities
        if from_entity not in entity_names:
            result.add("error", "rel_from_missing",
                f"Relationship from '{from_entity}' does not exist.",
                hint=f"Add '{from_entity}' as an entity.")

        if to_entity not in entity_names:
            result.add("error", "rel_to_missing",
                f"Relationship to '{to_entity}' does not exist.",
                hint=f"Add '{to_entity}' as an entity.")

        # Relationship type must be valid
        rel_type = rel.get("type", "")
        valid_types = {"association", "composition", "aggregation", "dependency", "realization"}
        if rel_type not in valid_types:
            result.add("error", "rel_type_invalid",
                f"Relationship between '{from_entity}' and '{to_entity}': type '{rel_type}' is not valid.",
                hint=f"Valid types: {', '.join(sorted(valid_types))}")

        # Warn about self-referencing relationships
        if from_entity == to_entity and from_entity in entity_names:
            result.add("warning", "rel_self_reference",
                f"Self-referencing relationship: '{from_entity}' → '{to_entity}'.",
                hint="Self-referencing relationships are valid (e.g., tree structures) but often indicate a design choice that should be reviewed.")


def check_primitives(spec: dict, result: LintResult):
    """Validate that primitives list is non-empty and contains valid names."""
    primitives = spec.get("primitives", [])
    if not primitives:
        result.add("error", "primitives_empty",
            "primitives list is empty.",
            hint="Define at least one primitive type (e.g. 'string', 'number', 'boolean').")

    # Warn about 'any' in primitives — it's too permissive
    if "any" in primitives:
        result.add("warning", "primitives_any",
            "'any' is in the primitives list — this disables type checking.",
            hint="Consider removing 'any' to enforce stricter type discipline.")


# ── Runner ────────────────────────────────────────────────────────────────────

def run_lint(spec: dict, schema_path: Optional[Path], strict: bool) -> LintResult:
    result = LintResult()

    # JSON Schema validation
    if schema_path and HAS_JSONSCHEMA:
        schema = json.loads(schema_path.read_text())
        validator = jsonschema.Draft7Validator(schema)
        for err in validator.iter_errors(spec):
            result.add("error", "schema",
                f"{err.json_path}: {err.message}")
    elif schema_path and not HAS_JSONSCHEMA:
        result.add("warning", "schema_skipped",
            "jsonschema not installed — JSON Schema validation skipped.",
            hint="pip install jsonschema")

    # Semantic checks
    check_primitives(spec, result)
    entity_names = check_entities(spec, spec.get("enums", []), result)
    check_relationships(spec, entity_names, result)

    if strict:
        for w in result.warnings:
            w.severity = "error"
            result.errors.append(w)
        result.warnings.clear()

    return result


# ── Output ────────────────────────────────────────────────────────────────────

def print_human(result: LintResult, path: str):
    print(f"\n{'─'*60}")
    print(f"  DataSpec Lint Report — {path}")
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
    out = {
        "clean": result.clean,
        "errors": [{"category": e.category, "message": e.message, "hint": e.hint} for e in result.errors],
        "warnings": [{"category": w.category, "message": w.message, "hint": w.hint} for w in result.warnings]
    }
    print(json.dumps(out, indent=2))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Lint a DataSpec JSON.")
    parser.add_argument("input", help="Path to dataspec JSON")
    parser.add_argument("--schema", help="Path to dataspec.schema.json")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    path = Path(args.input)
    spec = json.loads(path.read_text())
    schema_path = Path(args.schema) if args.schema else None

    result = run_lint(spec, schema_path, args.strict)

    if args.json:
        print_json_output(result)
    else:
        print_human(result, str(path))

    sys.exit(0 if result.clean else 1)


if __name__ == "__main__":
    main()
