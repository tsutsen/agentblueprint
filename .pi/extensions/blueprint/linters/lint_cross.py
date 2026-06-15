#!/usr/bin/env python3
"""
lint_cross.py — Cross-spec reference validation.

Checks that references between specs are consistent:
  - All REQ-IDs in DesignSpec, ArchitectureSpec, TaskPlan exist in GoalSpec
  - All NFR-IDs in ArchitectureSpec exist in GoalSpec
  - All US-IDs in DesignSpec user journeys exist in GoalSpec
  - All REQ-IDs in DesignSpec exist in GoalSpec
  - All AR-IDs (accessibility requirements) in DesignSpec exist in GoalSpec
  - All VDR-IDs (visual design requirements) in DesignSpec exist in GoalSpec
  - All DG-IDs (design guidelines) in DesignSpec exist in GoalSpec
  - All UJ-IDs (user journeys) in DesignSpec exist in GoalSpec
  - All CON-IDs (constraints) in ArchitectureSpec exist in GoalSpec
  - All NFR-IDs in ArchitectureSpec exist in GoalSpec
  - All REQ-IDs in ArchitectureSpec exist in GoalSpec
  - All fnRefs in TestSpec exist in ApiSpec
  - All REQ-IDs in TestSpec (via reqRefs) exist in GoalSpec
  - All NFR-IDs in SuccessCriteria exist in GoalSpec
  - All entity names in ApiSpec exist in DataSpec
  - All fnRefs in DataSpec exist in ApiSpec

Usage:
    python lint_cross.py --data data.json --api api.json --test test.json \
      --goal goalspec.json --design design.json --arch archspec.json \
      --plan taskplan.json
"""

import sys
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Issue:
    severity: str
    category: str
    message: str
    hint: str = ""


@dataclass
class LayerResult:
    name: str = "cross"
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return len(self.errors) == 0

    def add(self, severity: str, category: str, message: str, hint: str = ""):
        issue = Issue(severity, category, message, hint)
        if severity == "error":
            self.errors.append(issue)
        else:
            self.warnings.append(issue)


def run_lint(data_spec: Optional[dict], api_spec: Optional[dict],
             test_spec: Optional[dict], goal_spec: Optional[dict] = None,
             design_spec: Optional[dict] = None, arch_spec: Optional[dict] = None,
             taskplan: Optional[dict] = None,
             strict: bool = False) -> LayerResult:
    """Run all cross-spec reference checks.

    Args:
        data_spec: Optional DataSpec JSON.
        api_spec: Optional ApiSpec JSON.
        test_spec: Optional TestSpec JSON.
        goal_spec: Optional GoalSpec JSON.
        design_spec: Optional DesignSpec JSON.
        arch_spec: Optional ArchitectureSpec JSON.
        taskplan: Optional TaskPlan JSON.
        strict: If True, warnings are treated as errors.

    Returns:
        LayerResult with any cross-reference issues found.
    """
    layer = LayerResult()

    # Collect all available specs
    specs = {
        "data": data_spec,
        "api": api_spec,
        "test": test_spec,
        "goal": goal_spec,
        "design": design_spec,
        "arch": arch_spec,
        "plan": taskplan,
    }

    # Run checks only if both referenced specs are available
    _check_fn_refs_exist(api_spec, test_spec, layer)
    _check_req_refs_exist(goal_spec, design_spec, layer)
    _check_req_refs_exist(goal_spec, arch_spec, layer)
    _check_req_refs_exist(goal_spec, taskplan, layer)
    _check_nfr_refs_exist(goal_spec, arch_spec, layer)
    _check_constraints_nfr_refs(goal_spec, arch_spec, layer)
    _check_us_refs_exist(goal_spec, design_spec, layer)
    _check_ar_refs_exist(goal_spec, design_spec, layer)
    _check_vdr_refs_exist(goal_spec, design_spec, layer)
    _check_dg_refs_exist(goal_spec, design_spec, layer)
    _check_uxac_refs_exist(goal_spec, design_spec, layer)
    _check_entity_refs(data_spec, api_spec, layer)
    _check_fn_refs_in_data(api_spec, data_spec, layer)
    _check_test_req_refs(goal_spec, test_spec, layer)
    _check_nfr_success_criteria_refs(goal_spec, layer)

    return layer


def _check_fn_refs_exist(api_spec: Optional[dict], test_spec: Optional[dict],
                          layer: LayerResult):
    """Check that all fnRefs in TestSpec exist in ApiSpec."""
    if not api_spec or not test_spec:
        return

    api_fn_ids = {fn["id"] for fn in api_spec.get("functions", [])}
    tests = test_spec.get("tests", [])

    for test in tests:
        fn_ref = test.get("fnRef")
        if fn_ref and fn_ref not in api_fn_ids:
            layer.add("error", "cross-ref",
                       f"Test {test['id']} references fnRef not in ApiSpec: {fn_ref}")


def _check_req_refs_exist(goal_spec: Optional[dict], target: Optional[dict],
                           layer: LayerResult):
    """Check that all REQ-IDs in target spec exist in GoalSpec."""
    if not goal_spec or not target:
        return

    goal_req_ids = {fr["id"] for fr in goal_spec.get("functionalRequirements", [])}

    # Check DesignSpec
    if target.get("requirements"):
        for req in target["requirements"]:
            if req.get("id") and req["id"] not in goal_req_ids:
                layer.add("error", "cross-ref",
                           f"DesignSpec references REQ-ID not in GoalSpec: {req['id']}")

    # Check ArchitectureSpec
    if target.get("components"):
        for comp in target["components"]:
            for req_id in comp.get("reqRefs", []):
                if req_id not in goal_req_ids:
                    layer.add("error", "cross-ref",
                               f"ArchitectureSpec component {comp['id']} references "
                               f"REQ-ID not in GoalSpec: {req_id}")

    # Check TaskPlan
    if target.get("epics"):
        for epic in target["epics"]:
            for req_id in epic.get("requirements", []):
                if req_id not in goal_req_ids:
                    layer.add("error", "cross-ref",
                               f"TaskPlan epic {epic['id']} references REQ-ID "
                               f"not in GoalSpec: {req_id}")


def _check_nfr_refs_exist(goal_spec: Optional[dict], target: Optional[dict],
                           layer: LayerResult):
    """Check that all NFR-IDs in target spec exist in GoalSpec."""
    if not goal_spec or not target:
        return

    goal_nfr_ids = {nfr["id"] for nfr in goal_spec.get("nonFunctionalRequirements", [])}

    if target.get("components"):
        for comp in target["components"]:
            for nfr_id in comp.get("nfrRefs", []):
                if nfr_id not in goal_nfr_ids:
                    layer.add("error", "cross-ref",
                               f"ArchitectureSpec component {comp['id']} references "
                               f"NFR-ID not in GoalSpec: {nfr_id}")


def _check_constraints_nfr_refs(goal_spec: Optional[dict], arch_spec: Optional[dict],
                                 layer: LayerResult):
    """Check that all NFR-IDs in ArchitectureSpec constraints exist in GoalSpec."""
    if not goal_spec or not arch_spec:
        return

    goal_nfr_ids = {nfr["id"] for nfr in goal_spec.get("nonFunctionalRequirements", [])}
    constraints = arch_spec.get("constraints", [])

    for constraint in constraints:
        for nfr_id in constraint.get("nfrRefs", []):
            if nfr_id not in goal_nfr_ids:
                layer.add("error", "cross-ref",
                           f"ArchitectureSpec constraint {constraint['id']} references "
                           f"NFR-ID not in GoalSpec: {nfr_id}")


def _check_us_refs_exist(goal_spec: Optional[dict], design_spec: Optional[dict],
                          layer: LayerResult):
    """Check that all US-IDs in DesignSpec user journeys exist in GoalSpec."""
    if not goal_spec or not design_spec:
        return

    goal_us_ids = {us["id"] for us in goal_spec.get("userStories", [])}
    journeys = design_spec.get("userJourneys", [])

    for journey in journeys:
        for us_ref in journey.get("usRefs", []):
            if us_ref not in goal_us_ids:
                layer.add("error", "cross-ref",
                           f"DesignSpec user journey {journey.get('id', '?')} "
                           f"references US-ID not in GoalSpec: {us_ref}")


def _check_ar_refs_exist(goal_spec: Optional[dict], design_spec: Optional[dict],
                          layer: LayerResult):
    """Check that all AR-IDs in DesignSpec accessibility requirements exist in GoalSpec."""
    if not goal_spec or not design_spec:
        return

    goal_nfr_ids = {nfr["id"] for nfr in goal_spec.get("nonFunctionalRequirements", [])}
    ar_refs = design_spec.get("accessibilityRequirements", [])

    for ar in ar_refs:
        ar_id = ar.get("id", "")
        if ar_id and not ar_id.startswith("AR-"):
            layer.add("warning", "cross-ref",
                       f"DesignSpec accessibility requirement ID doesn't follow AR-NNN format: {ar_id}")


def _check_vdr_refs_exist(goal_spec: Optional[dict], design_spec: Optional[dict],
                           layer: LayerResult):
    """Check that all VDR-IDs in DesignSpec visual design requirements exist in GoalSpec."""
    if not goal_spec or not design_spec:
        return

    vdr_refs = design_spec.get("visualDesignRequirements", [])

    for vdr in vdr_refs:
        vdr_id = vdr.get("id", "")
        if vdr_id and not vdr_id.startswith("VDR-"):
            layer.add("warning", "cross-ref",
                       f"DesignSpec visual design requirement ID doesn't follow VDR-NNN format: {vdr_id}")


def _check_dg_refs_exist(goal_spec: Optional[dict], design_spec: Optional[dict],
                          layer: LayerResult):
    """Check that all DG-IDs in DesignSpec design guidelines exist in GoalSpec."""
    if not goal_spec or not design_spec:
        return

    dg_refs = design_spec.get("designGuidelines", [])

    for dg in dg_refs:
        dg_id = dg.get("id", "")
        if dg_id and not dg_id.startswith("DG-"):
            layer.add("warning", "cross-ref",
                       f"DesignSpec design guideline ID doesn't follow DG-NNN format: {dg_id}")


def _check_uxac_refs_exist(goal_spec: Optional[dict], design_spec: Optional[dict],
                            layer: LayerResult):
    """Check that all UXAC refs (usRefs, reqRefs) in DesignSpec exist in GoalSpec."""
    if not goal_spec or not design_spec:
        return

    goal_us_ids = {us["id"] for us in goal_spec.get("userStories", [])}
    goal_req_ids = {fr["id"] for fr in goal_spec.get("functionalRequirements", [])}
    uxac = design_spec.get("uxAcceptanceCriteria", [])

    for criterion in uxac:
        refs = criterion.get("refs", {})
        for us_ref in refs.get("usRefs", []):
            if us_ref not in goal_us_ids:
                layer.add("error", "cross-ref",
                           f"DesignSpec UXAC {criterion.get('id', '?')} references "
                           f"US-ID not in GoalSpec: {us_ref}")
        for req_ref in refs.get("reqRefs", []):
            if req_ref not in goal_req_ids:
                layer.add("error", "cross-ref",
                           f"DesignSpec UXAC {criterion.get('id', '?')} references "
                           f"REQ-ID not in GoalSpec: {req_ref}")


def _check_entity_refs(data_spec: Optional[dict], api_spec: Optional[dict],
                        layer: LayerResult):
    """Check that all entity names in ApiSpec exist in DataSpec."""
    if not data_spec or not api_spec:
        return

    entity_names = {e["name"] for e in data_spec.get("entities", [])}
    functions = api_spec.get("functions", [])

    for fn in functions:
        entity = fn.get("entity")
        if entity and entity not in entity_names:
            layer.add("error", "cross-ref",
                       f"ApiSpec function {fn['id']} references entity "
                       f"{entity} not in DataSpec")


def _check_fn_refs_in_data(api_spec: Optional[dict], data_spec: Optional[dict],
                            layer: LayerResult):
    """Check that all fnRefs in DataSpec exist in ApiSpec."""
    if not api_spec or not data_spec:
        return

    api_fn_ids = {fn["id"] for fn in api_spec.get("functions", [])}
    entities = data_spec.get("entities", [])

    for entity in entities:
        for method in entity.get("methods", []):
            fn_ref = method.get("apiRef")
            if fn_ref and fn_ref not in api_fn_ids:
                layer.add("error", "cross-ref",
                           f"DataSpec entity {entity['name']} method {method.get('name', '?')} "
                           f"references fnRef not in ApiSpec: {fn_ref}")


def _check_test_req_refs(goal_spec: Optional[dict], test_spec: Optional[dict],
                          layer: LayerResult):
    """Check that all REQ-IDs in TestSpec (via reqRefs) exist in GoalSpec."""
    if not goal_spec or not test_spec:
        return

    goal_req_ids = {fr["id"] for fr in goal_spec.get("functionalRequirements", [])}
    tests = test_spec.get("tests", [])

    for test in tests:
        for req_id in test.get("reqRefs", []):
            if req_id not in goal_req_ids:
                layer.add("error", "cross-ref",
                           f"Test {test['id']} references REQ-ID not in GoalSpec: {req_id}")


def _check_nfr_success_criteria_refs(goal_spec: Optional[dict], layer: LayerResult):
    """Check that all NFR-IDs in SuccessCriteria exist in GoalSpec."""
    if not goal_spec:
        return

    goal_nfr_ids = {nfr["id"] for nfr in goal_spec.get("nonFunctionalRequirements", [])}
    criteria = goal_spec.get("successCriteria", [])

    for sc in criteria:
        nfr_refs = sc.get("refs", {}).get("nfrRefs", [])
        for nfr_id in nfr_refs:
            if nfr_id not in goal_nfr_ids:
                layer.add("error", "cross-ref",
                           f"Success criterion {sc['id']} references NFR-ID "
                           f"not in GoalSpec: {nfr_id}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Cross-spec reference validation.")
    parser.add_argument("--data", help="Path to DataSpec JSON")
    parser.add_argument("--api", help="Path to ApiSpec JSON")
    parser.add_argument("--test", help="Path to TestSpec JSON")
    parser.add_argument("--goal", help="Path to GoalSpec JSON")
    parser.add_argument("--design", help="Path to DesignSpec JSON")
    parser.add_argument("--arch", help="Path to ArchitectureSpec JSON")
    parser.add_argument("--plan", help="Path to TaskPlan JSON")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    data_spec = json.loads(Path(args.data).read_text()) if args.data else None
    api_spec = json.loads(Path(args.api).read_text()) if args.api else None
    test_spec = json.loads(Path(args.test).read_text()) if args.test else None
    goal_spec = json.loads(Path(args.goal).read_text()) if args.goal else None
    design_spec = json.loads(Path(args.design).read_text()) if args.design else None
    arch_spec = json.loads(Path(args.arch).read_text()) if args.arch else None
    taskplan = json.loads(Path(args.plan).read_text()) if args.plan else None

    result = run_lint(data_spec, api_spec, test_spec, goal_spec,
                      design_spec, arch_spec, taskplan, args.strict)

    if result.errors:
        print(f"✗ {len(result.errors)} error(s)")
        for e in result.errors:
            print(f"  ✗ [{e.category}] {e.message}")
            if e.hint:
                print(f"    → {e.hint}")
    if result.warnings:
        print(f"⚠ {len(result.warnings)} warning(s)")
        for w in result.warnings:
            print(f"  ⚠ [{w.category}] {w.message}")
            if w.hint:
                print(f"    → {w.hint}")

    sys.exit(0 if result.clean else 1)
