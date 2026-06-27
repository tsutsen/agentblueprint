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
import re
from pathlib import Path
from typing import Optional, Dict, Any
from shared import BaseLinter, LayerResult, SemanticRule, validate_project_and_version


# ── Helpers ───────────────────────────────────────────────────────────────────


def resolve_base_type(type_str: str) -> str:
    """Remove array notation from type string."""
    return type_str.replace("[]", "")


def _check_visibility(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Validate function visibility values."""
    for fn in spec.get("functions", []):
        vis = fn.get("visibility", "public")
        if vis not in ("public", "internal"):
            result.add("error", "fn_visibility_invalid",
                f"Function '{fn['id']}': visibility '{vis}' is not valid.",
                hint="Function visibility must be 'public' or 'internal'.")


def _check_duplicate_names(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
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


def _check_missing_descriptions(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Warn about outputs without descriptions (functions/params use non_empty rule)."""
    for fn in spec.get("functions", []):
        fid = fn["id"]

        # Output description
        output = fn.get("output", {})
        if output and not output.get("description"):
            result.add("info", "missing_output_description",
                f"Function '{fid}': output has no description.",
                hint="Add a description explaining what this function returns.")


def _check_required_param_description(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Required parameters must have descriptions."""
    for fn in spec.get("functions", []):
        fid = fn["id"]
        for param in fn.get("inputs", []):
            if param.get("required", False) and not param.get("description"):
                result.add("warning", "required_param_no_description",
                    f"Function '{fid}': required parameter '{param['name']}' has no description.",
                    hint="Required parameters should always have a description explaining their purpose.")


def _check_internal_function_visibility(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Warn about internal functions with public-facing characteristics."""
    for fn in spec.get("functions", []):
        if fn.get("visibility") == "internal":
            fid = fn["id"]
            if fn.get("errors"):
                result.add("info", "internal_function_with_errors",
                    f"Function '{fid}' is internal but documents error conditions.",
                    hint="Internal functions should handle errors internally. "
                         "Consider making this public if errors need to be exposed.")
            public_tags = {"public", "api", "rest", "graphql"}
            if public_tags & set(fn.get("tags", [])):
                result.add("info", "internal_function_public_tags",
                    f"Function '{fid}' is internal but has public-facing tags: {fn.get('tags')}.",
                    hint="Internal functions should not have public-facing tags.")


def _check_fn_no_errors(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Warn if mutation functions have no error conditions documented."""
    mutation_keywords = ("create", "update", "delete", "remove")
    for fn in spec.get("functions", []):
        fid = fn["id"]
        if any(kw in fid.lower() for kw in mutation_keywords):
            if not fn.get("errors"):
                result.add("warning", "fn_no_errors",
                    f"Function '{fid}' likely modifies data but has no error conditions documented.",
                    hint="Document error conditions such as NOT_FOUND, CONFLICT, UNAUTHORIZED, etc.")


def _check_errors_format(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Validate error code format."""
    for fn in spec.get("functions", []):
        for err in fn.get("errors", []):
            code = err.get("code", "")
            if code and not re.match(r"^[A-Z][A-Z0-9_]*$", code):
                result.add("error", "error_code_format",
                    f"Function '{fn['id']}': error code '{code}' does not follow SCREAMING_SNAKE_CASE.",
                    hint="Error codes must be uppercase with underscores, e.g. 'NOT_FOUND'.")


def _check_fn_name_format(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Validate function name format (camelCase)."""
    for fn in spec.get("functions", []):
        fname = fn.get("name", "")
        if fname and not re.match(r"^[a-z][A-Za-z0-9]*$", fname):
            result.add("error", "fn_name_format",
                f"Function '{fn['id']}': name '{fname}' does not follow camelCase.",
                hint="Function names must start with a lowercase letter.")


def _check_param_name_format(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Validate parameter name format (camelCase)."""
    for fn in spec.get("functions", []):
        for param in fn.get("inputs", []):
            pname = param.get("name", "")
            if pname and not re.match(r"^[a-z][A-Za-z0-9]*$", pname):
                result.add("error", "param_name_format",
                    f"Function '{fn['id']}': parameter '{pname}' does not follow camelCase.",
                    hint="Parameter names must start with a lowercase letter.")


def _check_output_type_format(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Validate output type format."""
    for fn in spec.get("functions", []):
        output_type = fn.get("output", {}).get("type", "")
        if output_type and output_type != "void":
            base = resolve_base_type(output_type)
            if base and not re.match(r"^[A-Za-z]", base):
                result.add("error", "output_type_format",
                    f"Function '{fn['id']}': output type '{output_type}' is invalid.",
                    hint="Output type must be a valid type name starting with a letter, or 'void'.")


def _check_type_refs(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Validate that parameter and output types are defined in the data spec."""
    data_spec = extra_specs.get("data") if extra_specs else None
    if not data_spec:
        return

    entity_names = {e["name"] for e in data_spec.get("entities", [])}
    enum_names = {e["name"] for e in data_spec.get("enums", [])}
    # Handle both string list and dict list for primitives
    raw_primitives = data_spec.get("primitives", ["string", "number", "boolean", "null", "any"])
    primitives = {p if isinstance(p, str) else p.get("id", "") for p in raw_primitives}
    valid_types = entity_names | enum_names | primitives
    api_primitives = {"string", "number", "boolean", "null", "any", "void"}

    for fn in spec.get("functions", []):
        fid = fn["id"]

        # Check parameter types
        for param in fn.get("inputs", []):
            ptype = param.get("type", "")
            base = resolve_base_type(ptype)
            if base and base not in valid_types:
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
                if base not in api_primitives:
                    result.add("error", "output_type_ref_missing",
                        f"Function '{fid}': output type '{output_type}' "
                        f"is not defined in the data spec.",
                        hint=f"Define '{base}' in the data spec or use an existing type.")
                else:
                    result.add("error", "output_type_not_in_data_spec",
                        f"Function '{fid}': output type '{output_type}' is a valid API primitive but not defined in the data spec.",
                        hint=f"Add '{base}' to the data spec's primitives list or use an existing type.")


# ── Semantic Rules ────────────────────────────────────────────────────────────

SEMANTIC_RULES: list[SemanticRule] = [
    # Entity references must exist in data spec
    {
        "type": "exists",
        "target": "functions.entity",
        "inside": "data:entities.name",
        "target_label": "Function",
        "ref_label": "DataSpec entity",
        "category": "entity_ref_missing",
        "hint": "Add this entity to the data spec or correct the reference.",
    },
    # Function descriptions must not be empty
    {
        "type": "non_empty",
        "target": "functions.description",
        "target_label": "Function",
        "category": "missing_function_description",
        "hint": "Add a one-sentence description of what this function does.",
    },
    # Parameter descriptions must not be empty
    {
        "type": "non_empty",
        "target": "functions.inputs.description",
        "target_label": "Parameter",
        "category": "missing_parameter_description",
        "hint": "Add a description explaining the purpose of this parameter.",
    },
]

# ── Misc Checks ───────────────────────────────────────────────────────────────

MISC_CHECKS = [
    ("fn_name_format", _check_fn_name_format),
    ("param_name_format", _check_param_name_format),
    ("output_type_format", _check_output_type_format),
    ("error_code_format", _check_errors_format),
    ("fn_visibility", _check_visibility),
    ("duplicate_names", _check_duplicate_names),
    ("missing_descriptions", _check_missing_descriptions),
    ("required_param_desc", _check_required_param_description),
    ("internal_function", _check_internal_function_visibility),
    ("fn_no_errors", _check_fn_no_errors),
    ("type_refs", _check_type_refs),
]


# ── Cross-spec dependency ─────────────────────────────────────────────────────

CROSS_SPEC_DEPS = ["data"]


# ── Linter Class ──────────────────────────────────────────────────────────────

class ApiSpecLinter(BaseLinter):
    """Linter for ApiSpec artifacts."""
    
    SPEC_NAME = "apispec"
    SEMANTIC_RULES = SEMANTIC_RULES
    MISC_CHECKS = MISC_CHECKS
    CROSS_SPEC_DEPS = CROSS_SPEC_DEPS
    
    def _validate_cross_spec_consistency(self) -> None:
        """Check project match, version pinning, module match, and dataSpecVersion match."""
        super()._validate_cross_spec_consistency()
        
        data = self.extra_specs.get("data")
        if not data:
            return
        
        # Module name must match
        api_module = self.spec.get("module", "")
        data_module = data.get("module", "")
        if api_module and data_module and api_module != data_module:
            self.result.add("error", "module_mismatch",
                f"ApiSpec module '{api_module}' does not match DataSpec module '{data_module}'.",
                hint="Both specs must describe the same module.")
        
        # dataSpecVersion must match DataSpec version
        api_data_ver = self.spec.get("dataSpecVersion")
        data_ver = data.get("version")
        if api_data_ver and data_ver and api_data_ver != data_ver:
            self.result.add("error", "version_mismatch",
                f"ApiSpec dataSpecVersion '{api_data_ver}' does not match DataSpec version '{data_ver}'.",
                hint="Update dataSpecVersion in the API spec after updating the data spec.")


# ── Backward-compatible entry point ───────────────────────────────────────────

def run_lint(spec, schema_path, data_spec, strict):
    """Backward-compatible entry point for lint_all.py."""
    linter = ApiSpecLinter(spec, schema_path, strict)
    return linter.run(data=data_spec)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ApiSpecLinter.main()
