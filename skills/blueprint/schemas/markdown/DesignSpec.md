---
name: DesignSpec
type: schema
version: 4.0.0
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

---

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

* **glossaryRefs** (array of GL-NNN): Glossary terms the persona's role maps to

---

### User Journeys

End-to-end workflows from the user's perspective.

Each journey must have a unique identifier in format `UJ-NNN-slug`, e.g. `UJ-001-full-research-session`.

Each journey must:

* Reference a persona by its ID
* Reference one or more `US-NNN` IDs from GoalSpec
* Have a clearly defined starting state
* Have alternating user and system steps
* Have a defined desired outcome
* Each journey step may have **glossaryRefs** (array of GL-NNN): Concepts in the step's action description
* **reqRefs** (array of REQ-NNN-slug): GoalSpec requirements this journey exercises end-to-end
* **fnRefs** (array of FN-NNN-slug): ApiSpec functions this journey exercises

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

Screen IDs are in format `SCR-NNN-slug`, e.g. `SCR-001-landing-page`.

For each screen:

* **glossaryRefs** (array of GL-NNN): Domain concepts in the screen's purpose description

---

### Screen Specifications

Detailed description of each screen. Every screen in the inventory must
have a screen spec.

For each screen spec:

  and any interaction pattern IDs that apply
  * Each component may have **glossaryRefs** (array of GL-NNN): Concepts in the component's purpose description

---

### Interaction Patterns

Reusable interaction rules. Defined once, referenced throughout screen specs.

Each pattern must have a unique identifier in format `PAT-NNN-slug`, e.g. `PAT-001-pipeline-status-indicators`.

Should be defined once and referenced by screen spec components and interactions.
Do not repeat pattern definitions inline in screen specs.

---

### Visual Design Requirements

Appearance constraints. Must describe requirements, not artistic preferences.

Each requirement must have a unique identifier in format `VDR-NNN-slug`, e.g. `VDR-001-design-token-system`.

Examples:

* VDR-001: All output must render correctly in an 80-column terminal.
* VDR-002: Status indicators must not rely on colour alone.

---

### Design System

Reusable UI building blocks that define consistency across the product.

For each component:

* **Usage notes** (optional)

Screen spec components should reference design system names.

---

### Accessibility Requirements

Accessibility expectations. Each must be independently verifiable.

Each requirement must have a unique identifier in format `AR-NNN-slug`, e.g. `AR-001-contrast-ratio-4-5`.

Examples:

* AR-001: Every interactive action must be triggerable via keyboard.
* AR-002: Status indicators must not rely on colour alone.

---

### UX Acceptance Criteria

Design-specific success criteria. Each must be binary and independently
verifiable.

Each criterion must have a unique identifier in format `UXAC-NNN-slug`, e.g. `UXAC-001-new-research-session`.

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

### Design Tokens

Reusable visual values that define consistency across the product. Tokens replace
hardcoded values in screen specs and styles.

Each token must have:

Examples:
* `TKN-001-color-primary`: `#1a73e8` — Primary brand color, used for buttons and links
* `TKN-002-spacing-md`: `16px` — Medium spacing, used for padding between sections
* `TKN-003-font-size-lg`: `18px` — Large text, used for headings


