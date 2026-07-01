---
name: SubIssue
type: schema
version: 1.0.0
---

# SubIssue

A SubIssue is the smallest unit of work — an atomic task that an agent can
execute end-to-end. Sub-issues decompose an Issue into discrete, implementable
steps. Each sub-issue corresponds to a GitHub PR.

Sub-issues live inside their parent issue's directory:
`tasks/EP-NNN-slug/IS-NNN-slug/SI-NNN-slug/`.

---

## Directory Structure

```
tasks/
  EP-001-userOnboarding/
    IS-001-implementLogin/
      SI-001-createLoginSchema/
        SI-001-createLoginSchema.json  ← sub-issue definition
        SI-001-createLoginSchema.md    ← rendered from JSON
        work/                          ← agent writes code here
      SI-002-createLoginAPI/
        SI-002-createLoginAPI.json
        SI-002-createLoginAPI.md
        work/
```

Sub-issue IDs are **project-global**, sequential (`SI-001-createLoginSchema`,
`SI-002-createLoginAPI`, ...), and never restart per issue. Always scan
`tasks/*/IS-*/SI-*/` for the highest existing SI-NNN before creating new
sub-issues.

---

## SubIssue JSON Schema

```json
{
  "schemaVersion": "1.0.0",
  "artifact": "SubIssue",
  "id": "SI-001-createLoginSchema",
  "name": "Create login database schema",
  "description": "Create users table with email and password_hash columns, plus indexes",
  "type": "AFK",
  "status": "not_started",
  "milestone": "MIL-001-Setup",
  "scope": {
    "inScope": [
      {
        "description": "Create users table with email and password_hash columns",
        "glRefs": ["GL-001-Authentication"],
        "reqRefs": ["REQ-001-createAccount"],
        "nfrRefs": [],
        "ujRefs": [],
        "miscRefs": ["ENT-001-User"]
      }
    ],
    "outOfScope": []
  },
  "acceptanceCriteria": [
    {
      "description": "Users table has email and password_hash columns with appropriate indexes",
      "uxacRefs": [],
      "scRefs": ["SC-001-dataIntegrity"],
      "miscRefs": ["ENT-001-User"]
    }
  ],
  "files": [],
  "priority": "P1",
  "effort": "S",
  "tags": ["database", "schema"],
  "isRefs": ["IS-001-implementLogin"],
  "epRefs": ["EP-001-userOnboarding"],
  "githubBranch": "SI-001-createLoginSchema",
  "githubBaseBranch": "EP-001-userOnboarding",
  "githubPrNumber": null,
  "created": "2026-07-01T14:32:00Z",
  "updated": "2026-07-01T14:32:00Z"
}
```

**Required fields:** `schemaVersion`, `artifact`, `id`, `name`, `description`,
`type`, `status`, `milestone`, `acceptanceCriteria`, `isRefs`, `epRefs`,
`created`, `updated`

**Optional fields:** `files` (audit trail — populated after work is done),
`priority`, `effort`, `tags`, `githubBranch`, `githubBaseBranch`, `githubPrNumber`

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | SI-NNN-lowerCamelCase (project-global, sequential) |
| `name` | string | Short descriptive name |
| `description` | string | Detailed description of what to build |
| `type` | AFK\|HITL | AFK: agent works autonomously. HITL: requires human judgment |
| `status` | string | not_started → in_progress → needs_review → complete |
| `milestone` | string | Parent milestone ID (e.g. MIL-001-Setup) |
| `scope` | object | inScope/outOfScope with structured refs |
| `acceptanceCriteria` | array | Verifiable pass/fail conditions |
| `files` | array | Audit trail: `{path, action}` after work completes |
| `priority` | P0\|P1\|P2\|P3 | P0=critical, P1=high, P2=medium, P3=low |
| `effort` | XS\|S\|M\|L\|XL | Estimated effort |
| `isRefs` | array | Parent issue IDs (must include containing issue) |
| `epRefs` | array | Parent epic IDs (must include containing epic) |
| `githubBranch` | string | Branch name for this sub-issue (defaults to SI ID) |
| `githubBaseBranch` | string | Base branch (EP branch) |
| `githubPrNumber` | number | PR number, populated after gh_create_pr |

### Enum Values

- **type**: `AFK` (agent works alone) or `HITL` (human in the loop)
- **status**: `not_started` → `in_progress` → `needs_review` → `complete`
- **priority**: `P0` (critical), `P1` (high), `P2` (medium), `P3` (low)
- **effort**: `XS` (< 1h), `S` (1-3h), `M` (3-8h), `L` (1-2 days), `XL` (> 2 days)
- **files[].action**: `create`, `modify`, `delete`

---

## Process

### Step 1 — Orientation

Report a brief orientation summary for the parent issue:

- Issue title, description, and scope
- Parent epic objective
- Relevant architectural constraints
- Current sub-issue count and IDs
- Any open questions in the issue

### Step 2 — Decompose

Analyze the parent issue and propose sub-issues. Each sub-issue must:

- Be a single atomic unit of work
- Have clear acceptance criteria
- Reference specific files to create/modify
- Be independently reviewable

Present the proposed sub-issues as a numbered list. For each show:

- **ID**: SI-NNN-slug (proposed)
- **Name**: short descriptive name
- **Type**: AFK or HITL
- **Description**: one-sentence description of what to build
- **Files**: expected file paths and actions
- **Accepts**: which issue acceptance criteria this addresses

Then ask:

1. Granularity — too coarse or too fine?
2. Coverage — does every issue acceptance criterion have at least one sub-issue?
3. Dependencies — should any sub-issues block others?
4. HITL/AFK — are the assignments correct?
5. Scope — should any sub-issues be merged or split?

Iterate until the user explicitly approves. Do not write any files before approval.

### Step 3 — Write Sub-issues

After approval, for each sub-issue:

1. Call `gh_create_sub_issue(epId, issueId, data)` with the sub-issue data
2. This creates:
   - `tasks/EP-NNN-slug/IS-NNN-slug/SI-NNN-slug/SI-NNN-slug.json`
   - `tasks/EP-NNN-slug/IS-NNN-slug/SI-NNN-slug/SI-NNN-slug.md`
   - `tasks/EP-NNN-slug/IS-NNN-slug/SI-NNN-slug/work/`

For each sub-issue, verify the write by reading it back. Report each written
file to the user as it completes.

### Step 4 — Validate

Run `lint_subissues.py` to validate all sub-issues:

```
python lint_subissues.py --epic EP-001-userOnboarding --issue IS-001-implementLogin
```

This checks:
- Required fields present
- Valid enum values (type, status, priority, effort)
- isRefs and epRefs point to real issues/epics
- Scope inheritance from parent Issue
- files array format (paths valid, actions valid)
- ISO 8601 timestamps
- Directory structure (work/ exists)

If validation fails, show the errors and suggest fixes. Do not modify without
explicit user approval.

### Step 5 — Update Parent Issue

After all sub-issues are written, update the parent issue's markdown to include
the sub-issue checklist in the `## Sub-issues` section.

---

## Execution Flow

```
1. Agent picks a sub-issue (status: not_started)
2. Agent calls gh_create_pr(siId, epBranch, targetBranch, jsonPath)
   → Creates SI branch from EP branch, PR targets IS branch
3. Agent does work in work/ directory
4. Agent calls gh_update_sub_issue(jsonPath, files, status)
   → Populates files audit trail, marks status
5. Agent calls gh_merge_pr(prNumber, jsonPath)
   → Merges PR, updates JSON (branch preserved until Issue completes)
6. Repeat for all sub-issues
7. All SIs done → delete SI branches, merge IS into EP branch
8. All IS done → delete IS branch, merge EP into main
```

### GitHub Branch Strategy

All SI branches fork from the EP branch (not from IS branch). PRs target the
IS branch. This avoids deep branch chains and keeps the merge graph flat.

- SI branch: `SI-NNN-slug` (from EP branch)
- PR target: IS branch (which tracks as the merge target within EP branch)
- Branch deletion: SI branches deleted when all SIs for an Issue are merged

### Files Audit Trail

The `files` array on SubIssue is an audit trail only — populated *after* the
agent completes work. Each entry records:

```json
{
  "path": "migrations/001_create_users.sql",
  "action": "create"
}
```

Actions: `create` (new file), `modify` (existing file changed), `delete` (file removed).

Git handles merge conflicts naturally — the `files` array is for tracking and
reporting, not conflict prevention.

---

## Validation Rules

The linter (`lint_subissues.py`) enforces:

1. **Required fields**: schemaVersion, artifact, id, name, description, type,
   status, milestone, acceptanceCriteria, isRefs, epRefs, created, updated
2. **Enum values**: type ∈ {AFK, HITL}, status ∈ {not_started, in_progress,
   needs_review, complete}, priority ∈ {P0, P1, P2, P3}, effort ∈ {XS, S, M, L, XL}
3. **References**: isRefs and epRefs must point to existing issues/epics
4. **Scope inheritance**: inScope/outOfScope descriptions must match parent Issue
5. **Files format**: each entry has valid `path` (string) and `action` (create/modify/delete)
6. **Timestamps**: created/updated must be valid ISO 8601, updated >= created
7. **Structure**: work/ directory must exist
