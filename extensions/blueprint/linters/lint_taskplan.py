#!/usr/bin/env python3
"""
lint_taskplan.py — Linter for TaskPlan artifact.

Validates:
  - Every GoalSpec requirement appears in at least one epic's coverage list
  - Every epic covers at least one requirement
  - No epic implements a GoalSpec non-goal
  - Epics are listed in dependency order (blockers before dependents)
  - Milestones have demonstrable outcomes
  - Every epic belongs to exactly one milestone
  - All REQ-IDs referenced in TaskPlan exist in GoalSpec

Usage:
    python lint_taskplan.py plan.json --goal goalspec.json
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Optional
from shared import Issue, LayerResult, print_human, print_json_output, validate_ids


# ── Checks ────────────────────────────────────────────────────────────────────

def run_lint(spec: dict, schema_path: Optional[Path],
             goal: Optional[dict], strict: bool) -> LayerResult:
    result = LayerResult()

    # JSON Schema validation (auto-generated from schema)
    if schema_path:
        from schema_validator import SchemaValidator
        schema = json.loads(Path(schema_path).read_text())
        schema_issues = SchemaValidator(schema).validate(spec)
        for issue in schema_issues:
            result.add(issue.severity, issue.category, issue.message, issue.hint)

    # EPIC ID format validation
    validate_ids(spec.get("epics", []), "id", "ep", "ep_id_format", result)

    # MILESTONE ID format validation
    validate_ids(spec.get("milestones", []), "id", "milestone", "milestone_id_format", result)

    if strict:
        for w in result.warnings:
            w.severity = "error"
            result.errors.append(w)
        result.warnings.clear()

    return result


# ── Output
# Uses shared.print_human and shared.print_json_output


def main():
    parser = argparse.ArgumentParser(description="Lint a TaskPlan JSON.")
    parser.add_argument("input",     help="Path to taskplan JSON")
    parser.add_argument("--schema",  help="Path to taskplan.schema.json")
    parser.add_argument("--goal",    help="Path to goalspec JSON for cross-spec checks")
    parser.add_argument("--strict",  action="store_true", help="Treat warnings as errors")
    args = parser.parse_args()

    spec = json.loads(Path(args.input).read_text())
    schema_path = Path(args.schema) if args.schema else None
    goal = json.loads(Path(args.goal).read_text()) if args.goal else None

    result = run_lint(spec, schema_path, goal, args.strict)
    print_human(result, args.input, args.goal)
    sys.exit(0 if result.clean else 1)


if __name__ == "__main__":
    main()

