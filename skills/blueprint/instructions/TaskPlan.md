---
name: TaskPlan
type: schema
version: 1.0.0
---

## Task Plan

The Task Plan translates project goals and architecture into an organised,
sequenced set of epics and milestones. It is produced by analysing GoalSpec,
DesignSpec, ArchitectureSpec, DataSpec, ApiSpec, and TestSpec — not by
open-ended interview. The agent must derive a proposed structure from those
artifacts first, present it for review, refine it, then write.

Individual epic files live in `tasks/EP-<NNN>-<slug>/`. Each epic is a folder
containing `EP-<NNN>-<slug>.json` (machine-readable) and
`EP-<NNN>-<slug>.md` (human-readable, generated from JSON).
This file (`tasks/PLAN.md`) is the index — it references epics by ID but does
not duplicate their content.

After all epics are written and approved, run `/skill:blueprint breakdown
EP-NNN-slug` to decompose each epic into independently-grabbable issues.

---

## Directory Structure

```
tasks/
  PLAN.md                    ← epic index (human-readable)
  PLAN.json                  ← milestones + epic list (machine-readable)
  EP-001-UserOnboarding/
    EP-001-UserOnboarding.json  ← epic definition
    EP-001-UserOnboarding.md    ← rendered from JSON
    IS-001-ImplementLogin/
      IS-001-ImplementLogin.json
      IS-001-ImplementLogin.md
      SI-001-CreateLoginSchema/
        SI-001-CreateLoginSchema.json
        SI-001-CreateLoginSchema.md
        work/                   ← agent writes code here
```

---

## How to produce this artifact

### Phase 1 — Silent analysis

Before presenting anything to the user, analyse the loaded artifacts:

| Source | Extract |
|--------|---------|
| GoalSpec | FRs, NFRs, user stories, success criteria, non-goals |
| DesignSpec | Product capabilities, user-facing behaviours |
| ArchitectureSpec | Components, boundaries, integration points, cross-cutting concerns |
| DataSpec | Entity relationships, migration-heavy entities, integrity constraints |
| ApiSpec | API surface area, external dependencies, versioning concerns |
| TestSpec | Test coverage needs, integration scenarios, perf/security requirements |

**Derive epics:** group related requirements into candidate epics. Each epic
must cover at least one requirement. Foundational epics (data model, auth,
infra) come before feature epics. Identify blocking relationships.

**Derive milestones:** use success criteria as anchors. Aim for 3–5
milestones, each producing a demonstrable outcome. Every epic belongs to
exactly one milestone.

### Phase 2 — Present and refine

Present the proposed structure to the user before writing anything:

```
Proposed plan for <project name>:

Epics (X total):
  EP-001  <title>  [foundational]           covers: REQ-001, REQ-002
  EP-002  <title>  [blocked by EP-001]      covers: REQ-003
  EP-003  <title>                           covers: REQ-004, REQ-005
  ...

Milestones:
  M1 — <name>: <one-sentence outcome>       epics: EP-001
  M2 — <name>: <one-sentence outcome>       epics: EP-002, EP-003
  ...

Requirement coverage:
  ✓ REQ-001 → EP-001
  ✓ REQ-002 → EP-001
  ✗ REQ-005 → not assigned (needs discussion)
  ...

Does this structure look right? Any epics to split, merge, rename, or resequence?
```

Iterate — splitting, merging, resequencing, adding — until the user explicitly
approves. Do not write any files during this phase. Ask one clarifying question
at a time if feedback is ambiguous. Never silently drop an orphan requirement.

### Phase 3 — Deep-dive each epic

Once the structure is approved, flesh out each epic in sequence. For each one:

1. Present what the analysis already determined (objective, requirements
   covered, architectural constraints). Ask the user to confirm, correct,
   or expand — do not start from scratch.
2. Work through each section below (Objective, Scope, Acceptance Criteria,
   Dependencies, Notes) one question at a time.
3. Provide a recommended answer for each question derived from the loaded
   artifacts. Wait for the user's response before proceeding.

Good epics:
- Deliver a narrow but complete vertical slice of value
- Have acceptance criteria that are independently verifiable
- Have explicit scope boundaries that tell breakdown what NOT to issue

Bad epics:
- Cover a single technical layer only (e.g. "write all database migrations")
- Have acceptance criteria that depend on another epic being complete first
- Have vague scope that could expand indefinitely

### Phase 4 — Write

After each epic is agreed, write its file immediately — do not batch.
Write the epic JSON to `tasks/EP-NNN-slug/EP-NNN-slug.json`.

**Epic JSON schema:**

```json
{
  "schemaVersion": "1.0.0",
  "artifact": "Epic",
  "id": "EP-001-UserOnboarding",
  "name": "Implement user onboarding flow",
  "description": "End-to-end user registration, email verification, and account activation",
  "status": "not_started",
  "milestone": "MIL-001-Setup",
  "scope": {
    "inScope": [
      {
        "description": "Registration page with email and password fields",
        "glRefs": ["GL-001-Authentication"],
        "reqRefs": ["REQ-001-createAccount"],
        "nfrRefs": ["NFR-001-security"],
        "ujRefs": ["UJ-001-registration"],
        "miscRefs": ["COMP-001-AuthService"]
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
      "description": "User can register with email and password",
      "uxacRefs": ["UXAC-001-touchTarget"],
      "scRefs": ["SC-001-userRegistration"],
      "miscRefs": []
    }
  ],
  "blockedBy": [],
  "githubBranch": "EP-001-UserOnboarding",
  "created": "2026-07-01T14:32:00Z",
  "updated": "2026-07-01T14:32:00Z"
}
```

**Required fields:** `schemaVersion`, `artifact`, `id`, `name`, `description`,
`status`, `milestone`, `acceptanceCriteria`, `created`, `updated`

After writing the epic JSON:
1. Generate the markdown from JSON using `generate_artifact_markdown` tool
2. Call `gh_create_epic(jsonPath)` to sync to GitHub (creates GitHub Issue + EP branch)
3. Update `tasks/PLAN.json` with the new epic entry

---

### Milestones

Major checkpoints. Each must produce a demonstrable project outcome.

Each milestone contains:
* Identifier: MIL-001-Setup, MIL-002-MVP, ...
* Name: short, outcome-oriented (e.g. "Working ingestion pipeline", not "Sprint 2")
* Outcome: one sentence describing what can be demonstrated at this milestone
* Epics: list of EP-NNN-slug IDs that must be complete

A milestone with no demonstrable outcome should be merged with an adjacent one.

---

### Epic Index

Reference table only — content lives in `tasks/EP-NNN-slug/`. Do not
duplicate epic content here.

Each entry contains:
* EP-NNN-slug — sequential, zero-padded to three digits, project-global
* Title — action-oriented (e.g. "Implement document ingestion pipeline")
* Status — not_started | in_progress | complete
* Milestone — MIL-001-Setup, ...
* Requirements covered — REQ-IDs from scope.inScope[].reqRefs
* Summary — one line describing what this epic delivers

Validation (enforce before writing):
* Every GoalSpec requirement appears in at least one epic's scope.inScope[].reqRefs.
  Flag uncovered requirements — do not silently omit them.
* Every epic covers at least one requirement. An epic with no requirement
  is a scope addition — surface it to the user before including it.
* No epic objective implements a GoalSpec non-goal. Flag any that do.
* Epics are listed in dependency order — blockers before dependents.

---

### Epic file sections

Each `tasks/EP-NNN-slug/EP-NNN-slug.json` contains:

#### Name & Description
What capability this epic delivers and which requirements it addresses.
Should NOT describe implementation details.

#### Scope
In scope: capabilities included with glossary/requirement refs.
Out of scope: related work deferred.
Be specific — vague scope produces scope creep.

#### Acceptance Criteria
Independently verifiable, binary (pass/fail) conditions describing observable behaviour.
Each criterion can reference UX acceptance criteria (uxacRefs), success criteria (scRefs),
and miscellaneous refs (miscRefs).

#### Dependencies
blockedBy: list of epic IDs that must complete first.

#### GitHub Integration
githubBranch: branch name for this epic (defaults to epic ID).
githubIssueNumber: populated after gh_create_epic sync.
