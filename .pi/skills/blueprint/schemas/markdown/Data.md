---
name: DataSpec
type: schema
version: 1.0.0
---

## Data Spec

Defines the logical data model of the system: all entities, their fields,
enumerated types, and the relationships between them.

DataSpec is the source of truth for types used across ApiSpec and TestSpec.
It produces a machine-readable JSON artifact and a deterministically
generated PlantUML class diagram.

The DataSpec does NOT define:

* Function signatures or API contracts — those belong to **ApiSpec**
* Database schemas, table definitions, or ORM models — those are implementation
* Any UI or screen structure — that belongs to **DesignSpec**

---

## Output Format

This artifact produces two files:

- `artifacts/DataSpec.md` — human-readable document
- `artifacts/Data.json` — machine-readable, conforming to `schemas/data.schema.json`

---

## Inputs

* GoalSpec (`artifacts/GoalSpec.json`) — required
* ArchitectureSpec (`artifacts/ArchitectureSpec.json`) — required

---

## Before the interview

Load `artifacts/ArchitectureSpec.json`. Extract component names — these are
candidates for entities. Also load `artifacts/GoalSpec.json` and note the
domain nouns in functional requirements. Propose these as starting entities
rather than asking the user to enumerate from scratch.

---

### Primitives

The set of primitive type names used as field types.

Defaults: `string`, `number`, `boolean`, `null`, `any`.

Additional primitives may be added for the project (e.g. `Date`, `UUID`).

Every field type must resolve to a primitive, an entity name, or an enum name
defined in this spec.

---

### Enums

Enumerated types used across entities and API contracts.

Each enum must have:

* **Name** — PascalCase, e.g. `OrderStatus`
* **Description** (optional)
* **Values** — each with:
  * **Name** — SCREAMING_SNAKE_CASE, e.g. `PENDING`
  * **Description** (optional)

**Rules:**

* No duplicate enum names.
* Each enum must have at least one value.
* Enums with only one value should be questioned — may be better as a boolean.

---

### Entities

All domain entities (classes) in the system.

Each entity must have:

* **Name** — PascalCase, unique, e.g. `User`, `OrderItem`
* **Description** — what this entity represents in the domain
* **Fields** — each with:
  * **Name** — camelCase, e.g. `createdAt`, `userId`
  * **Type** — a primitive, entity name, enum name, or array thereof
    (e.g. `string`, `User`, `OrderStatus`, `OrderItem[]`)
  * **Required** — boolean, default true
  * **Description** (optional)
  * **Example** (optional) — a concrete example value
* **Methods** (optional) — functions this entity exposes. Each method must
  reference a function ID in ApiSpec via `apiRef`.
* **Abstract** (optional) — true if this entity cannot be instantiated directly
* **Extends** (optional) — parent entity name for inheritance
* **Visibility** — `public` or `internal`

**Rules:**

* No duplicate entity names.
* Every field type must resolve to a defined primitive, entity, or enum.
* If a field has an entity type, a relationship must exist between them.
* Every `extends` reference must name a real entity in this spec.

---

### Relationships

Directional relationships between entities.

Each relationship must have:

* **From** — source entity name
* **To** — target entity name
* **Type** — one of:
  * `association` — general link
  * `composition` — target cannot exist without source
  * `aggregation` — target can exist independently
  * `dependency` — source uses target but does not own it
  * `realization` — source implements target interface
* **Cardinality** (optional) — labels on each end, e.g. `1` to `0..*`
* **Label** (optional) — verb on the arrow, e.g. `places`, `contains`

**Rules:**

* Both `from` and `to` must name real entities in this spec.
* No orphan entities — every entity must appear in at least one relationship
  (except in single-entity specs).
* No duplicate relationships of the same type between the same pair.


