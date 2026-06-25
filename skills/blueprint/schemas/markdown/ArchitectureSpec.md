---
name: ArchitectureSpec
type: schema
version: 2.0.0
---

## Architecture Spec

Defines the structural design of the system: components, their responsibilities,
how they interact, and the constraints they operate under.

The ArchitectureSpec does NOT define:

* Entity structures or data schemas — those belong to **DataSpec**
* Function signatures or API contracts — those belong to **ApiSpec**
* Screen layouts or UX flows — those belong to **DesignSpec**

---

## Output Format

This artifact produces two files:

- `artifacts/ArchitectureSpec.md` — human-readable document
- `artifacts/ArchitectureSpec.json` — machine-readable, conforming to `schemas/archspec.schema.json`

---

## Inputs

* GoalSpec (`artifacts/GoalSpec.json`) — required
* Glossary (`artifacts/Glossary.json`) — optional

---

### System Overview

High-level description of the system structure. Must be understandable
without implementation knowledge.

Includes:

* A summary paragraph: 2–4 sentences on structure, major subsystems, and interactions
* **Subsystems** — named groupings of components, each with a purpose

Every component must belong to a subsystem.

---

### Components

Defines major architectural units.

Each component must have:

* **ID** — format `COMP-NNN-slug`, e.g. `COMP-001-session-manager`
* **Name** — human-readable
* **Purpose** — one sentence: what this component exists to do
* **Responsibilities** — exclusive behaviours owned by this component.
  No two components may claim the same responsibility.
* **Dependencies** — IDs of other components this one depends on.
  Must reference real component IDs in this spec.
* **REQ refs** (optional) — `REQ-NNN-slug` IDs from GoalSpec this component satisfies
* **NFR refs** (optional) — `NFR-NNN-slug` IDs from GoalSpec this component is responsible for
* **fnRefs** (optional) — `FN-NNN-slug` IDs from ApiSpec that this component owns
* **Visibility** — `external` (exposed to callers) or `internal`
* **glossaryRefs** (array of GL-NNN): Glossary terms the component's concepts map to

**Rules:**

* No two components may have identical or near-identical responsibilities.
* No circular dependencies.
* Every `REQ-NNN` and `NFR-NNN` referenced must exist in GoalSpec.
* Every FR in GoalSpec should be covered by at least one component.

---

### Data Flow

Describes movement of information through the system as named, ordered flows.

Each flow must have:

* **ID** — format `FLOW-NNN-slug`, e.g. `FLOW-001-session-creation`
* **Name** — human-readable
* **Description** (optional) — prose summary
* **REQ refs** (optional) — `REQ-NNN` IDs this flow implements
* **glossaryRefs** (array of GL-NNN): Glossary terms the flow's concepts map to
* **Steps** — ordered list of at least 2 steps, each naming:
  * The **component** performing the step (must reference a real component ID)
  * The **action** performed
  * The **data** moving through (optional reference to a DataSpec entity)

---

### Constraints

Architectural limitations and hard requirements. Each must be independently
verifiable.

Each constraint must have a unique identifier in format `CON-NNN-slug`, e.g. `CON-001-must-implemented-dynamically`.

Each constraint must:

* Describe what is required, not which technology satisfies it
* Optionally reference `NFR-NNN` IDs from GoalSpec
* Have **glossaryRefs** (array of GL-NNN): Glossary terms the constraint's concepts map to

Examples:

* CON-001: The system must operate on a single machine with no external
  service dependencies for local-only operation.
* CON-002: The external API interface must be OpenAI-compatible.

---

## Output

After the interview is complete and the JSON artifact has been written via
`write_section`, the Markdown file must be regenerated from the JSON to
ensure zero drift between formats.


```
tool: generate_artifact_markdown
args:
  artifactType: arch
  jsonPath: artifacts/ArchitectureSpec.json
```

This overwrites the Markdown file with content derived from the JSON.
The JSON is the single source of truth; the Markdown is derived.

---

## Linting

After producing `artifacts/ArchitectureSpec.json`, run:

```
python extensions/blueprint/linters/lint_archspec.py artifacts/ArchitectureSpec.json \
  --schema schemas/archspec.schema.json \
  --goal   artifacts/GoalSpec.json \
  --json
```

All errors must be resolved before handoff.
