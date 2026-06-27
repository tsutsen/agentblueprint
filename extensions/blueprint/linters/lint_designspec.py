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

from shared import (
    BaseLinter,
    LayerResult,
    print_human,
    print_json_output,
)
from rules import SemanticRule


# ── Semantic Rules ────────────────────────────────────────────────────────────

SEMANTIC_RULES: list[SemanticRule] = [
    # Design goals must not contain implementation details
    {
        "type": "contains_patterns",
        "target": "designGoals.goal",
        "patterns": [
            "database", "api", "endpoint", "framework", "library",
            "class", "function", "sql", "http", "rest", "json",
        ],
        "target_label": "Design goal",
        "category": "design_goal_implementation_smell",
        "hint": "Design goals must describe UX qualities, not technology choices.",
    },

    # UXAC must not contain subjective language
    {
        "type": "contains_patterns",
        "target": "uxAcceptanceCriteria.description",
        "patterns": [
            "feel", "feels", "intuitive", "easy", "simple", "nice",
            "smooth", "fast", "slow", "good", "beautiful", "clean",
        ],
        "target_label": "UXAC",
        "category": "uxac_subjective",
        "hint": "UX acceptance criteria must be binary and independently verifiable.",
    },
    
    # Screen specs must reference valid screens
    {
        "type": "exists",
        "target": "screenSpecs.screenRef",
        "inside": "screenInventory.id",
        "target_label": "Screen spec",
        "ref_label": "screen inventory",
        "category": "screen_spec_ref",
        "hint": "Add screen to screenInventory or correct the screenRef.",
    },
    
    # Screens must have states
    {
        "type": "non_empty",
        "target": "screenSpecs.states",
        "target_label": "Screen spec",
        "category": "screen_no_states",
        "hint": "Every screen should document at least its empty, loaded, and error states.",
    },
    
    # UXAC must have refs
    {
        "type": "non_empty",
        "target": "uxAcceptanceCriteria.refs",
        "target_label": "UXAC",
        "category": "uxac_no_refs",
        "hint": "Every UX acceptance criterion must link to at least one user story or requirement.",
    },
    
    # UXAC refs must resolve to GoalSpec
    {
        "type": "exists",
        "target": "uxAcceptanceCriteria.refs.usRefs",
        "inside": "goal:userStories.id",
        "target_label": "UXAC",
        "ref_label": "GoalSpec userStory",
        "category": "uxac_us_ref",
        "hint": "Add to GoalSpec userStories or correct the reference.",
    },
    {
        "type": "exists",
        "target": "uxAcceptanceCriteria.refs.reqRefs",
        "inside": "goal:functionalRequirements.id",
        "target_label": "UXAC",
        "ref_label": "GoalSpec requirement",
        "category": "uxac_req_ref",
        "hint": "Add to GoalSpec functionalRequirements or correct the reference.",
    },
    
    # User stories must be covered by journeys
    {
        "type": "covers_all",
        "target": "userJourneys.usRefs",
        "should_cover_all": "goal:userStories",
        "category": "us_uncovered",
        "covered_label": "GoalSpec US",
        "target_label": "user journey",
    },

    # Screens in inventory must be covered by screen specs
    {
        "type": "covers_all",
        "target": "screenSpecs.screenRef",
        "should_cover_all": "screenInventory.id",
        "category": "screen_unspecified",
        "covered_label": "Screen inventory",
        "target_label": "screen spec",
    },
    
    # Journey personaRef must resolve to personas
    {
        "type": "exists",
        "target": "userJourneys.personaRef",
        "inside": "personas.id",
        "target_label": "User journey",
        "ref_label": "persona",
        "category": "journey_persona_ref",
        "hint": "Add the persona to the personas section or correct the reference.",
    },
    
    # Journey usRefs must resolve to GoalSpec userStories
    {
        "type": "exists",
        "target": "userJourneys.usRefs",
        "inside": "goal:userStories.id",
        "target_label": "User journey",
        "ref_label": "GoalSpec userStory",
        "category": "journey_us_ref",
        "hint": "Add to GoalSpec userStories or correct the reference.",
    },
    
    # Journey step screenRefs must resolve to screen inventory
    {
        "type": "exists",
        "target": "userJourneys.steps.screenRef",
        "inside": "screenInventory.id",
        "target_label": "Journey step",
        "ref_label": "screen inventory",
        "category": "journey_screen_ref",
        "hint": "Add a screen to screenInventory or correct the reference.",
    },
    
    # Screen specs must not contain forbidden content
    {
        "type": "contains_patterns",
        "target": "screenSpecs",
        "extra_keys": ["layout", "wireframe"],
        "patterns": [
            ("create table", "database schema"),
            ("alter table", "database schema"),
            ("primary key", "database schema"),
            ("foreign key", "database schema"),
            ("schema migration", "database schema"),
            ("orm model", "database schema"),
            ("endpoint", "internal API detail"),
            ("rest api", "internal API detail"),
            ("graphql", "internal API detail"),
            ("grpc", "internal API detail"),
            ("http method", "internal API detail"),
            ("status code", "internal API detail"),
            ("json schema", "internal API detail"),
            ("request body", "internal API detail"),
            ("def ", "source code"),
            ("function\\(", "source code"),
            ("class ", "source code"),
            ("import ", "source code"),
            ("const ", "source code"),
            ("var ", "source code"),
            ("return ", "source code"),
            ("if \\(", "source code"),
            ("for \\(", "source code"),
            ("while \\(", "source code"),
            ("react", "technology selection"),
            ("vue", "technology selection"),
            ("angular", "technology selection"),
            ("tailwind", "technology selection"),
            ("bootstrap", "technology selection"),
            ("postgresql", "technology selection"),
            ("redis", "technology selection"),
            ("kafka", "technology selection"),
            ("webpack", "technology selection"),
        ],
        "target_label": "Screen spec",
        "category": "forbidden_content",
        "hint": "DesignSpec must not contain {category}. Move this to the appropriate spec.",
    },
    # Glossary refs: Personas must reference valid glossary terms
    {
        "type": "exists",
        "target": "personas.glossaryRefs",
        "inside": "glossary.terms.id",
        "target_label": "Persona",
        "ref_label": "Glossary",
        "category": "glossary_ref_missing",
    },
    # Glossary refs: Screens must reference valid glossary terms
    {
        "type": "exists",
        "target": "screenInventory.glossaryRefs",
        "inside": "glossary.terms.id",
        "target_label": "Screen",
        "ref_label": "Glossary",
        "category": "glossary_ref_missing",
    },
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


def _check_ia_screen_refs_exist(nodes: list, screens: set[str], result: LayerResult) -> None:
    """Recursively check that all IA screenRefs resolve to screen inventory."""
    for node in nodes:
        if node.get("screenRef") and node["screenRef"] not in screens:
            result.add("error", "ia_screen_ref",
                f"IA node '{node.get('name', '?')}': screenRef '{node['screenRef']}' not found in screen inventory.",
                hint="Add the screen to the inventory or correct the reference.")
        if node.get("children"):
            _check_ia_screen_refs_exist(node["children"], screens, result)


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


def _check_personas(spec: dict, result: LayerResult, extra_specs: dict) -> set:
    """Check persona actor consistency."""
    personas = spec.get("personas", [])
    goal = extra_specs.get("goal")
    
    if goal:
        goal_actors = {fr["actor"] for fr in goal.get("functionalRequirements", [])}
        goal_actors |= {us["actor"] for us in goal.get("userStories", [])}
        for persona in personas:
            if persona["role"] not in goal_actors:
                result.add("warning", "persona_actor_mismatch",
                    f"Persona '{persona['id']}': role '{persona['role']}' does not match any actor in GoalSpec.",
                    hint="Persona roles must be consistent with actors named in GoalSpec requirements and stories.")
    
    return set(p["id"] for p in personas)


def _check_journeys(spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Check journey system step requirement."""
    for journey in spec.get("userJourneys", []):
        jid = journey["id"]
        
        # At least one step should be a system response
        actors = [s["actor"] for s in journey.get("steps", [])]
        if "system" not in actors:
            result.add("warning", "journey_no_system_step",
                f"{jid}: no system steps defined — journeys must include system responses.",
                hint="Add at least one step with actor='system' to show what the system does.")


def _check_ia(spec: dict, result: LayerResult, extra_specs: dict) -> tuple:
    """Check IA leaf nodes and screen refs."""
    ia = spec.get("informationArchitecture", {})
    root = ia.get("root", [])
    screens = {s["id"] for s in spec.get("screenInventory", [])}
    
    _collect_ia_leaf_issues(root, result)
    ia_screen_refs = _collect_ia_screen_refs(root)

    # IA screenRefs must resolve (recursive walk)
    _check_ia_screen_refs_exist(root, screens, result)

    return ia_screen_refs


def _check_screen_specs(spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Check screen specs, pattern refs, and screens with no spec."""
    screen_specs = spec.get("screenSpecs", [])
    screens = {s["id"] for s in spec.get("screenInventory", [])}
    patterns = {p["id"] for p in spec.get("interactionPatterns", [])}
    
    spec_screen_ids = set(ss["screenRef"] for ss in screen_specs)
    
    # pattern refs in components
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


# ── Linter Class ──────────────────────────────────────────────────────────────

class DesignSpecLinter(BaseLinter):
    SPEC_NAME = "designspec"
    SEMANTIC_RULES = SEMANTIC_RULES
    CROSS_SPEC_DEPS = ["goal", "glossary"]
    MISC_CHECKS = [
        ("personas", _check_personas),
        ("journeys", _check_journeys),
        ("ia", _check_ia),
        ("screen_specs", _check_screen_specs),
        ("screens_reachable", _check_screens_reachable),
    ]


# ── Backward Compatibility ────────────────────────────────────────────────────

def run_lint(spec, schema_path, goal, strict, glossary=None):
    """Backward-compatible entry point for lint_all.py."""
    linter = DesignSpecLinter(spec, schema_path, strict)
    return linter.run(goal=goal, glossary=glossary)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    DesignSpecLinter.main()
