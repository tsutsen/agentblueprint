#!/usr/bin/env python3
"""
lint_all.py — Unified linter for the full SDLC spec suite.

Runs all individual linters in dependency order, then runs cross-spec checks,
then produces a completeness assessment for each spec and the suite as a whole.

Dependency order:
  1. goalspec    (root)
  2. glossary    (← goalspec)
  3. designspec  (← goalspec)
  4. archspec    (← goalspec)
  5. dataspec    (standalone linter)
  6. apispec     (schema validation + cross-check with dataspec)
  7. testspec    (← apispec, dataspec)
  8. taskplan    (← all prior specs)
  9. cross       (dataspec ↔ apispec ↔ testspec)
 10. issues     (← taskplan, requires --epic)
 11. completeness (← all layers)

Completeness gates:
  Each spec has a set of readiness conditions. A spec that fails its gate
  is flagged even if it passes all lint checks. Gates are lifecycle-aware
  (draft / review / confirmed).

Usage:
    python lint_all.py --suite suite.json
    python lint_all.py --goal g.json --arch a.json --data d.json --api api.json
                       [--design design.json] [--glossary gl.json] [--test t.json]
                       [--schemas ./schemas] [--linters ./linters]
                       [--strict] [--json] [--stop-on-error]
"""

import json
import sys
import argparse
import importlib.util
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


# ── Shared types ──────────────────────────────────────────────────────────────

@dataclass
class Issue:
    severity: str
    category: str
    message: str
    hint: str = ""

@dataclass
class CompletenessGate:
    """A single readiness condition for a spec."""
    description: str
    passed: bool
    required_at: str   # "draft" | "review" | "confirmed"
    detail: str = ""

@dataclass
class CompletenessScore:
    spec: str
    status: str           # the spec's own lifecycle status
    gates: list[CompletenessGate] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.gates)

    @property
    def passed(self) -> int:
        return sum(1 for g in self.gates if g.passed)

    @property
    def score_pct(self) -> int:
        return int(100 * self.passed / self.total) if self.total else 0

    @property
    def ready_for_review(self) -> bool:
        return all(g.passed for g in self.gates if g.required_at in ("draft", "review"))

    @property
    def ready_for_confirm(self) -> bool:
        return all(g.passed for g in self.gates)

    @property
    def blocking_gates(self) -> list[CompletenessGate]:
        """Gates that must pass for the current status but haven't."""
        status_order = {"draft": 0, "review": 1, "confirmed": 2}
        current = status_order.get(self.status, 0)
        return [
            g for g in self.gates
            if not g.passed and status_order.get(g.required_at, 0) <= current
        ]

@dataclass
class LayerResult:
    name: str
    skipped: bool = False
    skip_reason: str = ""
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    completeness: Optional[CompletenessScore] = None

    @property
    def clean(self) -> bool:
        return len(self.errors) == 0

    @property
    def all_issues(self):
        return self.errors + self.warnings

    def add(self, severity: str, category: str, message: str, hint: str = ""):
        issue = Issue(severity, category, message, hint)
        if severity == "error":
            self.errors.append(issue)
        else:
            self.warnings.append(issue)

@dataclass
class SuiteResult:
    layers: list[LayerResult] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return all(l.clean for l in self.layers if not l.skipped)

    @property
    def total_errors(self) -> int:
        return sum(len(l.errors) for l in self.layers)

    @property
    def total_warnings(self) -> int:
        return sum(len(l.warnings) for l in self.layers)

    @property
    def completeness_scores(self) -> list[CompletenessScore]:
        return [l.completeness for l in self.layers if l.completeness]


# ── Completeness gates ────────────────────────────────────────────────────────

def gate(desc: str, passed: bool, required_at: str, detail: str = "") -> CompletenessGate:
    return CompletenessGate(description=desc, passed=passed,
                             required_at=required_at, detail=detail)

def assess_goalspec(spec: dict) -> CompletenessScore:
    status = spec.get("status", "draft")
    frs = spec.get("functionalRequirements", [])
    nfrs = spec.get("nonFunctionalRequirements", [])
    stories = spec.get("userStories", [])
    criteria = spec.get("successCriteria", [])
    non_goals = spec.get("nonGoals", [])

    fr_ids = {fr["id"] for fr in frs}
    story_refs = {ref for us in stories for ref in us.get("reqRefs", [])}
    sc_refs = {ref for sc in criteria for ref in sc.get("refs", {}).get("reqRefs", [])}

    tbd_nfrs = [n for n in nfrs if
                str(n.get("scale","")).upper().startswith("TBD") or
                str(n.get("meter","")).upper().startswith("TBD")]

    gates = [
        gate("Has project objective", bool(spec.get("objective", {}).get("statement")), "draft"),
        gate("Has at least one functional requirement", len(frs) >= 1, "draft"),
        gate("Has at least one user story", len(stories) >= 1, "draft"),
        gate("Has at least one success criterion", len(criteria) >= 1, "draft"),
        gate("Has at least one non-goal", len(non_goals) >= 1, "draft"),
        gate("All FRs covered by at least one story", fr_ids <= story_refs, "review",
             detail=f"Uncovered: {fr_ids - story_refs}" if not fr_ids <= story_refs else ""),
        gate("All FRs gated by at least one success criterion", fr_ids <= sc_refs, "review",
             detail=f"Uncovered: {fr_ids - sc_refs}" if not fr_ids <= sc_refs else ""),
        gate("All NFRs have Scale and Meter defined (no TBD)", len(tbd_nfrs) == 0, "review",
             detail=f"TBD NFRs: {[n['id'] for n in tbd_nfrs]}" if tbd_nfrs else ""),
        gate("Objective re-confirmed after completion",
             spec.get("objective", {}).get("confirmedAfterCompletion", False), "confirmed"),
        gate("Status is confirmed", status == "confirmed", "confirmed"),
    ]
    return CompletenessScore(spec="goalspec", status=status, gates=gates)


def assess_glossary(spec: dict) -> CompletenessScore:
    status = spec.get("status", "draft") if "status" in spec else "draft"
    terms = spec.get("terms", [])
    gates = [
        gate("Has at least 3 terms", len(terms) >= 3, "draft"),
        gate("All terms have definitions ≥ 10 chars",
             all(len(t.get("definition","")) >= 10 for t in terms), "draft"),
        gate("Has at least 5 terms", len(terms) >= 5, "review"),
        gate("All terms have examples or related terms",
             all(t.get("examples") or t.get("relatedTerms") for t in terms), "confirmed"),
    ]
    return CompletenessScore(spec="glossary", status=status, gates=gates)


def assess_designspec(spec: dict) -> CompletenessScore:
    status = spec.get("status", "draft")
    screens = spec.get("screenInventory", [])
    screen_ids = {s["id"] for s in screens}
    spec_refs = {s["screenRef"] for s in spec.get("screenSpecs", [])}
    journeys = spec.get("userJourneys", [])
    uxac = spec.get("uxAcceptanceCriteria", [])
    patterns = spec.get("interactionPatterns", [])

    unspecced = screen_ids - spec_refs

    gates = [
        gate("Has design goals", len(spec.get("designGoals", [])) >= 1, "draft"),
        gate("Has at least one persona", len(spec.get("personas", [])) >= 1, "draft"),
        gate("Has at least one user journey", len(journeys) >= 1, "draft"),
        gate("Has screen inventory", len(screens) >= 1, "draft"),
        gate("All screens have specs",
             len(unspecced) == 0, "review",
             detail=f"Missing specs: {unspecced}" if unspecced else ""),
        gate("Has interaction patterns", len(patterns) >= 1, "review"),
        gate("Has UX acceptance criteria", len(uxac) >= 1, "review"),
        gate("Has visual design requirements",
             len(spec.get("visualDesignRequirements", [])) >= 1, "review"),
        gate("Has accessibility requirements",
             len(spec.get("accessibilityRequirements", [])) >= 1, "review"),
        gate("Has design system components",
             len(spec.get("designSystem", {}).get("components", [])) >= 1, "confirmed"),
        gate("All journeys reference user stories",
             all(len(j.get("usRefs", [])) >= 1 for j in journeys), "confirmed"),
    ]
    return CompletenessScore(spec="designspec", status=status, gates=gates)


def assess_archspec(spec: dict) -> CompletenessScore:
    status = spec.get("status", "draft")
    components = spec.get("components", [])
    flows = spec.get("dataFlow", [])
    constraints = spec.get("constraints", [])

    comps_with_reqs = [c for c in components if c.get("reqRefs")]
    comps_with_deps_or_dependents = set()
    for c in components:
        for dep in c.get("dependencies", []):
            comps_with_deps_or_dependents.add(c["id"])
            comps_with_deps_or_dependents.add(dep)

    gates = [
        gate("Has system overview summary",
             len(spec.get("overview", {}).get("summary", "")) >= 30, "draft"),
        gate("Has at least one subsystem",
             len(spec.get("overview", {}).get("subsystems", [])) >= 1, "draft"),
        gate("Has at least 2 components", len(components) >= 2, "draft"),
        gate("Has at least one data flow", len(flows) >= 1, "draft"),
        gate("Has at least one constraint", len(constraints) >= 1, "draft"),
        gate("All components have REQ refs",
             len(comps_with_reqs) == len(components), "review",
             detail=f"{len(components) - len(comps_with_reqs)} component(s) missing reqRefs"),
        gate("All components participate in at least one dependency",
             len(comps_with_deps_or_dependents) == len(components), "review",
             detail="Isolated components found" if len(comps_with_deps_or_dependents) < len(components) else ""),
        gate("goalSpecVersion is set", bool(spec.get("goalSpecVersion")), "review"),
        gate("dataSpecVersion is set", bool(spec.get("dataSpecVersion")), "confirmed"),
        gate("apiSpecVersion is set", bool(spec.get("apiSpecVersion")), "confirmed"),
    ]
    return CompletenessScore(spec="archspec", status=status, gates=gates)


def assess_dataspec(spec: dict) -> CompletenessScore:
    status = spec.get("status", "draft") if "status" in spec else "draft"
    entities = spec.get("entities", [])
    relationships = spec.get("relationships", [])
    enums = spec.get("enums", [])

    entities_with_desc = [e for e in entities if e.get("description")]
    entities_with_examples = [
        e for e in entities
        if any(f.get("example") for f in e.get("fields", []))
    ]
    rel_participants = set()
    for r in relationships:
        rel_participants.add(r.get("from"))
        rel_participants.add(r.get("to"))
    entity_names = {e["name"] for e in entities}
    orphans = entity_names - rel_participants

    # Find entities only referenced as field types, never in relationships
    type_referenced = set()
    for entity in entities:
        for field_def in entity.get("fields", []):
            base = field_def.get("type", "").replace("[]", "")
            if base in entity_names and base != entity["name"]:
                type_referenced.add(base)
    standalone = type_referenced - rel_participants

    # Orphan percentage
    orphan_pct = (len(orphans) / len(entities) * 100) if entities else 0

    gates = [
        gate("Has at least one entity", len(entities) >= 1, "draft"),
        gate("Has at least one relationship", len(relationships) >= 1, "draft"),
        gate("All entities have descriptions",
             len(entities_with_desc) == len(entities), "review",
             detail=f"{len(entities)-len(entities_with_desc)} entity/entities missing descriptions"),
        gate("No orphan entities",
             len(orphans) == 0 or len(entities) <= 1, "review",
             detail=f"Orphans: {orphans}" if orphans and len(entities) > 1 else ""),
        gate("Orphan entities < 20%",
             orphan_pct < 20, "review",
             detail=f"{orphan_pct:.0f}% of entities are orphans ({len(orphans)}/{len(entities)})"),
        gate("All entities have at least one field with an example",
             len(entities_with_examples) == len(entities), "confirmed",
             detail=f"{len(entities)-len(entities_with_examples)} entity/entities missing field examples"),
        gate("No standalone type-only entities",
             len(standalone) == 0 or len(standalone) <= 2, "review",
             detail=f"Standalone type-only entities: {standalone}" if standalone else ""),
        gate("Has enums if domain uses categorical values",
             True, "draft",   # advisory — can't auto-detect need for enums
             detail="Review whether domain categorical values should be enums"),
    ]
    return CompletenessScore(spec="dataspec", status=status, gates=gates)


def assess_apispec(spec: dict, data: Optional[dict] = None) -> CompletenessScore:
    status = spec.get("status", "draft") if "status" in spec else "draft"
    functions = spec.get("functions", [])

    fns_with_desc = [f for f in functions if f.get("description")]
    fns_with_errors = [f for f in functions if f.get("errors")]
    fns_with_entity = [f for f in functions if f.get("entity")]
    fns_pure_declared = [f for f in functions if "pure" in f]

    gates = [
        gate("Has at least one function", len(functions) >= 1, "draft"),
        gate("All functions have descriptions",
             len(fns_with_desc) == len(functions), "review",
             detail=f"{len(functions)-len(fns_with_desc)} function(s) missing descriptions"),
        gate("All functions have documented error conditions",
             len(fns_with_errors) == len(functions), "review",
             detail=f"{len(functions)-len(fns_with_errors)} function(s) with no errors documented"),
        gate("All functions declare entity affinity",
             len(fns_with_entity) == len(functions), "review",
             detail=f"{len(functions)-len(fns_with_entity)} function(s) missing entity field"),
        gate("All functions declare pure/impure",
             len(fns_pure_declared) == len(functions), "confirmed",
             detail=f"{len(functions)-len(fns_pure_declared)} function(s) missing 'pure' field"),
        gate("dataSpecVersion is set", bool(spec.get("dataSpecVersion")), "review"),
    ]
    return CompletenessScore(spec="apispec", status=status, gates=gates)


def assess_testspec(spec: dict, api: Optional[dict] = None) -> CompletenessScore:
    status = spec.get("status", "draft")
    tests = spec.get("tests", [])
    coverage = spec.get("functionCoverage", [])

    fn_ids = {fn["id"] for fn in api.get("functions", [])} if api else set()
    tested_fns = {t["fnRef"] for t in tests if t.get("fnRef")}
    error_tests = [t for t in tests if t.get("category") == "error-path"]
    coverage_fns = {c["fnRef"] for c in coverage}

    all_out_of_scope = all(c.get("outOfScope") for c in coverage)
    verification = spec.get("verificationStatus", "pending")

    gates = [
        gate("Has at least one test", len(tests) >= 1, "draft"),
        gate("Has functionCoverage summary", len(coverage) >= 1, "draft"),
        gate("Has error-path tests", len(error_tests) >= 1, "review"),
        gate("All ApiSpec functions have tests",
             fn_ids <= tested_fns, "review",
             detail=f"Untested: {fn_ids - tested_fns}" if api and not fn_ids <= tested_fns else ""),
        gate("All functions have out-of-scope declarations",
             all_out_of_scope, "review",
             detail="Some functionCoverage entries missing outOfScope" if not all_out_of_scope else ""),
        gate("functionCoverage covers all tested functions",
             tested_fns <= coverage_fns, "review",
             detail=f"Missing: {tested_fns - coverage_fns}" if not tested_fns <= coverage_fns else ""),
        gate("apiSpecVersion is set", bool(spec.get("apiSpecVersion")), "review"),
        gate("Independent verification completed",
             verification == "passed", "confirmed",
             detail=f"verificationStatus is '{verification}'" if verification != "passed" else ""),
    ]
    return CompletenessScore(spec="testspec", status=status, gates=gates)


def assess_taskplan(plan: dict, goal_spec: Optional[dict] = None,
                    design_spec: Optional[dict] = None,
                    arch_spec: Optional[dict] = None) -> CompletenessScore:
    """Completeness gates for TaskPlan.

    Validates that epics cover requirements from GoalSpec, capabilities from
    DesignSpec, and components from ArchitectureSpec.
    """
    epics = plan.get("epics", [])
    milestones = plan.get("milestones", [])

    # Collect all epic text for matching
    epic_texts = []
    for epic in epics:
        text = ' '.join([
            epic.get("title", ""),
            epic.get("summary", ""),
            epic.get("objective", ""),
            " ".join(epic.get("scope", {}).get("inScope", [])),
        ]).lower()
        epic_texts.append(text)

    gates = [
        # Draft: basic structure
        gate("Has at least one milestone", len(milestones) >= 1, "draft"),
        gate("Has at least one epic", len(epics) >= 1, "draft"),
        gate("Every epic covers at least one requirement", all(
            epic.get("requirements") for epic in epics
        ), "draft"),
        gate("All epics assigned to a milestone", all(
            epic.get("milestone") for epic in epics
        ), "draft"),

        # Review: quality and completeness
        gate("All epics have acceptance criteria", all(
            epic.get("acceptanceCriteria") for epic in epics
        ), "review"),
        gate("All epics have scope (inScope + outOfScope)", all(
            epic.get("scope", {}).get("inScope") and epic.get("scope", {}).get("outOfScope")
            for epic in epics
        ), "review"),
        gate("All epics have explicit dependencies", all(
            epic.get("dependencies", {}).get("blockedBy") is not None or
            epic.get("dependencies", {}).get("blocks") is not None
            for epic in epics
        ), "review"),
        gate("Epics are in dependency order", True, "review",
             detail="Dependency order validated by lint_taskplan.py"),
        gate("No circular dependencies", True, "review",
             detail="Circular dependency check validated by lint_taskplan.py"),
        gate("All milestones have demonstrable outcomes", all(
            m.get("outcome") and len(m.get("outcome", "")) >= 10
            for m in milestones
        ), "review"),
        gate("All epics have an objective", all(
            epic.get("objective") for epic in epics
        ), "review"),
        gate("All acceptance criteria are meaningful length", all(
            all(len(ac.strip()) >= 15 for ac in epic.get("acceptanceCriteria", []))
            for epic in epics
        ), "review"),
        gate("All scope items are meaningful length", all(
            all(len(item.strip()) >= 10 for item in epic.get("scope", {}).get("inScope", []))
            and all(len(item.strip()) >= 10 for item in epic.get("scope", {}).get("outOfScope", []))
            for epic in epics
        ), "review"),

        # Cross-spec: GoalSpec coverage
        gate("All GoalSpec requirements covered by epics", True, "review",
             detail="Requirement coverage validated by lint_taskplan.py"),
    ]

    # Cross-spec: DesignSpec capability coverage
    if design_spec:
        capabilities = design_spec.get("capabilities", [])
        if capabilities:
            uncovered = []
            for cap in capabilities:
                cap_name = cap.get("name", "").lower()
                if not cap_name:
                    continue
                if not any(cap_name in text for text in epic_texts):
                    uncovered.append(cap.get("name"))
            gates.append(gate(
                "All DesignSpec capabilities covered by epics",
                len(uncovered) == 0, "review",
                detail=f"Uncovered: {', '.join(uncovered)}" if uncovered else ""
            ))

    # Cross-spec: ArchitectureSpec component coverage
    if arch_spec:
        components = arch_spec.get("components", [])
        if components:
            uncovered = []
            for comp in components:
                comp_name = comp.get("name", "").lower()
                if not comp_name:
                    continue
                if not any(comp_name in text for text in epic_texts):
                    uncovered.append(comp.get("name"))
            gates.append(gate(
                "All ArchitectureSpec components covered by epics",
                len(uncovered) == 0, "review",
                detail=f"Uncovered: {', '.join(uncovered)}" if uncovered else ""
            ))

    if goal_spec:
        gates.append(gate("No epic implements a non-goal", True, "review",
                          detail="Non-goal compliance validated by lint_taskplan.py"))

    status = plan.get("status", "draft")
    return CompletenessScore(spec="taskplan", status=status, gates=gates)


def assess_glossary_full(spec: dict) -> CompletenessScore:
    terms = spec.get("terms", [])
    categories = {t.get("category") for t in terms if t.get("category")}
    has_domain = "domain" in categories

    base = assess_glossary(spec)
    base.gates.append(
        gate("Has domain-category terms", has_domain, "review",
             detail="No terms tagged 'domain' — consider categorising terms")
    )
    return base


# ── Suite-level completeness ──────────────────────────────────────────────────

SPEC_ORDER = ["goalspec", "glossary", "designspec", "archspec",
              "dataspec", "apispec", "testspec", "plan", "issues"]

def suite_completeness_pct(scores: list[CompletenessScore]) -> int:
    if not scores:
        return 0
    total = sum(s.total for s in scores)
    passed = sum(s.passed for s in scores)
    return int(100 * passed / total) if total else 0


# ── Linter loader ─────────────────────────────────────────────────────────────

def load_linter(path: Path):
    spec = importlib.util.spec_from_file_location("linter", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def issues_from_lr(lr) -> tuple[list[Issue], list[Issue]]:
    errors   = [Issue(i.severity, i.category, i.message, getattr(i, 'hint', '')) for i in lr.errors]
    warnings = [Issue(i.severity, i.category, i.message, getattr(i, 'hint', '')) for i in lr.warnings]
    return errors, warnings


# ── Layer runners ─────────────────────────────────────────────────────────────

def _run(name: str, linter_path: Path, fn, strict: bool) -> LayerResult:
    layer = LayerResult(name=name)
    if not linter_path.exists():
        layer.skipped = True
        layer.skip_reason = f"Linter not found: {linter_path}"
        return layer
    try:
        lr = fn(strict)
        layer.errors, layer.warnings = issues_from_lr(lr)
    except Exception as e:
        layer.add("error", "runner_error", f"Linter raised: {e}",
                  hint="Check the linter and spec file for errors.")
    return layer


def run_goalspec(linter_dir, schema_dir, paths, loaded, strict) -> LayerResult:
    if not paths.get("goal"):
        return LayerResult(name="goalspec", skipped=True, skip_reason="No goalspec provided.")
    linter_path = linter_dir / "lint_goalspec.py"
    spec = json.loads(Path(paths["goal"]).read_text())
    schema_path = (schema_dir / "goalspec.schema.json") if schema_dir else None
    mod = load_linter(linter_path)
    layer = _run("goalspec", linter_path,
                 lambda s: mod.run_lint(spec, schema_path, s,
                                        glossary=loaded.get("glossary")), strict)
    layer.completeness = assess_goalspec(spec)
    return layer


def run_glossary(linter_dir, schema_dir, paths, loaded, strict) -> LayerResult:
    if not paths.get("glossary"):
        return LayerResult(name="glossary", skipped=True, skip_reason="No glossary provided.")
    linter_path = linter_dir / "lint_glossary.py"
    spec = json.loads(Path(paths["glossary"]).read_text())
    schema_path = (schema_dir / "glossary.schema.json") if schema_dir else None
    mod = load_linter(linter_path)
    other = {"goal": loaded.get("goal"), "arch": loaded.get("arch"),
             "data": loaded.get("data"), "api":  loaded.get("api")}
    layer = _run("glossary", linter_path, lambda s: mod.run_lint(spec, schema_path, other, s), strict)
    layer.completeness = assess_glossary_full(spec)
    return layer


def run_designspec(linter_dir, schema_dir, paths, loaded, strict) -> LayerResult:
    if not paths.get("design"):
        return LayerResult(name="designspec", skipped=True, skip_reason="No designspec provided.")
    linter_path = linter_dir / "lint_designspec.py"
    spec = json.loads(Path(paths["design"]).read_text())
    schema_path = (schema_dir / "designspec.schema.json") if schema_dir else None
    mod = load_linter(linter_path)
    layer = _run("designspec", linter_path,
                 lambda s: mod.run_lint(spec, schema_path, loaded.get("goal"), s), strict)
    layer.completeness = assess_designspec(spec)
    return layer


def run_archspec(linter_dir, schema_dir, paths, loaded, strict) -> LayerResult:
    if not paths.get("arch"):
        return LayerResult(name="archspec", skipped=True, skip_reason="No archspec provided.")
    linter_path = linter_dir / "lint_archspec.py"
    spec = json.loads(Path(paths["arch"]).read_text())
    schema_path = (schema_dir / "archspec.schema.json") if schema_dir else None
    mod = load_linter(linter_path)
    layer = _run("archspec", linter_path,
                 lambda s: mod.run_lint(spec, schema_path, loaded.get("goal"), s,
                                        glossary=loaded.get("glossary"),
                                        data_spec=loaded.get("data"),
                                        api_spec=loaded.get("api")), strict)
    layer.completeness = assess_archspec(spec)
    return layer


def run_dataspec(linter_dir, schema_dir, paths, loaded, strict) -> LayerResult:
    if not paths.get("data"):
        return LayerResult(name="dataspec", skipped=True, skip_reason="No dataspec provided.")
    linter_path = linter_dir / "lint_dataspec.py"
    spec = json.loads(Path(paths["data"]).read_text())
    schema_path = (schema_dir / "dataspec.schema.json") if schema_dir else None
    api_spec = loaded.get("api")
    mod = load_linter(linter_path)
    layer = _run("dataspec", linter_path, lambda s: mod.run_lint(spec, schema_path, s, api_spec), strict)
    layer.completeness = assess_dataspec(spec)
    return layer


def run_apispec(linter_dir, schema_dir, paths, loaded, strict) -> LayerResult:
    if not paths.get("api"):
        return LayerResult(name="apispec", skipped=True, skip_reason="No apispec provided.")
    linter_path = linter_dir / "lint_apispec.py"
    spec = json.loads(Path(paths["api"]).read_text())
    schema_path = (schema_dir / "apispec.schema.json") if schema_dir else None
    mod = load_linter(linter_path)
    layer = _run("apispec", linter_path,
                 lambda s: mod.run_lint(spec, schema_path, loaded.get("data"), s), strict)
    layer.completeness = assess_apispec(spec, loaded.get("data"))
    return layer


def run_testspec(linter_dir, schema_dir, paths, loaded, strict) -> LayerResult:
    if not paths.get("test"):
        return LayerResult(name="testspec", skipped=True, skip_reason="No testspec provided.")
    linter_path = linter_dir / "lint_testspec.py"
    spec = json.loads(Path(paths["test"]).read_text())
    schema_path = (schema_dir / "testspec.schema.json") if schema_dir else None
    api = loaded.get("api")
    mod = load_linter(linter_path)
    layer = _run("testspec", linter_path,
                 lambda s: mod.run_lint(spec, schema_path, api, s), strict)
    layer.completeness = assess_testspec(spec, api)
    return layer


def run_taskplan(linter_dir, schema_dir, paths, loaded, strict) -> LayerResult:
    if not paths.get("plan"):
        return LayerResult(name="taskplan", skipped=True, skip_reason="No taskplan provided.")
    linter_path = linter_dir / "lint_taskplan.py"
    spec = json.loads(Path(paths["plan"]).read_text())
    goal_spec = loaded.get("goal")
    design_spec = loaded.get("design")
    arch_spec = loaded.get("arch")
    data_spec = loaded.get("data")
    api_spec = loaded.get("api")
    test_spec = loaded.get("test")
    mod = load_linter(linter_path)
    layer = _run("taskplan", linter_path,
                 lambda s: mod.run_lint(spec, goal_spec, design_spec, arch_spec,
                                        data_spec, api_spec, test_spec, s), strict)
    layer.completeness = assess_taskplan(spec, goal_spec, design_spec, arch_spec)
    return layer


def run_issues(linter_dir, paths, loaded, args, strict) -> LayerResult:
    epic_id = getattr(args, 'epic', None)
    epics_dir = getattr(args, 'epics_dir', 'tasks/epics')
    if not epic_id:
        return LayerResult(name="issues", skipped=True,
                           skip_reason="No --epic provided (issues lint is optional).")
    linter_path = linter_dir / "lint_issues.py"
    mod = load_linter(linter_path)
    taskplan = loaded.get("plan")
    goal = loaded.get("goal")
    glossary = loaded.get("glossary")
    layer = _run("issues", linter_path,
                 lambda s: mod.run_lint(epic_id, epics_dir, taskplan, goal, glossary, s), strict)
    return layer


def run_consistency(linter_dir, paths, strict, args=None) -> LayerResult:
    """Run Markdown/JSON consistency checks."""
    linter_path = linter_dir / "lint_consistency.py"
    if not linter_path.exists():
        return LayerResult(name="consistency", skipped=True,
                           skip_reason="Consistency linter not found.")

    # Determine which specs to check
    if args and hasattr(args, 'specs'):
        specs_to_check = [s.strip() for s in args.specs.split(",")]
    else:
        specs_to_check = [key for key in ["goal", "design", "data", "api", "test"] if paths.get(key)]

    # Filter to only specs that have paths
    specs_to_check = [s for s in specs_to_check if paths.get(s)]

    if not specs_to_check:
        return LayerResult(name="consistency", skipped=True,
                           skip_reason="No spec paths provided.")

    # Find the spec directory (parent of the first spec path)
    spec_dir = Path(paths[specs_to_check[0]]).parent

    mod = load_linter(linter_path)
    layer = _run("consistency", linter_path,
                 lambda s: mod.run_lint(spec_dir, specs_to_check), strict)
    return layer


def run_cross(linter_dir, paths, loaded, strict) -> LayerResult:
    if not (paths.get("data") and paths.get("api")):
        return LayerResult(name="cross", skipped=True,
                           skip_reason="Requires both dataspec and apispec.")
    linter_path = linter_dir / "lint_cross.py"
    mod = load_linter(linter_path)
    data = loaded.get("data") or json.loads(Path(paths["data"]).read_text())
    api  = loaded.get("api")  or json.loads(Path(paths["api"]).read_text())
    test = loaded.get("test")
    goal = loaded.get("goal")
    design = loaded.get("design")
    arch = loaded.get("arch")
    plan = loaded.get("plan")
    return _run("cross", linter_path,
                lambda s: mod.run_lint(data, api, test, goal, design, arch, plan, s), strict)


# ── Completeness gate check layer ─────────────────────────────────────────────

def run_completeness_gates(suite: "SuiteResult") -> LayerResult:
    """
    Produce a dedicated layer that surfaces all blocking completeness gate
    failures as errors. Non-blocking gates at a higher lifecycle level are
    warnings.
    """
    layer = LayerResult(name="completeness")
    for score in suite.completeness_scores:
        status_order = {"draft": 0, "review": 1, "confirmed": 2}
        current = status_order.get(score.status, 0)

        for g in score.gates:
            if g.passed:
                continue
            gate_level = status_order.get(g.required_at, 0)
            if gate_level <= current:
                # This gate is required at current status — error
                detail = f" ({g.detail})" if g.detail else ""
                layer.add("error", f"{score.spec}_gate",
                    f"[{score.spec}] Gate failed: {g.description}{detail}.",
                    hint=f"Required at '{g.required_at}' status. Fix before advancing.")
            else:
                # This gate is required at a future status — warning
                detail = f" ({g.detail})" if g.detail else ""
                layer.add("warning", f"{score.spec}_gate",
                    f"[{score.spec}] Future gate: {g.description}{detail}.",
                    hint=f"Will be required at '{g.required_at}' status.")
    return layer


# ── Main runner ───────────────────────────────────────────────────────────────

def run_suite(paths, linter_dir, schema_dir, strict, stop_on_error, args=None) -> SuiteResult:
    suite = SuiteResult()

    def add(layer: LayerResult) -> bool:
        suite.layers.append(layer)
        return not (stop_on_error and not layer.clean and not layer.skipped)

    # Pre-load specs referenced by multiple layers
    loaded: dict = {}
    for key, path_key in [("goal","goal"), ("glossary","glossary"), ("data","data"),
                           ("api","api"), ("test","test"), ("arch","arch"), ("plan","plan")]:
        if paths.get(path_key):
            try:
                loaded[key] = json.loads(Path(paths[path_key]).read_text())
            except Exception as e:
                l = LayerResult(name=key)
                l.add("error", "load_error", f"Failed to load {paths[path_key]}: {e}")
                suite.layers.append(l)

    if not add(run_goalspec(linter_dir, schema_dir, paths, loaded, strict)):  return suite
    if not add(run_glossary(linter_dir, schema_dir, paths, loaded, strict)):  return suite
    if not add(run_designspec(linter_dir, schema_dir, paths, loaded, strict)):return suite
    if not add(run_archspec(linter_dir, schema_dir, paths, loaded, strict)):  return suite
    if not add(run_dataspec(linter_dir, schema_dir, paths, loaded, strict)):  return suite
    if not add(run_apispec(linter_dir, schema_dir, paths, loaded, strict)):   return suite
    if not add(run_testspec(linter_dir, schema_dir, paths, loaded, strict)):  return suite
    if not add(run_taskplan(linter_dir, schema_dir, paths, loaded, strict)):   return suite
    if not add(run_cross(linter_dir, paths, loaded, strict)):                 return suite
    if not add(run_issues(linter_dir, paths, loaded, args, strict)):           return suite
    if not add(run_consistency(linter_dir, paths, strict, args)):             return suite

    # Completeness gates layer — runs after all linters
    suite.layers.append(run_completeness_gates(suite))

    return suite


# ── Human output ──────────────────────────────────────────────────────────────

SCORE_BARS = [(90, "█████"), (75, "████░"), (50, "███░░"), (25, "██░░░"), (0, "█░░░░")]

def score_bar(pct: int) -> str:
    for threshold, bar in SCORE_BARS:
        if pct >= threshold:
            return bar
    return "░░░░░"

def print_human(suite: SuiteResult):
    print(f"\n{'═'*64}")
    print(f"  SDLC Spec Suite — Lint + Completeness Report")
    print(f"{'═'*64}\n")

    # ── Lint summary ──
    print("  LINT")
    for layer in suite.layers:
        if layer.name == "completeness":
            continue
        if layer.skipped:
            print(f"  –  {layer.name:<14} skipped  ({layer.skip_reason})")
        elif layer.clean and not layer.warnings:
            print(f"  ✓  {layer.name:<14} clean")
        elif layer.clean:
            print(f"  ⚠  {layer.name:<14} {len(layer.warnings)} warning(s)")
        else:
            print(f"  ✗  {layer.name:<14} {len(layer.errors)} error(s)  {len(layer.warnings)} warning(s)")

    # ── Completeness summary ──
    scores = suite.completeness_scores
    if scores:
        print(f"\n  COMPLETENESS")
        for score in scores:
            bar = score_bar(score.score_pct)
            blocking = len(score.blocking_gates)
            block_str = f"  [{blocking} blocking gate(s)]" if blocking else ""
            print(f"  {bar}  {score.score_pct:3d}%  {score.spec:<14} "
                  f"(status: {score.status}){block_str}")

        overall = suite_completeness_pct(scores)
        print(f"\n  {'─'*50}")
        print(f"  {score_bar(overall)}  {overall:3d}%  suite overall")

    # ── Issue details ──
    any_issues = False
    for layer in suite.layers:
        if layer.skipped or not layer.all_issues:
            continue
        any_issues = True
        print(f"\n  {'─'*60}")
        print(f"  [{layer.name.upper()}]")
        for issue in layer.errors:
            print(f"    ✗ [{issue.category}] {issue.message}")
            if issue.hint:
                print(f"      → {issue.hint}")
        for issue in layer.warnings:
            print(f"    ⚠ [{issue.category}] {issue.message}")
            if issue.hint:
                print(f"      → {issue.hint}")

    if not any_issues:
        print("\n  No issues found.")

    print(f"\n{'═'*64}")
    status = "PASS" if suite.clean else "FAIL"
    print(f"  {status}  —  {suite.total_errors} error(s), "
          f"{suite.total_warnings} warning(s) across {len(suite.layers)} layers")
    print(f"{'═'*64}\n")


# ── JSON output ───────────────────────────────────────────────────────────────

def print_json_output(suite: SuiteResult):
    scores = [
        {
            "spec": s.spec,
            "status": s.status,
            "scorePct": s.score_pct,
            "passed": s.passed,
            "total": s.total,
            "readyForReview": s.ready_for_review,
            "readyForConfirm": s.ready_for_confirm,
            "gates": [
                {
                    "description": g.description,
                    "passed": g.passed,
                    "requiredAt": g.required_at,
                    "detail": g.detail
                }
                for g in s.gates
            ]
        }
        for s in suite.completeness_scores
    ]
    out = {
        "clean": suite.clean,
        "totalErrors": suite.total_errors,
        "totalWarnings": suite.total_warnings,
        "suiteCompletenessPct": suite_completeness_pct(suite.completeness_scores),
        "layers": [
            {
                "name": l.name,
                "skipped": l.skipped,
                "skipReason": l.skip_reason if l.skipped else None,
                "clean": l.clean,
                "errors":   [{"category": e.category, "message": e.message, "hint": e.hint}
                             for e in l.errors],
                "warnings": [{"category": w.category, "message": w.message, "hint": w.hint}
                             for w in l.warnings],
            }
            for l in suite.layers
        ],
        "completeness": scores
    }
    print(json.dumps(out, indent=2))


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run the full SDLC spec lint suite.")
    parser.add_argument("--suite",    help="Path to suite.json config file")
    parser.add_argument("--goal",     help="Path to goalspec JSON")
    parser.add_argument("--design",   help="Path to designspec JSON")
    parser.add_argument("--arch",     help="Path to archspec JSON")
    parser.add_argument("--data",     help="Path to dataspec JSON")
    parser.add_argument("--api",      help="Path to apispec JSON")
    parser.add_argument("--test",     help="Path to testspec JSON")
    parser.add_argument("--plan",     help="Path to taskplan JSON")
    parser.add_argument("--glossary", help="Path to glossary JSON")
    parser.add_argument("--epic",     help="Epic ID for issues lint (e.g., EP-001)")
    parser.add_argument("--epics-dir", default="tasks/epics",
                        help="Path to epics directory (default: tasks/epics)")
    parser.add_argument("--schemas",  default=".", help="Directory with *.schema.json files")
    parser.add_argument("--linters",  default=".", help="Directory with lint_*.py files")
    parser.add_argument("--strict",   action="store_true", help="Treat warnings as errors")
    parser.add_argument("--stop-on-error", action="store_true",
                        help="Stop after first layer with errors")
    parser.add_argument("--specs",      default="goal,design,data,api,test",
                        help="Comma-separated list of specs for consistency check")
    parser.add_argument("--json",     action="store_true", help="Output as JSON")
    args = parser.parse_args()

    paths: dict = {}
    schema_dir = Path(args.schemas)
    linter_dir = Path(args.linters)

    if args.suite:
        cfg = json.loads(Path(args.suite).read_text())
        base = Path(args.suite).parent
        if cfg.get("schemas"):
            schema_dir = base / cfg["schemas"]
        if cfg.get("linters"):
            linter_dir = base / cfg["linters"]
        for key, val in cfg.get("specs", {}).items():
            paths[key] = str(base / val)

    for key in ["goal","design","arch","data","api","test","glossary"]:
        val = getattr(args, key, None)
        if val:
            paths[key] = val

    if not paths:
        parser.error("Provide --suite or at least one spec path.")

    suite = run_suite(
        paths=paths,
        linter_dir=linter_dir,
        schema_dir=schema_dir if schema_dir.exists() else None,
        strict=args.strict,
        stop_on_error=args.stop_on_error,
        args=args,
    )

    if args.json:
        print_json_output(suite)
    else:
        print_human(suite)

    sys.exit(0 if suite.clean else 1)


if __name__ == "__main__":
    main()
