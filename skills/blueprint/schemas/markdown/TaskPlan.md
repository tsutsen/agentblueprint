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

Before presenting anything to the user, analyse the loaded artifacts silently.

**From GoalSpec extract:**
- All functional and non-functional requirements (by ID where present)
- All user stories
- Success criteria — these anchor milestone boundaries
- Non-goals — these constrain what epics may cover

**From DesignSpec extract:**
- Major product capabilities and feature areas
- User-facing behaviours that group naturally into deliverables

**From ArchitectureSpec extract:**
- Major system components and their boundaries
- Integration points that imply sequencing constraints
- Cross-cutting concerns (auth, data model, infrastructure) that must
  precede feature work — these become foundational epics

**From DataSpec extract:**
- Entity relationships and data model complexity
- Migration-heavy entities that require dedicated setup epics
- Data integrity constraints that influence epic ordering

**From ApiSpec extract:**
- API surface area (endpoints, resources) that groups into delivery epics
- External integrations or third-party dependencies that imply blocking
  relationships
- API versioning or backward-compatibility concerns

**From TestSpec extract:**
- Test coverage requirements that may need dedicated setup or infrastructure
  epics
- Integration test scenarios that span multiple components — these may
  indicate epic boundaries
- Performance or security test requirements that imply foundational epics
  before feature work

**Derive a proposed epic structure:**
- Group related requirements and capabilities into candidate epics
- Each epic must cover at least one requirement — no orphan epics
- Every requirement must appear in at least one epic — no orphan requirements
- Foundational epics (data model, auth, infrastructure) come before feature epics
- Identify blocking relationships between epics
- Flag any requirement that does not fit cleanly into any proposed epic

**Derive a proposed milestone structure:**
- Use GoalSpec success criteria as milestone anchors — each criterion
  should be demonstrable at some milestone
- Group epics into milestones by dependency order and deliverable value
- Each milestone must produce a demonstrable outcome, not just completed tasks
- Aim for 3–5 milestones; adjust if scope clearly warrants more or fewer
- Every epic must belong to exactly one milestone

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

Each `tasks/epics/EP-<NNN>/EP-<NNN>-<slug>.md` contains the following sections.
Guidance for each is below.

#### Objective
What this epic delivers and why.
Must answer: what capability does completing this epic produce, and which
requirements does it address?
Should NOT describe implementation details or task breakdown.

Good: "Enables users to upload PDF documents and receive structured text output."
Bad: "Implement the PDF parser using PyMuPDF and store results in Postgres."

**titleGlossaryRefs** (array of GL-NNN): Glossary terms the epic's title and objective reference.
**inScopeGlossaryRefs** (array of GL-NNN): Glossary terms referenced in inScope items.
**outOfScopeGlossaryRefs** (array of GL-NNN): Glossary terms referenced in outOfScope items.

#### Scope
Explicit boundary of this epic.
* In scope: capabilities and behaviours included
* Out of scope: related work intentionally deferred or excluded

Out-of-scope items are instructions to breakdown — they tell it what NOT to
generate issues for. Be specific. Vague scope produces scope creep.

Scope items may have **glossaryRefs** (array of GL-NNN): Domain concepts in each scope item.

Good out-of-scope: "Batch upload of multiple PDFs — deferred to EP-004."
Bad out-of-scope: "Advanced features."

#### Acceptance Criteria
Objective conditions that mark this epic complete.
* Each criterion must be independently verifiable
* Binary (pass/fail) where possible
* Describes observable behaviour, not implementation

Good: "User can upload a PDF up to 100MB and receive extracted text within 10s."
Bad: "PDF parsing works correctly."

#### Dependencies
* Blocked by: epics that must complete before this one can start
* Blocks: epics that cannot start until this one is complete
* If none: state explicitly "None."

#### Notes
Open questions, risks, or context for whoever implements this epic.
Use for:
* Unresolved design questions breakdown should surface during issue creation
* Known risks or constraints
* References to relevant ADRs or KnowledgeBase entries
* Prototype findings or spikes

May be empty if nothing to record.
## Output

After the interview is complete and the JSON artifact has been written via
`write_section`, the Markdown file must be regenerated from the JSON to
ensure zero drift between formats.

Run the following tool after `dual_output` completes:

 ```
tool: generate_artifact_markdown
args:
  artifactType: <type>
  jsonPath: artifacts/<Type>.json
 ```

This overwrites the Markdown file with content derived from the JSON.
The JSON is the single source of truth; the Markdown is derived.
