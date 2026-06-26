#!/usr/bin/env python3
"""
lint_archspec.py — Validate an ArchSpec JSON against its schema and semantic rules.
Optionally cross-checks against a GoalSpec for REQ/NFR reference resolution.

What this catches beyond JSON Schema:
  - Duplicate component IDs, constraint IDs, flow IDs
  - Component dependency references that don't exist
  - Subsystem componentRefs that don't exist
  - Data flow step componentRefs that don't exist
  - REQ/NFR refs that don't exist in the GoalSpec (if provided)
  - Components with no REQ coverage at confirmed status
  - Overlapping responsibilities across components
  - Circular component dependencies
  - project/goalSpecVersion mismatch against loaded GoalSpec
  - FRs in GoalSpec not covered by any component
  - Constraints with implementation smells

Usage:
    python lint_archspec.py <archspec.json> [--schema archspec.schema.json]
                            [--goal goalspec.json] [--strict] [--json]
"""

import json
import sys
import argparse
import re
from pathlib import Path
from typing import Optional
from shared import Issue, LayerResult, print_human, print_json_output, validate_spec_ids
from schema_validator import SchemaValidator


# ── Helpers ───────────────────────────────────────────────────────────────────

def check_duplicates(ids: list[str], label: str, result: LayerResult):
    seen = set()
    for id_ in ids:
        if id_ in seen:
            result.add("error", "duplicate_id",
                f"Duplicate {label} id '{id_}'.",
                hint=f"Each {label} must have a unique identifier.")
        seen.add(id_)


def detect_cycle(graph: dict[str, list[str]]) -> Optional[list[str]]:
    """Return a cycle path if one exists in the dependency graph, else None."""
    visited = set()
    path = []

    def dfs(node):
        if node in path:
            return path[path.index(node):]
        if node in visited:
            return None
        visited.add(node)
        path.append(node)
        for dep in graph.get(node, []):
            cycle = dfs(dep)
            if cycle:
                return cycle
        path.pop()
        return None

    for node in graph:
        if node not in visited:
            cycle = dfs(node)
            if cycle:
                return cycle
    return None


# ── Checks ────────────────────────────────────────────────────────────────────

def check_project_match(spec: dict, goal: dict, result: LayerResult):
    if spec["project"] != goal["project"]:
        result.add("error", "project_match",
            f"Project mismatch: archspec='{spec['project']}' goalspec='{goal['project']}'.",
            hint="Both specs must have identical 'project' values.")


def check_version_pins(spec: dict, goal: dict, result: LayerResult):
    pinned = spec.get("goalSpecVersion")
    if pinned and pinned != goal["version"]:
        result.add("error", "version_drift",
            f"archspec.goalSpecVersion='{pinned}' does not match goalspec.version='{goal['version']}'.",
            hint="Re-review architecture against updated GoalSpec, then update goalSpecVersion.")


def check_components(spec: dict, result: LayerResult) -> set[str]:
    components = spec.get("components", [])
    ids = [c["id"] for c in components]
    check_duplicates(ids, "component", result)
    

    
    component_ids = set(ids)

    # Build dependency graph for cycle detection
    dep_graph: dict[str, list[str]] = {}
    for comp in components:
        cid = comp["id"]
        deps = comp.get("dependencies", [])
        dep_graph[cid] = deps

        # Dependency references must exist
        for dep in deps:
            if dep not in component_ids:
                result.add("error", "dependency_ref",
                    f"Component '{cid}': dependency '{dep}' is not a defined component.",
                    hint=f"Add a component with id='{dep}' or correct the dependency reference.")

        # Warn: component with no reqRefs at non-draft status
        if not comp.get("reqRefs") and spec.get("status") in ("review", "confirmed"):
            result.add("warning", "component_no_reqs",
                f"Component '{cid}' has no reqRefs.",
                hint="Link each component to the requirements it helps satisfy.")

    # Circular dependency check
    cycle = detect_cycle(dep_graph)
    if cycle:
        result.add("error", "circular_dependency",
            f"Circular component dependency detected: {' → '.join(cycle + [cycle[0]])}.",
            hint="Refactor to break the cycle — introduce an abstraction or invert a dependency.")

    # Overlapping responsibilities
    all_responsibilities: dict[str, str] = {}  # responsibility → first component that claimed it
    for comp in components:
        for resp in comp.get("responsibilities", []):
            resp_norm = resp.strip().lower().rstrip(".")
            if resp_norm in all_responsibilities:
                result.add("warning", "overlapping_responsibility",
                    f"Component '{comp['id']}' responsibility '{resp}' "
                    f"is identical or near-identical to one claimed by '{all_responsibilities[resp_norm]}'.",
                    hint="Each responsibility must be owned by exactly one component.")
            else:
                all_responsibilities[resp_norm] = comp["id"]

    return component_ids


def check_subsystems(spec: dict, component_ids: set[str], result: LayerResult):
    subsystems = spec.get("overview", {}).get("subsystems", [])
    all_comp_refs = []
    comp_to_subs: dict[str, list[str]] = {}

    for sub in subsystems:
        refs = sub.get("componentRefs", [])
        
        # Check for empty subsystem
        if not refs:
            result.add("warning", "subsystem_empty",
                f"Subsystem '{sub['name']}' has no components assigned.",
                hint="Assign components to this subsystem or remove it.")
        
        for ref in refs:
            if ref not in component_ids:
                result.add("error", "subsystem_ref",
                    f"Subsystem '{sub['name']}': componentRef '{ref}' is not a defined component.",
                    hint=f"Add a component with id='{ref}' or correct the reference.")
            all_comp_refs.append(ref)
            comp_to_subs.setdefault(ref, []).append(sub["name"])

    # Warn: components not assigned to any subsystem
    for cid in component_ids:
        if cid not in all_comp_refs:
            result.add("warning", "component_no_subsystem",
                f"Component '{cid}' is not assigned to any subsystem.",
                hint="Assign every component to a subsystem in overview.subsystems.")
    
    # Warn: component assigned to multiple subsystems
    for comp, subs in comp_to_subs.items():
        if len(subs) > 1:
            result.add("warning", "subsystem_overlap",
                f"Component '{comp}' is assigned to multiple subsystems: {', '.join(subs)}.",
                hint="Each component should belong to exactly one subsystem.")


def check_data_flows(spec: dict, component_ids: set[str], result: LayerResult):
    flows = spec.get("dataFlow", [])
    ids = [f["id"] for f in flows]
    check_duplicates(ids, "FLW", result)



    for flow in flows:
        fid = flow["id"]
        steps = flow.get("steps", [])

        for i, step in enumerate(steps):
            ref = step.get("componentRef")
            if ref and ref not in component_ids:
                result.add("error", "flow_component_ref",
                    f"Flow '{fid}' step {i+1}: componentRef '{ref}' is not a defined component.",
                    hint=f"Add a component with id='{ref}' or correct the reference.")

        # Flow with only one step is not a flow
        if len(steps) < 2:
            result.add("error", "flow_too_short",
                f"Flow '{fid}' has fewer than 2 steps — not a valid flow.",
                hint="A data flow must show at least a source and a sink step.")


def check_constraints(spec: dict, result: LayerResult):
    constraints = spec.get("constraints", [])
    ids = [c["id"] for c in constraints]
    check_duplicates(ids, "CON", result)



    # Implementation smells in constraints
    impl_smells = ["postgres", "mysql", "redis", "sqlite", "mongodb", "fastapi",
                   "flask", "django", "docker", "kubernetes", "s3", "lambda",
                   "python", "typescript", "rust", "golang", "java"]
    for con in constraints:
        desc_lower = con.get("description", "").lower()
        found = [s for s in impl_smells if s in desc_lower]
        if found:
            result.add("warning", "constraint_implementation_leak",
                f"{con['id']}: constraint mentions specific technology: {found}.",
                hint="Constraints should describe what is required, not which technology satisfies it.")


def check_req_nfr_refs(spec: dict, goal: Optional[dict], result: LayerResult):
    """Resolve all REQ/NFR refs across components, flows, and constraints against GoalSpec."""
    if not goal:
        return

    goal_req_ids = {r["id"] for r in goal.get("functionalRequirements", [])}
    goal_nfr_ids = {r["id"] for r in goal.get("nonFunctionalRequirements", [])}

    def check_req(ref: str, source: str):
        if ref not in goal_req_ids:
            result.add("error", "req_ref_missing",
                f"{source}: REQ ref '{ref}' not found in GoalSpec.",
                hint=f"Add '{ref}' to GoalSpec functionalRequirements or correct the reference.")

    def check_nfr(ref: str, source: str):
        if ref not in goal_nfr_ids:
            result.add("error", "nfr_ref_missing",
                f"{source}: NFR ref '{ref}' not found in GoalSpec.",
                hint=f"Add '{ref}' to GoalSpec nonFunctionalRequirements or correct the reference.")

    for comp in spec.get("components", []):
        for ref in comp.get("reqRefs", []):
            check_req(ref, f"Component '{comp['id']}'")
        for ref in comp.get("nfrRefs", []):
            check_nfr(ref, f"Component '{comp['id']}'")

    for flow in spec.get("dataFlow", []):
        for ref in flow.get("reqRefs", []):
            check_req(ref, f"Flow '{flow['id']}'")

    for con in spec.get("constraints", []):
        for ref in con.get("nfrRefs", []):
            check_nfr(ref, f"Constraint '{con['id']}'")


def check_fr_coverage(spec: dict, goal: Optional[dict], result: LayerResult):
    """Every FR in GoalSpec should be covered by at least one component."""
    if not goal:
        return

    covered_reqs = set()
    for comp in spec.get("components", []):
        for ref in comp.get("reqRefs", []):
            covered_reqs.add(ref)

    for fr in goal.get("functionalRequirements", []):
        if fr["id"] not in covered_reqs:
            result.add("warning", "fr_uncovered",
                f"GoalSpec {fr['id']} ('{fr['description'][:60]}...') is not covered by any component.",
                hint=f"Add reqRef '{fr['id']}' to the component responsible for this requirement.")


def check_nfr_coverage(spec: dict, goal: Optional[dict], result: LayerResult):
    """Every NFR in GoalSpec should be covered by at least one component or constraint."""
    if not goal:
        return

    covered_nfrs = set()
    for comp in spec.get("components", []):
        for ref in comp.get("nfrRefs", []):
            covered_nfrs.add(ref)
    for con in spec.get("constraints", []):
        for ref in con.get("nfrRefs", []):
            covered_nfrs.add(ref)

    for nfr in goal.get("nonFunctionalRequirements", []):
        if nfr["id"] not in covered_nfrs:
            result.add("warning", "nfr_uncovered",
                f"GoalSpec {nfr['id']} ('{nfr['description'][:60]}...') is not covered by any component or constraint.",
                hint=f"Add nfrRef '{nfr['id']}' to a component or constraint responsible for this NFR.")


def check_subsystem_empty(spec: dict, component_ids: set[str], result: LayerResult):
    """Warn if a subsystem has no components assigned."""
    subsystems = spec.get("overview", {}).get("subsystems", [])
    for sub in subsystems:
        refs = sub.get("componentRefs", [])
        if not refs:
            result.add("warning", "subsystem_empty",
                f"Subsystem '{sub['name']}' has no components assigned.",
                hint="Assign components to this subsystem or remove it.")


def check_subsystem_overlap(spec: dict, result: LayerResult):
    """Warn if a component is assigned to multiple subsystems."""
    subsystems = spec.get("overview", {}).get("subsystems", [])
    comp_to_subs: dict[str, list[str]] = {}
    for sub in subsystems:
        for ref in sub.get("componentRefs", []):
            comp_to_subs.setdefault(ref, []).append(sub["name"])
    
    for comp, subs in comp_to_subs.items():
        if len(subs) > 1:
            result.add("warning", "subsystem_overlap",
                f"Component '{comp}' is assigned to multiple subsystems: {', '.join(subs)}.",
                hint="Each component should belong to exactly one subsystem.")


def check_data_ref_valid(spec: dict, data_spec: Optional[dict], result: LayerResult):
    """Warn if data flow steps reference non-existent DataSpec entities."""
    if not data_spec:
        return
    
    entity_names = {e["name"] for e in data_spec.get("entities", [])}
    for flow in spec.get("dataFlow", []):
        for step in flow.get("steps", []):
            data_ref = step.get("dataRef", "")
            if data_ref and data_ref not in entity_names:
                result.add("warning", "data_ref_missing",
                    f"Flow '{flow['id']}' step references data '{data_ref}' which is not a defined DataSpec entity.",
                    hint=f"Add '{data_ref}' to DataSpec or correct the dataRef.")


def check_component_responsibility_count(spec: dict, result: LayerResult):
    """Warn if a component has too many responsibilities (>5)."""
    for comp in spec.get("components", []):
        resps = comp.get("responsibilities", [])
        if len(resps) > 8:
            result.add("warning", "component_responsibility_count",
                f"Component '{comp['id']}' has {len(resps)} responsibilities — consider splitting.",
                hint="A component with >5 responsibilities may be doing too much. Consider splitting into multiple components.")


def check_data_flow_step_count(spec: dict, result: LayerResult):
    """Warn if a data flow has too many steps (>10)."""
    for flow in spec.get("dataFlow", []):
        steps = flow.get("steps", [])
        if len(steps) > 15:
            result.add("warning", "flow_step_count",
                f"Flow '{flow['id']}' has {len(steps)} steps — consider splitting.",
                hint="A data flow with >10 steps may be too complex. Consider splitting into multiple flows.")


def check_external_component_count(spec: dict, result: LayerResult):
    """Warn if too many components are external (>30% of total)."""
    components = spec.get("components", [])
    if not components:
        return
    external_count = sum(1 for c in components if c.get("visibility") == "external")
    if external_count > len(components) * 0.5:
        result.add("warning", "external_component_count",
            f"{external_count}/{len(components)} components ({external_count/len(components):.0%}) are external.",
            hint="Too many external components may indicate over-exposure. Review which components truly need to be external.")


def check_dependency_depth(spec: dict, result: LayerResult):
    """Warn if any component has a dependency chain >3 levels deep."""
    components = spec.get("components", [])
    comp_deps = {c["id"]: c.get("dependencies", []) for c in components}
    
    def get_depth(comp_id, visited=None):
        if visited is None:
            visited = set()
        if comp_id in visited:
            return 0  # Circular, stop
        visited.add(comp_id)
        deps = comp_deps.get(comp_id, [])
        if not deps:
            return 0
        return 1 + max(get_depth(d, visited.copy()) for d in deps)
    
    for comp_id in comp_deps:
        depth = get_depth(comp_id)
        if depth > 5:
            result.add("warning", "dependency_depth",
                f"Component '{comp_id}' has a dependency chain of {depth} levels.",
                hint="Deep dependency chains can make the system hard to understand and maintain.")


def check_isolated_components(spec: dict, result: LayerResult):
    """Warn if a component has no dependencies AND no dependents (isolated)."""
    components = spec.get("components", [])
    comp_ids = {c["id"] for c in components}
    
    # Build set of components that are depended upon
    depended_upon = set()
    for c in components:
        for dep in c.get("dependencies", []):
            depended_upon.add(dep)
    
    for c in components:
        cid = c["id"]
        has_deps = len(c.get("dependencies", [])) > 0
        is_depended_on = cid in depended_upon
        if not has_deps and not is_depended_on:
            result.add("warning", "isolated_component",
                f"Component '{cid}' is isolated: no dependencies and no dependents.",
                hint="An isolated component may indicate a design issue — consider whether it truly belongs in the architecture or should be merged.")


def check_flow_descriptions(spec: dict, result: LayerResult):
    """Warn if data flow descriptions are empty."""
    for flow in spec.get("dataFlow", []):
        desc = flow.get("description", "")
        if not desc or not desc.strip():
            result.add("warning", "flow_empty_description",
                f"Flow '{flow['id']}' has an empty description.",
                hint="Every data flow should have a one-sentence description explaining its purpose.")


def check_flow_data_refs(spec: dict, result: LayerResult):
    """Warn if flow steps have empty dataRef fields."""
    for flow in spec.get("dataFlow", []):
        for i, step in enumerate(flow.get("steps", [])):
            data_ref = step.get("dataRef", "")
            if data_ref is not None and not data_ref.strip():
                result.add("warning", "flow_step_empty_data_ref",
                    f"Flow '{flow['id']}' step {i+1} ({step.get('componentRef', '?')}) has an empty dataRef.",
                    hint="Name the data entity or payload moving through this step.")


def check_vague_responsibilities(spec: dict, result: LayerResult):
    """Warn if a component has only one responsibility that is vague/generic."""
    vague_patterns = [
        r"\bconsist(?:ent|ently)\b", r"\bacross all\b", r"\bthe system\b",
        r"\bprovide\s+(a |an )?\b", r"\bhandle\s+(all |the |any )?\b",
        r"\bmanage\s+(the |all |any )?\b", r"\bensure\s+(that |the |all )?\b",
    ]
    import re
    
    for comp in spec.get("components", []):
        resps = comp.get("responsibilities", [])
        if len(resps) == 1:
            resp_lower = resps[0].lower()
            for pattern in vague_patterns:
                if re.search(pattern, resp_lower):
                    result.add("warning", "vague_responsibility",
                        f"Component '{comp['id']}' has a single vague responsibility: '{resps[0][:80]}...'.",
                        hint="Break into specific, actionable responsibilities. Avoid generic statements like 'consistent error handling across all components'.")
                    break


def check_inline_req_refs_in_responsibilities(spec: dict, result: LayerResult):
    """Warn if responsibilities contain text that looks like non-standard refs (e.g. 'key flow 9b')."""
    import re
    
    # Patterns that look like refs but aren't REQ/NFR/GL
    non_standard_patterns = [
        (r"\bkey\s+flow\s+\w+\b", "key flow references"),
        (r"\bflow\s+\d+[a-z]?\b", "flow number references"),
        (r"\bsection\s+\d+\b", "section references"),
    ]
    
    for comp in spec.get("components", []):
        for resp in comp.get("responsibilities", []):
            for pattern, label in non_standard_patterns:
                matches = re.findall(pattern, resp.lower())
                if matches:
                    result.add("warning", "inline_ref_in_responsibility",
                        f"Component '{comp['id']}' responsibility references '{matches[0]}' — use reqRefs/nfrRefs arrays instead.",
                        hint="Move requirement references to the reqRefs/nfrRefs arrays. Use glossaryRefs for term references.")


def check_components_in_data_flows(spec: dict, result: LayerResult):
    """Warn if a component is not referenced in any data flow step."""
    components = spec.get("components", [])
    comp_ids = {c["id"] for c in components}
    
    # Collect all componentRefs from data flow steps
    flow_components = set()
    for flow in spec.get("dataFlow", []):
        for step in flow.get("steps", []):
            ref = step.get("componentRef")
            if ref:
                flow_components.add(ref)
    
    for cid in comp_ids:
        if cid not in flow_components:
            result.add("warning", "component_not_in_flow",
                f"Component '{cid}' is not referenced in any data flow step.",
                hint="Either add this component to a relevant data flow or remove it from the architecture if it's not part of the data pipeline.")


def check_cross_spec_versions(spec: dict, data_spec: Optional[dict], api_spec: Optional[dict], result: LayerResult):
    """Warn if dataSpecVersion/apiSpecVersion don't match loaded specs."""
    pinned_data = spec.get("dataSpecVersion")
    pinned_api = spec.get("apiSpecVersion")
    
    if pinned_data and data_spec:
        if pinned_data != data_spec.get("version"):
            result.add("warning", "dataspec_version_mismatch",
                f"archspec.dataSpecVersion='{pinned_data}' does not match dataspec.version='{data_spec.get('version')}'.",
                hint="Update dataSpecVersion to match the DataSpec's version.")
    
    if pinned_api and api_spec:
        if pinned_api != api_spec.get("version"):
            result.add("warning", "apispec_version_mismatch",
                f"archspec.apiSpecVersion='{pinned_api}' does not match apispec.version='{api_spec.get('version')}'.",
                hint="Update apiSpecVersion to match the ApiSpec's version.")


def check_glossary_refs(spec: dict, glossary: Optional[dict], result: LayerResult):
    """Warn if components/flows/constraints have no glossaryRefs.
    If a glossary is provided, also validate that refs point to valid GL-NNN IDs."""
    gl_ids = set()
    if glossary:
        gl_ids = {t["id"] for t in glossary.get("terms", [])}
    
    def validate_refs(refs, label, name):
        if not refs:
            return False  # No refs at all
        for ref in refs:
            if gl_ids and ref not in gl_ids:
                result.add("error", "glossary_ref_missing",
                    f"{label} '{name}': glossaryRef '{ref}' not found in Glossary.",
                    hint=f"Add a glossary entry with id='{ref}' or correct the reference.")
        return True
    
    # Warn: components with no glossaryRefs at all
    for comp in spec.get("components", []):
        refs = comp.get("glossaryRefs", [])
        if not refs:
            result.add("warning", "glossary_ref_missing_component",
                f"Component '{comp['id']}' has no glossaryRefs.",
                hint="Link this component's key concepts to glossary entries (GL-NNN) for cross-spec traceability.")
        validate_refs(refs, "Component", comp["id"])
    
    # Warn: flows with no glossaryRefs at all
    for flow in spec.get("dataFlow", []):
        refs = flow.get("glossaryRefs", [])
        if not refs:
            result.add("warning", "glossary_ref_missing_flow",
                f"Flow '{flow['id']}' has no glossaryRefs.",
                hint="Link this flow's data entities to glossary entries (GL-NNN) for cross-spec traceability.")
        validate_refs(refs, "Flow", flow["id"])
    
    # Warn: constraints with no glossaryRefs at all
    for con in spec.get("constraints", []):
        refs = con.get("glossaryRefs", [])
        if not refs:
            result.add("warning", "glossary_ref_missing_constraint",
                f"Constraint '{con['id']}' has no glossaryRefs.",
                hint="Link this constraint's key concepts to glossary entries (GL-NNN) for cross-spec traceability.")
        validate_refs(refs, "Constraint", con["id"])

# ── Runner ────────────────────────────────────────────────────────────────────

def run_lint(spec: dict, schema_path: Optional[Path],
             goal: Optional[dict], strict: bool,
             glossary: Optional[dict] = None,
             data_spec: Optional[dict] = None,
             api_spec: Optional[dict] = None) -> LayerResult:
    result = LayerResult()

    # JSON Schema validation (auto-generated from schema)
    if schema_path:
        schema = json.loads(Path(schema_path).read_text())
        schema_issues = SchemaValidator(schema).validate(spec)
        for issue in schema_issues:
            result.add(issue.severity, issue.category, issue.message, issue.hint)

    # ID format validation
    validate_spec_ids(spec, {
        "components": "comp",
        "dataFlow": "flw",
        "constraints": "con",
    }, result)

    # 
    # GoalSpec cross-checks
    if goal:
        check_project_match(spec, goal, result)
        check_version_pins(spec, goal, result)

    # Structural checks
    component_ids = check_components(spec, result)
    check_subsystems(spec, component_ids, result)
    check_data_flows(spec, component_ids, result)
    check_constraints(spec, result)

    # Cross-spec ref resolution
    check_req_nfr_refs(spec, goal, result)
    check_fr_coverage(spec, goal, result)

    # Quality checks (new)
    check_isolated_components(spec, result)
    check_flow_descriptions(spec, result)
    check_flow_data_refs(spec, result)
    check_vague_responsibilities(spec, result)
    check_inline_req_refs_in_responsibilities(spec, result)
    check_components_in_data_flows(spec, result)
    check_cross_spec_versions(spec, data_spec, api_spec, result)
    check_glossary_refs(spec, glossary, result)

    if strict:
        for w in result.warnings:
            w.severity = "error"
            result.errors.append(w)
        result.warnings.clear()

    return result


# ── Output
# Uses shared.print_human and shared.print_json_output


def main():
    parser = argparse.ArgumentParser(description="Lint an ArchSpec JSON.")
    parser.add_argument("input", help="Path to archspec JSON")
    parser.add_argument("--schema", help="Path to archspec.schema.json")
    parser.add_argument("--goal",   help="Path to goalspec JSON for cross-spec checks")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--json",   action="store_true", help="Output as JSON")
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
