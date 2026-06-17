#!/usr/bin/env python3
"""
generate_artifact_markdown.py — Convert artifact JSON files to Markdown format.

Reads an artifact's JSON file and generates the corresponding Markdown file
using the schema as a template. This is the inverse of dual_output:
instead of validating JSON→MD, it generates MD from JSON.

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
    "issue": ("issue.schema.json", "Issue", None),  # Issues have individual files
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
    "issue.schema.json": None,  # Issues use IS-NNN.md
}


def resolve_schema_path(schemas_dir: str, schema_name: str) -> str:
    """Resolve the path to a schema file."""
    return os.path.join(schemas_dir, schema_name)


def resolve_artifact_path(artifacts_dir: str, md_name: str) -> str:
    """Resolve the path to an artifact markdown file."""
    return os.path.join(artifacts_dir, md_name)


def generate_frontmatter(artifact_type: str, data: dict, json_path: str) -> str:
    """Generate YAML frontmatter for the markdown file."""
    lines = ["---"]

    # artifact name
    lines.append(f"artifact: {ARTIFACT_TYPE_MAP[artifact_type][2]}")

    # status
    if "status" in data:
        lines.append(f"status: {data['status']}")

    # sections_complete / sections_pending
    if artifact_type == "goal":
        sections = []
        pending = []
        if data.get("objective"):
            sections.append("Project Objective")
        if data.get("functionalRequirements"):
            sections.append("Functional Requirements")
        if data.get("nonFunctionalRequirements"):
            sections.append("Non-Functional Requirements")
        if data.get("userStories"):
            sections.append("User Stories")
        if data.get("successCriteria"):
            sections.append("Success Criteria")
        if data.get("nonGoals"):
            sections.append("Non-Goals")
        # Check for empty sections
        if not data.get("objective", {}).get("statement", "").strip():
            pending.append("Project Objective")
        if not data.get("functionalRequirements"):
            pending.append("Functional Requirements")
        if not data.get("nonFunctionalRequirements"):
            pending.append("Non-Functional Requirements")
        if not data.get("userStories"):
            pending.append("User Stories")
        if not data.get("successCriteria"):
            pending.append("Success Criteria")
        if not data.get("nonGoals"):
            pending.append("Non-Goals")

        if sections:
            lines.append("sections_complete:")
            for s in sections:
                lines.append(f"  - {s}")
        if pending:
            lines.append("sections_pending:")
            for s in pending:
                lines.append(f"  - {s}")

    elif artifact_type == "glossary":
        if data.get("terms"):
            lines.append("sections_complete:")
            lines.append("  - Terms")
        else:
            lines.append("sections_pending:")
            lines.append("  - Terms")

    elif artifact_type == "issue":
        if "id" in data:
            lines.append(f"id: {data['id']}")
        if "title" in data:
            lines.append(f"title: {data['title']}")
        if "type" in data:
            lines.append(f"type: {data['type']}")
        if "status" in data:
            lines.append(f"status: {data['status']}")
        if "epic" in data:
            lines.append(f"epic: {data['epic']}")
        if "blocked_by" in data:
            lines.append("blocked_by:")
            for b in data["blocked_by"]:
                lines.append(f"  - {b}")
        if "milestone" in data:
            lines.append(f"milestone: {data['milestone']}")
        if "titleGlossaryRefs" in data and data["titleGlossaryRefs"]:
            lines.append("titleGlossaryRefs:")
            for r in data["titleGlossaryRefs"]:
                lines.append(f"  - {r}")
        if "inScope" in data and data["inScope"]:
            lines.append("inScope:")
            for item in data["inScope"]:
                lines.append(f"  - description: \"{item.get('description', '')}\"")
                if item.get("glossaryRefs"):
                    lines.append("    glossaryRefs:")
                    for r in item["glossaryRefs"]:
                        lines.append(f"      - {r}")
        if "outOfScope" in data and data["outOfScope"]:
            lines.append("outOfScope:")
            for item in data["outOfScope"]:
                lines.append(f"  - description: \"{item.get('description', '')}\"")
                if item.get("glossaryRefs"):
                    lines.append("    glossaryRefs:")
                    for r in item["glossaryRefs"]:
                        lines.append(f"      - {r}")
        if "acceptanceCriteria" in data and data["acceptanceCriteria"]:
            lines.append("acceptanceCriteria:")
            for item in data["acceptanceCriteria"]:
                lines.append(f"  - description: \"{item.get('description', '')}\"")
                if item.get("glossaryRefs"):
                    lines.append("    glossaryRefs:")
                    for r in item["glossaryRefs"]:
                        lines.append(f"      - {r}")
        if "created" in data:
            lines.append(f"created: {data['created']}")
        if "updated" in data:
            lines.append(f"updated: {data['updated']}")

    # updated date
    if "updated" in data:
        lines.append(f"updated: {data['updated']}")
    elif "created" in data:
        lines.append(f"updated: {data['created']}")

    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def generate_goal_spec_md(data: dict) -> str:
    """Generate GoalSpec markdown from JSON data."""
    lines = []

    # Title
    lines.append("# Goal Specification")
    lines.append("")

    # Project Objective
    lines.append("## Project Objective")
    lines.append("")
    obj = data.get("objective", {})
    statement = obj.get("statement", "")
    for_actor = obj.get("for", "")
    problem = obj.get("problem", "")

    if statement:
        lines.append(statement)
        lines.append("")

    # Glossary refs
    if obj.get("glossaryRefs"):
        lines.append(f"**glossaryRefs:** {', '.join(f'`{r}`' for r in obj['glossaryRefs'])}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Functional Requirements
    lines.append("## Functional Requirements")
    lines.append("")
    for fr in data.get("functionalRequirements", []):
        id_ = fr.get("id", "")
        description = fr.get("description", "")
        actor = fr.get("actor", "")
        glossary_refs = fr.get("glossaryRefs", [])

        line = f"- **{id_}**: {description}"
        if actor:
            line += f" *(Actor: {actor})*"
        lines.append(line)

        if glossary_refs:
            lines.append(f"  **glossaryRefs:** {', '.join(f'`{r}`' for r in glossary_refs)}")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Non-Functional Requirements
    lines.append("## Non-Functional Requirements")
    lines.append("")
    for nfr in data.get("nonFunctionalRequirements", []):
        id_ = nfr.get("id", "")
        category = nfr.get("category", "")
        scale = nfr.get("scale", "")
        meter = nfr.get("meter", "")
        must = nfr.get("must", "")
        plan = nfr.get("plan", "")
        wish = nfr.get("wish", "")

        lines.append(f"### {id_} — {category}")
        lines.append(f"Category: {category}")
        lines.append(f"Scale: {scale}")
        lines.append(f"Meter: {meter}")
        lines.append(f"Must: {must}")
        if plan:
            lines.append(f"Plan: {plan}")
        if wish:
            lines.append(f"Wish: {wish}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # User Stories
    lines.append("## User Stories")
    lines.append("")
    for us in data.get("userStories", []):
        id_ = us.get("id", "")
        actor = us.get("actor", "")
        capability = us.get("capability", "")
        outcome = us.get("outcome", "")
        req_refs = us.get("reqRefs", [])

        lines.append(f"- **{id_}**: As a {actor}, I want to {capability}, so that {outcome}.")
        if req_refs:
            lines.append(f"  → {', '.join(req_refs)}")
        if us.get("glossaryRefs"):
            lines.append(f"  **glossaryRefs:** {', '.join(f'`{r}`' for r in us['glossaryRefs'])}")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Success Criteria
    lines.append("## Success Criteria")
    lines.append("")
    for sc in data.get("successCriteria", []):
        id_ = sc.get("id", "")
        description = sc.get("description", "")
        refs = sc.get("refs", {})
        verification = sc.get("verificationMethod", "")

        line = f"- **{id_}**: {description}"
        if verification:
            line += f" *(Verification: {verification})*"
        lines.append(line)
        if refs.get("reqRefs"):
            lines.append(f"  → {', '.join(refs['reqRefs'])}")
        if refs.get("nfrRefs"):
            lines.append(f"  → {', '.join(refs['nfrRefs'])}")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Non-Goals
    lines.append("## Non-Goals")
    lines.append("")
    for ng in data.get("nonGoals", []):
        capability = ng.get("capability", "")
        reason = ng.get("reason", "")
        line = f"- **{capability}** — {reason}"
        if ng.get("glossaryRefs"):
            line += f" *(glossaryRefs: {', '.join(f'`{r}`' for r in ng['glossaryRefs'])})*"
        lines.append(line)

    lines.append("")

    return "\n".join(lines)


def generate_glossary_md(data: dict) -> str:
    """Generate Glossary markdown from JSON data."""
    lines = ["# Glossary", ""]

    for term in data.get("terms", []):
        term_name = term.get("term", "")
        definition = term.get("definition", "")
        examples = term.get("examples", [])
        synonyms = term.get("synonyms", [])
        related = term.get("relatedTerms", [])
        category = term.get("category", "")
        id_ = term.get("id", "")

        lines.append(f"### {id_}: {term_name}")
        lines.append("")
        lines.append(definition)
        lines.append("")

        if synonyms:
            lines.append(f"**Synonyms:** {', '.join(synonyms)}")
            lines.append("")

        if examples:
            lines.append("**Examples:**")
            for ex in examples:
                lines.append(f"- {ex}")
            lines.append("")

        if related:
            lines.append(f"**Related:** {', '.join(related)}")
            lines.append("")

        if category:
            lines.append(f"**Category:** {category}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def generate_data_spec_md(data: dict) -> str:
    """Generate DataSpec markdown from JSON data."""
    lines = ["# Data Specification", ""]

    if data.get("description"):
        lines.append(data["description"])
        lines.append("")

    lines.append(f"**Module:** {data.get('module', '')}")
    lines.append(f"**Version:** {data.get('version', '')}")
    lines.append("")

    # Enums
    if data.get("enums"):
        lines.append("## Enumerated Types")
        lines.append("")
        for enum in data["enums"]:
            name = enum.get("name", "")
            values = enum.get("values", [])
            lines.append(f"### {name}")
            lines.append("")
            for val in values:
                vname = val.get("name", "")
                vdesc = val.get("description", "")
                if vdesc:
                    lines.append(f"- `{vname}` — {vdesc}")
                else:
                    lines.append(f"- `{vname}`")
            lines.append("")

    # Entities
    if data.get("entities"):
        lines.append("## Entities")
        lines.append("")
        for entity in data["entities"]:
            name = entity.get("name", "")
            desc = entity.get("description", "")
            abstract = entity.get("abstract", False)
            extends = entity.get("extends", "")
            visibility = entity.get("visibility", "public")
            fields = entity.get("fields", [])
            methods = entity.get("methods", [])

            lines.append(f"### {name}")
            lines.append("")
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

            # Fields
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

            # Methods
            if methods:
                lines.append("**Methods:**")
                lines.append("")
                for method in methods:
                    mname = method.get("name", "")
                    api_ref = method.get("apiRef", "")
                    mdesc = method.get("description", "")
                    lines.append(f"- `{mname}` → `{api_ref}` — {mdesc}")
                lines.append("")

    # Relationships
    if data.get("relationships"):
        lines.append("## Relationships")
        lines.append("")
        for rel in data["relationships"]:
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

            line = f"- **{from_}** ({from_label}) {icon} ({to_label}) **{to}**"
            if label:
                line += f" (*{label}*)"
            lines.append(line)
            if desc:
                lines.append(f"  {desc}")

        lines.append("")

    return "\n".join(lines)


def generate_architecture_spec_md(data: dict) -> str:
    """Generate ArchitectureSpec markdown from JSON data."""
    lines = ["# Architecture Specification", ""]

    if data.get("description"):
        lines.append(data["description"])
        lines.append("")

    # Components
    components = data.get("components", [])
    if components:
        lines.append("## Components")
        lines.append("")

        # Group by subsystem
        subsystems = {}
        for comp in components:
            subsystem = comp.get("subsystem", "Default")
            if subsystem not in subsystems:
                subsystems[subsystem] = []
            subsystems[subsystem].append(comp)

        for subsystem_name, comps in subsystems.items():
            lines.append(f"### {subsystem_name}")
            lines.append("")
            for comp in comps:
                name = comp.get("name", "")
                purpose = comp.get("purpose", "")
                deps = comp.get("dependencies", [])
                req_refs = comp.get("reqRefs", [])
                nfr_refs = comp.get("nfrRefs", [])
                visibility = comp.get("visibility", "internal")

                lines.append(f"#### {name}")
                lines.append("")
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
                lines.append(f"*Visibility:* {visibility}")
                lines.append("")

    # Data Flows
    flows = data.get("dataFlows", [])
    if flows:
        lines.append("## Data Flows")
        lines.append("")
        for flow in flows:
            name = flow.get("name", "")
            desc = flow.get("description", "")
            steps = flow.get("steps", [])

            lines.append(f"### {name}")
            lines.append("")
            if desc:
                lines.append(desc)
                lines.append("")

            for i, step in enumerate(steps, 1):
                component = step.get("component", "")
                action = step.get("action", "")
                data_ = step.get("data", "")
                lines.append(f"{i}. **{component}**: {action}")
                if data_:
                    lines.append(f"   Data: {data_}")

            lines.append("")

    # Constraints
    constraints = data.get("constraints", [])
    if constraints:
        lines.append("## Constraints")
        lines.append("")
        for constraint in constraints:
            id_ = constraint.get("id", "")
            description = constraint.get("description", "")
            nfr_refs = constraint.get("nfrRefs", [])

            lines.append(f"### {id_}")
            lines.append("")
            lines.append(description)
            if nfr_refs:
                lines.append(f"*NFR refs:* {', '.join(nfr_refs)}")
            lines.append("")

    return "\n".join(lines)


def generate_design_spec_md(data: dict) -> str:
    """Generate DesignSpec markdown from JSON data."""
    lines = ["# Design Specification", ""]

    # Design Goals
    goals = data.get("designGoals", [])
    if goals:
        lines.append("## Design Goals")
        lines.append("")
        for goal in goals:
            id_ = goal.get("id", "")
            description = goal.get("description", "")
            lines.append(f"- **{id_}**: {description}")
        lines.append("")

    # User Personas
    personas = data.get("userPersonas", [])
    if personas:
        lines.append("## User Personas")
        lines.append("")
        for persona in personas:
            name = persona.get("name", "")
            role = persona.get("role", "")
            goals_p = persona.get("goals", [])
            pain_points = persona.get("painPoints", [])

            lines.append(f"### {name}")
            lines.append("")
            lines.append(f"*Role:* {role}")
            lines.append("")
            if goals_p:
                lines.append("**Goals:**")
                for g in goals_p:
                    lines.append(f"- {g}")
                lines.append("")
            if pain_points:
                lines.append("**Pain Points:**")
                for p in pain_points:
                    lines.append(f"- {p}")
                lines.append("")

    # User Journeys
    journeys = data.get("userJourneys", [])
    if journeys:
        lines.append("## User Journeys")
        lines.append("")
        for journey in journeys:
            name = journey.get("name", "")
            steps = journey.get("steps", [])
            persona = journey.get("persona", "")
            us_refs = journey.get("usRefs", [])

            lines.append(f"### {name}")
            lines.append("")
            if persona:
                lines.append(f"*Persona:* {persona}")
            if us_refs:
                lines.append(f"*Refs:* {', '.join(us_refs)}")
            lines.append("")

            for i, step in enumerate(steps, 1):
                actor = step.get("actor", "")
                action = step.get("action", "")
                lines.append(f"{i}. **{actor}**: {action}")
            lines.append("")

    # Screen Inventory
    screens = data.get("screenInventory", [])
    if screens:
        lines.append("## Screen Inventory")
        lines.append("")
        for screen in screens:
            id_ = screen.get("id", "")
            name = screen.get("name", "")
            purpose = screen.get("purpose", "")
            actions = screen.get("primaryActions", [])

            lines.append(f"### {name} (`{id_}`)")
            lines.append("")
            if purpose:
                lines.append(purpose)
                lines.append("")
            if actions:
                lines.append("**Primary Actions:**")
                for a in actions:
                    lines.append(f"- {a}")
                lines.append("")

    return "\n".join(lines)


def generate_api_spec_md(data: dict) -> str:
    """Generate ApiSpec markdown from JSON data."""
    lines = ["# API Specification", ""]

    lines.append(f"**Module:** {data.get('module', '')}")
    if data.get("description"):
        lines.append(data["description"])
        lines.append("")

    functions = data.get("functions", [])
    if functions:
        lines.append("## Functions")
        lines.append("")

        for func in functions:
            id_ = func.get("id", "")
            name = func.get("name", "")
            description = func.get("description", "")
            entity = func.get("entity", "")
            inputs = func.get("inputs", [])
            output = func.get("output", {})
            errors = func.get("errors", [])
            pure = func.get("pure", False)
            visibility = func.get("visibility", "public")

            lines.append(f"### {id_}: {name}")
            lines.append("")
            if description:
                lines.append(description)
                lines.append("")

            if entity:
                lines.append(f"*Entity:* {entity}")
                lines.append("")

            if inputs:
                lines.append("**Inputs:**")
                lines.append("")
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
                lines.append(f"**Output:** `{otype}` — {odesc}")
                lines.append("")

            if errors:
                lines.append("**Errors:**")
                lines.append("")
                for err in errors:
                    code = err.get("code", "")
                    condition = err.get("condition", "")
                    return_type = err.get("returnType", "")
                    lines.append(f"- `{code}`: {condition} (returns `{return_type}`)")
                lines.append("")

            lines.append(f"*Pure:* {pure} | *Visibility:* {visibility}")
            lines.append("")

    return "\n".join(lines)


def generate_test_spec_md(data: dict) -> str:
    """Generate TestSpec markdown from JSON data."""
    lines = ["# Test Specification", ""]

    api_version = data.get("apiSpecVersion", "")
    if api_version:
        lines.append(f"**ApiSpec Version:** {api_version}")
        lines.append("")

    # Function Coverage
    coverage = data.get("functionCoverage", [])
    if coverage:
        lines.append("## Function Coverage")
        lines.append("")
        for func in coverage:
            fn_ref = func.get("fnRef", "")
            description = func.get("description", "")
            tests = func.get("tests", [])
            out_of_scope = func.get("outOfScope", [])

            lines.append(f"### {fn_ref}")
            lines.append("")
            if description:
                lines.append(description)
                lines.append("")

            # Happy path
            happy = [t for t in tests if t.get("category") == "happy"]
            if happy:
                lines.append("**Happy Path:**")
                lines.append("")
                for test in happy:
                    id_ = test.get("id", "")
                    desc = test.get("description", "")
                    lines.append(f"- **{id_}**: {desc}")
                lines.append("")

            # Edge cases
            edge = [t for t in tests if t.get("category") == "edge"]
            if edge:
                lines.append("**Edge Cases:**")
                lines.append("")
                for test in edge:
                    id_ = test.get("id", "")
                    desc = test.get("description", "")
                    lines.append(f"- **{id_}**: {desc}")
                lines.append("")

            # Error paths
            errors = [t for t in tests if t.get("category") == "error"]
            if errors:
                lines.append("**Error Paths:**")
                lines.append("")
                for test in errors:
                    id_ = test.get("id", "")
                    desc = test.get("description", "")
                    error_code = test.get("errorCode", "")
                    lines.append(f"- **{id_}**: {desc} *(Error: {error_code})*")
                lines.append("")

            if out_of_scope:
                lines.append("**Out of Scope:**")
                lines.append("")
                for item in out_of_scope:
                    desc = item.get("description", "") if isinstance(item, dict) else item
                    lines.append(f"- {desc}")
                lines.append("")

    return "\n".join(lines)


def generate_task_plan_md(data: dict) -> str:
    """Generate TaskPlan markdown from JSON data."""
    lines = ["# Task Plan", ""]

    lines.append(f"**Project:** {data.get('project', '')}")
    lines.append("")

    # Milestones
    milestones = data.get("milestones", [])
    if milestones:
        lines.append("## Milestones")
        lines.append("")
        for ms in milestones:
            id_ = ms.get("id", "")
            name = ms.get("name", "")
            outcome = ms.get("outcome", "")
            epics = ms.get("epics", [])

            lines.append(f"### {id_}: {name}")
            lines.append("")
            lines.append(outcome)
            lines.append("")
            lines.append(f"*Epics:* {', '.join(epics)}")
            lines.append("")

    # Epics
    epics = data.get("epics", [])
    if epics:
        lines.append("## Epics")
        lines.append("")
        for epic in epics:
            id_ = epic.get("id", "")
            title = epic.get("title", "")
            milestone = epic.get("milestone", "")
            requirements = epic.get("requirements", [])
            summary = epic.get("summary", "")
            objective = epic.get("objective", "")
            scope = epic.get("scope", {})
            acceptance = epic.get("acceptanceCriteria", [])
            deps = epic.get("dependencies", {})

            lines.append(f"### {id_}: {title}")
            lines.append("")
            if objective:
                lines.append(objective)
                lines.append("")
            if summary:
                lines.append(f"*{summary}*")
                lines.append("")
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

            # Scope
            if scope:
                in_scope = scope.get("inScope", [])
                out_of_scope = scope.get("outOfScope", [])
                if in_scope:
                    lines.append("**In Scope:**")
                    for item in in_scope:
                        lines.append(f"- {item}")
                    lines.append("")
                if out_of_scope:
                    lines.append("**Out of Scope:**")
                    for item in out_of_scope:
                        lines.append(f"- {item}")
                    lines.append("")

            # Acceptance Criteria
            if acceptance:
                lines.append("**Acceptance Criteria:**")
                lines.append("")
                for ac in acceptance:
                    lines.append(f"- [ ] {ac}")
                lines.append("")

    return "\n".join(lines)


def generate_issue_md(data: dict) -> str:
    """Generate Issue markdown from JSON data."""
    id_ = data.get("id", "")
    title = data.get("title", "")
    epic = data.get("epic", "")
    milestone = data.get("milestone", "")
    created = data.get("created", "")
    updated = data.get("updated", "")
    status = data.get("status", "not_started")
    issue_type = data.get("type", "AFK")
    blocked_by = data.get("blocked_by", [])
    in_scope = data.get("inScope", [])
    out_of_scope = data.get("outOfScope", [])
    acceptance = data.get("acceptanceCriteria", [])

    lines = [f"# {id_}: {title}", ""]

    # What to build
    body = data.get("body", "")
    if body:
        lines.append("## What to build")
        lines.append("")
        lines.append(body)
        lines.append("")

    # Acceptance criteria
    if acceptance:
        lines.append("## Acceptance criteria")
        lines.append("")
        for ac in acceptance:
            desc = ac.get("description", "") if isinstance(ac, dict) else ac
            lines.append(f"- [ ] {desc}")
        lines.append("")

    # Blocked by
    if blocked_by:
        lines.append("## Blocked by")
        lines.append("")
        lines.append(", ".join(blocked_by))
        lines.append("")

    lines.append(f"*Status:* {status}")
    lines.append(f"*Type:* {issue_type}")
    lines.append(f"*Epic:* {epic}")
    lines.append(f"*Milestone:* {milestone}")
    lines.append(f"*Created:* {created}")
    lines.append(f"*Updated:* {updated}")

    return "\n".join(lines)


# Map artifact types to their generator functions
GENERATOR_MAP = {
    "goal": generate_goal_spec_md,
    "glossary": generate_glossary_md,
    "data": generate_data_spec_md,
    "arch": generate_architecture_spec_md,
    "design": generate_design_spec_md,
    "api": generate_api_spec_md,
    "test": generate_test_spec_md,
    "plan": generate_task_plan_md,
    "issue": generate_issue_md,
}


def generate_artifact_markdown(artifact_type: str, data: dict, json_path: str,
                                schemas_dir: str, artifacts_dir: str,
                                output_path: Optional[str] = None) -> str:
    """Generate markdown from artifact JSON data."""
    # Get schema info
    schema_name, md_name, artifact_name = ARTIFACT_TYPE_MAP[artifact_type]

    # Determine output path
    if output_path is None:
        output_path = os.path.join(artifacts_dir, md_name)

    # Generate frontmatter
    frontmatter = generate_frontmatter(artifact_type, data, json_path)

    # Generate body
    generator = GENERATOR_MAP.get(artifact_type)
    if generator:
        body = generator(data)
    else:
        # Fallback: generic JSON-to-markdown
        body = json.dumps(data, indent=2)

    return frontmatter + body


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
