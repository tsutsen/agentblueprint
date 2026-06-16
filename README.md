# AgentBlueprint

Structured software lifecycle artifacts through guided interviews. Produces
enforceable, structured documentation (GoalSpec, Glossary, DesignSpec,
ArchitectureSpec, DataSpec, ApiSpec, TestSpec) with cross-spec validation.

## Quick Start

```bash
# Install in your project
npm install github:tsutsen/agentblueprint

# Initialize workspace (creates artifacts/, tasks/, pre-creates artifact files, installs deps)
/skill:blueprint init

# Start with the first artifact
/skill:blueprint goal
```

Then follow the guided interview. Each artifact produces both a human-readable
Markdown document and a machine-readable JSON file.

## Structure

```
AgentBlueprint/
├── package.json              ← Pi package manifest
├── README.md                 ← this file
├── .gitignore
├── extensions/
│   └── blueprint/
│       ├── index.ts          ← registers all tools
│       ├── scripts/          ← automation scripts
│       │   ├── generate_tests.py
│       │   └── json_uml_convert.py
│       └── linters/          ← spec validation linters
│           ├── lint_all.py
│           ├── lint_goalspec.py
│           ├── lint_glossary.py
│           ├── lint_designspec.py
│           ├── lint_archspec.py
│           ├── lint_dataspec.py
│           ├── lint_apispec.py
│           ├── lint_testspec.py
│           ├── lint_issues.py
│           ├── lint_taskplan.py
│           └── lint_cross.py
└── skills/
    ├── blueprint/
    │   ├── SKILL.md          ← orchestrator skill
    │   └── schemas/
    │       ├── markdown/     ← interview schemas (human-readable)
    │       │   ├── GoalSpec.md
    │       │   ├── Glossary.md
    │       │   ├── DesignSpec.md
    │       │   ├── ArchitectureSpec.md
    │       │   ├── DataSpec.md
    │       │   ├── ApiSpec.md
    │       │   ├── TestSpec.md
    │       │   ├── TaskPlan.md
    │       │   └── Issue.md
    │       └── json/         ← JSON validation schemas
    │           ├── goalspec.schema.json
    │           ├── glossary.schema.json
    │           ├── designspec.schema.json
    │           ├── archspec.schema.json
    │           ├── dataspec.schema.json
    │           ├── apispec.schema.json
    │           ├── testspec.schema.json
    │           ├── taskplan.schema.json
    │           ├── issue.schema.json
    │           ├── example.goalspec.json
    │           ├── example.glossary.json
    │           ├── example.designspec.json
    │           ├── example.archspec.json
    │           ├── example.dataspec.json
    │           ├── example.apispec.json
    │           ├── example.testspec.json
    │           ├── example.taskplan.json
    │           └── suite.json
    └── interview/
        └── SKILL.md          ← interview skill
```

### Skills

| Skill | Purpose |
|-------|---------|
| `blueprint` | Orchestrator — loads schemas, manages dependencies, runs linters, delegates |
| `interview` | Conducts schema-driven interviews with structured questioning |

### Schemas

Each spec has two files:

- **Interview schema** (`skills/blueprint/schemas/markdown/`) — human-readable instructions for the blueprint orchestrator
- **JSON schema** (`skills/blueprint/schemas/json/`) — machine-validation schema

### Linters

| File | Purpose |
|------|---------|
| `lint_all.py` | Unified cross-spec linter — runs all individual linters, cross-checks, completeness gates |
| `lint_goalspec.py` | GoalSpec — duplicate IDs, reference resolution, Planguage enforcement |
| `lint_glossary.py` | Glossary — circular definitions, cross-spec coverage, definition quality |
| `lint_designspec.py` | DesignSpec — IA/screen consistency, journey coverage, forbidden content |
| `lint_archspec.py` | ArchitectureSpec — dependency cycles, REQ/NFR resolution, overlapping responsibilities |
| `lint_dataspec.py` | DataSpec — entity/field naming, type resolution, relationship endpoints, enum formats |
| `lint_apispec.py`  | ApiSpec — function ID format, parameter naming, entity/type refs, cross-spec module/version match |
| `lint_testspec.py` | TestSpec — fnRef resolution, error coverage, placeholder detection, ID consistency |
| `lint_taskplan.py` | TaskPlan — requirement coverage, dependency ordering, milestone outcomes |
| `lint_issues.py` | Issue — ID sequencing, dependency consistency, epic coverage |
| `lint_cross.py` | Cross-spec — all inter-spec reference validation (REQ/NFR/US/FN/entity/api refs) |

<details>
<summary>Linter details</summary>

#### `lint_all.py`
Unified orchestrator. Runs all individual linters in dependency order, then cross-spec validation, then completeness gates. Outputs a combined report with per-layer pass/fail and an overall suite score.

<details>
<summary>lint_goalspec.py</summary>

**Checks:**
- Duplicate IDs, sequential numbering gaps
- Reference resolution (reqRefs in stories/criteria → FRs/NFRs)
- Planguage enforcement (no implementation details or thresholds in FRs)
- Actor consistency between stories and requirements
- Coverage (every FR referenced by a story and gated by a criterion)
- NFR completeness (TBD Scale/Meter flagged by status level)
- Non-goal quality (vague exclusions, weak reasoning)

**Completeness gates (10):**
- `draft` — objective present, ≥1 FR, ≥1 story, ≥1 criterion, ≥1 non-goal
- `review` — all FRs covered by stories, all FRs gated by criteria, no TBD NFRs
- `confirmed` — objective re-confirmed, status is confirmed
</details>

<details>
<summary>lint_glossary.py</summary>

**Checks:**
- Circular definitions
- Cross-spec coverage (terms referenced in other specs)
- Definition quality (≥10 chars, examples/related terms)
- Category coverage (domain-tagged terms)

**Completeness gates (5):**
- `draft` — ≥3 terms, all definitions ≥10 chars
- `review` — ≥5 terms, has domain-category terms
- `confirmed` — all terms have examples or related terms
</details>

<details>
<summary>lint_designspec.py</summary>

**Checks:**
- IA/screen consistency (all inventory screens have specs)
- Journey coverage (all journeys reference user stories)
- Forbidden content (implementation leaks in design goals)
- UXAC completeness (all screens have acceptance criteria)
- Pattern coverage (interaction patterns present)

**Completeness gates (12):**
- `draft` — design goals, ≥1 persona, ≥1 journey, ≥1 screen
- `review` — all screens specced, patterns present, UXAC present, visual design requirements, accessibility requirements
- `confirmed` — design system components present, all journeys reference stories
</details>

<details>
<summary>lint_archspec.py</summary>

**Checks:**
- Dependency cycles between components
- REQ/NFR resolution (every requirement assigned to a component)
- Overlapping responsibilities (components sharing REQ refs)
- Isolated components (no dependency participation)
- Version tracking (dataSpecVersion, apiSpecVersion)

**Completeness gates (10):**
- `draft` — overview summary, ≥1 subsystem, ≥2 components, ≥1 data flow, ≥1 constraint
- `review` — all components have REQ refs, all components in dependencies, goalSpecVersion set
- `confirmed` — dataSpecVersion set, apiSpecVersion set
</details>

<details>
<summary>lint_dataspec.py</summary>

**Checks:**
- Entity naming (PascalCase), field naming (camelCase), method naming (camelCase)
- Type resolution (primitives, entities, enums)
- Relationship endpoints (valid entities, valid types, warns on self-references)
- Enum formats (SCREAMING_SNAKE_CASE)
- Method apiRef format (FN-<camelCase>)
- Primitives quality (warns on "any")

**Completeness gates (6):**
- `draft` — ≥1 entity, ≥1 relationship
- `review` — all entities have descriptions, no orphan entities
- `confirmed` — all entities have field examples
</details>

<details>
<summary>lint_apispec.py</summary>

**Checks:**
- Function ID format (FN-<camelCase>), parameter naming (camelCase)
- Entity/type references (cross-checked against data spec)
- Module/version match (against data spec)
- Error code format (SCREAMING_SNAKE_CASE)
- Side-effect detection (create/update/delete without error conditions)
- Visibility validation

**Completeness gates (6):**
- `draft` — ≥1 function
- `review` — all functions have descriptions, all have error conditions, all declare entity affinity, dataSpecVersion set
- `confirmed` — all functions declare pure/impure
</details>

<details>
<summary>lint_testspec.py</summary>

**Checks:**
- fnRef resolution (against API spec)
- Error coverage (every documented error has a test)
- Placeholder detection (TODO/empty descriptions)
- ID consistency (TST-<name>-NNN format, no duplicates)
- Category balance (error-path and edge-case tests present)

**Completeness gates (9):**
- `draft` — ≥1 test, functionCoverage summary present
- `review` — error-path tests exist, all API functions tested, all coverage entries have outOfScope, coverage includes all tested functions, apiSpecVersion set
- `confirmed` — independent verification passed
</details>

<details>
<summary>lint_taskplan.py</summary>

**Checks:**
- Requirement coverage (every REQ/NFR/US covered by tasks)
- Dependency ordering (no circular or forward references)
- Milestone outcomes (measurable, not just task lists)

**Completeness gates:** None defined — taskplan coverage is derived from spec completeness.
</details>

<details>
<summary>lint_issues.py</summary>

**Checks:**
- ID sequencing (IS-NNN gaps)
- Dependency consistency (epic/issue parent references)
- Epic coverage (all epics have issues)

**Completeness gates:** None defined — issue lint is optional and epic-specific.
</details>

<details>
<summary>lint_cross.py</summary>

**Checks:**
- REQ/NFR refs across all specs resolve correctly
- US/FN refs consistent between specs
- Entity/api refs match data spec definitions
- API function coverage (every function tested)
- Data-API alignment (API parameter/output types match data spec types)

**Completeness gates:** None — cross-spec layer is purely structural.
</details>
</details>

## Artifact Dependency Graph

```
Dependency resolution order:
  goal → glossary → design → arch → data → api → test → plan → issues
```

Run artifacts in order. The orchestrator will warn about missing dependencies.

```
Each spec depends on:
  goal        → GoalSpec
  glossary    → GoalSpec
  design      → GoalSpec, Glossary
  arch        → GoalSpec, Glossary
  data        → GoalSpec, ArchitectureSpec
  api         → GoalSpec, ArchitectureSpec, DataSpec
  test        → GoalSpec, ApiSpec, DataSpec
  plan        → GoalSpec, DesignSpec, ArchitectureSpec, DataSpec, ApiSpec, TestSpec
  issues      → TaskPlan (epic file + existing IS-NNN directories)
```

## Commands

| Command | Artifact | Description |
|---------|----------|-------------|
| `/skill:blueprint init` | — | Create workspace structure, pre-create artifact files, install deps. Add `force:true` to overwrite existing files. |
| `/skill:blueprint goal` | GoalSpec | Define project objectives and scope |
| `/skill:blueprint glossary` | Glossary | Define domain terminology |
| `/skill:blueprint design` | DesignSpec | Define user-facing design |
| `/skill:blueprint architecture` | ArchitectureSpec | Define system structure |
| `/skill:blueprint data` | DataSpec | Define data model |
| `/skill:blueprint api` | ApiSpec | Define API contracts |
| `/skill:blueprint test` | TestSpec | Define test cases |
| `/skill:blueprint plan` | TaskPlan | Generate task breakdown |
| `/skill:blueprint issues EP-NNN` | Issue | Decompose epic into issues |

## Output Layout

After running a command, artifacts appear in the target project:

```
project/
├── artifacts/              ← generated artifacts
│   ├── GoalSpec.md + .json
│   ├── Glossary.md + .json
│   ├── DesignSpec.md + .json
│   ├── ArchitectureSpec.md + .json
│   ├── DataSpec.md + .json
│   ├── ApiSpec.md + .json
│   ├── TestSpec.md + .json
├── tasks/                  ← generated tasks
│   ├── PLAN.md
│   ├── epics/
│   │   ├── EP-001/
│   │   │   ├── EP-001-slug.md + .json
│   │   │   └── IS-001/
│   │   │       ├── IS-001.md + .json
│   │   └── EP-002/
│   └── reviews/
└── diagrams/               ← generated from DataSpec
    ├── plantuml_data_diagram.puml
    ├── mermaid_data_diagram.md
    ├── drawio_data_diagram.drawio
    ├── dbml_data_diagram.dbml
    └── d2_data_diagram.d2
```

## Tool Signatures

| Tool | Parameters | Purpose |
|------|-----------|---------|
| `init_workspace` | `force?` | Creates directories, pre-creates artifact files, installs deps |
| `load_artifact` | `artifactType` | Loads schema + dependencies, prefers JSON, validates required deps |
| `write_section` | `filePath, section, content, sections_complete, sections_pending, jsonContent?` | Writes a confirmed section; optionally writes JSON artifact |
| `update_frontmatter` | `filePath, status, sections_complete, sections_pending` | Updates artifact frontmatter (status, sections, date) |
| `dual_output` | `artifactType, filePath` | Validates existing JSON, sets status from frontmatter, finalizes JSON |
| `lint` | `artifacts?[], mode?, epic?, epicsDir?` | Structural linting (`assess` for decisions, `raw` for full report) |
| `handoff` | `{}` | Checks artifact availability against DEPS, produces handoff table |
| `generate_tests` | `apiSpecPath?, goalSpecPath?, testSpecPath?, reqMappingPath?` | Auto-generate TestSpec from ApiSpec (happy/edge/error paths, reqRefs) |
| `generate_diagrams` | `dataSpecPath?, formats?, outputDir?` | Generate data model diagrams (puml, mermaid, drawio, dbml, d2) |

## ID Naming Conventions

| Spec | Pattern | Abbreviation | Examples |
|------|---------|--------------|----------|
| GoalSpec | `REQ-NNN` | **REQ** — Requirement | `REQ-001` |
| | `NFR-NNN` | **NFR** — Non-Functional Requirement | `NFR-001` |
| | `SC-NNN` | **SC** — Scenario | `SC-001` |
| | `US-NNN` | **US** — User Story | `US-001` |
| DesignSpec | `DG-NNN` | **DG** — Design Guideline | `DG-001` |
| | `UXAC-NNN` | **UXAC** — UX Acceptance Criterion | `UXAC-001` |
| | `VDR-NNN` | **VDR** — Visual Design Requirement | `VDR-001` |
| | `AR-NNN` | **AR** — Accessibility Requirement | `AR-001` |
| | `UJ-NNN` | **UJ** — User Journey | `UJ-001` |
| ArchitectureSpec | `CON-NNN` | **CON** — Component / Concern | `CON-001` |
| TaskPlan | `EP-NNN` | **EP** — Epic | `EP-001` |
| | `M\d+` | **M** — Milestone | `M1` |
| Issues | `IS-NNN` | **IS** — Implementation Story | `IS-001` |
| ApiSpec | `FN-<camelCase>` | **FN** — Function / API Endpoint | `FN-createUser` |
| TestSpec | `TST-<name>-NNN` | **TST** — Test Case | `TST-createUser-001` |
| DataSpec | PascalCase entities, camelCase fields | — | `User`, `orderItem` |
| DataSpec enums | SCREAMING_SNAKE_CASE | — | `PENDING`, `SHIPPED` |
| Screens/flows/components | kebab-case | — | `library-screen`, `query-flow` |

## Design Principles

1. **Dual output** — every artifact has a Markdown version (human) and a JSON
   version (machine). JSON is the authoritative dependency for downstream
   artifacts.
2. **Enforceable** — schemas define strict structure. Linters validate
   cross-spec consistency. No free-form gaps.
3. **Composable** — each skill has a single responsibility. The orchestrator
   composes them. Skills can be extended independently.
4. **Resumable** — artifacts track their sections and status. Sessions can be
   resumed from the last incomplete section.
5. **Read-only schemas** — schema files define the rules for artifacts but are
   never modified by artifact commands. To change a schema, edit it directly.
   Artifact commands only create new files in `artifacts/`.
6. **JSON-first** — `write_section` accumulates JSON in memory across sections.
   `dual_output` validates and finalizes. Markdown is never parsed for JSON.
7. **Automation-ready** — `generate_tests` and `generate_diagrams` tools provide
   programmatic generation from ApiSpec and DataSpec, with post-generation
   review required.
