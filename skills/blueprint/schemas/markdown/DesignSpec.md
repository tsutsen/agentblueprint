---
name: DesignSpec
type: schema
version: 1.0.0
---

# Design Spec

## Purpose

Defines the user experience, interaction model, and visual design requirements
of the system.

The Design Spec serves as the contract between product requirements and
implementation.

It answers:

* What should users see?
* What should users be able to do?
* How should workflows feel?
* How should information be presented?

It does NOT define implementation details.

---

## Output Format

This artifact produces two files:

- `artifacts/DesignSpec.md` — human-readable document
- `artifacts/DesignSpec.json` — machine-readable, conforming to `schemas/designspec.schema.json`

---

## Inputs

* GoalSpec (`artifacts/GoalSpec.json`) — required
* Glossary (`artifacts/Glossary.json`) — required

## Outputs

* ArchitectureSpec
* TaskPlan
* TestSpec

---

## Required Sections

### Design Goals

High-level UX objectives. Each must describe a desired user experience
quality, not an implementation approach.

Each goal must have a unique identifier in format `DG-NNN`.

Examples:

* DG-001: Minimize cognitive load.
* DG-002: Enable keyboard-first workflows.

---

### User Personas

Descriptions of target users. Persona roles must match actor names used
in GoalSpec functional requirements and user stories.

For each persona:

* **ID** — kebab-case identifier, e.g. `power-developer`
* **Name** — human name for the persona
* **Role** — actor role, must match a GoalSpec actor
* **Goals** — what this persona is trying to accomplish
* **Pain Points** — current frustrations this system addresses
* **Technical Skill Level** — one of: non-technical, basic, intermediate, advanced, expert

---

### User Journeys

End-to-end workflows from the user's perspective.

Each journey must have a unique identifier in format `UJ-NNN`.

Each journey must:

* Reference a persona by its ID
* Reference one or more `US-NNN` IDs from GoalSpec
* Have a clearly defined starting state
* Have alternating user and system steps
* Have a defined desired outcome

Every `US-NNN` in GoalSpec must be covered by at least one journey.

---

### Information Architecture

Defines how information is organized. Represented as a navigation tree.

Rules:

* Leaf nodes (no children) must reference a screen ID
* Every screen ID referenced in the IA must exist in the Screen Inventory
* Every screen in the Screen Inventory must appear in the IA

---

### Screen Inventory

List of all screens and views. Screen IDs are the shared key referenced
throughout this spec.

Screen IDs are kebab-case, e.g. `library-screen`, `search-panel`.

For each screen:

* **ID** — kebab-case, unique
* **Name** — human-readable
* **Purpose** — one sentence: what the user accomplishes here
* **Primary Actions** — the main things a user can do
* **Inputs** (optional) — data the user provides
* **Outputs** (optional) — data the screen displays
* **US refs** (optional) — `US-NNN` IDs this screen helps fulfil

---

### Screen Specifications

Detailed description of each screen. Every screen in the inventory must
have a screen spec.

For each screen spec:

* **Screen ref** — must match a screen ID in the inventory
* **Layout** — spatial arrangement of elements
* **Wireframe** (optional) — ASCII sketch of the low-fidelity layout
* **Components** — UI components present, each referencing the design system
  and any interaction pattern IDs that apply
* **States** — all distinct states: at minimum empty, loaded, error
* **Interactions** — trigger → system response pairs, referencing pattern IDs

---

### Interaction Patterns

Reusable interaction rules. Defined once, referenced throughout screen specs.

Each pattern must have a unique kebab-case ID, e.g. `keyboard-navigation`.

Should be defined once and referenced by screen spec components and interactions.
Do not repeat pattern definitions inline in screen specs.

---

### Visual Design Requirements

Appearance constraints. Must describe requirements, not artistic preferences.

Each requirement must have a unique identifier in format `VDR-NNN`.

Examples:

* VDR-001: All output must render correctly in an 80-column terminal.
* VDR-002: Status indicators must not rely on colour alone.

---

### Design System

Reusable UI building blocks that define consistency across the product.

For each component:

* **Name** — e.g. Button, Card, Dialog
* **Purpose** — what it communicates or enables
* **Variants** (optional) — named variants, e.g. primary, destructive
* **Usage notes** (optional)

Screen spec components should reference design system names.

---

### Accessibility Requirements

Accessibility expectations. Each must be independently verifiable.

Each requirement must have a unique identifier in format `AR-NNN`.

Examples:

* AR-001: Every interactive action must be triggerable via keyboard.
* AR-002: Status indicators must not rely on colour alone.

---

### UX Acceptance Criteria

Design-specific success criteria. Each must be binary and independently
verifiable.

Each criterion must have a unique identifier in format `UXAC-NNN`.

Each criterion must:

* Be binary — passes or fails
* Reference at least one `US-NNN` or `REQ-NNN` from GoalSpec
* Not use subjective language (feel, intuitive, easy, nice, smooth)

---

## Forbidden Content

* Database schemas
* Internal APIs
* Source code
* Implementation details
* Technology selection

---

## Completion Criteria

A developer unfamiliar with the project can:

* Understand all screens.
* Understand all workflows.
* Understand all interactions.
* Build the UI without asking design questions.

---

## Linting

After producing `artifacts/DesignSpec.json`, run:

```
python extensions/blueprint/linters/lint_designspec.py artifacts/DesignSpec.json \
  --schema schemas/designspec.schema.json \
  --goal   artifacts/GoalSpec.json \
  --json
```

All errors must be resolved before handoff.
