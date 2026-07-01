---
name: Issue
type: schema
version: 1.0.0
---

# Issue

An Issue is a single vertical slice (tracer bullet) decomposed from an Epic.
Each issue cuts end-to-end through all relevant integration layers and is
independently implementable.

Issues live inside their parent epic's directory: `tasks/EP-NNN-slug/IS-NNN-slug/`.
Each issue has two files: `IS-NNN-slug.md` (human-readable) and `IS-NNN-slug.json`
(machine-readable).

Sub-issues (SI-NNN-slug) live under each issue and represent the atomic units
of work that an agent can execute.

---

## Directory Structure

```
tasks/
  EP-001-userOnboarding/
    EP-001-userOnboarding.json    ← epic file
    EP-001-userOnboarding.md
    IS-001-implementLogin/
      IS-001-implementLogin.json  ← issue file
      IS-001-implementLogin.md
      SI-001-createLoginSchema/
        SI-001-createLoginSchema.json
        SI-001-createLoginSchema.md
        work/                     ← agent writes code here
      SI-002-createLoginAPI/
        SI-002-createLoginAPI.json
        SI-002-createLoginAPI.md
        work/
    IS-002-verifyEmail/
      IS-002-verifyEmail.json
      IS-002-verifyEmail.md
```

Issue IDs are **project-global**, sequential (`IS-001-implementLogin`, `IS-002-verifyEmail`, ...),
and never restart per epic. Always scan `tasks/*/IS-*/` for the highest
existing IS-NNN before creating new issues.

---

## Issue File Structure

Each issue has two files: `IS-NNN-slug.md` (human-readable) and `IS-NNN-slug.json` (machine-readable).

### Issue JSON

```json
{
  "schemaVersion": "1.0.0",
  "artifact": "Issue",
  "id": "IS-001-implementLogin",
  "name": "Implement user login",
  "description": "Vertical slice: user authenticates with email/password and receives a session token",
  "type": "AFK",
  "status": "not_started",
  "milestone": "MIL-001-Setup",
  "scope": {
    "inScope": [
      {
        "description": "Login page with email and password fields",
        "glRefs": ["GL-001-Authentication"],
        "reqRefs": ["REQ-001-createAccount"],
        "nfrRefs": ["NFR-001-security"],
        "ujRefs": ["UJ-001-login"],
        "miscRefs": ["COMP-001-AuthService", "ENT-001-User"]
      }
    ],
    "outOfScope": [
      {
        "description": "Social login via Google",
        "glRefs": [],
        "reqRefs": [],
        "nfrRefs": [],
        "ujRefs": [],
        "miscRefs": []
      }
    ]
  },
  "acceptanceCriteria": [
    {
      "description": "User can login with email/password and receives session token",
      "uxacRefs": ["UXAC-001-touchTarget"],
      "scRefs": ["SC-001-authenticationSuccess"],
      "miscRefs": ["FN-001-authenticate"]
    }
  ],
  "blockedBy": [],
  "priority": "P0",
  "effort": "M",
  "tags": ["auth", "backend"],
  "githubIssueNumber": null,
  "githubBranch": "IS-001-implementLogin",
  "githubParentBranch": "EP-001-userOnboarding",
  "created": "2026-07-01T14:32:00Z",
  "updated": "2026-07-01T14:32:00Z"
}
```

**Required fields:** `schemaVersion`, `artifact`, `id`, `name`, `description`,
`type`, `status`, `milestone`, `acceptanceCriteria`, `created`, `updated`

**Optional fields:** `blockedBy`, `priority`, `effort`, `tags`,
`githubIssueNumber`, `githubBranch`, `githubParentBranch`

### Issue Markdown (generated from JSON)

```markdown
# IS-001-implementLogin: Implement user login

## Description
Vertical slice: user authenticates with email/password and receives a session token

## Type
AFK

## Status
not_started

## Milestone
MIL-001-Setup

## Scope
### In Scope
- Login page with email and password fields

### Out of Scope
- Social login via Google

## Acceptance Criteria
- [ ] User can login with email/password and receives session token

## Blocked By
None — can start immediately.

## Sub-issues
- [ ] SI-001-createLoginSchema: Create login database schema
- [ ] SI-002-createLoginAPI: Create login API endpoint
```

The sub-issue checklist is assembled by reading `tasks/EP-NNN/IS-NNN/*/` directories.

---

## Reference Rules

### Reference direction (unidirectional — downstream → upstream)

```
SubIssue → isRefs, epRefs (upstream)
Issue    → epRefs (implicit via directory structure)
Epic     → requirements, design, arch (upstream via scope refs)
```

### Reference fields in scope items

| Refs | inScope | outOfScope | acceptanceCriteria |
|------|---------|-----------|-------------------|
| `glRefs` | ✓ | ✓ | ✓ |
| `reqRefs` | ✓ | ✓ | |
| `nfrRefs` | ✓ | ✓ | |
| `uxacRefs` | | | ✓ |
| `ujRefs` | ✓ | ✓ | |
| `scRefs` | | | ✓ |
| `miscRefs` | ✓ | ✓ | ✓ |

### Scope inheritance

- **Epic**: `scope.inScope`/`scope.outOfScope` are free-form descriptions with refs
- **Issue**: `scope.inScope`/`scope.outOfScope` must reference Epic's scope items (description must match parent)
- **SubIssue**: `scope.inScope`/`scope.outOfScope` must reference Issue's scope items (description must match parent)

---

## Process

### Step 1 — Lint issues

Run `lint_issues.py` for the target epic. Report any blocking errors.

If blocking errors exist, report them to the user before proceeding:

> "The linter found <N> error(s) in existing issues. These must be
> resolved before proceeding."

List each error with its category, message, and hint.

### Step 2 — Orientation

Report a brief orientation summary:

- Epic title, objective, and scope
- Relevant architectural constraints from ArchitectureSpec
- Current highest issue ID (next will be IS-NNN+1)
- Any open questions noted in the epic's Notes section

### Step 3 — Quiz

Analyze the epic and draft vertical slices. Each issue must be a thin
vertical slice that cuts through ALL relevant integration layers end-to-end.

A slice is horizontal (wrong) if it only touches one layer (e.g., "add
database migration"). Split or reframe horizontal slices as end-to-end
behaviour.

Present the proposed issues as a numbered list. For each slice show:

- **ID**: IS-NNN-slug (proposed)
- **Name**: short descriptive name using domain vocabulary
- **Type**: AFK or HITL
- **Blocked by**: which other proposed issues (if any)
- **Accepts**: which epic acceptance criteria this addresses
- **Priority**: P0/P1/P2/P3
- **Effort**: XS/S/M/L/XL

Then ask:

1. Granularity — too coarse or too fine?
2. Dependencies — are the blocking relationships correct?
3. Coverage — does every acceptance criterion have at least one issue?
4. HITL/AFK — are the assignments correct?
5. Scope — should any slices be merged or split?

Iterate until the user explicitly approves the issues. Do not write any
files before approval.

### Step 4 — Write Issue Files

After the user approves the issues, write each issue file in dependency order
(blockers first, so that `blocked_by` references real IS-NNN identifiers):

1. Create directory: `tasks/EP-NNN-slug/IS-NNN-slug/`
2. Write `IS-NNN-slug.json` with full issue data
3. Generate `IS-NNN-slug.md` from JSON
4. Call `gh_create_issue(jsonPath, parentBranch)` to sync to GitHub

For each issue, verify the write by reading it back. Report each written
file to the user as it completes.

### Step 5 — Sub-issue Decomposition

After creating each issue, decompose it into sub-issues. Sub-issues are the
atomic units of work that an agent executes.

For each issue, present proposed sub-issues:

- **ID**: SI-NNN-slug (proposed)
- **Name**: short descriptive name
- **Type**: AFK or HITL
- **Description**: what this sub-issue builds
- **Files**: expected file paths and actions

After approval, for each sub-issue:

1. Create directory: `tasks/EP-NNN-slug/IS-NNN-slug/SI-NNN-slug/`
2. Create `work/` subdirectory inside
3. Call `gh_create_sub_issue(epId, issueId, data)` to write local files
4. This creates `SI-NNN-slug.json` + `SI-NNN-slug.md` automatically

### Step 6 — Validate

Validate each issue's JSON file against the schema. Report any validation
errors.

If validation fails, show the errors to the user and suggest fixes. Do not
modify the JSON without explicit user approval. After user confirms, apply
the fix and re-validate.

After all issue files are written, update the parent epic file:
- Add the issue list to the epic JSON
- Update the `updated` date
- Do not modify any other part of the epic file

Verify the update by reading back the front matter.

### Step 7 — Sub-issue Validation

Run `lint_subissues.py` for each issue to validate sub-issue files:

```
python lint_subissues.py --epic EP-001-userOnboarding --issue IS-001-implementLogin
```

This checks:
- Required fields present
- Valid enum values (type, status, priority, effort)
- isRefs and epRefs point to real issues/epics
- Scope inheritance from parent Issue
- files array format (audit trail)
- ISO 8601 timestamps
- Directory structure correctness

---

## Sub-issue JSON Schema

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
