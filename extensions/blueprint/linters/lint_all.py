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
  9. issues      (← taskplan, requires --epic)
 10. completeness (← all layers)

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

from shared import (
    Issue,
    LayerResult as SharedLayerResult,
    CompletenessGate,
    CompletenessScore,
    suite_completeness_pct,
    SPEC_ORDER,
)


# ── Shared types ──────────────────────────────────────────────────────────────

@dataclass
class LayerResult(SharedLayerResult):
    """Extended LayerResult with suite-level fields."""
    skipped: bool = False
    skip_reason: str = ""
    completeness: Optional[CompletenessScore] = None

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


@dataclass
class LayerConfig:
    """Configuration for a single lint layer.

    call_fn(mod, spec, schema_path, loaded, strict) -> LayerResult from linter
    assess_fn(mod, spec, loaded) -> CompletenessScore (optional)
    """
    name: str
    linter_file: str
    schema_file: str
    path_key: str
    skip_reason: str
    call_fn: callable
    assess_fn: callable = None


def _run_layer(cfg: LayerConfig, linter_dir: Path, schema_dir: Optional[Path],
               paths: dict, loaded: dict, strict: bool) -> LayerResult:
    """Execute one lint layer from its config.

    Handles: path check, JSON loading, schema resolution, linter loading,
    invocation, and completeness assessment.
    """
    path_val = paths.get(cfg.path_key)
    if not path_val:
        return LayerResult(name=cfg.name, skipped=True, skip_reason=cfg.skip_reason)

    spec = json.loads(Path(path_val).read_text())
    schema_path = (schema_dir / cfg.schema_file) if schema_dir else None
    linter_path = linter_dir / cfg.linter_file

    layer = LayerResult(name=cfg.name)
    if not linter_path.exists():
        layer.skipped = True
        layer.skip_reason = f"Linter not found: {linter_path}"
        return layer

    try:
        mod = load_linter(linter_path)
        lr = cfg.call_fn(mod, spec, schema_path, loaded, strict)
        layer.errors, layer.warnings = issues_from_lr(lr)
    except Exception as e:
        layer.add("error", "runner_error", f"Linter raised: {e}",
                  hint="Check the linter and spec file for errors.")

    if cfg.assess_fn:
        layer.completeness = cfg.assess_fn(mod, spec, loaded)

    return layer


def _run_issues_layer(cfg: LayerConfig, linter_dir: Path, schema_dir: Optional[Path],
                      paths: dict, loaded: dict, strict: bool, args) -> LayerResult:
    """Execute the issues lint layer from its config.

    Special handling: uses epics_dir and epic_id from args instead of schema.
    """
    epic_id = getattr(args, 'epic', None)
    epics_dir = getattr(args, 'epics_dir', 'tasks/epics')
    if not epic_id:
        return LayerResult(name=cfg.name, skipped=True, skip_reason=cfg.skip_reason)

    linter_path = linter_dir / cfg.linter_file
    layer = LayerResult(name=cfg.name)
    if not linter_path.exists():
        layer.skipped = True
        layer.skip_reason = f"Linter not found: {linter_path}"
        return layer
    try:
        mod = load_linter(linter_path)
        lr = cfg.call_fn(mod, epics_dir, epic_id, loaded, strict)
        layer.errors, layer.warnings = issues_from_lr(lr)
    except Exception as e:
        layer.add("error", "runner_error", f"Linter raised: {e}",
                  hint="Check the linter and spec file for errors.")
    return layer


# ── Layer factory functions ──────────────────────────────────────────────────
# Named functions replace inline lambdas for readability.
# Each call_fn: (mod, spec, schema_path, loaded, strict) -> LayerResult


def _call_goalspec(m, s, sp, l, st):
    return m.LinterClass(s, sp, st).run(glossary=l.get("glossary"))


def _call_glossary(m, s, sp, l, st):
    return m.LinterClass(s, sp, st).run(
        goal=l.get("goal"), arch=l.get("arch"),
        data=l.get("data"), api=l.get("api"))


def _call_designspec(m, s, sp, l, st):
    return m.LinterClass(s, sp, st).run(
        goal=l.get("goal"), glossary=l.get("glossary"))


def _call_archspec(m, s, sp, l, st):
    return m.LinterClass(s, sp, st).run(
        goal=l.get("goal"), glossary=l.get("glossary"),
        data=l.get("data"), api=l.get("api"))


def _call_dataspec(m, s, sp, l, st):
    return m.LinterClass(s, sp, st).run(
        api=l.get("api"), glossary=l.get("glossary"))


def _call_apispec(m, s, sp, l, st):
    return m.LinterClass(s, sp, st).run(data=l.get("data"))


def _call_testspec(m, s, sp, l, st):
    return m.LinterClass(s, sp, st).run(
        api=l.get("api"), glossary=l.get("glossary"))


def _call_taskplan(m, s, sp, l, st):
    return m.LinterClass(s, sp, st).run(
        goal=l.get("goal"), design=l.get("design"),
        arch=l.get("arch"), data=l.get("data"),
        api=l.get("api"), test=l.get("test"),
        glossary=l.get("glossary"))


def _call_issues(m, epics_dir, epic_id, l, st):
    """Issues layer: special handling (no schema, epics_dir + epic_id args)."""
    return m.LinterClass(epics_dir, epic_id, strict=st).run(
        taskplan=l.get("plan"),
        goal=l.get("goal"),
        glossary=l.get("glossary"))


def _assess(m, s, l):
    """Standard completeness assessment: run LinterClass.run_completeness()."""
    return m.LinterClass(s, None, False).run_completeness(l)


# ── Layer definitions ─────────────────────────────────────────────────────

_LAYERS = [
    LayerConfig(
        name="goalspec",
        linter_file="lint_goalspec.py",
        schema_file="goalspec.schema.json",
        path_key="goal",
        skip_reason="No goalspec provided.",
        call_fn=_call_goalspec,
        assess_fn=_assess,
    ),
    LayerConfig(
        name="glossary",
        linter_file="lint_glossary.py",
        schema_file="glossary.schema.json",
        path_key="glossary",
        skip_reason="No glossary provided.",
        call_fn=_call_glossary,
        assess_fn=_assess,
    ),
    LayerConfig(
        name="designspec",
        linter_file="lint_designspec.py",
        schema_file="designspec.schema.json",
        path_key="design",
        skip_reason="No designspec provided.",
        call_fn=_call_designspec,
        assess_fn=_assess,
    ),
    LayerConfig(
        name="archspec",
        linter_file="lint_archspec.py",
        schema_file="archspec.schema.json",
        path_key="arch",
        skip_reason="No archspec provided.",
        call_fn=_call_archspec,
        assess_fn=_assess,
    ),
    LayerConfig(
        name="dataspec",
        linter_file="lint_dataspec.py",
        schema_file="dataspec.schema.json",
        path_key="data",
        skip_reason="No dataspec provided.",
        call_fn=_call_dataspec,
        assess_fn=_assess,
    ),
    LayerConfig(
        name="apispec",
        linter_file="lint_apispec.py",
        schema_file="apispec.schema.json",
        path_key="api",
        skip_reason="No apispec provided.",
        call_fn=_call_apispec,
        assess_fn=_assess,
    ),
    LayerConfig(
        name="testspec",
        linter_file="lint_testspec.py",
        schema_file="testspec.schema.json",
        path_key="test",
        skip_reason="No testspec provided.",
        call_fn=_call_testspec,
        assess_fn=_assess,
    ),
    LayerConfig(
        name="taskplan",
        linter_file="lint_taskplan.py",
        schema_file="taskplan.schema.json",
        path_key="plan",
        skip_reason="No taskplan provided.",
        call_fn=_call_taskplan,
        assess_fn=_assess,
    ),
    LayerConfig(
        name="issues",
        linter_file="lint_issues.py",
        schema_file="",  # issues has no schema
        path_key="epic",  # uses epic as the path key
        skip_reason="No --epic provided (issues lint is optional).",
        call_fn=_call_issues,
        assess_fn=None,  # issues don't have completeness gates
    ),
]


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

    # Run all layers (including issues) from config table
    for cfg in _LAYERS:
        if cfg.name == "issues":
            # Issues layer: special handling (no schema, epics_dir + epic_id args)
            if not add(_run_issues_layer(cfg, linter_dir, schema_dir, paths, loaded, strict, args)):
                return suite
        else:
            if not add(_run_layer(cfg, linter_dir, schema_dir, paths, loaded, strict)):
                return suite

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
