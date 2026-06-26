#!/usr/bin/env python3
"""
schema_validator.py — JSON Schema-driven validation for linters.

Reads a JSON schema and validates a document against it, returning
Issue objects with structured categories, messages, and hints.

This eliminates duplication between schema definitions and linter checks.
When a schema constraint changes, validation updates automatically.

Usage:
    from schema_validator import SchemaValidator

    validator = SchemaValidator(schema_path="path/to/schema.json")
    issues = validator.validate(document)

    # Or validate a file directly:
    issues = SchemaValidator.validate_file(schema_path, file_path)
"""

import json
import re
from pathlib import Path
from typing import Any, Optional

from linters.shared import Issue, LayerResult


# ── Constraint metadata ──────────────────────────────────────────────────────

CONSTRAINT_HINTS = {
    "pattern": "Value must match the required pattern.",
    "enum": "Value must be one of the allowed values.",
    "const": "Value must be exactly this value.",
    "minLength": "String must be at least this many characters.",
    "maxLength": "String must be at most this many characters.",
    "minimum": "Value must be at least this number.",
    "maximum": "Value must be at most this number.",
    "minItems": "Array must have at least this many items.",
    "maxItems": "Array must have at most this many items.",
    "required": "This field is required.",
    "type": "Value must be of the correct type.",
}

TYPE_HINTS = {
    "string": "a string value",
    "number": "a number (integer or float)",
    "integer": "an integer value",
    "boolean": "a boolean value (true/false)",
    "array": "an array of values",
    "object": "an object with key-value pairs",
    "null": "a null value",
}


def _format_path(path: list[str]) -> str:
    """Format a JSON path list into a dot-notation string."""
    if not path:
        return "$"
    parts = []
    for p in path:
        if p.isdigit():
            parts.append(f"[{p}]")
        else:
            parts.append(f".{p}")
    return "$" + "".join(parts)


def _human_type(expected: Any) -> str:
    """Convert a JSON Schema type to a human-readable description."""
    if isinstance(expected, str):
        return TYPE_HINTS.get(expected, expected)
    if isinstance(expected, list):
        return " or ".join(TYPE_HINTS.get(t, t) for t in expected)
    return str(expected)


class SchemaValidator:
    """Validates a JSON document against a JSON Schema and returns Issues."""

    def __init__(self, schema: dict | Path | str):
        """Initialize with a schema dict, file path, or JSON string."""
        if isinstance(schema, (Path, str)):
            path = Path(schema)
            if path.exists():
                schema = json.loads(path.read_text())
            else:
                schema = json.loads(schema)  # Assume it's a JSON string
        self.schema = schema
        self._issues: list[Issue] = []

    def validate(self, document: dict) -> list[Issue]:
        """Validate a document against the schema and return Issues."""
        self._issues = []
        self._validate_node(document, self.schema, [])
        return self._issues

    def validate_file(self, schema_path: str | Path, doc_path: str | Path) -> list[Issue]:
        """Validate a JSON file against a schema file."""
        schema = json.loads(Path(schema_path).read_text())
        doc = json.loads(Path(doc_path).read_text())
        return self._validate_document(doc, schema)

    def _validate_document(self, doc: dict, schema: dict) -> list[Issue]:
        """Validate a document against a schema, returning Issues."""
        self._issues = []
        self._validate_node(doc, schema, [])
        return self._issues

    def _validate_node(self, node: Any, schema: dict, path: list[str]):
        """Recursively validate a node against its schema."""
        # Skip if no schema for this node (e.g., $ref resolved to empty)
        if not schema:
            return

        # Type check
        if "type" in schema:
            self._check_type(node, schema["type"], path)

        # Const check
        if "const" in schema:
            if node != schema["const"]:
                self._add_issue(
                    "error", "schema_const",
                    f"{_format_path(path)}: expected {json.dumps(schema['const'])}, "
                    f"got {json.dumps(node)}",
                    hint=CONSTRAINT_HINTS["const"]
                )

        # Enum check
        if "enum" in schema:
            if node not in schema["enum"]:
                allowed = ", ".join(json.dumps(v) for v in schema["enum"])
                self._add_issue(
                    "error", "schema_enum",
                    f"{_format_path(path)}: value must be one of: {allowed}",
                    hint=CONSTRAINT_HINTS["enum"]
                )

        # Pattern check (strings only)
        if "pattern" in schema and isinstance(node, str):
            if not re.search(schema["pattern"], node):
                self._add_issue(
                    "error", "schema_pattern",
                    f"{_format_path(path)}: value '{node}' does not match pattern "
                    f"'{schema['pattern']}'",
                    hint=CONSTRAINT_HINTS["pattern"]
                )

        # String constraints
        if isinstance(node, str):
            if "minLength" in schema and len(node) < schema["minLength"]:
                self._add_issue(
                    "error", "schema_min_length",
                    f"{_format_path(path)}: string length {len(node)} is less than "
                    f"minimum {schema['minLength']}",
                    hint=CONSTRAINT_HINTS["minLength"]
                )
            if "maxLength" in schema and len(node) > schema["maxLength"]:
                self._add_issue(
                    "error", "schema_max_length",
                    f"{_format_path(path)}: string length {len(node)} exceeds "
                    f"maximum {schema['maxLength']}",
                    hint=CONSTRAINT_HINTS["maxLength"]
                )

        # Numeric constraints
        if isinstance(node, (int, float)) and not isinstance(node, bool):
            if "minimum" in schema and node < schema["minimum"]:
                self._add_issue(
                    "error", "schema_minimum",
                    f"{_format_path(path)}: value {node} is less than minimum "
                    f"{schema['minimum']}",
                    hint=CONSTRAINT_HINTS["minimum"]
                )
            if "maximum" in schema and node > schema["maximum"]:
                self._add_issue(
                    "error", "schema_maximum",
                    f"{_format_path(path)}: value {node} exceeds maximum "
                    f"{schema['maximum']}",
                    hint=CONSTRAINT_HINTS["maximum"]
                )

        # Object constraints
        if isinstance(node, dict):
            # Required fields
            if "required" in schema:
                for field in schema["required"]:
                    if field not in node:
                        self._add_issue(
                            "error", "schema_required",
                            f"{_format_path(path)}: missing required field '{field}'",
                            hint=CONSTRAINT_HINTS["required"]
                        )

            # Additional properties
            if "additionalProperties" in schema:
                if schema["additionalProperties"] is False:
                    allowed = set(schema.get("properties", {}).keys())
                    extra = set(node.keys()) - allowed
                    if extra:
                        self._add_issue(
                            "error", "schema_additional_properties",
                            f"{_format_path(path)}: unexpected fields: {sorted(extra)}",
                            hint="Remove unexpected fields or update the schema."
                        )

            # Validate properties
            if "properties" in schema:
                for prop, prop_schema in schema["properties"].items():
                    if prop in node:
                        self._validate_node(node[prop], prop_schema, path + [prop])

        # Array constraints
        if isinstance(node, list):
            if "minItems" in schema and len(node) < schema["minItems"]:
                self._add_issue(
                    "error", "schema_min_items",
                    f"{_format_path(path)}: array has {len(node)} items, minimum is "
                    f"{schema['minItems']}",
                    hint=CONSTRAINT_HINTS["minItems"]
                )
            if "maxItems" in schema and len(node) > schema["maxItems"]:
                self._add_issue(
                    "error", "schema_max_items",
                    f"{_format_path(path)}: array has {len(node)} items, maximum is "
                    f"{schema['maxItems']}",
                    hint=CONSTRAINT_HINTS["maxItems"]
                )

            # Validate array items
            if "items" in schema:
                for i, item in enumerate(node):
                    self._validate_node(item, schema["items"], path + [str(i)])

    def _check_type(self, node: Any, expected: Any, path: list[str]):
        """Check if a node matches the expected JSON Schema type."""
        if isinstance(expected, str):
            type_map = {
                "string": str,
                "number": (int, float),
                "integer": int,
                "boolean": bool,
                "array": list,
                "object": dict,
                "null": type(None),
            }
            expected_type = type_map.get(expected)
            if expected_type and not isinstance(node, expected_type):
                # Special case: JSON Schema treats integers as numbers
                if expected == "number" and isinstance(node, int):
                    return
                self._add_issue(
                    "error", "schema_type",
                    f"{_format_path(path)}: expected {_human_type(expected)}, "
                    f"got {_human_type(type(node).__name__)}",
                    hint=f"Value must be {_human_type(expected)}."
                )
        elif isinstance(expected, list):
            # Type can be an array (e.g., ["string", "null"])
            matched = False
            for t in expected:
                if t == "string" and isinstance(node, str):
                    matched = True
                    break
                if t == "number" and isinstance(node, (int, float)) and not isinstance(node, bool):
                    matched = True
                    break
                if t == "integer" and isinstance(node, int) and not isinstance(node, bool):
                    matched = True
                    break
                if t == "boolean" and isinstance(node, bool):
                    matched = True
                    break
                if t == "array" and isinstance(node, list):
                    matched = True
                    break
                if t == "object" and isinstance(node, dict):
                    matched = True
                    break
                if t == "null" and node is None:
                    matched = True
                    break
            if not matched:
                self._add_issue(
                    "error", "schema_type",
                    f"{_format_path(path)}: expected {_human_type(expected)}, "
                    f"got {_human_type(type(node).__name__)}",
                    hint=f"Value must be {_human_type(expected)}."
                )

    def _add_issue(self, severity: str, category: str, message: str, hint: str = ""):
        """Add an issue to the results."""
        self._issues.append(Issue(severity, category, message, hint))


def validate_against_schema(schema_path: str | Path, doc_path: str | Path) -> list[Issue]:
    """Convenience function: validate a JSON file against a schema file."""
    return SchemaValidator.validate_file(schema_path, doc_path)


def validate_schema_doc(schema: dict, doc: dict) -> list[Issue]:
    """Convenience function: validate a document against a schema dict."""
    return SchemaValidator(schema).validate(doc)
