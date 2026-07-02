#!/usr/bin/env python3
"""
generate_schema.py — Assemble JSON Schema files from proto-schemas + shared blocks.

Usage:
    python generate_schema.py <type>          # Generate one schema
    python generate_schema.py --all           # Generate all schemas
    python generate_schema.py --dry-run <type> # Show assembled schema without writing

Proto-schema format: YAML files in artifact/ with simple declarative syntax.
Shared blocks: blocks/refs.yaml (ID patterns) and blocks/base.yaml (base fields).
Output: specs/<type>.schema.json
"""

import json
import os
import re
import sys
from pathlib import Path

import yaml

# ── Paths ──────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
BLOCKS_DIR = SCRIPT_DIR / "blocks"
ARTIFACT_DIR = SCRIPT_DIR / "artifact"
SPECS_DIR = SCRIPT_DIR / "specs"

# Artifact type → output filename mapping
ARTIFACT_OUTPUT = {
    "goalspec": "goalspec.schema.json",
    "glossary": "glossary.schema.json",
    "designspec": "designspec.schema.json",
    "archspec": "archspec.schema.json",
    "dataspec": "dataspec.schema.json",
    "apispec": "apispec.schema.json",
    "testspec": "testspec.schema.json",
    "taskplan": "taskplan.schema.json",
    "issue": "issue.schema.json",
}

# Artifact type → required top-level fields (beyond base fields)
ARTIFACT_REQUIRED = {
    "goalspec": ["objective", "functionalRequirements", "nonFunctionalRequirements",
                 "userStories", "successCriteria", "nonGoals"],
    "glossary": ["terms"],
    "designspec": ["designGoals", "personas", "userJourneys", "screenInventory",
                   "screenSpecs", "uxAcceptanceCriteria"],
    "archspec": ["overview", "components", "dataFlow", "constraints"],
    "dataspec": ["primitives", "enums", "entities", "relationships"],
    "apispec": ["module", "functions"],
    "testspec": ["functionCoverage", "tests"],
    "taskplan": ["milestones", "epics"],
    "issue": ["title", "type", "status", "epic"],
}


# ── YAML Loading ──────────────────────────────────────────────────────────────

def load_yaml(path):
    """Load a YAML file and return the parsed dict."""
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def load_refs():
    """Load ID reference patterns from blocks/refs.yaml."""
    return load_yaml(BLOCKS_DIR / "refs.yaml")


def load_base():
    """Load base fields from blocks/base.yaml."""
    return load_yaml(BLOCKS_DIR / "base.yaml")


def load_artifact(artifact_type):
    """Load a proto-schema from artifact/<type>.yaml."""
    path = ARTIFACT_DIR / f"{artifact_type}.yaml"
    if not path.exists():
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)
    return load_yaml(path)


# ── Schema Assembly ───────────────────────────────────────────────────────────

def build_definitions(refs, custom_defs=None):
    """Build the #/definitions section from refs + custom definitions.

    NOTE: All refs from refs.yaml are included in every schema, not just
    the ones used by this artifact. This keeps schemas self-contained
    (no external $ref needed) at the cost of ~7-15% larger files.
    Optimization possible via a "used refs" collection pass if needed.
    """
    definitions = {}

    # ID pattern definitions from refs.yaml
    for key, info in refs.items():
        def_name = f"{key}Id"
        definitions[def_name] = {
            "type": "string",
            "description": f"{info['title']} identifier.",
            "x_idPattern": key,
        }

    # Custom definitions (e.g., typeRef for apispec)
    if custom_defs:
        for cd in custom_defs:
            def_name = cd["name"]
            definitions[def_name] = {
                "type": cd.get("type", "string"),
                "description": cd.get("desc", ""),
            }

    return definitions


def build_base_properties(base_fields):
    """Build base field properties from blocks/base.yaml."""
    properties = {}
    for name, field in base_fields.items():
        properties[name] = build_base_field(field)
    return properties


def build_base_field(field):
    """Convert a base field dict to JSON Schema."""
    prop = {}
    if "type" in field:
        prop["type"] = field["type"]
    if "description" in field:
        prop["description"] = field["description"]
    if "pattern" in field:
        prop["pattern"] = field["pattern"]
    if "minLength" in field:
        prop["minLength"] = field["minLength"]
    if "enum" in field:
        prop["enum"] = field["enum"]
    if "default" in field:
        prop["default"] = field["default"]
    return prop


def auto_inject_id_name_desc(definitions, ref_key):
    """Build the auto-injected id/name/description properties for a ref'd object."""
    refs_info = {}  # Would need refs here; we pass definitions instead
    properties = {}

    # id field
    def_name = f"{ref_key}Id"
    properties["id"] = {
        "$ref": f"#/definitions/{def_name}",
        "description": f"Unique identifier for this {ref_key}.",
        "x_idPattern": ref_key,
    }

    # name field
    properties["name"] = {
        "type": "string",
        "minLength": 1,
        "description": f"Human-readable {ref_key} name.",
    }

    # description field
    properties["description"] = {
        "type": "string",
        "description": f"Longer description of this {ref_key}.",
    }

    return properties


def convert_field(field, refs, parent_ref=None, named_types=None):
    """Convert a proto-schema field to JSON Schema.

    Args:
        field: A field dict from the proto-schema
        refs: The refs.yaml dict
        parent_ref: The ref key of the parent object (for $ref: "self" resolution)
        named_types: List of named type names (for $ref resolution)
    """
    if named_types is None:
        named_types = []
    prop = {}

    # Handle auto-inject marker (for issue.yaml id field)
    if field.get("autoInject"):
        return None  # Skip — handled by auto-injection

    # Handle $ref shorthand: { $ref: "self" } or { $ref: "typeName" }
    if "$ref" in field:
        ref_target = field["$ref"]
        if ref_target == "self" and parent_ref:
            # Recursive: reference parent's definition
            # If parent is a named type, use it directly; otherwise append Id
            if parent_ref in named_types:
                return {"$ref": f"#/definitions/{parent_ref}"}
            return {"$ref": f"#/definitions/{parent_ref}Id"}
        elif ref_target == "self":
            # No parent ref — use a placeholder
            return {"$ref": "#/definitions/self"}
        else:
            # Named type reference (e.g., iaNode, planguageLevel)
            result = {"$ref": f"#/definitions/{ref_target}"}
            if "desc" in field:
                result["description"] = field["desc"]
            return result

    # Handle shorthand ref: { ref: "key" } (for array items that are just IDs)
    if "ref" in field and "type" not in field and "fields" not in field:
        ref_key = field["ref"]
        return {"$ref": f"#/definitions/{ref_key}Id"}

    # Type dispatch
    if field["type"] == "object":
        prop = convert_object(field, refs, parent_ref)
    elif field["type"] == "array":
        prop = convert_array(field, refs, parent_ref)
    elif field["type"] == "enum":
        prop = convert_enum(field)
    elif field["type"] == "any":
        prop = {
            "description": "Any value."
        }
    else:
        prop["type"] = field["type"]
        # Add constraints
        for constraint in ["minLength", "maxLength", "minimum", "maximum", "pattern"]:
            if constraint in field:
                prop[constraint] = field[constraint]
        if "default" in field:
            prop["default"] = field["default"]

    # Description (from proto-schema desc field)
    if "desc" in field:
        prop["description"] = field["desc"]

    # Ref on non-object, non-array fields (single ID reference)
    # $ref replaces the type — don't keep both
    if "ref" in field and field["type"] not in ("object", "array"):
        ref_key = field["ref"]
        prop = {
            "$ref": f"#/definitions/{ref_key}Id",
            "description": field.get("desc") or refs.get(ref_key, {}).get("title", f"{ref_key} reference"),
        }

    return prop


def convert_object(field, refs, parent_ref=None, named_types=None):
    """Convert an object field to JSON Schema."""
    if named_types is None:
        named_types = []
    prop = {
        "type": "object",
        "additionalProperties": False,
        "properties": {},
        "required": [],
    }

    ref_key = field.get("ref")

    # Auto-inject id/name/description if this object has a ref
    if ref_key:
        injected = auto_inject_id_name_desc({}, ref_key)
        prop["properties"].update(injected)
        # id is always required for ref'd objects
        prop["required"].append("id")
        prop["required"].append("name")
        prop["required"].append("description")

    # Process sub-fields
    for sub in field.get("fields", []):
        sub_name = sub["name"]

        # Skip auto-injected fields from explicit listing
        if ref_key and sub_name in ("id", "name", "description"):
            # Check if this is an explicit override (has autoInject: true)
            if sub.get("autoInject"):
                continue  # Skip — already injected
            # If the user explicitly lists id/name/description with overrides,
            # merge into the auto-injected version
            if sub.get("minLength") or sub.get("maxLength") or sub.get("desc"):
                existing = prop["properties"].get(sub_name, {})
                if sub.get("minLength"):
                    existing["minLength"] = sub["minLength"]
                if sub.get("maxLength"):
                    existing["maxLength"] = sub["maxLength"]
                if sub.get("desc"):
                    existing["description"] = sub["desc"]
                prop["properties"][sub_name] = existing
                continue

        sub_prop = convert_field(sub, refs, parent_ref=ref_key, named_types=named_types)
        if sub_prop is None:
            continue
        prop["properties"][sub_name] = sub_prop

        # Check if field is required
        required_list = field.get("required", [])
        if sub_name in required_list:
            if sub_name not in prop["required"]:
                prop["required"].append(sub_name)

    # Sort required for consistency
    prop["required"] = sorted(set(prop["required"]))

    return prop


def convert_array(field, refs, parent_ref=None, named_types=None):
    """Convert an array field to JSON Schema."""
    if named_types is None:
        named_types = []
    prop = {
        "type": "array",
    }

    if "minItems" in field:
        prop["minItems"] = field["minItems"]

    # Description
    if "desc" in field:
        prop["description"] = field["desc"]

    # Items
    if "of" in field:
        item_def = field["of"]

        # Shorthand: { ref: "key" } means array of ID strings
        if "ref" in item_def and "type" not in item_def and "fields" not in item_def:
            ref_key = item_def["ref"]
            prop["items"] = {"$ref": f"#/definitions/{ref_key}Id"}
            prop["description"] = f"{refs.get(ref_key, {}).get('title', ref_key)} IDs."
            if ref_key == "gl":
                prop["uniqueItems"] = True
        elif isinstance(item_def, dict) and "$ref" in item_def:
            prop["items"] = convert_field(item_def, refs, parent_ref, named_types)
        else:
            prop["items"] = convert_field(item_def, refs, parent_ref, named_types)

    # Array-level ref (for arrays where each item is an ID reference)
    if "ref" in field and "of" not in field:
        ref_key = field["ref"]
        prop["items"] = {"$ref": f"#/definitions/{ref_key}Id"}
        prop["description"] = f"{refs.get(ref_key, {}).get('title', ref_key)} IDs."
        if ref_key == "gl":
            prop["uniqueItems"] = True

    return prop


def convert_enum(field):
    """Convert an enum field to JSON Schema."""
    prop = {
        "type": "string",
        "enum": field["enum"],
    }
    if "default" in field:
        prop["default"] = field["default"]
    if "desc" in field:
        prop["description"] = field["desc"]
    return prop


def assemble_schema(artifact, refs, base_fields):
    """Assemble the complete JSON Schema from proto-schema + blocks."""
    artifact_type = artifact["artifact"]
    schema_version = artifact["schemaVersion"]
    title = artifact["title"]
    description = artifact["description"]

    # Output filename
    output_name = ARTIFACT_OUTPUT.get(artifact_type, f"{artifact_type}.schema.json")

    # Build definitions
    definitions = build_definitions(refs, artifact.get("customDefinitions"))

    # Process named types (for recursive structures like iaNode)
    named_types = artifact.get("namedTypes", [])
    named_type_names = [nt["name"] for nt in named_types]
    for nt in named_types:
        nt_name = nt["name"]
        nt_def = {
            "type": "object",
            "description": nt.get("desc", f"A {nt_name} type."),
            "additionalProperties": False,
            "properties": {},
            "required": [],
        }
        for sub in nt.get("fields", []):
            sub_prop = convert_field(sub, refs, parent_ref=nt_name, named_types=named_type_names)
            if sub_prop is None:
                continue
            nt_def["properties"][sub["name"]] = sub_prop
            if sub["name"] in nt.get("required", []):
                nt_def["required"].append(sub["name"])
        nt_def["required"] = sorted(set(nt_def["required"]))
        definitions[nt_name] = nt_def

    # Build base properties
    properties = build_base_properties(base_fields)

    # Inject schemaVersion
    properties["schemaVersion"] = {
        "type": "string",
        "description": f"Version of the {title} schema this document conforms to. Must be '{schema_version}'.",
        "const": schema_version,
    }

    # Required base fields
    required = ["version", "schemaVersion", "project"]

    # Convert artifact fields
    for field in artifact.get("fields", []):
        field_name = field["name"]

        # Handle special case: issue.yaml has id at top level
        if field.get("autoInject"):
            # Auto-inject id/name/description at top level
            ref_key = field.get("ref")
            if ref_key:
                injected = auto_inject_id_name_desc({}, ref_key)
                properties.update(injected)
                if "id" not in required:
                    required.append("id")
            continue

        field_prop = convert_field(field, refs, named_types=named_type_names)
        if field_prop is None:
            continue
        properties[field_name] = field_prop

    # Add artifact-specific required fields
    extra_required = ARTIFACT_REQUIRED.get(artifact_type, [])
    for req in extra_required:
        if req not in required:
            required.append(req)

    # Build the schema
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": output_name,
        "title": title,
        "description": f"{description}. Version {schema_version}.",
        "type": "object",
        "required": sorted(required),
        "additionalProperties": False,
        "definitions": definitions,
        "properties": properties,
    }

    return schema


# ── CLI ────────────────────────────────────────────────────────────────────────

def generate_one(artifact_type, dry_run=False):
    """Generate schema for a single artifact type."""
    if not dry_run:
        print(f"Generating schema for {artifact_type}...")

    # Load inputs
    artifact = load_artifact(artifact_type)
    refs = load_refs()
    base_fields = load_base()

    # Assemble
    schema = assemble_schema(artifact, refs, base_fields)

    # Output filename
    output_name = ARTIFACT_OUTPUT.get(artifact_type, f"{artifact_type}.schema.json")

    if dry_run:
        print(json.dumps(schema, indent=2))
    else:
        SPECS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = SPECS_DIR / output_name
        with open(output_path, "w") as f:
            json.dump(schema, f, indent=2)
            f.write("\n")
        print(f"  → {output_path}")


def generate_all(dry_run=False):
    """Generate schemas for all artifact types."""
    yaml_files = sorted(ARTIFACT_DIR.glob("*.yaml"))
    for yaml_path in yaml_files:
        artifact_type = yaml_path.stem
        if artifact_type in ARTIFACT_OUTPUT:
            generate_one(artifact_type, dry_run=dry_run)


def main():
    args = sys.argv[1:]

    if not args:
        print("Usage:")
        print("  python generate_schema.py <type>          Generate one schema")
        print("  python generate_schema.py --all           Generate all schemas")
        print("  python generate_schema.py --dry-run <type> Show without writing")
        print()
        print(f"Available types: {', '.join(ARTIFACT_OUTPUT.keys())}")
        sys.exit(1)

    dry_run = False
    if args[0] == "--dry-run":
        if len(args) < 2:
            print("Error: --dry-run requires a type argument", file=sys.stderr)
            sys.exit(1)
        dry_run = True
        artifact_type = args[1]
        generate_one(artifact_type, dry_run=dry_run)
    elif args[0] == "--all":
        generate_all(dry_run=dry_run)
    else:
        artifact_type = args[0]
        if artifact_type not in ARTIFACT_OUTPUT:
            print(f"Error: Unknown artifact type '{artifact_type}'", file=sys.stderr)
            print(f"Available: {', '.join(ARTIFACT_OUTPUT.keys())}", file=sys.stderr)
            sys.exit(1)
        generate_one(artifact_type, dry_run=dry_run)


if __name__ == "__main__":
    main()
