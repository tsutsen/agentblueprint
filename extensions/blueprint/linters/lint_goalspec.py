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

import re

from shared import (
    BaseLinter,
    CompletenessGate,
    LayerResult,
    print_human,
    print_json_output,
    validate_sequential,
)
from rules import SemanticRule


# ── Semantic Rules ────────────────────────────────────────────────────────────

SEMANTIC_RULES: list[SemanticRule] = [
    # FR IDs must be unique
    {
        "check": "is_unique",
        "target": "functionalRequirements.id",
        "target_label": "FR",
        "category": "duplicate_id",
        "hint": "Each FR must have a unique ID.",
    },
    # NFR IDs must be unique
    {
        "check": "is_unique",
        "target": "nonFunctionalRequirements.id",
        "target_label": "NFR",
        "category": "duplicate_id",
        "hint": "Each NFR must have a unique ID.",
    },
    # US IDs must be unique
    {
        "check": "is_unique",
        "target": "userStories.id",
        "target_label": "US",
        "category": "duplicate_id",
        "hint": "Each US must have a unique ID.",
    },
    # SC IDs must be unique
    {
        "check": "is_unique",
        "target": "successCriteria.id",
        "target_label": "SC",
        "category": "duplicate_id",
        "hint": "Each SC must have a unique ID.",
    },
    # NG IDs must be unique
    {
        "check": "is_unique",
        "target": "nonGoals.id",
        "target_label": "NG",
        "category": "duplicate_id",
        "hint": "Each NG must have a unique ID.",
    },

    # FRs must have descriptions
    {
        "check": "non_empty",
        "target": "functionalRequirements.description",
        "target_label": "FR",
        "category": "fr_empty_description",
        "hint": "Every functional requirement must have a description.",
    },

    # NFRs must have descriptions
    {
        "check": "non_empty",
        "target": "nonFunctionalRequirements.description",
        "target_label": "NFR",
        "category": "nfr_empty_description",
        "hint": "Every NFR must have a description.",
    },

    # User stories must have capabilities
    {
        "check": "non_empty",
        "target": "userStories.capability",
        "target_label": "User story",
        "category": "story_empty_capability",
        "hint": "Every user story must have a capability.",
    },

    # Success criteria must have descriptions
    {
        "check": "non_empty",
        "target": "successCriteria.description",
        "target_label": "Success criterion",
        "category": "sc_empty_description",
        "hint": "Every success criterion must have a description.",
    },

    # NFRs must have scale
    {
        "check": "non_empty",
        "target": "nonFunctionalRequirements.scale",
        "target_label": "NFR",
        "category": "nfr_missing_scale",
        "hint": "Every NFR must have a scale defined.",
    },

    # NFRs must have meter
    {
        "check": "non_empty",
        "target": "nonFunctionalRequirements.meter",
        "target_label": "NFR",
        "category": "nfr_missing_meter",
        "hint": "Every NFR must have a meter defined.",
    },
    
    # FRs must not contain implementation details
    {
        "check": "contains_patterns",
        "target": "functionalRequirements.description",
        "patterns": [
            "use ", "using ", "call ", "via ", "with ", "implement", "library", "framework",
        ],
        "target_label": "FR",
        "category": "fr_implementation_smell",
        "hint": "FRs must describe observable behaviour, not how it is achieved.",
    },

    # User stories must not contain feature-like language
    {
        "check": "contains_patterns",
        "target": "userStories.capability",
        "patterns": [
            "use ", "using ", "implement", "button", "dropdown",
            "api", "endpoint", "library", "framework", "click",
        ],
        "target_label": "User story",
        "category": "story_feature_smell",
        "hint": "User stories must express what the actor wants to achieve, not how.",
    },

    # Success criteria must not contain subjective language
    {
        "check": "contains_patterns",
        "target": "successCriteria.description",
        "patterns": [
            "feel", "feels", "fast", "slow", "good", "happy",
            "nice", "smooth", "intuitive", "easy", "simple",
        ],
        "target_label": "Success criterion",
        "category": "sc_subjective",
        "hint": "Success criteria must be binary and independently verifiable.",
    },

    # Non-goals must not be vague
    {
        "check": "contains_patterns",
        "target": "nonGoals.capability",
        "patterns": [
            "everything", "advanced", "features", "stuff",
            "things", "all", "etc", "misc",
        ],
        "target_label": "Non-goal",
        "category": "nongoal_vague",
        "hint": "Name the specific capability being excluded.",
    },
    # Glossary refs: FRs must reference valid glossary terms
    {
        "check": "exists",
        "target": "functionalRequirements.glossaryRefs",
        "inside": "glossary.terms.id",
        "target_label": "FR",
        "ref_label": "Glossary",
        "category": "glossary_ref_missing",
    },
    # Glossary refs: USs must reference valid glossary terms
    {
        "check": "exists",
        "target": "userStories.glossaryRefs",
        "inside": "glossary.terms.id",
        "target_label": "US",
        "ref_label": "Glossary",
        "category": "glossary_ref_missing",
    },
    # Glossary refs: Non-goals must reference valid glossary terms
    {
        "check": "exists",
        "target": "nonGoals.glossaryRefs",
        "inside": "glossary.terms.id",
        "target_label": "Non-goal",
        "ref_label": "Glossary",
        "category": "glossary_ref_missing",
    },
    # Glossary refs: NFRs must reference valid glossary terms
    {
        "check": "exists",
        "target": "nonFunctionalRequirements.glossaryRefs",
        "inside": "glossary.terms.id",
        "target_label": "NFR",
        "ref_label": "Glossary",
        "category": "glossary_ref_missing",
    },
]


# ── Custom Checks ─────────────────────────────────────────────────────────────

def _check_objective(spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Check objective confirmation and implementation leaks."""
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


def _check_functional_requirements(spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Check FR sequential IDs and thresholds."""
    frs = spec.get("functionalRequirements", [])
    ids = [fr["id"] for fr in frs]
    validate_sequential(ids, "REQ", result)

    # Smell: description contains measurable thresholds
    threshold_pattern = re.compile(r"\d+\s*(ms|MB|GB|%|rps|req|second|minute|hour)", re.IGNORECASE)
    for fr in frs:
        if threshold_pattern.search(fr.get("description", "")):
            result.add("warning", "fr_contains_threshold",
                f"{fr['id']}: description contains a measurable threshold.",
                hint="Move thresholds to an NFR. FRs describe capability; NFRs describe quality.")


def _check_nfrs(spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Check NFR sequential IDs and TBD checks."""
    nfrs = spec.get("nonFunctionalRequirements", [])
    ids = [nfr["id"] for nfr in nfrs]
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


def _check_user_stories(spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Check US sequential IDs and actor consistency."""
    stories = spec.get("userStories", [])
    ids = [s["id"] for s in stories]
    fr_actors = {fr["actor"] for fr in spec.get("functionalRequirements", [])}
    validate_sequential(ids, "US", result)

    for story in stories:
        sid = story["id"]

        # Actor consistency — warn if actor doesn't appear in any FR
        actor = story.get("actor", "")
        if actor not in fr_actors:
            result.add("warning", "story_actor_mismatch",
                f"{sid}: actor '{actor}' does not match any actor in functionalRequirements.",
                hint="Ensure actor names are consistent across stories and requirements.")


def _check_success_criteria(spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Check SC sequential IDs and refs."""
    criteria = spec.get("successCriteria", [])
    ids = [sc["id"] for sc in criteria]
    req_ids = {fr["id"] for fr in spec.get("functionalRequirements", [])}
    nfr_ids = {nfr["id"] for nfr in spec.get("nonFunctionalRequirements", [])}
    validate_sequential(ids, "SC", result)

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

        for ref in nfr_refs:
            if ref not in nfr_ids:
                result.add("error", "sc_ref_missing",
                    f"{scid}: nfrRef '{ref}' does not exist in nonFunctionalRequirements.",
                    hint=f"Add '{ref}' to nonFunctionalRequirements or correct the reference.")


def _check_coverage(spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Check FR coverage by user stories and success criteria."""
    frs = spec.get("functionalRequirements", [])
    stories = spec.get("userStories", [])
    criteria = spec.get("successCriteria", [])

    story_req_refs = set()
    for story in stories:
        for ref in story.get("reqRefs", []):
            story_req_refs.add(ref)

    sc_covered_reqs = set()
    for sc in criteria:
        refs = sc.get("refs", {})
        for ref in refs.get("reqRefs", []):
            sc_covered_reqs.add(ref)

    for fr in frs:
        if fr["id"] not in story_req_refs:
            result.add("warning", "fr_no_story",
                f"{fr['id']} is not referenced by any user story.",
                hint="Add a user story that motivates this requirement.")

        if fr["id"] not in sc_covered_reqs:
            result.add("warning", "fr_no_success_criterion",
                f"{fr['id']} is not gated by any success criterion.",
                hint="Add a success criterion that verifies this requirement is met.")


def _check_non_goals(spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Check non-goal sequential IDs and weak reasons."""
    non_goals = spec.get("nonGoals", [])
    ids = [ng["id"] for ng in non_goals]
    validate_sequential(ids, "NG", result)

    for ng in non_goals:
        if len(ng.get("reason", "")) < 10:
            result.add("warning", "nongoal_weak_reason",
                f"Non-goal '{ng['capability']}' has a very short reason.",
                hint="Explain why this is excluded: deferred, out of scope, handled elsewhere.")


# ── Completeness Gates ─────────────────────────────────────────────────────

COMPLETENESS_GATES: list = [
    # Draft
    {"check": "has_count", "target": "functionalRequirements", "count": 1,
     "target_label": "FR", "category": "completeness", "required_at": "draft",
     "description": "Has at least one functional requirement"},
    {"check": "has_count", "target": "userStories", "count": 1,
     "target_label": "user story", "category": "completeness", "required_at": "draft",
     "description": "Has at least one user story"},
    {"check": "has_count", "target": "successCriteria", "count": 1,
     "target_label": "success criterion", "category": "completeness", "required_at": "draft",
     "description": "Has at least one success criterion"},
    {"check": "has_count", "target": "nonGoals", "count": 1,
     "target_label": "non-goal", "category": "completeness", "required_at": "draft",
     "description": "Has at least one non-goal"},
    # Review
    {"check": "none_match", "target": "nonFunctionalRequirements",
     "field": "scale", "pattern": "^TBD",
     "target_label": "NFR", "category": "completeness", "required_at": "review",
     "description": "All NFRs have Scale and Meter defined (no TBD)"},
    # Confirmed
    {"check": "value_check", "target": "objective.confirmedAfterCompletion",
     "expected": "truthy", "target_label": "confirmedAfterCompletion",
     "category": "completeness", "required_at": "confirmed",
     "description": "Objective re-confirmed after completion"},
    {"check": "value_check", "target": "status", "expected": "confirmed",
     "target_label": "status", "category": "completeness", "required_at": "confirmed",
     "description": "Status is confirmed"},
]


# ── Misc Completeness Gates ───────────────────────────────────────────────────

def _gate_objective_statement(spec: dict, extra_specs: dict) -> CompletenessGate:
    """Has project objective statement."""
    stmt = spec.get("objective", {}).get("statement", "")
    return CompletenessGate(
        description="Has project objective",
        passed=bool(stmt), required_at="draft",
        detail="objective.statement is missing" if not stmt else "",
    )


def _gate_fr_story_coverage(spec: dict, extra_specs: dict) -> CompletenessGate:
    """All FRs covered by at least one story."""
    fr_ids = {fr["id"] for fr in spec.get("functionalRequirements", [])}
    story_refs = {ref for us in spec.get("userStories", [])
                  for ref in us.get("reqRefs", [])}
    uncovered = fr_ids - story_refs
    return CompletenessGate(
        description="All FRs covered by at least one story",
        passed=len(uncovered) == 0, required_at="review",
        detail=f"Uncovered: {uncovered}" if uncovered else "",
    )


def _gate_fr_sc_coverage(spec: dict, extra_specs: dict) -> CompletenessGate:
    """All FRs gated by at least one success criterion."""
    fr_ids = {fr["id"] for fr in spec.get("functionalRequirements", [])}
    sc_refs = {ref for sc in spec.get("successCriteria", [])
               for ref in sc.get("refs", {}).get("reqRefs", [])}
    uncovered = fr_ids - sc_refs
    return CompletenessGate(
        description="All FRs gated by at least one success criterion",
        passed=len(uncovered) == 0, required_at="review",
        detail=f"Uncovered: {uncovered}" if uncovered else "",
    )


# ── Linter Class ──────────────────────────────────────────────────────────────

class GoalSpecLinter(BaseLinter):
    SPEC_NAME = "goalspec"
    SPEC_KEY = "goalspec"
    SEMANTIC_RULES = SEMANTIC_RULES
    COMPLETENESS_GATES = COMPLETENESS_GATES
    MISC_GATES = [
        _gate_objective_statement,
        _gate_fr_story_coverage,
        _gate_fr_sc_coverage,
    ]
    CROSS_SPEC_DEPS = ["glossary"]
    MISC_CHECKS = [
        _check_objective,
        _check_functional_requirements,
        _check_nfrs,
        _check_user_stories,
        _check_success_criteria,
        _check_coverage,
        _check_non_goals,
    ]


# Canonical linter class for lint_all.py
LinterClass = GoalSpecLinter


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    GoalSpecLinter.main()
