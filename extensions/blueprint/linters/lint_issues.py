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
GL_ID_RE = re.compile(r"^GL-\d{3}$")


# ── Core linter ───────────────────────────────────────────────────────────────

class IssueLinter:
    def __init__(self, epics_dir: str, epic_id: str, strict: bool = False,
                 glossary: Optional[dict] = None):
        self.epics_dir = Path(epics_dir)
        self.epic_id = epic_id
        self.strict = strict
        self.glossary = glossary
        self.issues: list[Issue] = []
        self.issue_files: list[IssueFile] = []
        self.epic_data: dict = {}

    def add_issue(self, severity: str, category: str, message: str, hint: str = ""):
        self.issues.append(Issue(severity, category, message, hint))

    def load_epic(self):
        """Load the epic file for context (acceptance criteria, scope)."""
        # Try standard nested structure first: EP-NNN/EP-NNN-*.md
        epic_folder = self.epics_dir / self.epic_id
        epic_files = []
        if epic_folder.exists():
            epic_files = list(epic_folder.glob(f"{self.epic_id}-*.md"))

        # Fallback: flat structure in epics_dir root
        if not epic_files:
            epic_files = list(self.epics_dir.glob(f"{self.epic_id}-*.md"))

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

        # Check if epic has any issues
        if not issue_dirs:
            self.add_issue("info", "epic",
                f"Epic {self.epic_id} has no issues yet — decomposition may be pending")

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

    def lint_non_goal_violation(self):
        """Check that issue does not implement something explicitly out of scope.
        
        Uses GL-NNN references from glossary when available (most accurate).
        Falls back to glossary term/synonym matching, then word-level overlap.
        """
        # Build glossary lookup: id → {term, synonyms[], definition[]}
        glossary_lookup: dict[str, dict] = {}
        if self.glossary:
            for entry in self.glossary.get("terms", []):
                term_id = entry.get("id", "")
                if term_id and GL_ID_RE.match(term_id):
                    glossary_lookup[term_id] = {
                        "term": entry["term"],
                        "synonyms": [s.lower() for s in entry.get("synonyms", [])],
                        "definition": entry.get("definition", "").lower(),
                    }

        # Collect out-of-scope items from epic + GoalSpec
        out_of_scope_items: list[str] = []
        
        if self.epic_data and self.epic_data.get("content"):
            out_of_scope_match = re.search(
                r"##\s*out\s*of\s*scope\s*\n((?:-\s+.+\n?)*?)(?=\n##|$)",
                self.epic_data["content"],
                re.IGNORECASE | re.DOTALL
            )
            if out_of_scope_match:
                out_of_scope_items.extend([
                    line.strip().lstrip("- ").strip()
                    for line in out_of_scope_match.group(1).split("\n")
                    if line.strip().startswith("-") and len(line.strip()) > 5
                ])
        
        if hasattr(self, 'goal') and self.goal:
            for ng in self.goal.get("nonGoals", []):
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

        # Classify and expand each out-of-scope item
        expanded_items: list[tuple[str, str, str]] = []  # (display_name, check_text, source)
        
        for item in out_of_scope_items:
            item_lower = item.lower()
            
            # Strategy 1: GL-NNN reference (most accurate)
            gl_match = re.match(r"gl-(\d{3})", item_lower)
            if gl_match and gl_match.group(0).upper() in glossary_lookup:
                term_id = gl_match.group(0).upper()
                entry = glossary_lookup[term_id]
                check_text = f"{entry['term'].lower()} " + " ".join(entry["synonyms"])
                expanded_items.append((entry["term"], check_text, term_id))
                continue
            
            # Strategy 2: Direct glossary term match
            if glossary_lookup:
                for term_id, entry in glossary_lookup.items():
                    if entry["term"].lower() == item_lower:
                        check_text = entry["term"].lower() + " " + " ".join(entry["synonyms"])
                        expanded_items.append((entry["term"], check_text, term_id))
                        break
                else:
                    # Strategy 3: Synonym match
                    for term_id, entry in glossary_lookup.items():
                        if item_lower in [s.lower() for s in entry["synonyms"]]:
                            check_text = entry["term"].lower() + " " + " ".join(entry["synonyms"])
                            expanded_items.append((entry["term"], check_text, term_id))
                            break
                    else:
                        # Strategy 4: Fallback — word-level overlap
                        expanded_items.append((item, item_lower, "unknown"))

        for issue_file in self.issue_files:
            md_content = issue_file.md_content.lower()
            title = issue_file.data.get("title", "").lower()
            what_build = re.search(
                r"##\s+What to build\s*\n(.*?)(?=\n##|$)",
                md_content, re.DOTALL
            )
            body_text = what_build.group(1) if what_build else ""
            full_text = f"{title} {body_text}"

            for display_name, check_text, source_id in expanded_items:
                # Check for GL-NNN reference in issue text
                if source_id != "unknown":
                    gl_ref = f"{source_id.lower()}"
                    if gl_ref in full_text:
                        self.add_issue("error", "scope",
                            f"{issue_file.issue_id}: implements out-of-scope item {source_id} '{display_name}'")
                        continue
                
                # Check expanded terms
                for term in check_text.split():
                    if len(term) > 3 and term in full_text:
                        self.add_issue("error", "scope",
                            f"{issue_file.issue_id}: implements out-of-scope item '{display_name}'")
                        break

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

    def check_glossary_refs(self):
        """WARN: Check that issue text sections have glossaryRefs when they contain domain concepts.
        
        Checks title, what-to-build, and acceptance criteria for glossary term references.
        Each section has its own glossaryRefs field in the JSON.
        """
        if not self.glossary:
            return

        # Build glossary term map (lowercase -> id)
        glossary_lower = {}
        for t in self.glossary.get("terms", []):
            glossary_lower[t["term"].lower()] = t["id"]

        def has_domain_concept(text: str) -> bool:
            text_lower = text.lower()
            return any(len(term) > 3 and term in text_lower for term in glossary_lower)

        def find_glossary_refs(text: str) -> list:
            text_lower = text.lower()
            return [tid for term, tid in glossary_lower.items()
                    if len(term) > 3 and term in text_lower]

        for issue_file in self.issue_files:
            # Check title
            title = issue_file.data.get("title", "")
            title_refs = issue_file.data.get("titleGlossaryRefs", [])
            if title and has_domain_concept(title):
                if not title_refs:
                    expected = find_glossary_refs(title)
                    self.add_issue("warning", "glossary",
                        f"{issue_file.issue_id} title '{title}' references glossary terms "
                        f"({', '.join(expected)}) but has no titleGlossaryRefs.",
                        hint="Add titleGlossaryRefs (GL-NNN) for domain concepts in this issue's title.")

            # Check "What to build" section
            what_match = re.search(
                r"##\s+What to build\s*\n(.*?)(?=\n##|$)",
                issue_file.md_content, re.DOTALL
            )
            what_refs = issue_file.data.get("whatGlossaryRefs", [])
            if what_match:
                what_text = what_match.group(1).strip()
                if has_domain_concept(what_text):
                    if not what_refs:
                        expected = find_glossary_refs(what_text)
                        self.add_issue("warning", "glossary",
                            f"{issue_file.issue_id} 'What to build' references glossary terms "
                            f"({', '.join(expected)}) but has no whatGlossaryRefs.",
                            hint="Add whatGlossaryRefs (GL-NNN) for domain concepts in this issue's description.")

            # Check acceptance criteria
            ac_match = re.search(
                r"##\s+Acceptance\s*criteria\s*\n((?:-\s+\[\s*\]\s+.+\n?)*)",
                issue_file.md_content, re.IGNORECASE
            )
            ac_refs = issue_file.data.get("acGlossaryRefs", [])
            if ac_match:
                ac_text = ac_match.group(1)
                if has_domain_concept(ac_text):
                    if not ac_refs:
                        expected = find_glossary_refs(ac_text)
                        self.add_issue("warning", "glossary",
                            f"{issue_file.issue_id} acceptance criteria reference glossary terms "
                            f"({', '.join(expected)}) but have no acGlossaryRefs.",
                            hint="Add acGlossaryRefs (GL-NNN) for domain concepts in this issue's ACs.")

    def lint_coverage(self):
        """Check that every epic acceptance criterion maps to at least one issue.
        
        Uses multi-strategy matching: keyword overlap, phrase matching, and
        keyword-in-issue checking. Much more robust than the old 30-char prefix.
        """
        if not self.epic_data or not self.epic_data.get("acceptance_criteria"):
            return

        acceptance_criteria = self.epic_data["acceptance_criteria"]
        covered = set()

        for issue_file in self.issue_files:
            md_content = issue_file.md_content
            # Extract issue ACs from markdown
            ac_match = re.search(r"##\s+Acceptance ?criteria\s*\n((?:- \[ ?\] .+\n?)*)", md_content, re.IGNORECASE)
            if not ac_match:
                continue
            issue_acs_text = ac_match.group(1).lower()
            issue_acs_words = set(issue_acs_text.split())

            for epic_ac in acceptance_criteria:
                epic_ac_text = epic_ac.strip().lstrip("- ")
                # Strategy 1: exact phrase match (case-insensitive)
                if epic_ac_text.lower() in issue_acs_text:
                    covered.add(epic_ac)
                    continue
                # Strategy 2: keyword overlap — at least 2 meaningful words must match
                epic_words = {w for w in epic_ac_text.lower().split() if len(w) > 3}
                if epic_words & issue_acs_words:
                    # Count how many meaningful words overlap
                    overlap = epic_words & issue_acs_words
                    if len(overlap) >= 2:
                        covered.add(epic_ac)
                    elif len(overlap) >= 1 and len(epic_words) <= 4:
                        # Short AC: 1 word match is enough
                        covered.add(epic_ac)

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

    def lint_file_naming(self):
        """Check that directory name matches file name (IS-001/IS-001.md)."""
        for issue_file in self.issue_files:
            expected_name = f"{issue_file.issue_id}.md"
            if issue_file.md_path.name != expected_name:
                self.add_issue("error", "structure",
                    f"{issue_file.issue_id}: file is '{issue_file.md_path.name}' "
                    f"but directory is '{issue_file.md_path.parent.name}' — "
                    f"expected '{expected_name}'")
            expected_json_name = f"{issue_file.issue_id}.json"
            if issue_file.json_path.name != expected_json_name:
                self.add_issue("error", "structure",
                    f"{issue_file.issue_id}: file is '{issue_file.json_path.name}' "
                    f"but directory is '{issue_file.json_path.parent.name}' — "
                    f"expected '{expected_json_name}'")

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
        self.lint_file_naming()
        self.lint_id_sequence()
        self.lint_dependencies()
        self.lint_dependency_ordering()
        self.lint_blocked_by_cycles()
        self.lint_schema()
        self.lint_epic_consistency()
        self.lint_milestone_consistency(taskplan)
        self.lint_non_goal_violation()
        self.check_glossary_refs()
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

def run_lint(epic_id: str, epics_dir: str, taskplan: Optional[dict] = None,
             goal: Optional[dict] = None, glossary: Optional[dict] = None, strict: bool = False):
    """Run the issue linter for a single epic. Returns a LayerResult."""
    from lint_all import LayerResult
    linter = IssueLinter(epics_dir, epic_id, strict, glossary=glossary)
    if goal:
        linter.goal = goal
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
    parser.add_argument("--goal", default=None,
                        help="Path to goalspec.json for non-goal violation check")
    parser.add_argument("--glossary", default=None,
                        help="Path to glossary.json for synonym expansion")
    parser.add_argument("--strict", action="store_true",
                        help="Treat warnings as errors")
    args = parser.parse_args()

    taskplan = None
    if args.taskplan:
        try:
            taskplan = json.loads(Path(args.taskplan).read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"Warning: Could not load taskplan from {args.taskplan}")

    goal = None
    if args.goal:
        try:
            goal = json.loads(Path(args.goal).read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"Warning: Could not load goal from {args.goal}")

    glossary = None
    if args.glossary:
        try:
            glossary = json.loads(Path(args.glossary).read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"Warning: Could not load glossary from {args.glossary}")

    linter = IssueLinter(args.epics_dir, args.epic, args.strict, glossary=glossary)
    if goal:
        linter.goal = goal
    issues = linter.run(taskplan)

    print(linter.summary())

    errors = [i for i in issues if i.severity == "error"]
    if errors or (args.strict and [i for i in issues if i.severity == "warning"]):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
