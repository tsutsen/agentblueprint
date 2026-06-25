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

Individual epic files live in `tasks/epics/EP-<NNN>/`. Each epic is a folder
containing `EP-<NNN>-<slug>.md` (human-readable) and `EP-<NNN>-<slug>.json`
(machine-readable). This file (`tasks/PLAN.md`) is the index — it references
epics by ID but does not duplicate their content.

After all epics are written and approved, run `/skill:blueprint breakdown
EP-NNN` to decompose each epic into independently-grabbable issues.

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
See blueprint skill for file structure and write order.

---

### Milestones

Major checkpoints. Each must produce a demonstrable project outcome.

Each milestone contains:
* Identifier: M1, M2, M3 ...
* Name: short, outcome-oriented (e.g. "Working ingestion pipeline", not "Sprint 2")
* Outcome: one sentence describing what can be demonstrated at this milestone
* Epics: list of EP-NNN IDs that must be complete

A milestone with no demonstrable outcome should be merged with an adjacent one.

---

### Epic Index

Reference table only — content lives in `tasks/epics/EP-<NNN>/`. Do not
duplicate epic content here.

Each entry contains:
* EP-NNN — sequential, zero-padded to three digits, project-global
* Title — action-oriented (e.g. "Implement document ingestion pipeline")
* Status — not_started | in_progress | complete
* Milestone — M1, M2, ...
* Requirements covered — REQ-IDs or short statements from GoalSpec
* Summary — one line describing what this epic delivers

Validation (enforce before writing):
* Every GoalSpec requirement appears in at least one epic's coverage list.
  Flag uncovered requirements — do not silently omit them.
* Every epic covers at least one requirement. An epic with no requirement
  is a scope addition — surface it to the user before including it.
* No epic objective implements a GoalSpec non-goal. Flag any that do.
* Epics are listed in dependency order — blockers before dependents.

---

### Epic file sections

Each `tasks/epics/EP-<NNN>/EP-<NNN>-<slug>.md` contains:

#### Objective
What capability this epic delivers and which requirements it addresses.
Should NOT describe implementation details.

#### Scope
In scope: capabilities included. Out of scope: related work deferred.
Be specific — vague scope produces scope creep.

#### Acceptance Criteria
Independently verifiable, binary (pass/fail) conditions describing observable behaviour.

#### Dependencies
Blocked by / blocks epics. If none: "None."

#### Notes
Open questions, risks, references. May be empty.
