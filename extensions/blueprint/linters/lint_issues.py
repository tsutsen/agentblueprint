#!/usr/bin/env python3
"""
lint_issues.py — Linter for issue files produced by the breakdown process.

Validates issue files within an epic folder for structural correctness,
dependency consistency, and coverage completeness.

Usage:
    python lint_issues.py --epic EP-001 --epics-dir tasks/epics/
    python lint_issues.py --epic EP-001 --epics-dir tasks/epics/ --strict
"""

import json
import sys
import argparse
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


# ── Shared types ──────────────────────────────────────────────────────────────

@dataclass
class Issue:
    severity: str          # "error" | "warning" | "info"
    category: str          # "id" | "dependency" | "coverage" | "structure" | "schema"
    message: str
    hint: str = ""


@dataclass
class IssueFile:
    epic_id: str
    issue_id: str
    md_path: Path
    json_path: Path
    data: dict = field(default_factory=dict)
    md_content: str = ""
    errors: list = field(default_factory=list)


# ── Schema patterns ───────────────────────────────────────────────────────────

EPIC_ID_RE = re.compile(r"^EP-\d{3}$")
ISSUE_ID_RE = re.compile(r"^IS-\d{3}$")
MILESTONE_RE = re.compile(r"^M\d+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ── Core linter ───────────────────────────────────────────────────────────────

class IssueLinter:
    def __init__(self, epics_dir: str, epic_id: str, strict: bool = False):
        self.epics_dir = Path(epics_dir)
        self.epic_id = epic_id
        self.strict = strict
        self.issues: list[Issue] = []
        self.issue_files: list[IssueFile] = []
        self.epic_data: dict = {}

    def add_issue(self, severity: str, category: str, message: str, hint: str = ""):
        self.issues.append(Issue(severity, category, message, hint))

    def load_epic(self):
        """Load the epic file for context (acceptance criteria, scope)."""
        epic_md = self.epics_dir / self.epic_id / f"{self.epic_id}-*.md"
        epic_files = list(self.epics_dir.glob(f"{self.epic_id}/*.md"))
        if not epic_files:
            # Try flat structure for backward compatibility
            epic_files = list(self.epics_dir.parent.glob(f"{self.epic_id}-*.md"))

        if not epic_files:
            self.add_issue("error", "structure",
                f"Epic file not found for {self.epic_id} in {self.epics_dir}")
            return

        epic_file = epic_files[0]
        self.epic_data["md_path"] = epic_file
        self.epic_data["content"] = epic_file.read_text()

        # Extract acceptance criteria from epic content
        content = epic_file.read_text()
        ac_pattern = re.compile(r"- \[ \] (.+)")
        self.epic_data["acceptance_criteria"] = ac_pattern.findall(content)

    def load_issue_files(self):
        """Load all issue files in the epic folder."""
        epic_folder = self.epics_dir / self.epic_id
        if not epic_folder.exists():
            self.add_issue("error", "structure",
                f"Epic folder {epic_folder} does not exist")
            return

        # Find all IS-NNN directories
        issue_dirs = sorted([
            d for d in epic_folder.iterdir()
            if d.is_dir() and ISSUE_ID_RE.match(d.name)
        ])

        for issue_dir in issue_dirs:
            issue_id = issue_dir.name
            md_path = issue_dir / f"{issue_id}.md"
            json_path = issue_dir / f"{issue_id}.json"

            if not md_path.exists():
                self.add_issue("error", "structure",
                    f"Missing {issue_id}.md in {issue_dir}")
                continue

            if not json_path.exists():
                self.add_issue("error", "structure",
                    f"Missing {issue_id}.json in {issue_dir}")
                continue

            issue_file = IssueFile(
                epic_id=self.epic_id,
                issue_id=issue_id,
                md_path=md_path,
                json_path=json_path,
            )
            issue_file.md_content = md_path.read_text()

            try:
                issue_file.data = json.loads(json_path.read_text())
            except json.JSONDecodeError as e:
                self.add_issue("error", "schema",
                    f"{issue_id}.json is not valid JSON: {e}")
                self.issue_files.append(issue_file)
                continue

            self.issue_files.append(issue_file)

    def lint_id_sequence(self):
        """Check that issue IDs within this epic are sequential from the epic start."""
        if len(self.issue_files) < 2:
            return

        # Get numeric IDs within this epic only
        numeric_ids = sorted([int(f.issue_id.split("-")[1]) for f in self.issue_files])
        min_id = numeric_ids[0]
        max_id = numeric_ids[-1]

        expected = set(range(min_id, max_id + 1))
        actual = set(numeric_ids)
        missing = expected - actual

        for gap in missing:
            self.add_issue("warning", "id",
                f"Gap in issue ID sequence within epic: IS-{gap:03d} is missing",
                f"Within this epic, issue IDs should be sequential. "
                f"Current range: IS-{min_id:03d} to IS-{max_id:03d}.")

    def lint_dependencies(self):
        """Check that blocked_by references point to real issue files."""
        existing_ids = {f.issue_id for f in self.issue_files}

        for issue_file in self.issue_files:
            blocked_by = issue_file.data.get("blocked_by", [])
            for ref in blocked_by:
                if not ISSUE_ID_RE.match(ref):
                    self.add_issue("error", "dependency",
                        f"{issue_file.issue_id}: invalid blocked_by reference '{ref}'")
                    continue
                if ref not in existing_ids:
                    self.add_issue("error", "dependency",
                        f"{issue_file.issue_id}: blocked_by '{ref}' does not exist",
                        f"Available issue IDs: {', '.join(sorted(existing_ids))}")

    def lint_dependency_ordering(self):
        """Check that blocked issues have higher IS-NNN than their blockers."""
        existing_ids = {f.issue_id for f in self.issue_files}
        id_to_num = {f.issue_id: int(f.issue_id.split("-")[1]) for f in self.issue_files}

        for issue_file in self.issue_files:
            blocked_by = issue_file.data.get("blocked_by", [])
            issue_num = id_to_num[issue_file.issue_id]
            for ref in blocked_by:
                if ref in id_to_num and id_to_num[ref] >= issue_num:
                    self.add_issue("warning", "dependency",
                        f"{issue_file.issue_id}: blocked_by '{ref}' has equal or higher ID — "
                        f"the blocker should have a lower IS-NNN number")

    def lint_blocked_by_cycles(self):
        """Detect cycles in the blocked_by dependency graph."""
        if len(self.issue_files) < 2:
            return

        existing_ids = {f.issue_id for f in self.issue_files}
        graph: dict[str, list[str]] = {}
        for issue_file in self.issue_files:
            blocked_by = issue_file.data.get("blocked_by", [])
            graph[issue_file.issue_id] = [r for r in blocked_by if r in existing_ids]

        # DFS cycle detection
        visited = set()
        path = []

        def dfs(node):
            if node in path:
                cycle = path[path.index(node):]
                cycle.append(node)
                return cycle
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
                    self.add_issue("error", "dependency",
                        f"Circular dependency detected: {' → '.join(cycle)}")
                    break

    def lint_epic_consistency(self):
        """Check that issue.epic matches the target epic ID."""
        for issue_file in self.issue_files:
            issue_epic = issue_file.data.get("epic", "")
            if issue_epic and issue_epic != self.epic_id:
                self.add_issue("error", "epic",
                    f"{issue_file.issue_id}: epic field is '{issue_epic}' but issue is in {self.epic_id}")

    def lint_milestone_consistency(self, taskplan: Optional[dict] = None):
        """Check that issue.milestone exists in TaskPlan milestones."""
        if not taskplan:
            return
        valid_milestones = {m["id"] for m in taskplan.get("milestones", [])}
        for issue_file in self.issue_files:
            milestone = issue_file.data.get("milestone", "")
            if milestone and milestone not in valid_milestones:
                self.add_issue("warning", "milestone",
                    f"{issue_file.issue_id}: milestone '{milestone}' not found in TaskPlan. "
                    f"Valid: {', '.join(sorted(valid_milestones))}")

    def lint_coverage(self):
        """Check that every epic acceptance criterion maps to at least one issue."""
        if not self.epic_data or not self.epic_data.get("acceptance_criteria"):
            return

        acceptance_criteria = self.epic_data["acceptance_criteria"]
        covered = set()

        for issue_file in self.issue_files:
            md_content = issue_file.md_content
            # Extract acceptance criteria from issue markdown
            ac_pattern = re.compile(r"## Acceptance criteria\s*\n((?:- \[ \] .+\n?)*)")
            match = ac_pattern.search(md_content)
            if match:
                issue_acs = match.group(1)
                # Check if any epic AC is mentioned in this issue's ACs
                for epic_ac in acceptance_criteria:
                    epic_ac_text = epic_ac.strip().lstrip("- ")
                    if epic_ac_text.lower()[:30] in issue_acs.lower():
                        covered.add(epic_ac)

        for epic_ac in acceptance_criteria:
            if epic_ac not in covered:
                ac_text = epic_ac.strip().lstrip("- ")
                self.add_issue("warning", "coverage",
                    f"Epic acceptance criterion not covered by any issue: '{ac_text}'")

    def lint_schema(self):
        """Validate each issue's JSON against required fields."""
        required_fields = [
            "artifact", "id", "title", "type", "status",
            "epic", "blocked_by", "milestone", "created", "updated"
        ]

        for issue_file in self.issue_files:
            data = issue_file.data
            if not data:
                continue

            # Check required fields
            for field_name in required_fields:
                if field_name not in data:
                    self.add_issue("error", "schema",
                        f"{issue_file.issue_id}: missing required field '{field_name}'")

            # Validate field formats
            if data.get("id") and not ISSUE_ID_RE.match(data["id"]):
                self.add_issue("error", "schema",
                    f"{issue_file.issue_id}: invalid id format '{data['id']}'")

            if data.get("epic") and not EPIC_ID_RE.match(data["epic"]):
                self.add_issue("error", "schema",
                    f"{issue_file.issue_id}: invalid epic format '{data['epic']}'")

            if data.get("milestone") and not MILESTONE_RE.match(data["milestone"]):
                self.add_issue("error", "schema",
                    f"{issue_file.issue_id}: invalid milestone format '{data['milestone']}'")

            if data.get("created") and not DATE_RE.match(data["created"]):
                self.add_issue("error", "schema",
                    f"{issue_file.issue_id}: invalid created date '{data['created']}'")

            if data.get("updated") and not DATE_RE.match(data["updated"]):
                self.add_issue("error", "schema",
                    f"{issue_file.issue_id}: invalid updated date '{data['updated']}'")

            if data.get("type") and data["type"] not in ("AFK", "HITL"):
                self.add_issue("error", "schema",
                    f"{issue_file.issue_id}: invalid type '{data['type']}' (must be AFK or HITL)")

            if data.get("status") and data["status"] not in (
                "not_started", "in_progress", "needs_review", "complete"
            ):
                self.add_issue("error", "schema",
                    f"{issue_file.issue_id}: invalid status '{data['status']}'")

            # Check blocked_by is a list of valid IDs
            blocked_by = data.get("blocked_by", [])
            if not isinstance(blocked_by, list):
                self.add_issue("error", "schema",
                    f"{issue_file.issue_id}: blocked_by must be an array")
            else:
                # Check blocked_by items match pattern
                for item in blocked_by:
                    if not ISSUE_ID_RE.match(str(item)):
                        self.add_issue("error", "schema",
                            f"{issue_file.issue_id}: blocked_by item '{item}' is not a valid IS-NNN")
                # Check for duplicates
                if len(blocked_by) != len(set(blocked_by)):
                    self.add_issue("warning", "schema",
                        f"{issue_file.issue_id}: duplicate entries in blocked_by")

            # Check updated >= created
            created = data.get("created", "")
            updated = data.get("updated", "")
            if created and updated and updated < created:
                self.add_issue("warning", "schema",
                    f"{issue_file.issue_id}: updated ({updated}) is before created ({created})")

            # Check title length
            title = data.get("title", "")
            if title and len(title) < 5:
                self.add_issue("warning", "schema",
                    f"{issue_file.issue_id}: title is too short ({len(title)} chars)")

            # Check artifact value
            if data.get("artifact") != "Issue":
                self.add_issue("error", "schema",
                    f"{issue_file.issue_id}: artifact must be 'Issue', got '{data['artifact']}'")

    def lint_body(self):
        """Validate the markdown body of each issue file."""
        for issue_file in self.issue_files:
            md = issue_file.md_content

            # Check for required sections
            if "## What to build" not in md:
                self.add_issue("error", "structure",
                    f"{issue_file.issue_id}: missing 'What to build' section")

            if "## Acceptance criteria" not in md:
                self.add_issue("error", "structure",
                    f"{issue_file.issue_id}: missing 'Acceptance criteria' section")

            if "## Blocked by" not in md:
                self.add_issue("error", "structure",
                    f"{issue_file.issue_id}: missing 'Blocked by' section")

            # Check that acceptance criteria have checkboxes
            ac_pattern = re.compile(r"## Acceptance criteria\s*\n((?:- \[ \] .+\n?)*)")
            match = ac_pattern.search(md)
            if match:
                ac_content = match.group(1)
                unchecked = len(re.findall(r"- \[ \] ", ac_content))
                if unchecked == 0 and ac_content.strip():
                    self.add_issue("warning", "structure",
                        f"{issue_file.issue_id}: all acceptance criteria are checked — "
                        f"this issue may already be complete")
            else:
                # No AC section found (already caught above), skip
                pass

    def run(self, taskplan: Optional[dict] = None) -> list[Issue]:
        """Run all linters and return issues."""
        self.load_epic()
        self.load_issue_files()
        self.lint_id_sequence()
        self.lint_dependencies()
        self.lint_dependency_ordering()
        self.lint_blocked_by_cycles()
        self.lint_schema()
        self.lint_epic_consistency()
        self.lint_milestone_consistency(taskplan)
        self.lint_body()
        self.lint_coverage()
        return self.issues

    def summary(self) -> str:
        """Return a formatted summary of lint findings."""
        errors = [i for i in self.issues if i.severity == "error"]
        warnings = [i for i in self.issues if i.severity == "warning"]
        infos = [i for i in self.issues if i.severity == "info"]

        lines = []
        if errors:
            lines.append(f"Errors: {len(errors)}")
            for e in errors:
                lines.append(f"  [{e.category}] {e.message}" +
                             (f" — {e.hint}" if e.hint else ""))
        if warnings:
            lines.append(f"Warnings: {len(warnings)}")
            for w in warnings:
                lines.append(f"  [{w.category}] {w.message}" +
                             (f" — {w.hint}" if w.hint else ""))
        if infos:
            lines.append(f"Info: {len(infos)}")
            for i in infos:
                lines.append(f"  [{i.category}] {i.message}")

        if not self.issues:
            lines.append("No issues found.")

        return "\n".join(lines)


# ── Integration with lint_all.py ──────────────────────────────────────────────

def run_lint(epic_id: str, epics_dir: str, taskplan: Optional[dict] = None, strict: bool = False):
    """Run the issue linter for a single epic. Returns a LayerResult."""
    from lint_all import LayerResult
    linter = IssueLinter(epics_dir, epic_id, strict)
    issues = linter.run(taskplan)

    layer = LayerResult(name="issues")
    for issue in issues:
        layer.add(issue.severity, issue.category, issue.message, issue.hint)

    return layer


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Lint issue files for an epic")
    parser.add_argument("--epic", required=True, help="Epic ID (e.g., EP-001)")
    parser.add_argument("--epics-dir", default="tasks/epics",
                        help="Path to epics directory (default: tasks/epics)")
    parser.add_argument("--taskplan", default=None,
                        help="Path to taskplan.json for milestone validation")
    parser.add_argument("--strict", action="store_true",
                        help="Treat warnings as errors")
    args = parser.parse_args()

    taskplan = None
    if args.taskplan:
        try:
            taskplan = json.loads(Path(args.taskplan).read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"Warning: Could not load taskplan from {args.taskplan}")

    linter = IssueLinter(args.epics_dir, args.epic, args.strict)
    issues = linter.run(taskplan)

    print(linter.summary())

    errors = [i for i in issues if i.severity == "error"]
    if errors or (args.strict and [i for i in issues if i.severity == "warning"]):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
