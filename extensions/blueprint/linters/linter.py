#!/usr/bin/env python3
"""
linter.py — BaseLinter class and strict mode.

Provides BaseLinter, the base class all spec linters inherit from.
Orchestrates the full lint pipeline: schema → IDs → cross-spec → rules → misc.

All linters import BaseLinter from shared.py which re-exports it.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from linter_types import CompletenessGate, CompletenessScore, Issue, LayerResult
from id_validation import _validate_all_ids, validate_project_and_version
from output import print_human, print_json_output


def _apply_strict_mode(result: LayerResult) -> None:
    """Convert all warnings to errors."""
    for w in result.warnings:
        w.severity = "error"
    result.errors.extend(result.warnings)
    result.warnings.clear()


class BaseLinter:
    """Base class for all spec linters.

    Subclasses define:
    - SPEC_NAME: Name for error messages (e.g., "archspec")
    - SEMANTIC_RULES: Declarative rules for semantic validation
    - MISC_CHECKS: List of (name, func) tuples for custom checks

    The run() method orchestrates the full lint pipeline.
    """

    SPEC_NAME: str = ""
    SPEC_KEY: str = ""  # e.g. "goalspec", "dataspec" (for CompletenessScore)
    SEMANTIC_RULES: list = []
    COMPLETENESS_GATES: list = []  # Declarative GateDef list (from gates.py)
    MISC_GATES: list = []  # List of func(spec, extra_specs) -> CompletenessGate
    MISC_CHECKS: list = []  # List of check functions (bare, like MISC_GATES)
    CROSS_SPEC_DEPS: list = []  # e.g., ["goal", "data", "api"]

    def __init__(self, spec: dict, schema_path: Optional[Path], strict: bool):
        self.spec = spec
        self.schema_path = schema_path
        self.strict = strict
        self.result = LayerResult(name=self.SPEC_NAME)
        self.extra_specs: dict = {}

    def run(self, **kwargs) -> LayerResult:
        """Main entry point — runs all checks in order."""
        self._store_extra_specs(kwargs)
        self._validate_schema()
        self._validate_ids()
        self._validate_cross_spec_consistency()
        self._run_semantic_rules()
        self._run_misc_checks()
        self._strict_mode()
        return self.result

    def _store_extra_specs(self, kwargs: dict) -> None:
        """Store extra specs passed to run()."""
        for dep in self.CROSS_SPEC_DEPS:
            if dep in kwargs:
                self.extra_specs[dep] = kwargs[dep]

    def _validate_schema(self) -> None:
        """Validate spec against its JSON schema."""
        if not self.schema_path:
            return
        schema = json.loads(self.schema_path.read_text())
        from lint_schemas import SchemaValidator

        for issue in SchemaValidator(schema).validate(self.spec):
            self.result.add(issue.severity, issue.category, issue.message, issue.hint)

    def _validate_ids(self) -> None:
        """Validate all IDs in the spec."""
        _validate_all_ids(self.spec, self.result)

    def _validate_cross_spec_consistency(self) -> None:
        """Check project match and version pinning."""
        goal = self.extra_specs.get("goal")
        if goal:
            validate_project_and_version(self.spec, self.SPEC_NAME, goal, self.result)

    def _run_semantic_rules(self) -> None:
        """Execute declarative semantic rules."""
        from rules import _run_new_semantic_rules

        _run_new_semantic_rules(
            self.SEMANTIC_RULES, self.spec, self.result, self.extra_specs
        )

    def _run_misc_checks(self) -> None:
        """Run custom/spec-specific checks."""
        for func in self.MISC_CHECKS:
            func(self.spec, self.result, self.extra_specs)

    def _strict_mode(self) -> None:
        """Convert warnings to errors if strict mode."""
        if self.strict:
            _apply_strict_mode(self.result)

    # ── Completeness ──────────────────────────────────────────────────────

    def run_completeness(self, extra_specs: dict) -> CompletenessScore:
        """Run declarative completeness gates + misc custom gates.

        Subclasses define COMPLETENESS_GATES (GateDef list) and optionally
        MISC_GATES (list of func(spec, extra_specs) -> CompletenessGate).

        Returns CompletenessScore with all gates evaluated.
        """
        from gates import run_gates

        status = self.spec.get("status", "draft")
        spec_key = getattr(self, "SPEC_KEY", self.SPEC_NAME) or status

        # Run declarative gates
        score = run_gates(
            self.COMPLETENESS_GATES,
            self.spec,
            extra_specs,
            spec_name=spec_key,
            status=status,
        )

        # Append misc/custom gates
        for gate_fn in self.MISC_GATES:
            score.gates.append(gate_fn(self.spec, extra_specs))

        return score

    @classmethod
    def main(cls):
        """CLI entry point.

        Auto-generates --<dep> args from cls.CROSS_SPEC_DEPS.
        """
        parser = argparse.ArgumentParser(description=f"Lint {cls.SPEC_NAME} JSON.")
        parser.add_argument("input", help=f"Path to {cls.SPEC_NAME} JSON")
        parser.add_argument("--schema", help=f"Path to {cls.SPEC_NAME}.schema.json")
        parser.add_argument(
            "--strict", action="store_true", help="Treat warnings as errors"
        )
        parser.add_argument("--json", action="store_true", help="Output as JSON")

        # Auto-generate --<dep> args from CROSS_SPEC_DEPS
        for dep in cls.CROSS_SPEC_DEPS:
            parser.add_argument(
                f"--{dep}", help=f"Path to {dep}spec JSON for cross-spec checks"
            )

        args = parser.parse_args()

        spec = json.loads(Path(args.input).read_text())
        schema_path = Path(args.schema) if args.schema else None

        # Load extra specs from auto-generated args
        extra_specs = {}
        for dep in cls.CROSS_SPEC_DEPS:
            arg_value = getattr(args, dep, None)
            if arg_value:
                extra_specs[dep] = json.loads(Path(arg_value).read_text())

        linter = cls(spec, schema_path, args.strict)
        result = linter.run(**extra_specs)

        if args.json:
            print_json_output(result)
        else:
            print_human(result, str(args.input))

        sys.exit(0 if result.clean else 1)
