#!/usr/bin/env python3
"""
types.py — Canonical data types for the linter framework.

Provides:
    Issue           — a single lint finding
    LayerResult     — result from one lint layer
    Resolved        — result of resolving a target path
    CompletenessGate  — a single readiness condition
    CompletenessScore — aggregate completeness for one spec

All linters import from shared.py which re-exports these.
"""

from dataclasses import dataclass, field


# ── Lint result types ─────────────────────────────────────────────────────────

@dataclass
class Issue:
    """A single lint finding."""

    severity: str  # "error" | "warning" | "info"
    category: str  # e.g. "schema", "duplicate_id", "cross-ref"
    message: str  # Human-readable description of the issue
    hint: str = ""  # Optional suggestion for how to fix


@dataclass
class LayerResult:
    """Result from a single lint layer (one spec or cross-spec check)."""

    name: str = ""
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)

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


# ── Path resolution types ─────────────────────────────────────────────────────

@dataclass
class Resolved:
    """Result of resolving a target path."""

    values: list
    parent_ids: list
    parent_label: str = ""
    parent_items: list = None
    group_sizes: list = None


# ── Completeness types ────────────────────────────────────────────────────────

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


def gate(desc: str, passed: bool, required_at: str, detail: str = "") -> CompletenessGate:
    """Convenience constructor for CompletenessGate."""
    return CompletenessGate(description=desc, passed=passed,
                             required_at=required_at, detail=detail)
