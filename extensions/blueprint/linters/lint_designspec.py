#!/usr/bin/env python3
"""
lint_designspec.py — Validate a DesignSpec JSON against its schema and semantic rules.
Optionally cross-checks against a GoalSpec for US/REQ reference resolution.

What this catches beyond JSON Schema:
  - Duplicate IDs across all sections
  - Persona roles inconsistent with GoalSpec actors
  - Journey usRefs that don't exist in GoalSpec
  - Journey personaRefs that don't exist in personas
  - Journey step screenRefs that don't exist in screen inventory
  - IA leaf nodes with no screenRef
  - IA screenRefs that don't exist in screen inventory
  - Screens in inventory not present in IA
  - Screen specs that don't match a screen in inventory
  - Screens in inventory with no screen spec
  - Interaction pattern refs in screen specs that don't exist
  - UXAC refs (US/REQ) that don't exist in GoalSpec
  - User stories in GoalSpec not covered by any journey
  - Screens with no journey step passing through them
  - Forbidden content smells (database, API, implementation terms)
  - Subjective language in UXAC

Usage:
    python lint_designspec.py <designspec.json> [--schema designspec.schema.json]
                               [--goal goalspec.json] [--strict] [--json]
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional

from shared import (
    BaseLinter,
    LayerResult,
    find_duplicates,
    find_patterns,
    print_human,
    print_json_output,
    validate_coverage,
    validate_exists,
    validate_glossary_refs,
)


# ── Semantic Rules ────────────────────────────────────────────────────────────

SEMANTIC_RULES = [
    # Design goals must not contain implementation details
    {
        "type": "patterns",
        "section": "designGoals",
        "text_key": "goal",
        "patterns": [
            "database", "api", "endpoint", "framework", "library",
            "class", "function", "sql", "http", "rest", "json",
        ],
        "label": "Design goal",
        "category": "design_goal_implementation_smell",
        "hint": "Design goals must describe UX qualities, not technology choices.",
    },
    
    # UXAC must not contain subjective language
    {
        "type": "patterns",
        "section": "uxAcceptanceCriteria",
        "text_key": "description",
        "patterns": [
            "feel", "feels", "intuitive", "easy", "simple", "nice",
            "smooth", "fast", "slow", "good", "beautiful", "clean",
        ],
        "label": "UXAC",
        "category": "uxac_subjective",
        "hint": "UX acceptance criteria must be binary and independently verifiable.",
    },
]


# ── Glossary Checks ───────────────────────────────────────────────────────────

GLOSSARY_CHECKS = [
    ("Persona", "glossaryRefs", "personas"),
    ("Screen", "glossaryRefs", "screenInventory"),
]


# ── Custom Checks ─────────────────────────────────────────────────────────────

def _collect_ia_screen_refs(nodes: list) -> set:
    """Recursively collect all screenRefs from IA tree."""
    refs = set()
    for node in nodes:
        if node.get("screenRef"):
            refs.add(node["screenRef"])
        if node.get("children"):
            refs |= _collect_ia_screen_refs(node["children"])
    return refs


def _collect_ia_leaf_issues(nodes: list, result: LayerResult) -> None:
    """Leaf nodes (no children) must have a screenRef."""
    for node in nodes:
        children = node.get("children", [])
        if not children and not node.get("screenRef"):
            result.add("error", "ia_leaf_no_screen",
                f"IA leaf node '{node['name']}' has no screenRef.",
                hint="Every leaf node in the information architecture must point to a screen ID.")
        if children:
            _collect_ia_leaf_issues(children, result)


def _check_design_goals(spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Check design goal duplicates."""
    goals = spec.get("designGoals", [])
    ids = [g["id"] for g in goals]
    find_duplicates(ids, "DG", result)


def _check_personas(spec: dict, result: LayerResult, extra_specs: dict) -> set:
    """Check persona duplicates and actor consistency."""
    personas = spec.get("personas", [])
    ids = [p["id"] for p in personas]
    goal = extra_specs.get("goal")
    
    find_duplicates(ids, "persona", result)
    
    if goal:
        goal_actors = {fr["actor"] for fr in goal.get("functionalRequirements", [])}
        goal_actors |= {us["actor"] for us in goal.get("userStories", [])}
        for persona in personas:
            if persona["role"] not in goal_actors:
                result.add("warning", "persona_actor_mismatch",
                    f"Persona '{persona['id']}': role '{persona['role']}' does not match any actor in GoalSpec.",
                    hint="Persona roles must be consistent with actors named in GoalSpec requirements and stories.")
    
    return set(ids)


def _check_journeys(spec: dict, result: LayerResult, extra_specs: dict) -> tuple:
    """Check journey duplicates, refs, and coverage."""
    journeys = spec.get("userJourneys", [])
    ids = [j["id"] for j in journeys]
    goal = extra_specs.get("goal")
    
    find_duplicates(ids, "UJ", result)
    
    # Build lookup sets
    personas = {p["id"]: p for p in spec.get("personas", [])}
    screens = {s["id"]: s for s in spec.get("screenInventory", [])}
    goal_us_ids = {us["id"] for us in goal.get("userStories", [])} if goal else set()
    
    covered_us_ids = set()
    
    for journey in journeys:
        jid = journey["id"]
        
        # personaRef resolves
        persona_ref = journey.get("personaRef")
        if persona_ref and persona_ref not in personas:
            result.add("error", "journey_persona_ref",
                f"{jid}: personaRef '{persona_ref}' not found in personas.",
                hint="Add the persona to the personas section or correct the reference.")
        
        # usRefs resolve
        for ref in journey.get("usRefs", []):
            if goal and ref not in goal_us_ids:
                result.add("error", "journey_us_ref",
                    f"{jid}: usRef '{ref}' not found in GoalSpec userStories.",
                    hint=f"Add '{ref}' to GoalSpec or correct the reference.")
            covered_us_ids.add(ref)
        
        # step screenRefs resolve
        for i, step in enumerate(journey.get("steps", [])):
            sref = step.get("screenRef")
            if sref and sref not in screens:
                result.add("error", "journey_screen_ref",
                    f"{jid} step {i+1}: screenRef '{sref}' not found in screen inventory.",
                    hint=f"Add a screen with id='{sref}' to screenInventory or correct the reference.")
        
        # At least one step should be a system response
        actors = [s["actor"] for s in journey.get("steps", [])]
        if "system" not in actors:
            result.add("warning", "journey_no_system_step",
                f"{jid}: no system steps defined — journeys must include system responses.",
                hint="Add at least one step with actor='system' to show what the system does.")
    
    return covered_us_ids


def _check_ia(spec: dict, result: LayerResult, extra_specs: dict) -> tuple:
    """Check IA leaf nodes and screen refs."""
    ia = spec.get("informationArchitecture", {})
    root = ia.get("root", [])
    screens = {s["id"] for s in spec.get("screenInventory", [])}
    
    _collect_ia_leaf_issues(root, result)
    ia_screen_refs = _collect_ia_screen_refs(root)
    
    # IA screenRefs must resolve
    ia_nodes = []
    for node in root:
        if node.get("screenRef"):
            ia_nodes.append({"id": node.get("name", ""), "screenRef": node["screenRef"]})
    validate_exists(ia_nodes, "screenRef", screens, result, "IA node", "screen inventory")
    
    return ia_screen_refs


def _check_screen_inventory(spec: dict, result: LayerResult, extra_specs: dict) -> tuple:
    """Check screen inventory duplicates and IA refs."""
    screens = spec.get("screenInventory", [])
    ids = [s["id"] for s in screens]
    goal = extra_specs.get("goal")
    
    find_duplicates(ids, "SCR", result)
    
    screen_ids = set(ids)
    goal_us_ids = {us["id"] for us in goal.get("userStories", [])} if goal else set()
    
    return screen_ids, goal_us_ids


def _check_screen_specs(spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Check screen specs, pattern refs, and states."""
    screen_specs = spec.get("screenSpecs", [])
    screens = {s["id"] for s in spec.get("screenInventory", [])}
    patterns = {p["id"] for p in spec.get("interactionPatterns", [])}
    
    spec_refs = [s["screenRef"] for s in screen_specs]
    find_duplicates(spec_refs, "screenSpec.screenRef", result)
    spec_screen_ids = set(spec_refs)
    
    # screenRef must resolve
    validate_exists(screen_specs, "screenRef", screens, result, "Screen spec", "screen inventory")
    
    # pattern refs in components
    component_patterns = []
    for ss in screen_specs:
        for comp in ss.get("components", []):
            for pref in comp.get("patternRefs", []):
                if pref not in patterns:
                    result.add("error", "pattern_ref",
                        f"Screen spec '{ss['screenRef']}' component '{comp['name']}': patternRef '{pref}' not found in interactionPatterns.",
                        hint=f"Add a pattern with id='{pref}' or correct the reference.")
    
    # pattern refs in interactions
    for ss in screen_specs:
        for interaction in ss.get("interactions", []):
            pref = interaction.get("patternRef")
            if pref and pref not in patterns:
                result.add("error", "pattern_ref",
                    f"Screen spec '{ss['screenRef']}' interaction '{interaction['trigger'][:40]}': patternRef '{pref}' not found.",
                    hint=f"Add a pattern with id='{pref}' or correct the reference.")
    
    # Warn: screen with no states is suspicious
    for ss in screen_specs:
        if not ss.get("states"):
            result.add("warning", "screen_no_states",
                f"Screen spec '{ss['screenRef']}' has no states defined.",
                hint="Every screen should document at least its empty, loaded, and error states.")
    
    # Screens in inventory with no spec
    for sid in screens:
        if sid not in spec_screen_ids:
            result.add("warning", "screen_no_spec",
                f"Screen '{sid}' has no screen spec.",
                hint="Add a screen spec entry for every screen in the inventory.")


def _check_uxac(spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Check UXAC duplicates, refs, and subjective language."""
    criteria = spec.get("uxAcceptanceCriteria", [])
    ids = [c["id"] for c in criteria]
    goal = extra_specs.get("goal")
    
    find_duplicates(ids, "UXAC", result)
    
    goal_us_ids = {us["id"] for us in goal.get("userStories", [])} if goal else set()
    goal_req_ids = {fr["id"] for fr in goal.get("functionalRequirements", [])} if goal else set()
    
    for uxac in criteria:
        uid = uxac["id"]
        refs = uxac.get("refs", {})
        us_refs = refs.get("usRefs", [])
        req_refs = refs.get("reqRefs", [])
        
        # Must have at least one ref
        if not us_refs and not req_refs:
            result.add("error", "uxac_no_refs",
                f"{uid}: no US or REQ references.",
                hint="Every UX acceptance criterion must link to at least one user story or requirement.")
        
        # Refs resolve
        for ref in us_refs:
            if goal and ref not in goal_us_ids:
                result.add("error", "uxac_us_ref",
                    f"{uid}: usRef '{ref}' not found in GoalSpec.",
                    hint=f"Add '{ref}' to GoalSpec userStories or correct the reference.")
        
        for ref in req_refs:
            if goal and ref not in goal_req_ids:
                result.add("error", "uxac_req_ref",
                    f"{uid}: reqRef '{ref}' not found in GoalSpec.",
                    hint=f"Add '{ref}' to GoalSpec functionalRequirements or correct the reference.")


def _check_visual_design_requirements(spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Check VDR duplicates."""
    vdrs = spec.get("visualDesignRequirements", [])
    ids = [v["id"] for v in vdrs]
    find_duplicates(ids, "VDR", result)


def _check_us_journey_coverage(spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Check that all GoalSpec user stories are covered by journeys."""
    goal = extra_specs.get("goal")
    if not goal:
        return
    
    journeys = spec.get("userJourneys", [])
    validate_coverage(
        goal.get("userStories", []),
        journeys,
        "id",
        "usRefs",
        result,
        "GoalSpec US",
        "user journey",
    )


def _check_screens_reachable(spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Check that all screens are reachable from journeys."""
    screens = {s["id"] for s in spec.get("screenInventory", [])}
    journey_screen_refs = set()
    
    for journey in spec.get("userJourneys", []):
        for step in journey.get("steps", []):
            if step.get("screenRef"):
                journey_screen_refs.add(step["screenRef"])
    
    for sid in screens:
        if sid not in journey_screen_refs:
            result.add("warning", "screen_unreachable",
                f"Screen '{sid}' is not visited in any user journey.",
                hint="Add a journey step that passes through this screen, or reconsider whether it is needed.")


def _check_forbidden_content(spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Scan prose fields for forbidden content."""
    forbidden_terms = [
        ("database schema", ["create table", "alter table", "primary key", "foreign key",
                             "schema migration", "orm model"]),
        ("internal API detail", ["endpoint", "rest api", "graphql", "grpc", "http method",
                                  "status code", "json schema", "request body"]),
        ("source code", ["def ", "function(", "class ", "import ", "const ", "var ",
                          "return ", "if (", "for (", "while ("]),
        ("technology selection", ["react", "vue", "angular", "tailwind", "bootstrap",
                                   "postgresql", "redis", "kafka", "webpack"])
    ]
    
    prose_sources = []
    for ss in spec.get("screenSpecs", []):
        prose_sources.append((f"screenSpec '{ss['screenRef']}' layout", ss.get("layout", "")))
        prose_sources.append((f"screenSpec '{ss['screenRef']}' wireframe", ss.get("wireframe", "")))
    
    for label, text in prose_sources:
        text_lower = text.lower()
        for category, terms in forbidden_terms:
            found = [t for t in terms if t in text_lower]
            if found:
                result.add("warning", "forbidden_content",
                    f"{label}: may contain {category}: {found}.",
                    hint=f"DesignSpec must not contain {category}. Move this to the appropriate spec.")


# ── Linter Class ──────────────────────────────────────────────────────────────

class DesignSpecLinter(BaseLinter):
    SPEC_NAME = "designspec"
    SEMANTIC_RULES = SEMANTIC_RULES
    GLOSSARY_CHECKS = GLOSSARY_CHECKS
    CROSS_SPEC_DEPS = ["goal"]
    MISC_CHECKS = [
        ("design_goals", _check_design_goals),
        ("personas", _check_personas),
        ("journeys", _check_journeys),
        ("ia", _check_ia),
        ("screen_inventory", _check_screen_inventory),
        ("screen_specs", _check_screen_specs),
        ("uxac", _check_uxac),
        ("visual_design_requirements", _check_visual_design_requirements),
        ("us_journey_coverage", _check_us_journey_coverage),
        ("screens_reachable", _check_screens_reachable),
        ("forbidden_content", _check_forbidden_content),
    ]


# ── Backward Compatibility ────────────────────────────────────────────────────

def run_lint(spec, schema_path, goal, strict, glossary=None):
    """Backward-compatible entry point for lint_all.py."""
    linter = DesignSpecLinter(spec, schema_path, strict)
    return linter.run(goal=goal, glossary=glossary)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    DesignSpecLinter.main([
        ("--goal", {"help": "Path to goalspec JSON for cross-spec checks", "spec_name": "goal"}),
    ])
