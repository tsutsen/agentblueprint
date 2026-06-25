#!/usr/bin/env python3
"""
generate_markdown_schemas.py — Generate markdown schema docs from JSON schema files.

Reads each *.schema.json file and produces a corresponding *.md file in the
markdown schemas directory. The JSON schema is the single source of truth;
the markdown is derived documentation.

Usage:
    python generate_markdown_schemas.py                          # regenerate all
    python generate_markdown_schemas.py --type goal              # regenerate GoalSpec
    python generate_markdown_schemas.py --type goal glossary     # regenerate specific types
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# Mapping from artifact type name to JSON schema file name
ARTIFACT_TYPE_MAP = {
    "goal": "goalspec.schema.json",
    "glossary": "glossary.schema.json",
    "design": "designspec.schema.json",
    "arch": "archspec.schema.json",
    "data": "dataspec.schema.json",
    "api": "apispec.schema.json",
    "test": "testspec.schema.json",
    "plan": "taskplan.schema.json",
    "issue": "issue.schema.json",
}

# Mapping from schema file name to markdown output file name
SCHEMA_TO_MD = {
    "goalspec.schema.json": "GoalSpec.md",
    "glossary.schema.json": "Glossary.md",
    "designspec.schema.json": "DesignSpec.md",
    "archspec.schema.json": "ArchitectureSpec.md",
    "dataspec.schema.json": "DataSpec.md",
    "apispec.schema.json": "ApiSpec.md",
    "testspec.schema.json": "TestSpec.md",
    "taskplan.schema.json": "TaskPlan.md",
    "issue.schema.json": "Issue.md",
}


def resolve_ref(schema: dict, ref: str) -> dict | None:
    """Resolve a $ref to its definition."""
    if not ref.startswith("#/definitions/"):
        return None
    def_name = ref.split("/")[-1]
    return schema.get("definitions", {}).get(def_name)


def format_type(type_str: str, items_schema: dict | None = None) -> str:
    """Format a JSON Schema type for display."""
    if type_str == "object":
        return "`object`"
    if type_str == "array":
        if items_schema:
            item_type = get_type_string(items_schema)
            return f"`array` of {item_type}"
        return "`array`"
    return f"`{type_str}`"


def get_type_string(schema: dict) -> str:
    """Get a human-readable type string from a schema object."""
    if "$ref" in schema:
        ref = schema["$ref"]
        resolved = resolve_ref(schema, ref)
        if resolved:
            return get_type_string(resolved)
        return ref.split("/")[-1]

    if "enum" in schema:
        return "enum: `" + "` | `".join(str(v) for v in schema["enum"]) + "`"

    if "type" not in schema:
        return "any"

    type_str = schema["type"]
    if type_str == "array":
        items = schema.get("items", {})
        if "$ref" in items:
            resolved = resolve_ref(schema, items["$ref"])
            if resolved:
                return f"`array` of {get_type_string(resolved)}"
        if items.get("type"):
            item_type = get_type_string(items)
            return f"`array` of {item_type}"
        return "`array`"
    return f"`{type_str}`"


def get_constraints(schema: dict) -> list[str]:
    """Extract constraint information from a schema."""
    constraints = []

    if "pattern" in schema:
        pattern = schema["pattern"]
        # Convert regex pattern to a more readable format
        display = pattern.replace("\\", "").replace("$", "").replace("^", "")
        constraints.append(f"pattern: `{schema['pattern']}` (e.g. {display})")

    if "const" in schema:
        constraints.append(f"must be: `{schema['const']}`")

    if "enum" in schema:
        constraints.append("values: `" + "` | `".join(str(v) for v in schema["enum"]) + "`")

    if "minLength" in schema:
        constraints.append(f"min length: {schema['minLength']}")

    if "maxLength" in schema:
        constraints.append(f"max length: {schema['maxLength']}")

    if "minItems" in schema:
        constraints.append(f"min items: {schema['minItems']}")

    return constraints


def generate_field_table(
    properties: dict, required: list[str] | None = None, indent: int = 0
) -> str:
    """Generate a markdown field table from schema properties."""
    if required is None:
        required = []

    lines = []
    lines.append("| Field | Type | Required | Description |")
    lines.append("|-------|------|----------|-------------|")

    for field_name, field_schema in properties.items():
        is_required = field_name in required
        req_str = "Yes" if is_required else "No"
        type_str = get_type_string(field_schema)
        desc = field_schema.get("description", "")

        # Add constraints to description if present
        constraints = get_constraints(field_schema)
        if constraints and desc:
            desc += f" ({', '.join(constraints)})"
        elif constraints:
            desc = ", ".join(constraints)

        # Handle defaults
        if "default" in field_schema:
            default = field_schema["default"]
            if isinstance(default, str):
                default = f"`{default}`"
            else:
                default = str(default)
            desc += f" (default: {default})"

        lines.append(f"| `{field_name}` | {type_str} | {req_str} | {desc} |")

    return "\n".join(lines)


def generate_nested_object(
    schema: dict, name: str, indent: int = 0, is_array_item: bool = False
) -> str:
    """Generate markdown for a nested object definition."""
    prefix = "  " * indent

    lines = []

    # Object description
    if "description" in schema:
        lines.append(f"{prefix}* **{name}** — {schema['description']}")

    if "properties" in schema:
        required = schema.get("required", [])
        lines.append(f"{prefix}Each `{name}` must have:")
        lines.append(f"{prefix}")
        lines.append(f"{prefix}| Field | Type | Required | Description |")
        lines.append(f"{prefix}|-------|------|----------|-------------|")

        for field_name, field_schema in schema["properties"].items():
            is_required = field_name in required
            req_str = "Yes" if is_required else "No"
            type_str = get_type_string(field_schema)
            desc = field_schema.get("description", "")

            # Handle nested $refs
            if "$ref" in field_schema:
                resolved = resolve_ref(schema, field_schema["$ref"])
                if resolved and resolved.get("type") == "object":
                    type_str = f"nested `{field_name}`"

            # Add constraints
            constraints = get_constraints(field_schema)
            if constraints:
                if desc:
                    desc += f" ({', '.join(constraints)})"
                else:
                    desc = ", ".join(constraints)

            # Handle defaults
            if "default" in field_schema:
                default = field_schema["default"]
                if isinstance(default, str):
                    default = f"`{default}`"
                else:
                    default = str(default)
                desc += f" (default: {default})"

            lines.append(
                f"{prefix}| `{field_name}` | {type_str} | {req_str} | {desc} |"
            )

        # Handle nested objects recursively
        for field_name, field_schema in schema["properties"].items():
            if field_schema.get("type") == "object" and "properties" in field_schema:
                lines.append("")
                lines.append(f"{prefix}#### `{field_name}` structure")
                lines.append(f"{prefix}")
                lines.extend(
                    generate_nested_object(
                        field_schema, field_name, indent + 1
                    ).split("\n")
                )

            # Handle arrays of objects
            if field_schema.get("type") == "array" and "items" in field_schema:
                items = field_schema["items"]
                if items.get("type") == "object" and "properties" in items:
                    lines.append("")
                    lines.append(f"{prefix}#### `{field_name}` items")
                    lines.append(f"{prefix}")
                    lines.append(
                        f"{prefix}Each `{field_name}` item must have:"
                    )
                    lines.append(f"{prefix}")
                    lines.append(f"{prefix}| Field | Type | Required | Description |")
                    lines.append(f"{prefix}|-------|------|----------|-------------|")

                    item_required = items.get("required", [])
                    for field_name2, field_schema2 in items["properties"].items():
                        is_required = field_name2 in item_required
                        req_str = "Yes" if is_required else "No"
                        type_str = get_type_string(field_schema2)
                        desc = field_schema2.get("description", "")

                        # Handle nested $refs in array items
                        if "$ref" in field_schema2:
                            resolved = resolve_ref(items, field_schema2["$ref"])
                            if resolved and resolved.get("type") == "object":
                                type_str = f"nested `{field_name2}`"

                        constraints = get_constraints(field_schema2)
                        if constraints:
                            if desc:
                                desc += f" ({', '.join(constraints)})"
                            else:
                                desc = ", ".join(constraints)

                        if "default" in field_schema2:
                            default = field_schema2["default"]
                            if isinstance(default, str):
                                default = f"`{default}`"
                            else:
                                default = str(default)
                            desc += f" (default: {default})"

                        lines.append(
                            f"{prefix}| `{field_name2}` | {type_str} | {req_str} | {desc} |"
                        )

    return "\n".join(lines)


def generate_minimal_example(schema: dict, depth: int = 0) -> dict:
    """Generate a minimal valid example from the schema."""
    if "properties" not in schema:
        return {}

    result = {}
    required = schema.get("required", [])

    for field_name, field_schema in schema["properties"].items():
        field_type = field_schema.get("type")

        # Required fields first
        if field_name not in required:
            continue

        if field_type == "string":
            if "const" in field_schema:
                result[field_name] = field_schema["const"]
            elif "pattern" in field_schema:
                pattern = field_schema["pattern"]
                # Generate example based on pattern
                if "GL-" in pattern:
                    result[field_name] = "GL-001"
                elif "REQ-" in pattern:
                    result[field_name] = "REQ-001"
                elif "NFR-" in pattern:
                    result[field_name] = "NFR-001"
                elif "US-" in pattern:
                    result[field_name] = "US-001"
                elif "SC-" in pattern:
                    result[field_name] = "SC-001"
                elif "FN-" in pattern:
                    result[field_name] = "FN-example"
                elif "IS-" in pattern:
                    result[field_name] = "IS-001"
                elif "EP-" in pattern:
                    result[field_name] = "EP-001"
                elif "M\\d" in pattern:
                    result[field_name] = "M1"
                elif "^[A-Z]" in pattern:
                    result[field_name] = "Example"
                elif "camelCase" in field_schema.get("description", "").lower():
                    result[field_name] = "exampleField"
                else:
                    result[field_name] = "example"
            elif "enum" in field_schema:
                result[field_name] = field_schema["enum"][0]
            else:
                # Check description for hints
                desc = field_schema.get("description", "").lower()
                if "date" in desc:
                    result[field_name] = "2024-01-01"
                elif "version" in desc:
                    result[field_name] = "1.0.0"
                elif "project" in desc:
                    result[field_name] = "Example Project"
                elif "semver" in desc:
                    result[field_name] = "1.0.0"
                else:
                    result[field_name] = "example"
        elif field_type == "number":
            result[field_name] = 1
        elif field_type == "boolean":
            result[field_name] = False
        elif field_type == "array":
            items = field_schema.get("items", {})
            if items.get("type") == "string":
                result[field_name] = ["example"]
            elif items.get("$ref"):
                # Array of refs — use placeholder
                result[field_name] = ["example"]
            elif items.get("type") == "object":
                result[field_name] = [generate_minimal_example(items, depth + 1)]
            else:
                result[field_name] = []
        elif field_type == "object":
            result[field_name] = generate_minimal_example(field_schema, depth + 1)

    # Add optional fields with minimal examples
    for field_name, field_schema in schema["properties"].items():
        if field_name in result:
            continue
        field_type = field_schema.get("type")

        if field_type == "string":
            if "enum" in field_schema:
                result[field_name] = field_schema["enum"][0]
            elif "pattern" in field_schema:
                pattern = field_schema["pattern"]
                if "GL-" in pattern:
                    result[field_name] = ["GL-001"]
                elif "FN-" in pattern:
                    result[field_name] = ["FN-example"]
                elif "EP-" in pattern:
                    result[field_name] = ["EP-001"]
                elif "IS-" in pattern:
                    result[field_name] = ["IS-001"]
                else:
                    result[field_name] = "example"
            elif "enum" in field_schema:
                result[field_name] = field_schema["enum"][0]
            else:
                result[field_name] = "example"
        elif field_type == "number":
            result[field_name] = 1
        elif field_type == "boolean":
            result[field_name] = False
        elif field_type == "array":
            items = field_schema.get("items", {})
            if items.get("type") == "string":
                result[field_name] = ["example"]
            elif items.get("type") == "object":
                result[field_name] = [generate_minimal_example(items, depth + 1)]
            else:
                result[field_name] = []
        elif field_type == "object":
            result[field_name] = generate_minimal_example(field_schema, depth + 1)

    return result


def generate_markdown(schema: dict, artifact_name: str) -> str:
    """Generate complete markdown documentation for a schema."""
    lines = []

    # Frontmatter
    lines.append("---")
    lines.append(f"name: {artifact_name}")
    lines.append("type: schema")
    lines.append("version: 1.0.0")
    lines.append("---")
    lines.append("")

    # Title and description
    title = schema.get("title", artifact_name)
    description = schema.get("description", "")
    lines.append(f"# {title}")
    lines.append("")
    lines.append(description)
    lines.append("")

    # Output format section
    json_schema_name = schema.get("$id", f"{artifact_name.lower()}.schema.json")
    md_name = SCHEMA_TO_MD.get(json_schema_name, f"{artifact_name}.md")

    lines.append("## Output Format")
    lines.append("")
    lines.append(f"This artifact produces two files:")
    lines.append("")
    lines.append(f"- `artifacts/{md_name}` — human-readable document (this format)")
    lines.append(
        f"- `artifacts/{artifact_name}.json` — machine-readable, conforming to `schemas/{json_schema_name}`"
    )
    lines.append("")

    # Root properties
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    if properties:
        lines.append("## Schema Reference")
        lines.append("")
        lines.append("### Root Fields")
        lines.append("")
        lines.append(generate_field_table(properties, required))
        lines.append("")

        # Nested objects
        lines.append("### Nested Structures")
        lines.append("")

        for field_name, field_schema in properties.items():
            if field_schema.get("type") == "object" and "properties" in field_schema:
                lines.append(f"#### `{field_name}`")
                lines.append("")
                lines.append(generate_nested_object(field_schema, field_name))
                lines.append("")

            if field_schema.get("type") == "array" and "items" in field_schema:
                items = field_schema["items"]
                if items.get("type") == "object" and "properties" in items:
                    lines.append(f"#### `{field_name}` items")
                    lines.append("")
                    lines.append(generate_nested_object(items, field_name, is_array_item=True))
                    lines.append("")

        # Definitions (enums, ref types)
        definitions = schema.get("definitions", {})
        if definitions:
            lines.append("### Definitions")
            lines.append("")

            for def_name, def_schema in definitions.items():
                if def_schema.get("type") == "string" and "enum" in def_schema:
                    lines.append(f"#### `{def_name}`")
                    lines.append("")
                    lines.append(f"Enum values:")
                    lines.append("")
                    for val in def_schema["enum"]:
                        desc = def_schema.get("description", "")
                        if desc:
                            lines.append(f"- `{val}` — {desc}")
                        else:
                            lines.append(f"- `{val}`")
                    lines.append("")

    # Minimal example
    lines.append("## Minimal Example")
    lines.append("")
    example = generate_minimal_example(schema)
    lines.append("```json")
    lines.append(json.dumps(example, indent=2))
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def find_schemas(schemas_dir: str) -> list[tuple[str, str]]:
    """Find all schema files and their artifact types.
    Returns list of (artifact_type, schema_path) tuples."""
    schemas = []
    for type_name, schema_file in ARTIFACT_TYPE_MAP.items():
        schema_path = os.path.join(schemas_dir, schema_file)
        if os.path.exists(schema_path):
            schemas.append((type_name, schema_path))
    return schemas


def main():
    parser = argparse.ArgumentParser(
        description="Generate markdown schema docs from JSON schema files."
    )
    parser.add_argument(
        "--type",
        nargs="+",
        choices=list(ARTIFACT_TYPE_MAP.keys()),
        help="Artifact types to regenerate (default: all)",
    )
    parser.add_argument(
        "--schemas-dir",
        default=None,
        help="Path to schemas/json directory (default: auto-detect)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Path to instructions directory (default: auto-detect)",
    )
    args = parser.parse_args()

    # Auto-detect paths
    script_dir = Path(__file__).resolve().parent
    if args.schemas_dir is None:
        # extensions/blueprint/ -> ../../skills/blueprint/schemas/json/
        schemas_dir = str(script_dir.parent.parent / "skills" / "blueprint" / "schemas" / "json")
    else:
        schemas_dir = args.schemas_dir

    if args.output_dir is None:
        output_dir = str(
            Path(schemas_dir).parent.parent / "markdown"
        )
    else:
        output_dir = args.output_dir

    # Find schemas to process
    if args.type:
        schema_files = [(t, ARTIFACT_TYPE_MAP[t]) for t in args.type]
    else:
        schema_files = list(ARTIFACT_TYPE_MAP.items())

    generated = 0
    for type_name, schema_file in schema_files:
        schema_path = os.path.join(schemas_dir, schema_file)
        if not os.path.exists(schema_path):
            print(f"  SKIP: {schema_file} not found")
            continue

        # Load schema
        with open(schema_path, "r") as f:
            schema = json.load(f)

        # Generate markdown
        artifact_name = schema.get("title", type_name.title())
        md_content = generate_markdown(schema, artifact_name)

        # Determine output path
        md_filename = SCHEMA_TO_MD.get(schema_file, f"{type_name.title()}.md")
        md_path = os.path.join(output_dir, md_filename)

        # Write file (skip if exists to preserve hand-written content)
        os.makedirs(os.path.dirname(md_path), exist_ok=True)
        if os.path.exists(md_path):
            print(f"  SKIP: {md_path} (already exists — hand-written content preserved)")
        else:
            with open(md_path, "w") as f:
                f.write(md_content)
            print(f"  GENERATED: {md_path}")
            generated += 1

    print(f"\nGenerated {generated} markdown schema(s).")

    # Show diff summary
    print("\nRegenerated schemas:")
    for type_name, schema_file in schema_files:
        md_filename = SCHEMA_TO_MD.get(schema_file, f"{type_name.title()}.md")
        print(f"  - {md_filename}")


if __name__ == "__main__":
    main()
