#!/usr/bin/env python3
"""
lint_subissues.py — Linter for sub-issue files.

Validates SubIssue JSON files for:
  - Schema correctness (required fields, valid values)
  - isRefs and epRefs exist and point to real issues/epics
  - Scope inheritance from parent Issue
  - files array format (audit trail — paths valid, actions valid)
  - priority is one of P0/P1/P2/P3
  - effort is one of XS/S/M/L/XL
  - created/updated are ISO 8601 timestamps
  - Directory structure correctness

Usage:
    python lint_subissues.py --epic EP-001 --epics-dir tasks/
"""

import json
import re
import sys
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from shared import BaseLinter, LayerResult, print_human, print_json_output


# ── Constants ─────────────────────────────────────────────────────────────────

VALID_STATUSES = {"not_started", "in_progress", "needs_review", "complete"}
VALID_TYPES = {"AFK", "HITL"}
VALID_PRIORITIES = {"P0", "P1", "P2", "P3"}
VALID_EFFORTS = {"XS", "S", "M", "L", "XL"}
VALID_FILE_ACTIONS = {"create", "modify", "delete"}
ISO_8601_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
SI_ID_RE = re.compile(r"^SI-\d{3}-[a-z][a-zA-Z0-9]*$")
IS_ID_RE = re.compile(r"^IS-\d{3}-[a-z][a-zA-Z0-9]*$")
EP_ID_RE = re.compile(r"^EP-\d{3}-[a-z][a-zA-Z0-9]*$")


@dataclass
class SubIssueFile:
    epic_id: str
    issue_id: str
    sub_issue_id: str
    json_path: Path
    md_path: Path
    work_dir: Path
    data: dict = field(default_factory=dict)
    md_content: str = ""


# ── Validation Functions ──────────────────────────────────────────────────────

def _check_required_fields(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that all required fields are present."""
    required = [
        "schemaVersion", "artifact", "id", "name", "description",
        "type", "status", "milestone", "acceptanceCriteria",
        "isRefs", "epRefs", "created", "updated",
    ]
    sub_issues = spec.get("_sub_issue_files", [])

    for si in sub_issues:
        data = si.data
        if not data:
            continue
        for field in required:
            if field not in data:
                result.add("error", "schema",
                    f"{si.sub_issue_id}: missing required field '{field}'.",
                    hint=f"Add '{field}' to {si.sub_issue_id}.json")


def _check_artifact_type(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that artifact type is 'SubIssue'."""
    for si in spec.get("_sub_issue_files", []):
        data = si.data
        if not data:
            continue
        if data.get("artifact") != "SubIssue":
            result.add("error", "schema",
                f"{si.sub_issue_id}: artifact must be 'SubIssue', got '{data.get('artifact')}'.")


def _check_enum_values(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that enum fields have valid values."""
    for si in spec.get("_sub_issue_files", []):
        data = si.data
        if not data:
            continue
        iid = si.sub_issue_id

        # Status
        status = data.get("status")
        if status and status not in VALID_STATUSES:
            result.add("error", "schema",
                f"{iid}: status '{status}' is invalid. Must be one of {sorted(VALID_STATUSES)}.")

        # Type
        type_ = data.get("type")
        if type_ and type_ not in VALID_TYPES:
            result.add("error", "schema",
                f"{iid}: type '{type_}' is invalid. Must be one of {sorted(VALID_TYPES)}.")

        # Priority
        priority = data.get("priority")
        if priority and priority not in VALID_PRIORITIES:
            result.add("error", "schema",
                f"{iid}: priority '{priority}' is invalid. Must be one of {sorted(VALID_PRIORITIES)}.")

        # Effort
        effort = data.get("effort")
        if effort and effort not in VALID_EFFORTS:
            result.add("error", "schema",
                f"{iid}: effort '{effort}' is invalid. Must be one of {sorted(VALID_EFFORTS)}.")


def _check_timestamps(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that created/updated are ISO 8601 timestamps and updated >= created."""
    for si in spec.get("_sub_issue_files", []):
        data = si.data
        if not data:
            continue
        iid = si.sub_issue_id

        created = data.get("created", "")
        updated = data.get("updated", "")

        if created and not ISO_8601_RE.match(str(created)):
            result.add("error", "schema",
                f"{iid}: created '{created}' is not a valid ISO 8601 timestamp.")

        if updated and not ISO_8601_RE.match(str(updated)):
            result.add("error", "schema",
                f"{iid}: updated '{updated}' is not a valid ISO 8601 timestamp.")

        if created and updated and str(updated) < str(created):
            result.add("warning", "schema",
                f"{iid}: updated ({updated}) is before created ({created}).")


def _check_refs_exist(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Validate that isRefs and epRefs point to existing issues/epics."""
    sub_issues = spec.get("_sub_issue_files", [])
    epic_id = spec.get("_epic_id", "")
    issue_ids = spec.get("_issue_ids", set())

    for si in sub_issues:
        data = si.data
        if not data:
            continue
        iid = si.sub_issue_id

        # Check epRefs
        ep_refs = data.get("epRefs", [])
        if not isinstance(ep_refs, list):
            result.add("error", "schema", f"{iid}: epRefs must be an array.")
        else:
            if not ep_refs:
                result.add("warning", "schema", f"{iid}: epRefs is empty — sub-issue should reference its parent epic.")
            else:
                for ref in ep_refs:
                    if not EP_ID_RE.match(str(ref)):
                        result.add("error", "schema",
                            f"{iid}: epRefs contains invalid epic ID '{ref}'.")
                    elif ref != epic_id and epic_id:
                        result.add("warning", "schema",
                            f"{iid}: epRefs contains '{ref}' but sub-issue is under '{epic_id}'.")

        # Check isRefs
        is_refs = data.get("isRefs", [])
        if not isinstance(is_refs, list):
            result.add("error", "schema", f"{iid}: isRefs must be an array.")
        else:
            if not is_refs:
                result.add("warning", "schema", f"{iid}: isRefs is empty — sub-issue should reference its parent issue.")
            else:
                for ref in is_refs:
                    if not IS_ID_RE.match(str(ref)):
                        result.add("error", "schema",
                            f"{iid}: isRefs contains invalid issue ID '{ref}'.")
                    elif issue_ids and ref not in issue_ids:
                        result.add("error", "schema",
                            f"{iid}: isRefs references '{ref}' which does not exist in epic '{epic_id}'.")


def _check_scope_inheritance(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Validate that sub-issue scope items reference parent Issue scope items."""
    sub_issues = spec.get("_sub_issue_files", [])
    issue_data = spec.get("_issue_data", {})

    if not issue_data:
        return

    # Extract parent issue's in-scope descriptions
    issue_scope = issue_data.get("scope", {})
    parent_in_scope = {
        item.get("description", "")
        for item in issue_scope.get("inScope", [])
        if isinstance(item, dict) and item.get("description")
    }
    parent_out_scope = {
        item.get("description", "")
        for item in issue_scope.get("outOfScope", [])
        if isinstance(item, dict) and item.get("description")
    }

    if not parent_in_scope and not parent_out_scope:
        return  # Parent has no scope — can't validate inheritance

    for si in sub_issues:
        data = si.data
        if not data:
            continue
        iid = si.sub_issue_id

        si_scope = data.get("scope", {})
        si_in_scope = si_scope.get("inScope", [])
        si_out_scope = si_scope.get("outOfScope", [])

        # Check in-scope items reference parent
        for item in si_in_scope:
            desc = item.get("description", "") if isinstance(item, dict) else str(item)
            if desc and parent_in_scope and desc not in parent_in_scope:
                result.add("warning", "scope",
                    f"{iid}: in-scope item '{desc[:60]}' does not match any parent Issue in-scope item.",
                    hint="Sub-issue scope items should reference parent Issue scope items.")

        # Check out-of-scope items reference parent
        for item in si_out_scope:
            desc = item.get("description", "") if isinstance(item, dict) else str(item)
            if desc and parent_out_scope and desc not in parent_out_scope:
                result.add("warning", "scope",
                    f"{iid}: out-of-scope item '{desc[:60]}' does not match any parent Issue out-of-scope item.",
                    hint="Sub-issue scope items should reference parent Issue scope items.")


def _check_files_format(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Validate the files array (audit trail) — paths must be valid, actions must be valid."""
    for si in spec.get("_sub_issue_files", []):
        data = si.data
        if not data:
            continue
        iid = si.sub_issue_id

        files = data.get("files", [])
        if not isinstance(files, list):
            result.add("error", "schema", f"{iid}: files must be an array.")
            continue

        for i, f in enumerate(files):
            if not isinstance(f, dict):
                result.add("error", "schema",
                    f"{iid}: files[{i}] must be an object with 'path' and 'action'.")
                continue

            path = f.get("path")
            action = f.get("action")

            if not path or not isinstance(path, str):
                result.add("error", "schema",
                    f"{iid}: files[{i}] missing or invalid 'path'.")

            if not action:
                result.add("error", "schema",
                    f"{iid}: files[{i}] missing 'action'.")
            elif action not in VALID_FILE_ACTIONS:
                result.add("error", "schema",
                    f"{iid}: files[{i}] action '{action}' is invalid. Must be one of {sorted(VALID_FILE_ACTIONS)}.")


def _check_file_naming(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that directory name matches file name (SI-NNN-slug/SI-NNN-slug.md)."""
    for si in spec.get("_sub_issue_files", []):
        expected_md = f"{si.sub_issue_id}.md"
        if si.md_path.exists() and si.md_path.name != expected_md:
            result.add("error", "structure",
                f"{si.sub_issue_id}: md file is '{si.md_path.name}' but expected '{expected_md}'.")

        expected_json = f"{si.sub_issue_id}.json"
        if si.json_path.exists() and si.json_path.name != expected_json:
            result.add("error", "structure",
                f"{si.sub_issue_id}: json file is '{si.json_path.name}' but expected '{expected_json}'.")


def _check_directory_structure(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that work/ directory exists for each sub-issue."""
    for si in spec.get("_sub_issue_files", []):
        if not si.work_dir.exists():
            result.add("warning", "structure",
                f"{si.sub_issue_id}: missing 'work/' directory at {si.work_dir}.")


def _check_acceptance_criteria(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that acceptance criteria are non-empty and meaningful."""
    for si in spec.get("_sub_issue_files", []):
        data = si.data
        if not data:
            continue
        iid = si.sub_issue_id

        ac = data.get("acceptanceCriteria", [])
        if not isinstance(ac, list) or not ac:
            result.add("warning", "schema",
                f"{iid}: acceptanceCriteria is empty. Add at least one verifiable criterion.")
            continue

        for i, item in enumerate(ac):
            desc = item.get("description", "") if isinstance(item, dict) else str(item)
            if not desc or len(desc.strip()) < 10:
                result.add("warning", "schema",
                    f"{iid}: acceptanceCriteria[{i}] is too short or empty.",
                    hint="Each acceptance criterion should be a meaningful, verifiable statement.")


# ── Linter Class ──────────────────────────────────────────────────────────────

class SubIssuesLinter(BaseLinter):
    """BaseLinter wrapper for sub-issue file validation."""

    SPEC_NAME = "subissues"
    SEMANTIC_RULES = []
    MISC_CHECKS = [
        _check_required_fields,
        _check_artifact_type,
        _check_enum_values,
        _check_timestamps,
        _check_refs_exist,
        _check_scope_inheritance,
        _check_files_format,
        _check_file_naming,
        _check_directory_structure,
        _check_acceptance_criteria,
    ]
    CROSS_SPEC_DEPS = ["glossary"]

    def __init__(self, epics_dir: str, epic_id: str, issue_id: str, strict: bool = False):
        self.epics_dir = Path(epics_dir)
        self.epic_id = epic_id
        self.issue_id = issue_id

        # Load data before base init
        self._sub_issue_files: list[SubIssueFile] = []
        self._issue_data: dict = {}
        self._issue_ids: set = set()
        self._load_issue_data()
        self._load_sub_issue_files()

        dynamic_spec = {
            "_sub_issue_files": self._sub_issue_files,
            "_epic_id": self.epic_id,
            "_issue_id": self.issue_id,
            "_issue_data": self._issue_data,
            "_issue_ids": self._issue_ids,
        }

        super().__init__(dynamic_spec, strict=strict)

    def _load_issue_data(self) -> None:
        """Load parent issue data and sibling issue IDs."""
        epic_dir = self.epics_dir / self.epic_id
        issue_dir = epic_dir / self.issue_id

        if not issue_dir.exists():
            self.result.add("error", "structure",
                f"Issue directory not found: {issue_dir}")
            return

        # Load parent issue JSON
        issue_json = issue_dir / f"{self.issue_id}.json"
        if issue_json.exists():
            try:
                self._issue_data = json.loads(issue_json.read_text())
            except json.JSONDecodeError as e:
                self.result.add("error", "schema",
                    f"Parent issue JSON is invalid: {e}")
        else:
            self.result.add("warning", "structure",
                f"Parent issue JSON not found: {issue_json}")

        # Collect all issue IDs in this epic
        if epic_dir.exists():
            for entry in epic_dir.iterdir():
                if entry.is_dir() and IS_ID_RE.match(entry.name):
                    self._issue_ids.add(entry.name)

    def _load_sub_issue_files(self) -> None:
        """Load all sub-issue files in the issue folder."""
        issue_dir = self.epics_dir / self.epic_id / self.issue_id
        if not issue_dir.exists():
            return

        si_dirs = sorted([
            d for d in issue_dir.iterdir()
            if d.is_dir() and SI_ID_RE.match(d.name)
        ])

        if not si_dirs:
            self.result.add("info", "epic",
                f"Issue {self.issue_id} has no sub-issues yet")
            return

        for si_dir in si_dirs:
            si_id = si_dir.name
            json_path = si_dir / f"{si_id}.json"
            md_path = si_dir / f"{si_id}.md"
            work_dir = si_dir / "work"

            if not json_path.exists():
                self.result.add("error", "structure",
                    f"Missing {si_id}.json in {si_dir}")
                continue

            si_file = SubIssueFile(
                epic_id=self.epic_id,
                issue_id=self.issue_id,
                sub_issue_id=si_id,
                json_path=json_path,
                md_path=md_path,
                work_dir=work_dir,
            )

            try:
                si_file.data = json.loads(json_path.read_text())
            except json.JSONDecodeError as e:
                self.result.add("error", "schema",
                    f"{si_id}.json is not valid JSON: {e}")
                self._sub_issue_files.append(si_file)
                continue

            if md_path.exists():
                si_file.md_content = md_path.read_text()

            self._sub_issue_files.append(si_file)

    def run(self, glossary: Optional[dict] = None, **kwargs) -> LayerResult:
        """Run all sub-issue linters and return results."""
        self.extra_specs = {"glossary": glossary}
        super().run()
        return self.result

    def _run_misc_checks(self) -> None:
        """Run custom sub-issue-specific checks."""
        for func in self.MISC_CHECKS:
            func(self.spec, self.result, self.extra_specs)

    def _run_semantic_rules(self) -> None:
        """No semantic rules for sub-issues yet."""
        pass


# Canonical linter class for lint_all.py
LinterClass = SubIssuesLinter


# ── Main ──────────────────────────────────────────────────────────────────────

def run_lint(epic_id: str, issue_id: str, epics_dir: str,
             glossary: Optional[dict] = None, strict: bool = False):
    """Run the sub-issue linter. Returns a LayerResult."""
    linter = SubIssuesLinter(epics_dir, epic_id, issue_id, strict=strict)
    return linter.run(glossary=glossary)


def _load_json(path: str, label: str) -> Optional[dict]:
    """Load a JSON file, printing warning on failure."""
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"Warning: Could not load {label} from {path}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Lint sub-issue files for an issue")
    parser.add_argument("--epic", required=True, help="Epic ID (e.g., EP-001-userOnboarding)")
    parser.add_argument("--issue", required=True, help="Issue ID (e.g., IS-001-implementLogin)")
    parser.add_argument("--epics-dir", default="tasks",
                        help="Path to tasks directory (default: tasks)")
    parser.add_argument("--glossary", default=None,
                        help="Path to glossary.json for reference validation")
    parser.add_argument("--strict", action="store_true",
                        help="Treat warnings as errors")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    args = parser.parse_args()

    linter = SubIssuesLinter(args.epics_dir, args.epic, args.issue, strict=args.strict)
    result = linter.run(
        glossary=_load_json(args.glossary, "glossary") if args.glossary else None,
    )

    if args.json:
        print_json_output(result)
    else:
        print_human(result, f"{args.epic}/{args.issue} in {args.epics_dir}")

    sys.exit(0 if result.clean else 1)


if __name__ == "__main__":
    main()
