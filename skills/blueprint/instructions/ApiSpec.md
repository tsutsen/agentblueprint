---

---
name: ApiSpec
type: schema
version: 2.0.0
---

## API Spec

Defines the interface of the system: all functions exposed by each module,
their inputs, outputs, and documented error conditions.

ApiSpec is the source of truth for function contracts. TestSpec derives
from it. DataSpec provides all types — ApiSpec must not re-declare them.

The ApiSpec does NOT define:

* Entity structures — those belong to **DataSpec**
* Test cases — those belong to **TestSpec**
* Implementation logic — not captured in specs

---

---

---

## Before the interview

Load `artifacts/ArchitectureSpec.json`. Extract component names — each
component that has external or internal callers likely exposes functions.
Load `artifacts/DataSpec.json` — all input and output types must reference
entities, enums, or primitives defined there.

Propose functions grouped by component rather than asking the user to
enumerate all functions at once.

---

### Functions

All functions exposed by this module.

Each function must have:

  e.g. `FN-001-createUser`, `FN-002-cancelOrder`
  operates on. Must name a real entity.
  * **Description** (optional)
  * **Description** (optional)
  * **Example** (optional)
* **reqRefs** (array of REQ-NNN-slug): GoalSpec functional requirements this function implements
* **nfrRefs** (array of NFR-NNN-slug): GoalSpec non-functional requirements this function helps satisfy

**Rules:**

* No duplicate function IDs.
* Every input and output type must resolve to DataSpec.
* Every `entity` reference must name a real DataSpec entity.
* Every error `code` must be unique within a function.
* Functions with no documented errors should be questioned — most functions
  have at least one error condition.




