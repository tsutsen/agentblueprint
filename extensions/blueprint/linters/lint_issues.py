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

from shared import BaseLinter, Issue, LayerResult, print_human, print_json_output, _build_glossary_map, check_glossary_refs
from lint_schemas import SchemaValidator
from rules import _run_new_semantic_rules


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

EPIC_ID_RE = re.compile(r"^EP-\d{3}-[a-z][a-zA-Z0-9]*$")
ISSUE_ID_RE = re.compile(r"^IS-\d{3}-[a-z][a-zA-Z0-9]*$")
SUB_ISSUE_ID_RE = re.compile(r"^SI-\d{3}-[a-z][a-zA-Z0-9]*$")
MILESTONE_RE = re.compile(r"^MIL-\d+-[A-Z][a-zA-Z]*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
GL_ID_RE = re.compile(r"^GL-\d{3}$")


# ── Core linter ───────────────────────────────────────────────────────────────


def _check_id_sequence(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that issue IDs within this epic are sequential from the epic start."""
    issue_files = spec.get("_issue_files", [])
    if len(issue_files) < 2:
        return

    numeric_ids = sorted([int(f.issue_id.split("-")[1]) for f in issue_files])
    min_id = numeric_ids[0]
    max_id = numeric_ids[-1]

    expected = set(range(min_id, max_id + 1))
    actual = set(numeric_ids)
    missing = expected - actual

    for gap in missing:
        result.add("warning", "id",
            f"Gap in issue ID sequence within epic: IS-{gap:03d} is missing",
            f"Within this epic, issue IDs should be sequential. "
            f"Current range: IS-{min_id:03d} to IS-{max_id:03d}.")


def _check_dependency_ordering(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that blocked issues have higher IS-NNN than their blockers."""
    issue_files = spec.get("_issue_files", [])
    if not issue_files:
        return

    existing_ids = {f.issue_id for f in issue_files}
    id_to_num = {f.issue_id: int(f.issue_id.split("-")[1]) for f in issue_files}

    for issue_file in issue_files:
        blocked_by = issue_file.data.get("blocked_by", [])
        issue_num = id_to_num[issue_file.issue_id]
        for ref in blocked_by:
            if ref in id_to_num and id_to_num[ref] >= issue_num:
                result.add("warning", "dependency",
                    f"{issue_file.issue_id}: blocked_by '{ref}' has equal or higher ID — "
                    f"the blocker should have a lower IS-NNN number")


def _check_dependency_cycles(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Detect cycles in the blocked_by dependency graph."""
    issue_files = spec.get("_issue_files", [])
    if len(issue_files) < 2:
        return

    existing_ids = {f.issue_id for f in issue_files}
    graph: dict[str, list[str]] = {}
    for issue_file in issue_files:
        blocked_by = issue_file.data.get("blocked_by", [])
        graph[issue_file.issue_id] = [r for r in blocked_by if r in existing_ids]

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
                result.add("error", "dependency",
                    f"Circular dependency detected: {' → '.join(cycle)}")
                break


def _check_epic_consistency(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that issue.epic matches the target epic ID."""
    issue_files = spec.get("_issue_files", [])
    epic_id = spec.get("_epic_id", "")

    for issue_file in issue_files:
        issue_epic = issue_file.data.get("epic", "")
        if issue_epic and issue_epic != epic_id:
            result.add("error", "epic",
                f"{issue_file.issue_id}: epic field is '{issue_epic}' but issue is in {epic_id}")


def _check_non_goal_violation(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that issue does not implement something explicitly out of scope.

    Optimized to avoid O(n*m*k) text matching by:
    1. Pre-computing a keyword index from out-of-scope items
    2. Extracting issue text once per file
    3. Using set intersection for fast keyword matching
    """
    issue_files = spec.get("_issue_files", [])
    epic_data = spec.get("_epic_data", {})
    goal = extra_specs.get("goal")
    glossary = extra_specs.get("glossary")

    if not issue_files:
        return

    # Build glossary lookup
    glossary_lookup: dict[str, dict] = {}
    if glossary:
        for entry in glossary.get("terms", []):
            term_id = entry.get("id", "")
            if term_id and GL_ID_RE.match(term_id):
                glossary_lookup[term_id] = {
                    "term": entry["term"],
                    "synonyms": [s.lower() for s in entry.get("synonyms", [])],
                    "definition": entry.get("definition", "").lower(),
                }

    # Collect out-of-scope items from epic + GoalSpec
    out_of_scope_items: list[str] = []

    if epic_data and epic_data.get("content"):
        out_of_scope_items.extend(
            _extract_markdown_list_items(epic_data["content"], "out of scope")
        )

    if goal:
        for ng in goal.get("nonGoals", []):
            if isinstance(ng, str):
                ng_text = ng.strip()
            elif isinstance(ng, dict):
                ng_text = ng.get("capability", "").strip()
            else:
                continue
            if len(ng_text) > 5:
                out_of_scope_items.append(ng_text)

    if not out_of_scope_items:
        return

    # Build expanded out-of-scope entries with keywords
    expanded_items: list[tuple[str, set[str], str]] = []

    for item in out_of_scope_items:
        item_lower = item.lower()

        # Strategy 1: GL-NNN reference
        gl_match = re.match(r"gl-(\d{3})", item_lower)
        if gl_match and gl_match.group(0).upper() in glossary_lookup:
            term_id = gl_match.group(0).upper()
            entry = glossary_lookup[term_id]
            check_text = f"{entry['term'].lower()} " + " ".join(entry["synonyms"])
            keywords = {w for w in check_text.split() if len(w) > 3}
            expanded_items.append((entry["term"], keywords, term_id))
            continue

        # Strategy 2: Direct glossary term match
        if glossary_lookup:
            for term_id, entry in glossary_lookup.items():
                if entry["term"].lower() == item_lower:
                    check_text = entry["term"].lower() + " " + " ".join(entry["synonyms"])
                    keywords = {w for w in check_text.split() if len(w) > 3}
                    expanded_items.append((entry["term"], keywords, term_id))
                    break
            else:
                # Strategy 3: Synonym match
                for term_id, entry in glossary_lookup.items():
                    if item_lower in [s.lower() for s in entry["synonyms"]]:
                        check_text = entry["term"].lower() + " " + " ".join(entry["synonyms"])
                        keywords = {w for w in check_text.split() if len(w) > 3}
                        expanded_items.append((entry["term"], keywords, term_id))
                        break
                else:
                    # Strategy 4: Fallback
                    keywords = {w for w in item_lower.split() if len(w) > 3}
                    expanded_items.append((item, keywords, "unknown"))

    # Pre-compute issue text once per file
    for issue_file in issue_files:
        md_content = issue_file.md_content.lower()
        title = issue_file.data.get("title", "").lower()

        # Robust extraction of "What to build" section
        body_text = _extract_markdown_section(md_content, "what to build")
        full_text = f"{title} {body_text}"
        full_text_words = set(full_text.split())

        for display_name, keywords, source_id in expanded_items:
            # Fast set intersection: check if any keyword is in the text
            if source_id != "unknown":
                gl_ref = f"{source_id.lower()}"
                if gl_ref in full_text:
                    result.add("error", "scope",
                        f"{issue_file.issue_id}: implements out-of-scope item {source_id} '{display_name}'")
                    continue

            # O(k) per item instead of O(k*n) — single set lookup
            if keywords & full_text_words:
                result.add("error", "scope",
                    f"{issue_file.issue_id}: implements out-of-scope item '{display_name}'")


def _extract_markdown_list_items(content: str, heading: str) -> list[str]:
    """Extract list items from a markdown section by heading.

    Robustly handles various heading formats and multi-line list items.
    """
    # Find the heading (case-insensitive, flexible whitespace)
    heading_match = re.search(
        rf'^##\s+{re.escape(heading)}\s*$',
        content,
        re.MULTILINE | re.IGNORECASE
    )
    if not heading_match:
        return []

    after_heading = content[heading_match.end():]

    # Collect list items until next heading
    items_match = re.match(
        r'(?:\s*- .+(?:\n(?![\s]*##)[^\n]*)*)*',
        after_heading
    )
    if not items_match:
        return []

    text = items_match.group(0)
    return [
        line.strip().lstrip("- ").strip()
        for line in text.split("\n")
        if line.strip().startswith("-") and len(line.strip()) > 5
    ]


def _extract_markdown_section(content: str, heading: str) -> str:
    """Extract section text from markdown by heading.

    Robustly handles various heading formats and multi-line content.
    """
    heading_match = re.search(
        rf'^##\s+{re.escape(heading)}\s*$',
        content,
        re.MULTILINE | re.IGNORECASE
    )
    if not heading_match:
        return ""

    after_heading = content[heading_match.end():]

    # Get content until next heading
    next_heading = re.search(r'^##\s+', after_heading, re.MULTILINE)
    if next_heading:
        return after_heading[:next_heading.start()]
    return after_heading


def _check_glossary_refs(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that issue text sections have glossaryRefs when they contain domain concepts."""
    issue_files = spec.get("_issue_files", [])
    glossary = extra_specs.get("glossary")

    if not issue_files or not glossary:
        return

    glossary_map = _build_glossary_map(glossary.get("terms", []))

    def _warn(text: str, refs: list, ctx: str) -> None:
        """Helper to warn about missing glossaryRefs."""
        missing = check_glossary_refs(text, glossary_map, refs)
        if missing:
            result.add("warning", "glossary",
                f"{ctx} references glossary terms ({', '.join(missing)}) but has no glossaryRefs.",
                hint="Add glossaryRefs (GL-NNN) for domain concepts.")

    for issue_file in issue_files:
        iid = issue_file.issue_id

        # Check title
        title = issue_file.data.get("title", "")
        title_refs = issue_file.data.get("titleGlossaryRefs", [])
        if title and not title_refs:
            _warn(title, title_refs, f"{iid} title '{title}'")

        # Check inScope items
        for i, item in enumerate(issue_file.data.get("inScope", [])):
            desc = item.get("description", "") if isinstance(item, dict) else str(item)
            refs = item.get("glossaryRefs", []) if isinstance(item, dict) else []
            if desc and not refs:
                _warn(desc, refs,
                    f"{iid} inScope #{i+1}: '{desc[:60]}...'")

        # Check outOfScope items
        for i, item in enumerate(issue_file.data.get("outOfScope", [])):
            desc = item.get("description", "") if isinstance(item, dict) else str(item)
            refs = item.get("glossaryRefs", []) if isinstance(item, dict) else []
            if desc and not refs:
                _warn(desc, refs,
                    f"{iid} outOfScope #{i+1}: '{desc[:60]}...'")

        # Check acceptance criteria
        for i, item in enumerate(issue_file.data.get("acceptanceCriteria", [])):
            desc = item.get("description", "") if isinstance(item, dict) else str(item)
            refs = item.get("glossaryRefs", []) if isinstance(item, dict) else []
            if desc and not refs:
                _warn(desc, refs,
                    f"{iid} AC #{i+1}: '{desc[:60]}...'")


def _check_coverage(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that every epic acceptance criterion maps to at least one issue.

    Uses a robust approach: extracts acceptance criteria from markdown by
    finding the section heading and collecting all list items under it,
    rather than relying on a fragile regex.
    """
    issue_files = spec.get("_issue_files", [])
    epic_data = spec.get("_epic_data", {})

    if not issue_files or not epic_data or not epic_data.get("acceptance_criteria"):
        return

    acceptance_criteria = epic_data["acceptance_criteria"]
    covered = set()

    for issue_file in issue_files:
        md_content = issue_file.md_content
        # Extract acceptance criteria text from markdown
        issue_acs_text = _extract_acceptance_criteria_text(md_content)
        if not issue_acs_text:
            continue

        issue_acs_words = set(issue_acs_text.lower().split())

        for epic_ac in acceptance_criteria:
            epic_ac_text = epic_ac.strip().lstrip("- ")
            if epic_ac_text.lower() in issue_acs_text:
                covered.add(epic_ac)
                continue
            epic_words = {w for w in epic_ac_text.lower().split() if len(w) > 3}
            if epic_words & issue_acs_words:
                overlap = epic_words & issue_acs_words
                if len(overlap) >= 2:
                    covered.add(epic_ac)
                elif len(overlap) >= 1 and len(epic_words) <= 4:
                    covered.add(epic_ac)


def _extract_acceptance_criteria_text(md_content: str) -> str:
    """Extract acceptance criteria text from markdown content.

    Finds the 'Acceptance criteria' heading and collects all subsequent
    list items (including multi-line items) until the next heading.
    """
    # Find the acceptance criteria heading
    heading_match = re.search(
        r'^##\s+Acceptance\s+(?:criteria|Criteria)\s*$',
        md_content,
        re.MULTILINE | re.IGNORECASE
    )
    if not heading_match:
        return ''

    # Get text after the heading
    after_heading = md_content[heading_match.end():]

    # Collect all list items until next heading (## or ###)
    items_match = re.match(
        r'(?:\s*- \[[ xX]\] .+(?:\n(?!\s*##)[^\n]*)*)*',
        after_heading
    )
    if not items_match:
        return ''

    return items_match.group(0)




def _check_schema(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Validate each issue's JSON against its schema and semantic rules."""
    issue_files = spec.get("_issue_files", [])
    if not issue_files:
        return

    schema_path = Path(__file__).resolve().parent.parent.parent.parent / "skills" / "blueprint" / "schemas" / "json" / "issue.schema.json"
    validator = SchemaValidator(schema_path) if schema_path.exists() else None

    for issue_file in issue_files:
        data = issue_file.data
        if not data:
            continue

        if validator:
            schema_issues = validator.validate(data)
            for issue in schema_issues:
                msg = f"{issue_file.issue_id}: {issue.message}"
                result.add(issue.severity, "schema", msg, issue.hint)

        # Check updated >= created
        created = data.get("created", "")
        updated = data.get("updated", "")
        if created and updated and updated < created:
            result.add("warning", "schema",
                f"{issue_file.issue_id}: updated ({updated}) is before created ({created})")

        # Check blocked_by duplicates
        blocked_by = data.get("blocked_by", [])
        if isinstance(blocked_by, list) and len(blocked_by) != len(set(blocked_by)):
            result.add("warning", "schema",
                f"{issue_file.issue_id}: duplicate entries in blocked_by")


def _check_file_naming(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that directory name matches file name (IS-001/IS-001.md)."""
    issue_files = spec.get("_issue_files", [])
    if not issue_files:
        return

    for issue_file in issue_files:
        expected_name = f"{issue_file.issue_id}.md"
        if issue_file.md_path.name != expected_name:
            result.add("error", "structure",
                f"{issue_file.issue_id}: file is '{issue_file.md_path.name}' "
                f"but directory is '{issue_file.md_path.parent.name}' — "
                f"expected '{expected_name}'")
        expected_json_name = f"{issue_file.issue_id}.json"
        if issue_file.json_path.name != expected_json_name:
            result.add("error", "structure",
                f"{issue_file.issue_id}: file is '{issue_file.json_path.name}' "
                f"but directory is '{issue_file.json_path.parent.name}' — "
                f"expected '{expected_json_name}'")


def _check_body(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Validate the markdown body of each issue file."""
    issue_files = spec.get("_issue_files", [])
    if not issue_files:
        return

    for issue_file in issue_files:
        md = issue_file.md_content

        # Support both old "What to build" and new "Description" sections
        if "## What to build" not in md and "## Description" not in md:
            result.add("error", "structure",
                f"{issue_file.issue_id}: missing 'What to build' or 'Description' section")

def _check_enum_values(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that type, status, priority, effort have valid values."""
    VALID_TYPES = {"AFK", "HITL"}
    VALID_STATUSES = {"not_started", "in_progress", "needs_review", "complete"}
    VALID_PRIORITIES = {"P0", "P1", "P2", "P3"}
    VALID_EFFORTS = {"XS", "S", "M", "L", "XL"}

    for issue_file in spec.get("_issue_files", []):
        data = issue_file.data
        if not data:
            continue
        iid = issue_file.issue_id

        type_ = data.get("type")
        if type_ and type_ not in VALID_TYPES:
            result.add("error", "schema",
                f"{iid}: type '{type_}' is invalid. Must be one of {sorted(VALID_TYPES)}.")

        status = data.get("status")
        if status and status not in VALID_STATUSES:
            result.add("error", "schema",
                f"{iid}: status '{status}' is invalid. Must be one of {sorted(VALID_STATUSES)}.")

        priority = data.get("priority")
        if priority and priority not in VALID_PRIORITIES:
            result.add("error", "schema",
                f"{iid}: priority '{priority}' is invalid. Must be one of {sorted(VALID_PRIORITIES)}.")

        effort = data.get("effort")
        if effort and effort not in VALID_EFFORTS:
            result.add("error", "schema",
                f"{iid}: effort '{effort}' is invalid. Must be one of {sorted(VALID_EFFORTS)}.")


def _check_sub_issue_structure(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that sub-issue directories under each issue are correctly structured."""
    issue_files = spec.get("_issue_files", [])
    if not issue_files:
        return

    for issue_file in issue_files:
        issue_dir = issue_file.md_path.parent
        if not issue_dir.exists():
            continue

        # Look for SI directories
        si_dirs = [d for d in issue_dir.iterdir() if d.is_dir() and SUB_ISSUE_ID_RE.match(d.name)]
        for si_dir in si_dirs:
            si_id = si_dir.name
            si_json = si_dir / f"{si_id}.json"
            si_md = si_dir / f"{si_id}.md"
            work_dir = si_dir / "work"

            if not si_json.exists():
                result.add("error", "structure",
                    f"{si_id}: missing JSON file at {si_json}")
            if not si_md.exists():
                result.add("warning", "structure",
                    f"{si_id}: missing markdown file at {si_md}")
            if not work_dir.exists():
                result.add("info", "structure",
                    f"{si_id}: missing 'work/' directory — create when agent starts work")


def _check_scope_refs(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that scope items have proper ref fields (new schema)."""
    issue_files = spec.get("_issue_files", [])
    glossary = extra_specs.get("glossary")

    if not issue_files:
        return

    gl_ids = set()
    if glossary:
        gl_ids = {t.get("id", "") for t in glossary.get("terms", [])}

    for issue_file in issue_files:
        data = issue_file.data
        if not data:
            continue
        iid = issue_file.issue_id

        for scope_type in ["inScope", "outOfScope"]:
            for item in data.get("scope", {}).get(scope_type, []):
                if not isinstance(item, dict):
                    continue

                # Check glRefs reference valid glossary terms
                for ref in item.get("glRefs", []):
                    if gl_ids and ref not in gl_ids:
                        result.add("warning", "ref",
                            f"{iid}: {scope_type} glRefs '{ref}' not found in glossary.")


def _check_required_fields(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that required fields are present (new schema)."""
    required = [
        "schemaVersion", "artifact", "id", "name", "description",
        "type", "status", "milestone", "acceptanceCriteria",
        "created", "updated",
    ]

    for issue_file in spec.get("_issue_files", []):
        data = issue_file.data
        if not data:
            continue
        for field in required:
            if field not in data:
                result.add("error", "schema",
                    f"{issue_file.issue_id}: missing required field '{field}'.")


def _check_artifact_type(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that artifact type is 'Issue'."""
    for issue_file in spec.get("_issue_files", []):
        data = issue_file.data
        if not data:
            continue
        if data.get("artifact") != "Issue":
            result.add("error", "schema",
                f"{issue_file.issue_id}: artifact must be 'Issue', got '{data.get('artifact')}'.")


class IssuesLinter(BaseLinter):
    """BaseLinter wrapper for issue file validation.

    This linter validates issue files within an epic folder for structural
    correctness, dependency consistency, and coverage completeness.

    Note: Most issue checks (dependency cycles, ID sequencing, non-goal
    violations, coverage, markdown body validation) are too complex for
    declarative semantic rules and remain in MISC_CHECKS.
    """

    SPEC_NAME = "issues"
    SEMANTIC_RULES = [
        # blocked_by references must exist in the epic's issue files
        {
            "check": "exists",
            "target": "_issue_files.blocked_by",
            "inside": "_issue_files",
            "target_label": "Issue",
            "ref_label": "Issue",
            "category": "dependency_missing",
            "hint": "The blocked_by reference must point to a real issue ID.",
        },
        # milestone must exist in TaskPlan milestones
        {
            "check": "exists",
            "target": "_issue_files.milestone",
            "inside": "taskplan:milestones",
            "target_label": "Issue",
            "ref_label": "TaskPlan milestone",
            "category": "milestone_missing",
            "hint": "The milestone must exist in TaskPlan milestones.",
        },
    ]
    MISC_CHECKS = [
        _check_required_fields,
        _check_artifact_type,
        _check_enum_values,
        _check_id_sequence,
        _check_dependency_ordering,
        _check_dependency_cycles,
        _check_epic_consistency,
        _check_non_goal_violation,
        _check_glossary_refs,
        _check_coverage,
        _check_scope_refs,
        _check_schema,
        _check_file_naming,
        _check_body,
        _check_sub_issue_structure,
    ]
    CROSS_SPEC_DEPS = ["taskplan", "goal", "glossary"]

    def __init__(self, epics_dir: str, epic_id: str, schema_path: Optional[Path] = None,
                 strict: bool = False):
        self.epics_dir = Path(epics_dir)
        self.epic_id = epic_id

        # Load epic and issue files first (need to build spec before base init)
        self._issue_files: list = []
        self._epic_data: dict = {}
        self._load_epic()
        self._load_issue_files()
        dynamic_spec = {"_issue_files": self._issue_files, "_epic_data": self._epic_data}

        # Initialize base class with dynamically built spec
        super().__init__(dynamic_spec, schema_path, strict)

    def _load_epic(self) -> None:
        """Load the epic file for context (acceptance criteria, scope)."""
        epic_folder = self.epics_dir / self.epic_id
        epic_files = []
        if epic_folder.exists():
            epic_files = list(epic_folder.glob(f"{self.epic_id}-*.md"))

        if not epic_files:
            epic_files = list(self.epics_dir.glob(f"{self.epic_id}-*.md"))

        if not epic_files:
            self.result.add("error", "structure",
                f"Epic file not found for {self.epic_id} in {self.epics_dir}")
            return

        epic_file = epic_files[0]
        self._epic_data["md_path"] = epic_file
        self._epic_data["content"] = epic_file.read_text()

        content = epic_file.read_text()
        ac_pattern = re.compile(r"- \[ \] (.+)")
        self._epic_data["acceptance_criteria"] = ac_pattern.findall(content)

    def _load_issue_files(self) -> None:
        """Load all issue files in the epic folder."""
        epic_folder = self.epics_dir / self.epic_id
        if not epic_folder.exists():
            self.result.add("error", "structure",
                f"Epic folder {epic_folder} does not exist")
            return

        issue_dirs = sorted([
            d for d in epic_folder.iterdir()
            if d.is_dir() and ISSUE_ID_RE.match(d.name)
        ])

        if not issue_dirs:
            self.result.add("info", "epic",
                f"Epic {self.epic_id} has no issues yet — decomposition may be pending")
            return

        for issue_dir in issue_dirs:
            issue_id = issue_dir.name
            md_path = issue_dir / f"{issue_id}.md"
            json_path = issue_dir / f"{issue_id}.json"

            if not md_path.exists():
                self.result.add("error", "structure",
                    f"Missing {issue_id}.md in {issue_dir}")
                continue

            if not json_path.exists():
                self.result.add("error", "structure",
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
                self.result.add("error", "schema",
                    f"{issue_id}.json is not valid JSON: {e}")
                self._issue_files.append(issue_file)
                continue

            self._issue_files.append(issue_file)

    def run(self, taskplan: Optional[dict] = None, goal: Optional[dict] = None,
            glossary: Optional[dict] = None, **kwargs) -> LayerResult:
        """Run all issue linters and return results."""
        self.extra_specs = {"taskplan": taskplan, "goal": goal, "glossary": glossary}

        # Run the BaseLinter pipeline
        super().run()

        return self.result

    def _run_misc_checks(self) -> None:
        """Run custom issue-specific checks."""
        for func in self.MISC_CHECKS:
            func(self.spec, self.result, self.extra_specs)

    def _run_semantic_rules(self) -> None:
        """Run semantic rules with issue files context."""
        _run_new_semantic_rules(self.SEMANTIC_RULES, self.spec, self.result, self.extra_specs)


def run_lint(epic_id: str, epics_dir: str, taskplan: Optional[dict] = None,
             goal: Optional[dict] = None, glossary: Optional[dict] = None, strict: bool = False):
    """Run the issue linter for a single epic. Returns a LayerResult."""
    linter = IssuesLinter(epics_dir, epic_id, strict=strict)
    return linter.run(taskplan=taskplan, goal=goal, glossary=glossary)


# Canonical linter class for lint_all.py
LinterClass = IssuesLinter


def _load_json(path: str, label: str) -> Optional[dict]:
    """Load a JSON file, printing warning on failure."""
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"Warning: Could not load {label} from {path}")
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Lint issue files for an epic")
    parser.add_argument("--epic", required=True, help="Epic ID (e.g., EP-001)")
    parser.add_argument("--epics-dir", default="tasks/epics",
                        help="Path to epics directory (default: tasks/epics)")
    parser.add_argument("--taskplan", default=None,
                        help="Path to taskplan.json for milestone validation")
    parser.add_argument("--goal", default=None,
                        help="Path to goalspec.json for non-goal violation check")
    parser.add_argument("--glossary", default=None,
                        help="Path to glossary.json for synonym expansion")
    parser.add_argument("--strict", action="store_true",
                        help="Treat warnings as errors")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    args = parser.parse_args()

    linter = IssuesLinter(args.epics_dir, args.epic, strict=args.strict)
    result = linter.run(
        taskplan=_load_json(args.taskplan, "taskplan") if args.taskplan else None,
        goal=_load_json(args.goal, "goal") if args.goal else None,
        glossary=_load_json(args.glossary, "glossary") if args.glossary else None,
    )

    if args.json:
        print_json_output(result)
    else:
        print_human(result, f"{args.epic} in {args.epics_dir}")

    sys.exit(0 if result.clean else 1)


if __name__ == "__main__":
    main()
