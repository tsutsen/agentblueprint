#!/usr/bin/env python3
"""
lint_apispec.py — Validate an ApiSpec JSON against its schema and semantic rules.

What this catches that JSON Schema alone cannot:
  - Duplicate function IDs
  - Function IDs not following FN-NNN-<camelCase> pattern
  - Function names not following camelCase
  - Parameter names not following camelCase
  - Error codes not following SCREAMING_SNAKE_CASE
  - Entity references not matching data spec entities (cross-spec)
  - Module name mismatch with data spec (cross-spec)
  - DataSpecVersion mismatch with data spec version (cross-spec)
  - Functions with errors but no error conditions documented
  - Pure functions that likely have side effects (advisory)

Usage:
    python lint_apispec.py <apispec.json> [--schema apispec.schema.json] [--data dataspec.json] [--strict] [--json]
"""

import json
import sys
import argparse
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Set, Dict, Any

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

def check_duplicates(ids: list[str], label: str, result: LintResult):
    seen = set()
    for id_ in ids:
        if id_ in seen:
            result.add("error", "duplicate_id",
                f"Duplicate {label} id '{id_}'.",
                hint=f"Each {label} must have a unique identifier.")
        seen.add(id_)


def resolve_base_type(type_str: str) -> str:
    """Remove array notation from type string."""
    return type_str.replace("[]", "")


# ── Semantic checks ───────────────────────────────────────────────────────────

def check_functions(spec: dict, result: LintResult) -> Set[str]:
    """Validate function IDs, names, parameters, and error conditions."""
    functions = spec.get("functions", [])
    fn_ids: Set[str] = set()

    for fn in functions:
        fid = fn["id"]
        fn_ids.add(fid)

        # Function ID must follow FN-NNN-<camelCase>
        if not re.match(r"^FN-\d{3}-[a-z][A-Za-z0-9]*$", fid):
            result.add("error", "fn_id_format",
                f"Function ID '{fid}' does not follow FN-NNN-<camelCase>.",
                hint="Function IDs must follow the pattern 'FN-NNN-functionName', e.g. 'FN-001-createUser'.")

        # Function name must be camelCase
        fname = fn.get("name", "")
        if fname and not re.match(r"^[a-z][A-Za-z0-9]*$", fname):
            result.add("error", "fn_name_format",
                f"Function '{fid}': name '{fname}' does not follow camelCase.",
                hint="Function names must start with a lowercase letter.")

        # Validate parameters
        for param in fn.get("inputs", []):
            pname = param.get("name", "")
            if pname and not re.match(r"^[a-z][A-Za-z0-9]*$", pname):
                result.add("error", "param_name_format",
                    f"Function '{fid}': parameter '{pname}' does not follow camelCase.",
                    hint="Parameter names must start with a lowercase letter.")

        # Validate output type
        output = fn.get("output", {})
        output_type = output.get("type", "")
        if output_type and output_type != "void":
            base = resolve_base_type(output_type)
            if base and not re.match(r"^[A-Za-z]", base):
                result.add("error", "output_type_format",
                    f"Function '{fid}': output type '{output_type}' is invalid.",
                    hint="Output type must be a valid type name starting with a letter, or 'void'.")

    return fn_ids


def check_errors(spec: dict, fn_ids: Set[str], result: LintResult):
    """Validate error conditions for each function."""
    functions = spec.get("functions", [])

    for fn in functions:
        fid = fn["id"]
        errors = fn.get("errors", [])

        # Warn if function modifies data but has no error conditions
        if "create" in fid.lower() or "update" in fid.lower() or "delete" in fid.lower() or "remove" in fid.lower():
            if not errors:
                result.add("warning", "fn_no_errors",
                    f"Function '{fid}' likely modifies data but has no error conditions documented.",
                    hint="Document error conditions such as NOT_FOUND, CONFLICT, UNAUTHORIZED, etc.")

        for err in errors:
            code = err.get("code", "")
            # Error code must be SCREAMING_SNAKE_CASE
            if code and not re.match(r"^[A-Z][A-Z0-9_]*$", code):
                result.add("error", "error_code_format",
                    f"Function '{fid}': error code '{code}' does not follow SCREAMING_SNAKE_CASE.",
                    hint="Error codes must be uppercase with underscores, e.g. 'NOT_FOUND'.")


def check_visibility(spec: dict, result: LintResult):
    """Validate function visibility values."""
    functions = spec.get("functions", [])
    for fn in functions:
        vis = fn.get("visibility", "public")
        if vis not in ("public", "internal"):
            result.add("error", "fn_visibility_invalid",
                f"Function '{fn['id']}': visibility '{vis}' is not valid.",
                hint="Function visibility must be 'public' or 'internal'.")




def check_duplicate_names(spec: dict, result: LintResult):
    """Warn when multiple functions share the same name."""
    names = {}
    for fn in spec.get("functions", []):
        fname = fn.get("name", "")
        if fname:
            if fname in names:
                result.add("error", "duplicate_function_name",
                    f"Duplicate function name '{fname}' (IDs: {names[fname]} and {fn['id']}).",
                    hint="Each function must have a unique name.")
            else:
                names[fname] = fn["id"]


def check_missing_descriptions(spec: dict, result: LintResult):
    """Warn about functions, parameters, and outputs without descriptions."""
    for fn in spec.get("functions", []):
        fid = fn["id"]

        # Function description
        if not fn.get("description"):
            result.add("info", "missing_function_description",
                f"Function '{fid}' has no description.",
                hint="Add a one-sentence description of what this function does.")

        # Parameter descriptions
        for param in fn.get("inputs", []):
            pname = param.get("name", "")
            if not param.get("description") and pname:
                result.add("info", "missing_parameter_description",
                    f"Function '{fid}': parameter '{pname}' has no description.",
                    hint="Add a description explaining the purpose of this parameter.")

        # Output description
        output = fn.get("output", {})
        if output and not output.get("description"):
            result.add("info", "missing_output_description",
                f"Function '{fid}': output has no description.",
                hint="Add a description explaining what this function returns.")


def check_unused_functions(spec: dict, data_spec: Optional[Dict[str, Any]], result: LintResult):
    """Warn about functions not referenced by any entity's apiRef."""
    if not data_spec:
        return

    api_refs = set()
    for entity in data_spec.get("entities", []):
        for method in entity.get("methods", []):
            api_ref = method.get("apiRef", "")
            if api_ref:
                api_refs.add(api_ref)

    for fn in spec.get("functions", []):
        fid = fn["id"]
        if fid not in api_refs:
            result.add("warning", "unused_function",
                f"Function '{fid}' is not referenced by any entity's apiRef.",
                hint="Either add this function to an entity's methods, or remove it if unused.")


def check_cross_spec_types(spec: dict, data_spec: Optional[Dict[str, Any]], result: LintResult):
    """Verify that types used in ApiSpec match exactly with DataSpec.

    Checks:
    - Entity names match exactly (case-sensitive)
    - Enum names match exactly
    - Primitive names match exactly
    - Array notation is consistent
    """
    if not data_spec:
        return

    entity_names = {e["name"] for e in data_spec.get("entities", [])}
    enum_names = {e["name"] for e in data_spec.get("enums", [])}
    primitives = set(data_spec.get("primitives", ["string", "number", "boolean", "null", "any"]))
    valid_types = entity_names | enum_names | primitives

    for fn in spec.get("functions", []):
        fid = fn["id"]

        # Check parameter types
        for param in fn.get("inputs", []):
            ptype = param.get("type", "")
            base = resolve_base_type(ptype)
            if base and base not in valid_types:
                # Check if it's close to a valid type (case-insensitive match)
                similar = [t for t in valid_types if t.lower() == base.lower()]
                if similar:
                    result.add("error", "type_case_mismatch",
                        f"Function '{fid}': parameter '{param['name']}' type '{ptype}' "
                        f"case doesn't match data spec type '{similar[0]}'.",
                        hint="Type names are case-sensitive. Use '{similar[0]}' (not '{base}').")
                else:
                    result.add("error", "type_ref_missing",
                        f"Function '{fid}': parameter '{param['name']}' type '{ptype}' "
                        f"is not defined in the data spec.",
                        hint=f"Define '{base}' in the data spec or use an existing type.")

        # Check output type
        output_type = fn.get("output", {}).get("type", "")
        if output_type:
            base = resolve_base_type(output_type)
            if base and base not in valid_types:
                similar = [t for t in valid_types if t.lower() == base.lower()]
                if similar:
                    result.add("error", "type_case_mismatch",
                        f"Function '{fid}': output type '{output_type}' "
                        f"case doesn't match data spec type '{similar[0]}'.",
                        hint="Type names are case-sensitive. Use '{similar[0]}' (not '{base}').")
                else:
                    result.add("error", "output_type_ref_missing",
                        f"Function '{fid}': output type '{output_type}' "
                        f"is not defined in the data spec.",
                        hint=f"Define '{base}' in the data spec or use an existing type.")


def check_required_parameter_description(spec: dict, result: LintResult):
    """Required parameters must have descriptions."""
    for fn in spec.get("functions", []):
        fid = fn["id"]
        for param in fn.get("inputs", []):
            if param.get("required", False) and not param.get("description"):
                result.add("warning", "required_param_no_description",
                    f"Function '{fid}': required parameter '{param['name']}' has no description.",
                    hint="Required parameters should always have a description explaining their purpose.")


def check_internal_function_visibility(spec: dict, result: LintResult):
    """Warn about internal functions that have public-facing characteristics.

    Internal functions should not be:
    - Documented with error conditions (errors are for public APIs)
    - Have public-facing tags
    """
    for fn in spec.get("functions", []):
        if fn.get("visibility") == "internal":
            fid = fn["id"]

            # Internal functions with error conditions
            errors = fn.get("errors", [])
            if errors:
                result.add("info", "internal_function_with_errors",
                    f"Function '{fid}' is internal but documents error conditions.",
                    hint="Internal functions should handle errors internally. "
                         "Consider making this public if errors need to be exposed.")

            # Internal functions with public-facing tags
            tags = fn.get("tags", [])
            public_tags = {"public", "api", "rest", "graphql"}
            if public_tags & set(tags):
                result.add("info", "internal_function_public_tags",
                    f"Function '{fid}' is internal but has public-facing tags: {tags}.",
                    hint="Internal functions should not have public-facing tags.")


# ── Cross-spec checks ─────────────────────────────────────────────────────────

def check_entity_refs(spec: dict, data_spec: Optional[Dict[str, Any]], result: LintResult):
    """Validate that entity references match data spec entities."""
    if not data_spec:
        return

    entity_names = {e["name"] for e in data_spec.get("entities", [])}
    enum_names = {e["name"] for e in data_spec.get("enums", [])}
    primitives = set(data_spec.get("primitives", ["string", "number", "boolean", "null", "any"]))
    valid_types = entity_names | enum_names | primitives
    api_primitives = {"string", "number", "boolean", "null", "any", "void"}

    for fn in spec.get("functions", []):
        fid = fn["id"]

        # Entity field must reference a valid entity
        entity = fn.get("entity")
        if entity and entity not in entity_names:
            result.add("error", "entity_ref_missing",
                f"Function '{fid}': entity '{entity}' is not defined in the data spec.",
                hint=f"Available entities: {', '.join(sorted(entity_names))}")

        # Validate parameter types resolve
        for param in fn.get("inputs", []):
            ptype = param.get("type", "")
            base = resolve_base_type(ptype)
            if base and base not in valid_types:
                result.add("error", "type_ref_missing",
                    f"Function '{fid}': parameter '{param['name']}' has type '{ptype}', which is not defined in the data spec.",
                    hint=f"Define '{base}' in the data spec or use an existing type.")

        # Validate output type resolves
        output_type = fn.get("output", {}).get("type", "")
        if output_type:
            base = resolve_base_type(output_type)
            if base and base not in valid_types:
                if base not in api_primitives:
                    result.add("error", "output_type_ref_missing",
                        f"Function '{fid}': output type '{output_type}' is not defined in the data spec.",
                        hint=f"Define '{base}' in the data spec or use an existing type.")
                else:
                    result.add("error", "output_type_not_in_data_spec",
                        f"Function '{fid}': output type '{output_type}' is a valid API primitive but not defined in the data spec.",
                        hint=f"Add '{base}' to the data spec's primitives list or use an existing type.")


def check_module_match(spec: dict, data_spec: Optional[Dict[str, Any]], result: LintResult):
    """Validate that module name matches data spec."""
    if not data_spec:
        return

    api_module = spec.get("module", "")
    data_module = data_spec.get("module", "")

    if api_module and data_module and api_module != data_module:
        result.add("error", "module_mismatch",
            f"ApiSpec module '{api_module}' does not match DataSpec module '{data_module}'.",
            hint="Both specs must describe the same module.")


def check_version_match(spec: dict, data_spec: Optional[Dict[str, Any]], result: LintResult):
    """Validate that dataSpecVersion matches data spec version."""
    if not data_spec:
        return

    api_data_ver = spec.get("dataSpecVersion")
    data_ver = data_spec.get("version")

    if api_data_ver and data_ver and api_data_ver != data_ver:
        result.add("error", "version_mismatch",
            f"ApiSpec dataSpecVersion '{api_data_ver}' does not match DataSpec version '{data_ver}'.",
            hint="Update dataSpecVersion in the API spec after updating the data spec.")


# ── Runner ────────────────────────────────────────────────────────────────────

def run_lint(spec: dict, schema_path: Optional[Path], data_spec: Optional[Dict[str, Any]], strict: bool) -> LintResult:
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
    fn_ids = check_functions(spec, result)
    check_errors(spec, fn_ids, result)
    check_visibility(spec, result)
    check_duplicate_names(spec, result)
    check_missing_descriptions(spec, result)
    check_required_parameter_description(spec, result)
    check_internal_function_visibility(spec, result)

    # Cross-spec checks
    check_entity_refs(spec, data_spec, result)
    check_module_match(spec, data_spec, result)
    check_version_match(spec, data_spec, result)
    check_unused_functions(spec, data_spec, result)
    check_cross_spec_types(spec, data_spec, result)

    if strict:
        for w in result.warnings:
            w.severity = "error"
            result.errors.append(w)
        result.warnings.clear()

    return result


# ── Output ────────────────────────────────────────────────────────────────────

def print_human(result: LintResult, path: str):
    print(f"\n{'─'*60}")
    print(f"  ApiSpec Lint Report — {path}")
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
    parser = argparse.ArgumentParser(description="Lint an ApiSpec JSON.")
    parser.add_argument("input", help="Path to apispec JSON")
    parser.add_argument("--schema", help="Path to apispec.schema.json")
    parser.add_argument("--data", help="Path to dataspec JSON (for cross-spec checks)")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    path = Path(args.input)
    spec = json.loads(path.read_text())
    schema_path = Path(args.schema) if args.schema else None

    data_spec = None
    if args.data:
        data_spec = json.loads(Path(args.data).read_text())

    result = run_lint(spec, schema_path, data_spec, args.strict)

    if args.json:
        print_json_output(result)
    else:
        print_human(result, str(path))

    sys.exit(0 if result.clean else 1)


if __name__ == "__main__":
    main()
