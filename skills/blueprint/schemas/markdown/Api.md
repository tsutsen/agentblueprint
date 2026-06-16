---
name: ApiSpec
type: schema
version: 1.0.0
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

## Output Format

This artifact produces two files:

- `artifacts/ApiSpec.md` — human-readable document
- `artifacts/Api.json` — machine-readable, conforming to `schemas/api.schema.json`

---

## Inputs

* GoalSpec (`artifacts/GoalSpec.json`) — required
* ArchitectureSpec (`artifacts/ArchitectureSpec.json`) — required
* DataSpec (`artifacts/DataSpec.json`) — required

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

* **ID** — stable unique identifier in format `fn_camelCase`,
  e.g. `fn_createUser`, `fn_cancelOrder`
* **Name** — camelCase function name as it appears in code
* **Description** — one sentence: what this function does
* **Entity** (optional) — the entity from DataSpec this function primarily
  operates on. Must name a real entity.
* **Inputs** — list of parameters, each with:
  * **Name** — camelCase
  * **Type** — must resolve to a primitive, entity, or enum in DataSpec
  * **Required** — boolean, default true
  * **Description** (optional)
  * **Example** — a concrete example value
* **Output** — the return value:
  * **Type** — must resolve to a type in DataSpec, or `void`
  * **Description** (optional)
  * **Example** (optional)
* **Errors** — all documented error conditions, each with:
  * **Code** — SCREAMING_SNAKE_CASE error code, e.g. `NOT_FOUND`
  * **Condition** — when this error is thrown
  * **Return type** — what the caller receives
* **Visibility** — `public` or `internal`
* **Pure** — boolean: true if no side effects (same input → same output always)

**Rules:**

* No duplicate function IDs.
* Every input and output type must resolve to DataSpec.
* Every `entity` reference must name a real DataSpec entity.
* Every error `code` must be unique within a function.
* Functions with no documented errors should be questioned — most functions
  have at least one error condition.

---

### Confirmation gate

Before proceeding to TestSpec, confirm the full function list with the user:

> "Here are all functions in the API surface. Please confirm this is
> complete before we move to the test spec — additions after that point
> will require revisiting tests."

This gate is mandatory. Do not skip it.

---

## Cross-spec consistency

After producing `artifacts/ApiSpec.json`, run the cross-spec linter:

```
python extensions/blueprint/linters/lint_cross.py \
  --data artifacts/DataSpec.json \
  --api  artifacts/ApiSpec.json \
  --json
```

All errors must be resolved before handoff. In particular:

* Every function input/output type must resolve in DataSpec
* Every `entity` reference must exist in DataSpec
* Every DataSpec entity method `apiRef` must resolve to a function in this spec
