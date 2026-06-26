#!/usr/bin/env python3
"""
lint_goalspec.py — Validate a GoalSpec JSON against its schema and semantic rules.

What this catches that JSON Schema alone cannot:
  - Duplicate REQ/NFR/US/SC IDs
  - Non-sequential ID numbering (gaps)
  - REQ-IDs referenced in stories that don't exist
  - FR/NFR refs in success criteria that don't exist
  - Success criteria with no refs at all
  - NFRs with TBD Scale or Meter at confirmed status
  - Objective not re-confirmed after completion
  - Actors in stories inconsistent with actors in requirements
  - FRs not covered by any success criterion
  - FRs not referenced by any user story

Usage:
    python lint_goalspec.py <goalspec.json> [--schema goalspec.schema.json] [--strict] [--json]
"""

import json
import sys
import argparse
import re
from pathlib import Path
from typing import Optional
from shared import extract_ids, Issue, LayerResult, print_human, print_json_output, validate_spec_ids, find_duplicates, validate_sequential, validate_project_and_version
from schema_validator import SchemaValidator


# ── Helpers ───────────────────────────────────────────────────────────────────
# ── Semantic checks ───────────────────────────────────────────────────────────

def check_objective(spec: dict, result: LayerResult):
    obj = spec["objective"]
    status = spec.get("status", "draft")

    # Objective not re-confirmed at non-draft status
    if status in ("review", "confirmed") and not obj.get("confirmedAfterCompletion", False):
        result.add("warning", "objective_unconfirmed",
            f"Spec status is '{status}' but objective has not been re-confirmed after completion.",
            hint="Re-read the objective, confirm it still accurately describes the project, and set confirmedAfterCompletion: true.")

    # Smell: objective mentions technology keywords
    tech_smells = ["fastapi", "flask", "django", "postgres", "mysql", "redis",
                   "docker", "kubernetes", "lambda", "s3", "sqlite", "mongodb",
                   "llama.cpp", "openrouter", "pytorch", "tensorflow"]
    text = (obj.get("statement", "") + " " + obj.get("problem", "")).lower()
    found = [t for t in tech_smells if t in text]
    if found:
        result.add("warning", "objective_implementation_leak",
            f"Objective may contain implementation details: {found}.",
            hint="Objective must describe what and why, not how. Move technology choices to architecture.")


def check_functional_requirements(spec: dict, result: LayerResult) -> set[str]:
    frs = spec.get("functionalRequirements", [])
    ids = extract_ids(frs, "id")

    find_duplicates(ids, "REQ", result)
    validate_sequential(ids, "REQ", result)

    # Smell: description contains measurable thresholds
    threshold_pattern = re.compile(r"\d+\s*(ms|MB|GB|%|rps|req|second|minute|hour)", re.IGNORECASE)
    for fr in frs:
        if threshold_pattern.search(fr.get("description", "")):
            result.add("warning", "fr_contains_threshold",
                f"{fr['id']}: description contains a measurable threshold.",
                hint="Move thresholds to an NFR. FRs describe capability; NFRs describe quality.")

        # Smell: description sounds like implementation
        impl_smells = ["use ", "using ", "call ", "via ", "with ", "implement", "library", "framework"]
        desc_lower = fr.get("description", "").lower()
        if any(s in desc_lower for s in impl_smells):
            result.add("warning", "fr_implementation_smell",
                f"{fr['id']}: description may contain implementation detail.",
                hint="FRs must describe observable behaviour, not how it is achieved.")

    return set(ids)


def check_nfrs(spec: dict, result: LayerResult) -> set[str]:
    nfrs = spec.get("nonFunctionalRequirements", [])
    ids = extract_ids(nfrs, "id")

    find_duplicates(ids, "NFR", result)
    validate_sequential(ids, "NFR", result)

    status = spec.get("status", "draft")

    for nfr in nfrs:
        nid = nfr["id"]

        # TBD Scale/Meter at confirmed status is an error
        if status == "confirmed":
            if nfr.get("scale", "").upper().startswith("TBD"):
                result.add("error", "nfr_tbd_at_confirmed",
                    f"{nid}: Scale is TBD but spec status is 'confirmed'.",
                    hint="Define Scale before marking the spec confirmed.")
            if nfr.get("meter", "").upper().startswith("TBD"):
                result.add("error", "nfr_tbd_at_confirmed",
                    f"{nid}: Meter is TBD but spec status is 'confirmed'.",
                    hint="Define Meter before marking the spec confirmed.")

        # TBD Scale/Meter at review is a warning
        elif status == "review":
            if nfr.get("scale", "").upper().startswith("TBD"):
                result.add("warning", "nfr_tbd",
                    f"{nid}: Scale is TBD — needs definition before confirmation.",
                    hint="Define Scale and Meter for all NFRs before finalising.")
            if nfr.get("meter", "").upper().startswith("TBD"):
                result.add("warning", "nfr_tbd",
                    f"{nid}: Meter is TBD — needs definition before confirmation.",
                    hint="Define Scale and Meter for all NFRs before finalising.")

        # Must with no Plan and no Wish — missing levels warning (not at draft)
        if status != "draft":
            if not nfr.get("plan") and not nfr.get("wish"):
                result.add("warning", "nfr_single_level",
                    f"{nid}: only 'must' level defined — Plan and Wish are missing.",
                    hint="Define Plan and Wish levels, or mark them TBD explicitly.")

    return set(ids)


def check_user_stories(spec: dict, req_ids: set[str], result: LayerResult) -> set[str]:
    stories = spec.get("userStories", [])
    ids = extract_ids(stories, "id")
    fr_actors = {fr["actor"] for fr in spec.get("functionalRequirements", [])}

    find_duplicates(ids, "US", result)
    validate_sequential(ids, "US", result)

    story_req_refs = set()

    for story in stories:
        sid = story["id"]

        # reqRefs resolve
        for ref in story.get("reqRefs", []):
            if ref not in req_ids:
                result.add("error", "story_ref_missing",
                    f"{sid}: reqRef '{ref}' does not exist in functionalRequirements.",
                    hint=f"Add '{ref}' to functionalRequirements or correct the reference.")
            story_req_refs.add(ref)

        # Actor consistency — warn if actor doesn't appear in any FR
        actor = story.get("actor", "")
        if actor not in fr_actors:
            result.add("warning", "story_actor_mismatch",
                f"{sid}: actor '{actor}' does not match any actor in functionalRequirements.",
                hint="Ensure actor names are consistent across stories and requirements.")

        # Smell: capability sounds like a feature not a goal
        feature_smells = ["use ", "using ", "implement", "button", "dropdown",
                          "api", "endpoint", "library", "framework", "click"]
        cap_lower = story.get("capability", "").lower()
        if any(s in cap_lower for s in feature_smells):
            result.add("warning", "story_feature_smell",
                f"{sid}: capability may describe a feature rather than a goal.",
                hint="User stories must express what the actor wants to achieve, not how.")

    return story_req_refs


def check_success_criteria(spec: dict, req_ids: set[str], nfr_ids: set[str], result: LayerResult) -> set[str]:
    criteria = spec.get("successCriteria", [])
    ids = extract_ids(criteria, "id")

    find_duplicates(ids, "SC", result)
    validate_sequential(ids, "SC", result)

    sc_covered_reqs = set()
    sc_covered_nfrs = set()

    for sc in criteria:
        scid = sc["id"]
        refs = sc.get("refs", {})
        req_refs = refs.get("reqRefs", [])
        nfr_refs = refs.get("nfrRefs", [])

        # Must reference at least one FR or NFR
        if not req_refs and not nfr_refs:
            result.add("error", "sc_no_refs",
                f"{scid}: success criterion has no FR or NFR references.",
                hint="Every criterion must map to at least one REQ-ID or NFR-ID.")

        # Refs must resolve
        for ref in req_refs:
            if ref not in req_ids:
                result.add("error", "sc_ref_missing",
                    f"{scid}: reqRef '{ref}' does not exist in functionalRequirements.",
                    hint=f"Add '{ref}' to functionalRequirements or correct the reference.")
            sc_covered_reqs.add(ref)

        for ref in nfr_refs:
            if ref not in nfr_ids:
                result.add("error", "sc_ref_missing",
                    f"{scid}: nfrRef '{ref}' does not exist in nonFunctionalRequirements.",
                    hint=f"Add '{ref}' to nonFunctionalRequirements or correct the reference.")
            sc_covered_nfrs.add(ref)

        # Smell: subjective language
        subjective = ["feel", "feels", "fast", "slow", "good", "happy",
                      "nice", "smooth", "intuitive", "easy", "simple"]
        desc_lower = sc.get("description", "").lower()
        if any(s in desc_lower for s in subjective):
            result.add("warning", "sc_subjective",
                f"{scid}: description may contain subjective language.",
                hint="Success criteria must be binary and independently verifiable.")

    return sc_covered_reqs


def check_coverage(spec: dict, req_ids: set[str], story_req_refs: set[str],
                   sc_covered_reqs: set[str], result: LayerResult):
    """
    Every FR should be:
    - Referenced by at least one user story
    - Gated by at least one success criterion
    """
    for req_id in req_ids:
        if req_id not in story_req_refs:
            result.add("warning", "fr_no_story",
                f"{req_id} is not referenced by any user story.",
                hint="Add a user story that motivates this requirement.")

        if req_id not in sc_covered_reqs:
            result.add("warning", "fr_no_success_criterion",
                f"{req_id} is not gated by any success criterion.",
                hint="Add a success criterion that verifies this requirement is met.")


def check_non_goals(spec: dict, result: LayerResult):
    non_goals = spec.get("nonGoals", [])
    ids = extract_ids(non_goals, "id")

    find_duplicates(ids, "NG", result)
    validate_sequential(ids, "NG", result)

    vague_smells = ["everything", "advanced", "features", "stuff",
                    "things", "all", "etc", "misc"]
    for ng in non_goals:
        cap_lower = ng.get("capability", "").lower()
        if any(s in cap_lower for s in vague_smells):
            result.add("warning", "nongoal_vague",
                f"Non-goal '{ng['capability']}' may be too vague.",
                hint="Name the specific capability being excluded.")

        if len(ng.get("reason", "")) < 10:
            result.add("warning", "nongoal_weak_reason",
                f"Non-goal '{ng['capability']}' has a very short reason.",
                hint="Explain why this is excluded: deferred, out of scope, handled elsewhere.")



def run_lint(spec: dict, schema_path: Optional[Path], strict: bool,
             glossary: Optional[dict] = None) -> LayerResult:
    result = LayerResult()

    # Schema validation (auto-generated from schema)
    if schema_path:
        schema = json.loads(Path(schema_path).read_text())
        schema_issues = SchemaValidator(schema).validate(spec)
        for issue in schema_issues:
            result.add(issue.severity, issue.category, issue.message, issue.hint)

    # Project match and version pinning
    validate_project_and_version(spec, "goalspec", spec, result)

    # ID format validation
    validate_spec_ids({"req": spec.get("functionalRequirements", []), "nfr": spec.get("nonFunctionalRequirements", []), "us": spec.get("userStories", []), "sc": spec.get("successCriteria", []), "ng": spec.get("nonGoals", [])}, result)

    # Semantic checks
    check_objective(spec, result)
    req_ids = check_functional_requirements(spec, result)
    nfr_ids = check_nfrs(spec, result)
    story_req_refs = check_user_stories(spec, req_ids, result)
    sc_covered_reqs = check_success_criteria(spec, req_ids, nfr_ids, result)
    check_coverage(spec, req_ids, story_req_refs, sc_covered_reqs, result)
    check_non_goals(spec, result)
    validate_glossary_refs(glossary, result, [
                ("FR", "glossaryRefs", spec.get("functionalRequirements", [])),
                ("US", "glossaryRefs", spec.get("userStories", [])),
                ("Non-goal", "glossaryRefs", spec.get("nonGoals", [])),
                ("NFR", "glossaryRefs", spec.get("nonFunctionalRequirements", [])),
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
    parser = argparse.ArgumentParser(description="Lint a GoalSpec JSON.")
    parser.add_argument("input", help="Path to goalspec JSON")
    parser.add_argument("--schema", help="Path to goalspec.schema.json")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    path = Path(args.input)
    spec = json.loads(path.read_text())
    schema_path = Path(args.schema) if args.schema else None

    result = run_lint(spec, schema_path, args.strict)

    if args.json:
        print_json_output(result)
    else:
        print_human(result, str(path))

    sys.exit(0 if result.clean else 1)


if __name__ == "__main__":
    main()
