#!/usr/bin/env python3
"""
generate_artifact_markdown.py — Convert artifact JSON files to Markdown format.

Schema-driven renderer: reads the JSON schema and derives rendering rules
from it. No hardcoded per-artifact generators.

Usage:
    python generate_artifact_markdown.py --type goal --json artifacts/GoalSpec.json
    python generate_artifact_markdown.py --type goal --json artifacts/GoalSpec.json --output artifacts/GoalSpec.md
    python generate_artifact_markdown.py --type all  # convert all artifacts in artifacts/
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

try:
    from jinja2 import Environment, FileSystemLoader
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False

# Mapping from artifact type to JSON schema file name
ARTIFACT_TYPE_MAP = {
    "goal": ("goalspec.schema.json", "GoalSpec", "Goal Specification"),
    "glossary": ("glossary.schema.json", "Glossary", "Glossary"),
    "design": ("designspec.schema.json", "DesignSpec", "Design Specification"),
    "arch": ("archspec.schema.json", "ArchitectureSpec", "Architecture Specification"),
    "data": ("dataspec.schema.json", "DataSpec", "Data Specification"),
    "api": ("apispec.schema.json", "ApiSpec", "API Specification"),
    "test": ("testspec.schema.json", "TestSpec", "Test Specification"),
    "plan": ("taskplan.schema.json", "TaskPlan", "Task Plan"),
    "issue": ("issue.schema.json", "Issue", "Issue"),
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
    "issue.schema.json": None,
}


# ─── Jinja2 Filters ───────────────────────────────────────────────────────────

def format_glossary_refs(refs):
    """Format glossary refs as backtick-quoted: `GL-001`, `GL-002`"""
    return ', '.join(f'`{r}`' for r in refs)


def format_inputs(inputs):
    """Format inputs as 'name: type' strings."""
    if not inputs:
        return ""
    return ', '.join(
        f"{inp['name']}: {inp['type']}" if isinstance(inp, dict) else str(inp)
        for inp in inputs
    )


def format_id_refs(text):
    """Wrap all ID references in backticks: REQ-001, NFR-002, TST-003, FN-063, GL-008, etc."""
    if isinstance(text, list):
        return ', '.join(f'`{r}`' for r in text)
    return re.sub(r'\b([A-Z]{1,4}-\d{3,})\b', r'`\1`', str(text))


def clean_flow_name(name):
    """Remove embedded ID references from flow names for clean display."""
    # Remove (**REQ-024**) pattern
    cleaned = re.sub(r'\s*\(\*\*[A-Z]{1,4}-\d{3,}+\*\*\)', '', name)
    # Remove (REQ-024) pattern
    cleaned = re.sub(r'\s*\([A-Z]{1,4}-\d{3,}\)', '', cleaned)
    return cleaned.strip()


def render_ia_tree(tree, indent=0):
    """Render an information architecture tree as indented text."""
    lines = []
    # Handle dict with 'root' key
    if isinstance(tree, dict) and 'root' in tree:
        return render_ia_tree(tree['root'], indent)
    if isinstance(tree, list):
        for item in tree:
            lines.append(render_ia_tree(item, indent))
    elif isinstance(tree, dict):
        name = tree.get('name', 'Unknown')
        screen_ref = tree.get('screenRef', '')
        prefix = '  ' * indent
        if indent == 0:
            lines.append(f'{prefix}{name}')
        else:
            ref = f' ({screen_ref})' if screen_ref else ''
            lines.append(f'{prefix}- {name}{ref}')
        if 'children' in tree:
            lines.append(render_ia_tree(tree['children'], indent + 1))
    return '\n'.join(lines)


def format_json(obj):
    """Format an object as compact JSON."""
    return json.dumps(obj, ensure_ascii=False)


# ─── Schema Loading ───────────────────────────────────────────────────────────

def resolve_schema_path(schemas_dir: str, schema_name: str) -> str:
    """Resolve the path to a schema file."""
    return os.path.join(schemas_dir, schema_name)


def load_schema(schemas_dir: str, schema_name: str) -> dict:
    """Load a JSON schema file."""
    schema_path = resolve_schema_path(schemas_dir, schema_name)
    with open(schema_path, "r") as f:
        return json.load(f)


# ─── Generic Rendering Helpers ────────────────────────────────────────────────

def render_value(value: Any, indent: int = 0, prop_schema: Optional[dict] = None) -> str:
    """Render a single value as markdown text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return render_array(value, prop_schema)
    if isinstance(value, dict):
        return render_object(value, prop_schema)
    return str(value)


def render_simple_object(obj: dict) -> str:
    """Render a simple key-value dict with each field on its own line."""
    if not obj:
        return ""
    lines = []
    for key, value in obj.items():
        label = key.replace("_", " ").title()
        lines.append(f"- {label}: {render_value(value)}")
    return "\n".join(lines)


def render_array(items: list, prop_schema: Optional[dict] = None) -> str:
    """Render an array as markdown."""
    if not items:
        return ""
    # Check if items are simple (strings, numbers, booleans)
    if all(isinstance(i, (str, int, float, bool)) for i in items):
        return ", ".join(str(i) for i in items)
    # Check if items are dicts with a common "name" or "title" field
    if all(isinstance(i, dict) for i in items):
        lines = []
        first_item = items[0]
        # Check if there's a common structure
        if "id" in first_item and "description" in first_item:
            # List of items with id and description
            for item in items:
                id_ = item.get("id", "")
                desc = item.get("description", "")
                if desc:
                    lines.append(f"- {id_}: {desc}")
                else:
                    lines.append(f"- {id_}")
        elif "name" in first_item and "description" in first_item:
            for item in items:
                name = item.get("name", "")
                desc = item.get("description", "")
                if desc:
                    lines.append(f"- {name}: {desc}")
                else:
                    lines.append(f"- {name}")
        elif "term" in first_item and "definition" in first_item:
            # Glossary terms
            for item in items:
                name = item.get("term", "")
                definition = item.get("definition", "")
                if definition:
                    lines.append(f"- {name}: {definition}")
                else:
                    lines.append(f"- {name}")
        else:
            # Generic list of objects
            for item in items:
                lines.append(render_object(item))
        return "\n".join(lines)
    # Fallback: simple list
    return "\n".join(f"- {render_value(i)}" for i in items)


def render_object(obj: dict, prop_schema: Optional[dict] = None) -> str:
    """Render an object as markdown."""
    if not obj:
        return ""
    # Check if it's a nested object with known structure
    if "statement" in obj:
        # Objective-like object
        return obj["statement"]
    if "term" in obj and "definition" in obj:
        # Term-like object
        return f"{obj['term']}: {obj['definition']}"
    # Check if this is a simple key-value object
    if all(isinstance(v, (str, int, float, bool)) for v in obj.values()):
        return render_simple_object(obj)
    # Generic nested object
    lines = []
    if prop_schema and "properties" in prop_schema:
        for prop_name, prop_def in prop_schema["properties"].items():
            if prop_name in obj:
                label = get_property_description(prop_def)
                value = obj[prop_name]
                rendered = render_value(value, prop_schema=prop_def)
                if rendered:
                    lines.append(f"- {label}: {rendered}")
    else:
        for key, value in obj.items():
            if isinstance(value, (str, int, float, bool)):
                label = key.replace("_", " ").title()
                lines.append(f"- {label}: {render_value(value)}")
            elif isinstance(value, (list, dict)):
                rendered = render_value(value)
                if rendered:
                    lines.append(f"- {key}:\n{rendered}")
    return "\n".join(lines) if lines else ""


def get_property_description(prop: dict) -> str:
    """Get the description of a property, falling back to a human-readable name."""
    if "description" in prop:
        return prop["description"]
    # Generate from name: snake_case to Title Case
    name = prop.get("name", "") or prop.get("$id", "")
    return name.replace("_", " ").title() if name else "Field"


# ─── Frontmatter ──────────────────────────────────────────────────────────────

# Artifact-specific frontmatter field order
FRONTMATTER_FIELDS = {
    "goal": ["objective", "functionalRequirements", "nonFunctionalRequirements", "userStories", "successCriteria", "nonGoals"],
    "glossary": ["terms"],
    "design": ["designGoals", "personas", "userJourneys", "informationArchitecture", "screenInventory", "screenSpecs", "interactionPatterns", "visualDesignRequirements", "designSystem", "accessibilityRequirements", "uxAcceptanceCriteria", "designTokens"],
    "arch": ["overview", "components", "dataModel", "apiContract", "dataFlow", "constraints"],
    "data": ["description", "primitives", "enums", "entities", "relationships"],
    "api": ["description", "functions"],
    "test": ["tests"],
    "plan": ["milestones", "epics"],
    "issue": ["id", "title", "type", "status", "epic", "blocked_by", "milestone", "created", "updated", "inScope", "outOfScope", "acceptanceCriteria"],
}

# Fields to skip entirely (metadata-only, already in frontmatter)
FRONTMATTER_SKIP = {
    "version", "schemaVersion", "updated", "created", "_meta",
    "glossaryRefs", "reqRefs", "nfrRefs", "usRefs", "fnRefs", "entityRefs",
    # Top-level metadata — already in frontmatter or not content
    "project", "status", "module", "description",
    "goalSpecVersion", "dataSpecVersion", "apiSpecVersion",
    "verificationStatus", "functionCoverage", "titleGlossaryRefs",
}


def generate_frontmatter(artifact_type: str, data: dict, schema: dict) -> str:
    """Generate YAML frontmatter for the markdown file."""
    lines = ["---"]

    # artifact name
    lines.append(f"artifact: {ARTIFACT_TYPE_MAP[artifact_type][2]}")

    # status
    if "status" in data:
        lines.append(f"status: {data['status']}")

    # sections_complete / sections_pending based on field presence
    ordered_fields = FRONTMATTER_FIELDS.get(artifact_type, [])
    if not ordered_fields and "properties" in schema:
        ordered_fields = list(schema["properties"].keys())

    sections = []
    pending = []
    for field in ordered_fields:
        value = data.get(field)
        if value:
            if isinstance(value, list) and len(value) > 0:
                sections.append(field.replace("_", " ").title())
            elif isinstance(value, str) and len(value.strip()) > 0:
                sections.append(field.replace("_", " ").title())
            elif isinstance(value, dict) and len(value) > 0:
                sections.append(field.replace("_", " ").title())
        else:
            pending.append(field.replace("_", " ").title())

    if sections:
        lines.append("sections_complete:")
        for s in sections:
            lines.append(f"  - {s}")
    if pending:
        lines.append("sections_pending:")
        for s in pending:
            lines.append(f"  - {s}")

    # updated/created date
    if "updated" in data:
        lines.append(f"updated: {data['updated']}")
    elif "created" in data:
        lines.append(f"updated: {data['created']}")

    lines.append("---")
    lines.append("")

    return "\n".join(lines)


# ─── Schema-Driven Rendering (fallback) ───────────────────────────────────────

def render_schema_properties(data: dict, schema: dict, artifact_type: str) -> str:
    """Render all properties from the schema that exist in the data.
    
    This is a fallback for artifact types that don't have Jinja2 templates yet.
    """
    lines = []
    properties = schema.get("properties", {})
    if not properties:
        # Fallback: render all top-level keys
        for key, value in data.items():
            if key in FRONTMATTER_SKIP or key.startswith("_"):
                continue
            rendered = render_simple_object(value) if isinstance(value, dict) else render_value(value)
            if rendered:
                label = key.replace("_", " ").title()
                lines.append(f"## {label}\n\n{rendered}\n")
        return "\n".join(lines)

    # Render in schema-defined order
    for prop_name, prop_def in properties.items():
        if prop_name not in data:
            continue
        if prop_name in FRONTMATTER_SKIP:
            continue

        title = prop_def.get("title", "")
        if not title and "description" in prop_def:
            title = prop_def["description"]
        if not title:
            title = prop_name.replace("_", " ").title()

        value = data[prop_name]
        rendered = render_value(value, prop_schema=prop_def)

        if not rendered:
            continue

        # Generic rendering — use the property name
        lines.append(f"## {prop_name.replace('_', ' ').title()}\n")
        lines.append(rendered)
        lines.append("")

    return "\n".join(lines)


# ─── Template Rendering ───────────────────────────────────────────────────────

def render_template(artifact_type: str, data: dict, json_path: str,
                     schemas_dir: str, artifacts_dir: str,
                     output_path: Optional[str] = None) -> str:
    """Generate markdown from artifact JSON data using Jinja2 templates."""
    script_dir = Path(__file__).resolve().parent
    templates_dir = script_dir / "templates"

    template_file = templates_dir / f"{artifact_type}.md.j2"
    if not template_file.exists():
        # Fall back to schema-driven rendering
        return render_schema_driven(artifact_type, data, json_path, schemas_dir, artifacts_dir, output_path)

    with open(template_file, "r") as f:
        template_str = f.read()

    if not HAS_JINJA2:
        print("Error: jinja2 is required but not installed.", file=sys.stderr)
        print("Install it with: pip install jinja2", file=sys.stderr)
        sys.exit(1)

    # Create Jinja2 environment with custom filters
    env = Environment(loader=FileSystemLoader(str(templates_dir)), trim_blocks=True, lstrip_blocks=True)
    env.filters['format_glossary_refs'] = format_glossary_refs
    env.filters['format_inputs'] = format_inputs
    env.filters['format_id_refs'] = format_id_refs
    env.filters['clean_flow_name'] = clean_flow_name
    env.filters['render_ia_tree'] = render_ia_tree
    env.filters['format_json'] = format_json

    template = env.from_string(template_str)

    # Prepare context: all top-level properties from the JSON data
    context = {
        "artifact_type": artifact_type,
        "status": data.get("status"),
        "updated": data.get("updated"),
    }
    for key, value in data.items():
        if key not in ("status", "updated", "version", "schemaVersion", "_meta"):
            context[key] = value

    return template.render(**context)


# ─── Schema-Driven Rendering (fallback) ───────────────────────────────────────

def render_schema_driven(artifact_type: str, data: dict, json_path: str,
                          schemas_dir: str, artifacts_dir: str,
                          output_path: Optional[str] = None) -> str:
    """Generate markdown from artifact JSON data using schema-driven rendering.
    
    Fallback when no Jinja2 template exists.
    """
    # Get schema info
    schema_name, md_name, artifact_name = ARTIFACT_TYPE_MAP[artifact_type]

    # Determine output path
    if output_path is None:
        output_path = os.path.join(artifacts_dir, md_name)

    # Load schema
    schema = load_schema(schemas_dir, schema_name)

    # Generate frontmatter
    frontmatter = generate_frontmatter(artifact_type, data, schema)

    # Generate body
    body = render_schema_properties(data, schema, artifact_type)

    return frontmatter + body


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def generate_artifact_markdown(artifact_type: str, data: dict, json_path: str,
                                schemas_dir: str, artifacts_dir: str,
                                output_path: Optional[str] = None) -> str:
    """Generate markdown from artifact JSON data."""
    # Try template rendering first, fall back to schema-driven
    return render_template(artifact_type, data, json_path, schemas_dir, artifacts_dir, output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Convert artifact JSON files to Markdown format."
    )
    parser.add_argument(
        "--type",
        required=True,
        choices=list(ARTIFACT_TYPE_MAP.keys()),
        help="Artifact type to convert",
    )
    parser.add_argument(
        "--json",
        required=True,
        help="Path to the JSON artifact file",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output markdown path (default: artifacts/<Type>.md)",
    )
    parser.add_argument(
        "--schemas-dir",
        default=None,
        help="Path to schemas directory (default: auto-detect)",
    )
    parser.add_argument(
        "--artifacts-dir",
        default=None,
        help="Path to artifacts directory (default: auto-detect)",
    )
    args = parser.parse_args()

    # Auto-detect paths
    script_dir = Path(__file__).resolve().parent
    if args.schemas_dir is None:
        schemas_dir = str(script_dir.parent.parent.parent / "skills" / "blueprint" / "schemas")
    else:
        schemas_dir = args.schemas_dir

    if args.artifacts_dir is None:
        artifacts_dir = str(Path(args.json).parent)
    else:
        artifacts_dir = args.artifacts_dir

    # Load JSON
    with open(args.json, "r") as f:
        data = json.load(f)

    # Generate markdown
    md_content = generate_artifact_markdown(
        args.type, data, args.json, schemas_dir, artifacts_dir, args.output
    )

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        schema_name = ARTIFACT_TYPE_MAP[args.type][0]
        md_name = SCHEMA_TO_MD[schema_name]
        output_path = os.path.join(artifacts_dir, md_name)

    # Write file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(md_content)

    print(f"Generated: {output_path}")
    print(f"  From: {args.json}")
    print(f"  Type: {args.type}")


if __name__ == "__main__":
    main()
