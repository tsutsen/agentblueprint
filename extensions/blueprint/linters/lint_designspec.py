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
import sys
import argparse
import re
from pathlib import Path
from typing import Optional
from shared import Issue, LayerResult, print_human, print_json_output, validate_spec_ids, validate_project_and_version, check_duplicates
from schema_validator import SchemaValidator


# ── Helpers ───────────────────────────────────────────────────────────────────


def collect_ia_screen_refs(nodes: list) -> set[str]:
    refs = set()
    for node in nodes:
        if node.get("screenRef"):
            refs.add(node["screenRef"])
        if node.get("children"):
            refs |= collect_ia_screen_refs(node["children"])
    return refs


def collect_ia_leaf_issues(nodes: list, result: LayerResult):
    """Leaf nodes (no children) must have a screenRef."""
    for node in nodes:
        children = node.get("children", [])
        if not children and not node.get("screenRef"):
            result.add("error", "ia_leaf_no_screen",
                f"IA leaf node '{node['name']}' has no screenRef.",
                hint="Every leaf node in the information architecture must point to a screen ID.")
        if children:
            collect_ia_leaf_issues(children, result)


# ── Checks ────────────────────────────────────────────────────────────────────

def validate_project_and_version(spec: dict, goal: Optional[dict], result: LayerResult):
    if not goal:
        return
    if spec["project"] != goal["project"]:
        result.add("error", "project_match",
            f"Project mismatch: designspec='{spec['project']}' goalspec='{goal['project']}'.",
            hint="Both specs must have identical 'project' values.")
    pinned = spec.get("goalSpecVersion")
    if pinned and pinned != goal["version"]:
        result.add("error", "version_drift",
            f"designspec.goalSpecVersion='{pinned}' does not match goalspec.version='{goal['version']}'.",
            hint="Update goalSpecVersion after reviewing design against the updated GoalSpec.")


def check_design_goals(spec: dict, result: LayerResult):
    goals = spec.get("designGoals", [])
    ids = [g["id"] for g in goals]
    check_duplicates(ids, "DG", result)



    forbidden = ["database", "api", "endpoint", "framework", "library",
                 "class", "function", "sql", "http", "rest", "json"]
    for g in goals:
        text = g.get("goal", "").lower()
        found = [f for f in forbidden if f in text]
        if found:
            result.add("warning", "design_goal_implementation_smell",
                f"{g['id']}: goal may contain implementation detail: {found}.",
                hint="Design goals must describe UX qualities, not technology choices.")


def check_personas(spec: dict, goal: Optional[dict], result: LayerResult) -> set[str]:
    personas = spec.get("personas", [])
    ids = [p["id"] for p in personas]
    check_duplicates(ids, "persona", result)



    if goal:
        goal_actors = {fr["actor"] for fr in goal.get("functionalRequirements", [])}
        goal_actors |= {us["actor"] for us in goal.get("userStories", [])}
        for persona in personas:
            if persona["role"] not in goal_actors:
                result.add("warning", "persona_actor_mismatch",
                    f"Persona '{persona['id']}': role '{persona['role']}' does not match any actor in GoalSpec.",
                    hint="Persona roles must be consistent with actors named in GoalSpec requirements and stories.")

    return set(ids)


def check_journeys(spec: dict, persona_ids: set[str],
                   screen_ids: set[str], goal: Optional[dict], result: LayerResult) -> set[str]:
    journeys = spec.get("userJourneys", [])
    ids = [j["id"] for j in journeys]
    check_duplicates(ids, "UJ", result)

    goal_us_ids = {us["id"] for us in goal.get("userStories", [])} if goal else set()
    covered_us_ids = set()

    for journey in journeys:
        jid = journey["id"]

        # personaRef resolves
        if journey["personaRef"] not in persona_ids:
            result.add("error", "journey_persona_ref",
                f"{jid}: personaRef '{journey['personaRef']}' not found in personas.",
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
            if sref and sref not in screen_ids:
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


def check_ia(spec: dict, screen_ids: set[str], result: LayerResult) -> set[str]:
    ia = spec.get("informationArchitecture", {})
    root = ia.get("root", [])

    collect_ia_leaf_issues(root, result)

    ia_screen_refs = collect_ia_screen_refs(root)

    # IA screenRefs must resolve
    for ref in ia_screen_refs:
        if ref not in screen_ids:
            result.add("error", "ia_screen_ref",
                f"IA references screen '{ref}' which is not in the screen inventory.",
                hint=f"Add a screen with id='{ref}' to screenInventory or correct the IA reference.")

    return ia_screen_refs


def check_screen_inventory(spec: dict, ia_screen_refs: set[str],
                            goal: Optional[dict], result: LayerResult) -> set[str]:
    screens = spec.get("screenInventory", [])
    ids = [s["id"] for s in screens]
    check_duplicates(ids, "SCR", result)



    screen_ids = set(ids)

    goal_us_ids = {us["id"] for us in goal.get("userStories", [])} if goal else set()

    for screen in screens:
        sid = screen["id"]

        # Screen not in IA
        if sid not in ia_screen_refs:
            result.add("warning", "screen_not_in_ia",
                f"Screen '{sid}' is not referenced in the information architecture.",
                hint="Add this screen to the IA tree so users can navigate to it.")

        # usRefs resolve
        for ref in screen.get("usRefs", []):
            if goal and ref not in goal_us_ids:
                result.add("error", "screen_us_ref",
                    f"Screen '{sid}': usRef '{ref}' not found in GoalSpec userStories.",
                    hint=f"Add '{ref}' to GoalSpec or correct the reference.")

    return screen_ids


def check_screen_specs(spec: dict, screen_ids: set[str],
                        pattern_ids: set[str], result: LayerResult):
    screen_specs = spec.get("screenSpecs", [])
    spec_refs = [s["screenRef"] for s in screen_specs]
    check_duplicates(spec_refs, "screenSpec.screenRef", result)
    spec_screen_ids = set(spec_refs)

    # screenRef must resolve
    for ss in screen_specs:
        ref = ss["screenRef"]
        if ref not in screen_ids:
            result.add("error", "screen_spec_ref",
                f"Screen spec references '{ref}' which is not in the screen inventory.",
                hint=f"Add screen '{ref}' to screenInventory or correct the screenRef.")

        # pattern refs in components
        for comp in ss.get("components", []):
            for pref in comp.get("patternRefs", []):
                if pref not in pattern_ids:
                    result.add("error", "pattern_ref",
                        f"Screen spec '{ref}' component '{comp['name']}': patternRef '{pref}' not found in interactionPatterns.",
                        hint=f"Add a pattern with id='{pref}' or correct the reference.")

        # pattern refs in interactions
        for interaction in ss.get("interactions", []):
            pref = interaction.get("patternRef")
            if pref and pref not in pattern_ids:
                result.add("error", "pattern_ref",
                    f"Screen spec '{ref}' interaction '{interaction['trigger'][:40]}': patternRef '{pref}' not found.",
                    hint=f"Add a pattern with id='{pref}' or correct the reference.")

        # Warn: screen with no states is suspicious
        if not ss.get("states"):
            result.add("warning", "screen_no_states",
                f"Screen spec '{ref}' has no states defined.",
                hint="Every screen should document at least its empty, loaded, and error states.")

    # Screens in inventory with no spec
    for sid in screen_ids:
        if sid not in spec_screen_ids:
            result.add("warning", "screen_no_spec",
                f"Screen '{sid}' has no screen spec.",
                hint="Add a screen spec entry for every screen in the inventory.")


def check_interaction_patterns(spec: dict, result: LayerResult) -> set[str]:
    patterns = spec.get("interactionPatterns", [])
    ids = [p["id"] for p in patterns]
    check_duplicates(ids, "interactionPattern", result)
    return set(ids)


def check_uxac(spec: dict, goal: Optional[dict], result: LayerResult):
    criteria = spec.get("uxAcceptanceCriteria", [])
    ids = [c["id"] for c in criteria]
    check_duplicates(ids, "UXAC", result)

    goal_us_ids  = {us["id"] for us in goal.get("userStories", [])} if goal else set()
    goal_req_ids = {fr["id"] for fr in goal.get("functionalRequirements", [])} if goal else set()

    subjective = ["feel", "feels", "intuitive", "easy", "simple", "nice",
                  "smooth", "fast", "slow", "good", "beautiful", "clean"]

    for uxac in criteria:
        uid = uxac["id"]
        refs = uxac.get("refs", {})
        us_refs  = refs.get("usRefs", [])
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

        # Subjective language
        desc_lower = uxac.get("description", "").lower()
        found = [s for s in subjective if s in desc_lower]
        if found:
            result.add("warning", "uxac_subjective",
                f"{uid}: description may contain subjective language: {found}.",
                hint="UX acceptance criteria must be binary and independently verifiable.")


def check_visual_design_requirements(spec: dict, result: LayerResult):
    vdrs = spec.get("visualDesignRequirements", [])
    ids = [v["id"] for v in vdrs]
    check_duplicates(ids, "VDR", result)




def check_us_journey_coverage(goal: Optional[dict], covered_us_ids: set[str], result: LayerResult):
    """Every GoalSpec user story should be covered by at least one journey."""
    if not goal:
        return
    for us in goal.get("userStories", []):
        if us["id"] not in covered_us_ids:
            result.add("warning", "us_no_journey",
                f"GoalSpec {us['id']} ('{us['capability'][:50]}') has no user journey.",
                hint=f"Add a user journey with usRef='{us['id']}' covering this story.")


def check_forbidden_content(spec: dict, result: LayerResult):
    """Scan prose fields for forbidden content: database schemas, internal APIs, source code."""
    forbidden_terms = [
        ("database schema", ["create table", "alter table", "primary key", "foreign key",
                             "schema migration", "orm model"]),
        ("internal API detail", ["endpoint", "rest api", "graphql", "grpc", "http method",
                                  "status code", "json schema", "request body"]),
        ("source code", ["def ", "function(", "class ", "import ", "const ", "var ",
                          "return ", "if (", "for (", "while ("]),  # space-sensitive to avoid false positives
        ("technology selection", ["react", "vue", "angular", "tailwind", "bootstrap",
                                   "postgresql", "redis", "kafka", "webpack"])
    ]

    # Collect all prose strings from screen specs and journey steps
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


def check_screens_reachable(spec: dict, screen_ids: set[str], result: LayerResult):
    """Every screen should appear in at least one journey step."""
    journey_screen_refs = set()
    for journey in spec.get("userJourneys", []):
        for step in journey.get("steps", []):
            if step.get("screenRef"):
                journey_screen_refs.add(step["screenRef"])

    for sid in screen_ids:
        if sid not in journey_screen_refs:
            result.add("warning", "screen_unreachable",
                f"Screen '{sid}' is not visited in any user journey.",
                hint="Add a journey step that passes through this screen, or reconsider whether it is needed.")



def run_lint(spec: dict, schema_path: Optional[Path],
             goal: Optional[dict], strict: bool,
             glossary: Optional[dict] = None) -> LayerResult:
    result = LayerResult()

    # JSON Schema validation (auto-generated from schema)
    if schema_path:
        schema = json.loads(Path(schema_path).read_text())
        schema_issues = SchemaValidator(schema).validate(spec)
        for issue in schema_issues:
            result.add(issue.severity, issue.category, issue.message, issue.hint)

    # ID format validation
    validate_spec_ids({"dg": spec.get("designGoals", []), "prs": spec.get("personas", []), "uj": spec.get("userJourneys", []), "scr": spec.get("screenInventory", []), "spc": spec.get("screenSpecs", []), "pat": spec.get("interactionPatterns", []), "uxac": spec.get("uxAcceptanceCriteria", []), "dt": spec.get("designTokens", []), "vdr": spec.get("visualDesignRequirements", [])}, result)

    # 
    # Cross-spec version checks
    validate_project_and_version(spec, "designspec", goal, result)

    # Section checks — order matters: build ID sets first, reference them later
    check_design_goals(spec, result)
    persona_ids    = check_personas(spec, goal, result)
    pattern_ids    = check_interaction_patterns(spec, result)

    # Build screen ID set from inventory first, then validate IA against it
    screens        = spec.get("screenInventory", [])
    screen_ids     = {s["id"] for s in screens}
    ia_screen_refs = check_ia(spec, screen_ids, result)
    screen_ids     = check_screen_inventory(spec, ia_screen_refs, goal, result)

    covered_us_ids = check_journeys(spec, persona_ids, screen_ids, goal, result)
    check_screen_specs(spec, screen_ids, pattern_ids, result)
    check_uxac(spec, goal, result)
    check_visual_design_requirements(spec, result)
    check_us_journey_coverage(goal, covered_us_ids, result)
    check_screens_reachable(spec, screen_ids, result)
    check_forbidden_content(spec, result)
    validate_glossary_refs(glossary, result, [
                ("Persona", "glossaryRefs", spec.get("personas", [])),
                ("Screen", "glossaryRefs", spec.get("screenInventory", [])),
                ("Component", "glossaryRefs", sum([s.get("components", []) for s in spec.get("screenSpecs", [])], [])),
                ("Journey step", "glossaryRefs", sum([step for j in spec.get("userJourneys", []) for step in j.get("steps", [])], [])),
            ])

    if strict:
        for w in result.warnings:
            w.severity = "error"
            result.errors.append(w)
        result.warnings.clear()

    return result


# ── Output
# Uses shared.print_human and shared.print_json_output


def main():
    parser = argparse.ArgumentParser(description="Lint a DesignSpec JSON.")
    parser.add_argument("input",     help="Path to designspec JSON")
    parser.add_argument("--schema",  help="Path to designspec.schema.json")
    parser.add_argument("--goal",    help="Path to goalspec JSON for cross-spec checks")
    parser.add_argument("--strict",  action="store_true", help="Treat warnings as errors")
    parser.add_argument("--json",    action="store_true", help="Output as JSON")
    args = parser.parse_args()

    spec = json.loads(Path(args.input).read_text())
    schema_path = Path(args.schema) if args.schema else None
    goal = json.loads(Path(args.goal).read_text()) if args.goal else None

    result = run_lint(spec, schema_path, goal, args.strict)

    if args.json:
        print_json_output(result)
    else:
        print_human(result, args.input)

    sys.exit(0 if result.clean else 1)


if __name__ == "__main__":
    main()
