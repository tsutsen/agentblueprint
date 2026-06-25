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
    from jinja2 import Template
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

# ID pattern: WORD-NNN (e.g. REQ-001, NFR-002, US-003, FN-001, GL-001, EP-001)
# Also matches IDs with suffixes like REQ-001-initiate-research-session
ID_PATTERN = re.compile(r'^[A-Z]+-\d+(-[a-z]+)*$')


def fmt_id(text: str) -> str:
    """Italicize IDs (WORD-NNN pattern)."""
    if ID_PATTERN.match(text):
        return f"*{text}*"
    return text


def fmt_name(text: str) -> str:
    """Boldify names (first meaningful word/phrase)."""
    if text and len(text.strip()) > 0:
        return f"**{text.strip()}**"
    return text


def fmt_field(text: str) -> str:
    """Leave field names (with underscores) unformatted."""
    return text


# Artifact-specific title overrides (schema-derived titles look ugly)
TITLE_OVERRIDES = {
    "goal": "Goal Specification",
    "glossary": "Glossary",
    "design": "Design Specification",
    "arch": "Architecture Specification",
    "data": "Data Specification",
    "api": "API Specification",
    "test": "Test Specification",
    "plan": "Task Plan",
    "issue": None,  # Issues use IS-NNN: title format
}

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


def resolve_schema_path(schemas_dir: str, schema_name: str) -> str:
    """Resolve the path to a schema file."""
    return os.path.join(schemas_dir, schema_name)


def resolve_artifact_path(artifacts_dir: str, md_name: str) -> str:
    """Resolve the path to an artifact markdown file."""
    return os.path.join(artifacts_dir, md_name)


def load_schema(schemas_dir: str, schema_name: str) -> dict:
    """Load a JSON schema file."""
    schema_path = resolve_schema_path(schemas_dir, schema_name)
    with open(schema_path, "r") as f:
        return json.load(f)


def get_property_description(prop: dict) -> str:
    """Get the description of a property, falling back to a human-readable name."""
    if "description" in prop:
        return prop["description"]
    # Generate from name: snake_case to Title Case
    name = prop.get("name", "") or prop.get("$id", "")
    return name.replace("_", " ").title() if name else "Field"


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


def render_schema_properties(data: dict, schema: dict, artifact_type: str) -> str:
    """Render all properties from the schema that exist in the data."""
    lines = []
    properties = schema.get("properties", {})
    if not properties:
        # Fallback: render all top-level keys
        for key, value in data.items():
            if key in FRONTMATTER_SKIP or key.startswith("_"):
                continue
            rendered = render_simple_object(value) if isinstance(value, dict) else render_value(value)
            if rendered:
                # Use the key as a simple header, not the schema description
                label = key.replace("_", " ").title()
                lines.append(f"## {label}\n\n{rendered}\n")
        return "\n".join(lines)

    # Render in schema-defined order
    for prop_name, prop_def in properties.items():
        if prop_name not in data:
            continue

        # Skip metadata fields
        if prop_name in FRONTMATTER_SKIP:
            continue

        # Get the display name
        title = prop_def.get("title", "")
        if not title and "description" in prop_def:
            title = prop_def["description"]
        if not title:
            title = prop_name.replace("_", " ").title()

        value = data[prop_name]
        rendered = render_value(value, prop_schema=prop_def)

        if not rendered:
            continue

        # Format based on artifact type and property
        if artifact_type == "goal" and prop_name == "objective":
            lines.append("## Project Objective\n")
            if isinstance(value, dict) and "statement" in value:
                lines.append(value["statement"])
                lines.append("")
                if value.get("glossaryRefs"):
                    lines.append(f"glossaryRefs: {', '.join(f'`{r}`' for r in value['glossaryRefs'])}")
                    lines.append("")
            else:
                lines.append(rendered)
            lines.append("---\n")

        elif artifact_type == "goal" and prop_name == "functionalRequirements":
            lines.append("## Functional Requirements\n")
            for fr in value:
                id_ = fmt_id(fr.get("id", ""))
                description = fr.get("description", "")
                actor = fr.get("actor", "")
                glossary_refs = fr.get("glossaryRefs", [])
                line = f"- {id_}: {description}"
                if actor:
                    line += f" (Actor: {actor})"
                lines.append(line)
                if glossary_refs:
                    lines.append(f"  glossaryRefs: {', '.join(f'`{r}`' for r in glossary_refs)}")
            lines.append("")
            lines.append("---\n")

        elif artifact_type == "goal" and prop_name == "nonFunctionalRequirements":
            lines.append("## Non-Functional Requirements\n")
            for nfr in value:
                id_ = nfr.get("id", "")
                description = nfr.get("description", "")
                category = nfr.get("category", "")
                scale = nfr.get("scale", "")
                meter = nfr.get("meter", "")
                must = nfr.get("must", "")
                plan = nfr.get("plan", "")
                wish = nfr.get("wish", "")
                if description:
                    title_text = description
                elif scale:
                    title_text = scale
                else:
                    title_text = category
                lines.append(f"### {fmt_id(id_)} — {title_text}")
                lines.append(f"Category: {category}")
                lines.append("")
                lines.append(f"Scale: {scale}")
                lines.append("")
                lines.append(f"Meter: {meter}")
                lines.append("")
                lines.append(f"Must: {must}")
                if plan:
                    lines.append("")
                    lines.append(f"Plan: {plan}")
                if wish:
                    lines.append("")
                    lines.append(f"Wish: {wish}")
                lines.append("")
            lines.append("---\n")

        elif artifact_type == "goal" and prop_name == "userStories":
            lines.append("## User Stories\n")
            for us in value:
                id_ = fmt_id(us.get("id", ""))
                actor = us.get("actor", "")
                capability = us.get("capability", "")
                outcome = us.get("outcome", "")
                req_refs = us.get("reqRefs", [])
                if capability.strip().startswith("As a"):
                    lines.append(f"- {id_}: {capability}, so that {outcome}.")
                else:
                    lines.append(f"- {id_}: As a {actor}, I want to {capability}, so that {outcome}.")
                if req_refs:
                    lines.append(f"  → {', '.join(req_refs)}")
                if us.get("glossaryRefs"):
                    lines.append(f"  glossaryRefs: {', '.join(f'`{r}`' for r in us['glossaryRefs'])}")
            lines.append("")
            lines.append("---\n")

        elif artifact_type == "goal" and prop_name == "successCriteria":
            lines.append("## Success Criteria\n")
            for sc in value:
                id_ = fmt_id(sc.get("id", ""))
                description = sc.get("description", "")
                verification = sc.get("verificationMethod", "")
                refs = sc.get("refs", {})
                line = f"- {id_}: {description}"
                if verification:
                    line += f" (Verification: {verification})"
                lines.append(line)
                if refs.get("reqRefs"):
                    lines.append(f"  → {', '.join(refs['reqRefs'])}")
                if refs.get("nfrRefs"):
                    lines.append(f"  → {', '.join(refs['nfrRefs'])}")
            lines.append("")
            lines.append("---\n")

        elif artifact_type == "goal" and prop_name == "nonGoals":
            lines.append("## Non-Goals\n")
            for ng in value:
                capability = fmt_name(ng.get("capability", ""))
                reason = ng.get("reason", "")
                line = f"- {capability} — {reason}"
                if ng.get("glossaryRefs"):
                    line += f" (glossaryRefs: {', '.join(f'`{r}`' for r in ng['glossaryRefs'])})"
                lines.append(line)
            lines.append("")

        elif artifact_type == "glossary" and prop_name == "terms":
            lines.append("## Terms\n")
            for term in value:
                # Schema says term/definition, but JSON uses name/description as synonyms
                term_name = term.get("term", term.get("name", ""))
                definition = term.get("definition", term.get("description", ""))
                examples = term.get("examples", [])
                synonyms = term.get("synonyms", [])
                related = term.get("relatedTerms", [])
                category = term.get("category", "")
                id_ = term.get("id", "")
                lines.append(f"### {fmt_id(id_)}: {fmt_name(term_name)}\n")
                lines.append(definition)
                lines.append("")
                if synonyms:
                    lines.append(f"Synonyms: {', '.join(synonyms)}")
                    lines.append("")
                if examples:
                    lines.append("Examples:")
                    for ex in examples:
                        lines.append(f"- {ex}")
                    lines.append("")
                if related:
                    lines.append(f"Related: {', '.join(related)}")
                    lines.append("")
                if category:
                    lines.append(f"Category: {category}")
                    lines.append("")
                lines.append("---\n")

        elif artifact_type == "data" and prop_name == "entities":
            lines.append("## Entities\n")
            for entity in value:
                name = entity.get("name", "")
                desc = entity.get("description", "")
                abstract = entity.get("abstract", False)
                extends = entity.get("extends", "")
                visibility = entity.get("visibility", "public")
                fields = entity.get("fields", [])
                methods = entity.get("methods", [])
                lines.append(f"### {fmt_name(name)}\n")
                if desc:
                    lines.append(desc)
                    lines.append("")
                if abstract:
                    lines.append("*Abstract entity*")
                    lines.append("")
                if extends:
                    lines.append(f"*Extends: {extends}*")
                    lines.append("")
                if visibility != "public":
                    lines.append(f"*Visibility: {visibility}*")
                    lines.append("")
                if fields:
                    lines.append("| Field | Type | Required | Description |")
                    lines.append("|-------|------|----------|-------------|")
                    for field in fields:
                        fname = field.get("name", "")
                        ftype = field.get("type", "")
                        required = field.get("required", True)
                        fdesc = field.get("description", "")
                        pk = field.get("primaryKey", False)
                        example = field.get("example", "")
                        if pk:
                            fname += " *"
                        if example:
                            fdesc += f" (e.g. `{example}`)"
                        lines.append(f"| `{fname}` | `{ftype}` | {'Yes' if required else 'No'} | {fdesc} |")
                    lines.append("")
                if methods:
                    lines.append("Methods:\n")
                    for method in methods:
                        mname = fmt_name(method.get("name", ""))
                        api_ref = fmt_id(method.get("apiRef", ""))
                        mdesc = method.get("description", "")
                        lines.append(f"- `{mname}` → `{api_ref}` — {mdesc}")
                    lines.append("")

        elif artifact_type == "data" and prop_name == "relationships":
            lines.append("## Relationships\n")
            for rel in value:
                from_ = rel.get("from", "")
                to = rel.get("to", "")
                rel_type = rel.get("type", "")
                label = rel.get("label", "")
                cardinality = rel.get("cardinality", {})
                desc = rel.get("description", "")
                from_label = cardinality.get("fromLabel", "1")
                to_label = cardinality.get("toLabel", "1")
                type_icons = {
                    "composition": "◆—",
                    "aggregation": "◇—",
                    "association": "→",
                    "dependency": "- - →",
                    "realization": "--|>",
                }
                icon = type_icons.get(rel_type, "→")
                line = f"- {from_} ({from_label}) {icon} ({to_label}) {to}"
                if label:
                    line += f" (*{label}*)"
                lines.append(line)
                if desc:
                    lines.append(f"  {desc}")
            lines.append("")

        elif artifact_type == "data" and prop_name == "enums":
            lines.append("## Enumerated Types\n")
            for enum in value:
                name = fmt_name(enum.get("name", ""))
                values = enum.get("values", [])
                lines.append(f"### {name}\n")
                for val in values:
                    vname = val.get("name", "")
                    vdesc = val.get("description", "")
                    if vdesc:
                        lines.append(f"- `{vname}` — {vdesc}")
                    else:
                        lines.append(f"- `{vname}`")
                lines.append("")

        elif artifact_type == "arch" and prop_name == "components":
            lines.append("## Components\n")
            subsystems = {}
            for comp in value:
                subsystem = comp.get("subsystem", "Default")
                if subsystem not in subsystems:
                    subsystems[subsystem] = []
                subsystems[subsystem].append(comp)
            for subsystem_name, comps in subsystems.items():
                lines.append(f"### {subsystem_name}\n")
                for comp in comps:
                    name = comp.get("name", "")
                    purpose = comp.get("purpose", "")
                    deps = comp.get("dependencies", [])
                    req_refs = comp.get("reqRefs", [])
                    nfr_refs = comp.get("nfrRefs", [])
                    visibility = comp.get("visibility", "internal")
                    lines.append(f"#### {name}\n")
                    if purpose:
                        lines.append(purpose)
                        lines.append("")
                    if deps:
                        lines.append(f"*Dependencies:* {', '.join(deps)}")
                        lines.append("")
                    if req_refs:
                        lines.append(f"*REQ refs:* {', '.join(req_refs)}")
                        lines.append("")
                    if nfr_refs:
                        lines.append(f"*NFR refs:* {', '.join(nfr_refs)}")
                        lines.append("")
                    lines.append(f"Visibility: {visibility}")
                    lines.append("")

        elif artifact_type == "arch" and prop_name == "dataFlows":
            lines.append("## Data Flows\n")
            for flow in value:
                name = flow.get("name", "")
                desc = flow.get("description", "")
                steps = flow.get("steps", [])
                lines.append(f"### {name}\n")
                if desc:
                    lines.append(desc)
                    lines.append("")
                for i, step in enumerate(steps, 1):
                    component = step.get("component", "")
                    action = step.get("action", "")
                    data_ = step.get("data", "")
                    lines.append(f"{i}. {component}: {action}")
                    if data_:
                        lines.append(f"   Data: {data_}")
                lines.append("")

        elif artifact_type == "arch" and prop_name == "constraints":
            lines.append("## Constraints\n")
            for constraint in value:
                id_ = constraint.get("id", "")
                description = constraint.get("description", "")
                nfr_refs = constraint.get("nfrRefs", [])
                lines.append(f"### {id_}\n")
                lines.append(description)
                if nfr_refs:
                    lines.append(f"*NFR refs:* {', '.join(nfr_refs)}")
                lines.append("")

        elif artifact_type == "design" and prop_name == "designGoals":
            lines.append("## Design Goals\n")
            for goal in value:
                id_ = goal.get("id", "")
                description = goal.get("description", "")
                lines.append(f"- {id_}: {description}")
            lines.append("")

        elif artifact_type == "design" and prop_name == "userPersonas":
            lines.append("## User Personas\n")
            for persona in value:
                name = persona.get("name", "")
                role = persona.get("role", "")
                goals_p = persona.get("goals", [])
                pain_points = persona.get("painPoints", [])
                lines.append(f"### {name}\n")
                lines.append(f"*Role:* {role}\n")
                if goals_p:
                    lines.append("Goals:\n")
                    for g in goals_p:
                        lines.append(f"- {g}")
                    lines.append("")
                if pain_points:
                    lines.append("Pain Points:\n")
                    for p in pain_points:
                        lines.append(f"- {p}")
                    lines.append("")

        elif artifact_type == "design" and prop_name == "userJourneys":
            lines.append("## User Journeys\n")
            for journey in value:
                name = journey.get("name", "")
                steps = journey.get("steps", [])
                persona = journey.get("persona", "")
                us_refs = journey.get("usRefs", [])
                lines.append(f"### {name}\n")
                if persona:
                    lines.append(f"*Persona:* {persona}")
                if us_refs:
                    lines.append(f"*Refs:* {', '.join(us_refs)}")
                lines.append("")
                for i, step in enumerate(steps, 1):
                    actor = step.get("actor", "")
                    action = step.get("action", "")
                    lines.append(f"{i}. {actor}: {action}")
                lines.append("")

        elif artifact_type == "design" and prop_name == "screenInventory":
            lines.append("## Screen Inventory\n")
            for screen in value:
                id_ = screen.get("id", "")
                name = screen.get("name", "")
                purpose = screen.get("purpose", "")
                actions = screen.get("primaryActions", [])
                lines.append(f"### {name} (`{id_}`)\n")
                if purpose:
                    lines.append(purpose)
                    lines.append("")
                if actions:
                    lines.append("Primary Actions:\n")
                    for a in actions:
                        lines.append(f"- {a}")
                    lines.append("")

        elif artifact_type == "api" and prop_name == "functions":
            lines.append("## Functions\n")
            for func in value:
                id_ = func.get("id", "")
                name = func.get("name", "")
                description = func.get("description", "")
                entity = func.get("entity", "")
                inputs = func.get("inputs", [])
                output = func.get("output", {})
                errors = func.get("errors", [])
                pure = func.get("pure", False)
                visibility = func.get("visibility", "public")
                lines.append(f"### {id_}: {name}\n")
                if description:
                    lines.append(description)
                    lines.append("")
                if entity:
                    lines.append(f"Entity: {entity}\n")
                if inputs:
                    lines.append("Inputs:\n")
                    for inp in inputs:
                        iname = inp.get("name", "")
                        itype = inp.get("type", "")
                        required = inp.get("required", True)
                        idesc = inp.get("description", "")
                        example = inp.get("example", "")
                        req_str = " (required)" if required else ""
                        example_str = f" (e.g. `{example}`)" if example else ""
                        lines.append(f"- `{iname}` ({itype}){req_str}: {idesc}{example_str}")
                    lines.append("")
                if output:
                    otype = output.get("type", "")
                    odesc = output.get("description", "")
                    lines.append(f"Output: `{otype}` — {odesc}\n")
                if errors:
                    lines.append("Errors:\n")
                    for err in errors:
                        code = err.get("code", "")
                        condition = err.get("condition", "")
                        return_type = err.get("returnType", "")
                        lines.append(f"- `{code}`: {condition} (returns `{return_type}`)")
                    lines.append("")
                lines.append(f"Pure: {pure} | Visibility: {visibility}\n")

        elif artifact_type == "test" and prop_name == "functionCoverage":
            lines.append("## Function Coverage\n")
            for func in value:
                fn_ref = func.get("fnRef", "")
                description = func.get("description", "")
                tests = func.get("tests", [])
                out_of_scope = func.get("outOfScope", [])
                lines.append(f"### {fn_ref}\n")
                if description:
                    lines.append(description)
                    lines.append("")
                happy = [t for t in tests if t.get("category") == "happy"]
                if happy:
                    lines.append("Happy Path:\n")
                    for test in happy:
                        id_ = test.get("id", "")
                        desc = test.get("description", "")
                        lines.append(f"- {id_}: {desc}")
                    lines.append("")
                edge = [t for t in tests if t.get("category") == "edge"]
                if edge:
                    lines.append("Edge Cases:\n")
                    for test in edge:
                        id_ = test.get("id", "")
                        desc = test.get("description", "")
                        lines.append(f"- {id_}: {desc}")
                    lines.append("")
                errors = [t for t in tests if t.get("category") == "error"]
                if errors:
                    lines.append("Error Paths:\n")
                    for test in errors:
                        id_ = test.get("id", "")
                        desc = test.get("description", "")
                        error_code = test.get("errorCode", "")
                        lines.append(f"- {id_}: {desc} (Error: {error_code})")
                    lines.append("")
                if out_of_scope:
                    lines.append("Out of Scope:\n")
                    for item in out_of_scope:
                        desc = item.get("description", "") if isinstance(item, dict) else item
                        lines.append(f"- {desc}")
                    lines.append("")

        elif artifact_type == "plan" and prop_name == "milestones":
            lines.append("## Milestones\n")
            for ms in value:
                id_ = ms.get("id", "")
                name = ms.get("name", "")
                outcome = ms.get("outcome", "")
                epics = ms.get("epics", [])
                lines.append(f"### {id_}: {name}\n")
                lines.append(outcome)
                lines.append("")
                lines.append(f"*Epics:* {', '.join(epics)}")
                lines.append("")

        elif artifact_type == "plan" and prop_name == "epics":
            lines.append("## Epics\n")
            for epic in value:
                id_ = epic.get("id", "")
                title = epic.get("title", "")
                milestone = epic.get("milestone", "")
                requirements = epic.get("requirements", [])
                summary = epic.get("summary", "")
                objective = epic.get("objective", "")
                scope = epic.get("scope", {})
                acceptance = epic.get("acceptanceCriteria", [])
                deps = epic.get("dependencies", {})
                lines.append(f"### {id_}: {title}\n")
                if objective:
                    lines.append(objective)
                    lines.append("")
                if summary:
                    lines.append(f"*{summary}*\n")
                lines.append(f"*Milestone:* {milestone}")
                if requirements:
                    lines.append(f"*Requirements:* {', '.join(requirements)}")
                if deps:
                    blocked_by = deps.get("blockedBy", [])
                    blocks = deps.get("blocks", [])
                    if blocked_by:
                        lines.append(f"*Blocked by:* {', '.join(blocked_by)}")
                    if blocks:
                        lines.append(f"*Blocks:* {', '.join(blocks)}")
                lines.append("")
                if scope:
                    in_scope = scope.get("inScope", [])
                    out_of_scope = scope.get("outOfScope", [])
                    if in_scope:
                        lines.append("In Scope:\n")
                        for item in in_scope:
                            lines.append(f"- {item}")
                        lines.append("")
                    if out_of_scope:
                        lines.append("Out of Scope:\n")
                        for item in out_of_scope:
                            lines.append(f"- {item}")
                        lines.append("")
                if acceptance:
                    lines.append("Acceptance Criteria:\n")
                    for ac in acceptance:
                        lines.append(f"- [ ] {ac}")
                    lines.append("")

        elif artifact_type == "issue" and prop_name == "inScope":
            lines.append("## In Scope\n")
            for item in value:
                desc = item.get("description", "") if isinstance(item, dict) else item
                lines.append(f"- {desc}")
            lines.append("")

        elif artifact_type == "issue" and prop_name == "outOfScope":
            lines.append("## Out of Scope\n")
            for item in value:
                desc = item.get("description", "") if isinstance(item, dict) else item
                lines.append(f"- {desc}")
            lines.append("")

        elif artifact_type == "issue" and prop_name == "acceptanceCriteria":
            lines.append("## Acceptance Criteria\n")
            for ac in value:
                desc = ac.get("description", "") if isinstance(ac, dict) else ac
                lines.append(f"- [ ] {desc}")
            lines.append("")

        elif artifact_type == "issue" and prop_name == "blocked_by":
            lines.append("## Blocked By\n")
            lines.append(", ".join(value))
            lines.append("")

        else:
            # Generic rendering — use the property name, not the schema description
            lines.append(f"## {prop_name.replace('_', ' ').title()}\n")
            lines.append(rendered)
            lines.append("")

    return "\n".join(lines)


def render_template(artifact_type: str, data: dict, json_path: str,
                     schemas_dir: str, artifacts_dir: str,
                     output_path: Optional[str] = None) -> str:
    """Generate markdown from artifact JSON data using Jinja2 templates."""
    script_dir = Path(__file__).resolve().parent
    templates_dir = script_dir / "templates"

    template_file = templates_dir / f"{artifact_type}.md.j2"
    print(f"DEBUG: template_file={template_file}, exists={template_file.exists()}")
    if not template_file.exists():
        # Fall back to schema-driven rendering
        print(f"DEBUG: Falling back to schema-driven rendering")
        return render_schema_driven(artifact_type, data, json_path, schemas_dir, artifacts_dir, output_path)

    with open(template_file, "r") as f:
        template_str = f.read()

    # Create template with custom filters
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(str(templates_dir)), trim_blocks=True, lstrip_blocks=True)
    
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
    
    env.filters['format_glossary_refs'] = format_glossary_refs
    env.filters['format_inputs'] = format_inputs

    def format_json(obj):
        """Format an object as compact JSON."""
        return json.dumps(obj, ensure_ascii=False)

    def format_id_refs(text):
        """Wrap all ID references in backticks: REQ-001, NFR-002, TST-003, FN-063, GL-008, etc."""
        import re
        return re.sub(r'\b([A-Z]{1,4}-\d{3,})\b', r'`\1`', str(text))

    env.filters['format_json'] = format_json
    env.filters['format_id_refs'] = format_id_refs
    template = env.from_string(template_str)

    # Prepare context for template
    context = {
        "artifact_type": artifact_type,
        "status": data.get("status"),
        "updated": data.get("updated"),
    }

    # Add all top-level properties from the JSON data
    for key, value in data.items():
        if key not in ("status", "updated", "version", "schemaVersion", "_meta"):
            context[key] = value

    return template.render(**context)


def render_schema_driven(artifact_type: str, data: dict, json_path: str,
                          schemas_dir: str, artifacts_dir: str,
                          output_path: Optional[str] = None) -> str:
    """Generate markdown from artifact JSON data using schema-driven rendering."""
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
        help="Path to schemas/json directory (default: auto-detect)",
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
        schemas_dir = str(script_dir.parent.parent.parent / "skills" / "blueprint" / "schemas" / "json")
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
