# AgentBlueprint

Structured software lifecycle artifacts through guided interviews. Produces
enforceable, structured documentation (GoalSpec, Glossary, DesignSpec,
ArchitectureSpec, DataSpec, ApiSpec, TestSpec) with cross-spec validation.

## Quick Start

```bash
# Install in your project
pi install git:github.com/tsutsen/agentblueprint

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
│       │   ├── generate_artifact_markdown.py
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
│           └── lint_schemas.py
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
    └── lint/
        └── SKILL.md          ← on-demand lint suite runner
```

### Skills

| Skill | Purpose |
|-------|---------|
| `blueprint` | Orchestrator — loads schemas, manages dependencies, runs linters, delegates |
| `interview` | Conducts schema-driven interviews with structured questioning |
| `lint` | Runs the full SDLC lint suite — validates artifacts, checks completeness gates, detects drift |
| `spec-upgrade` | Migrates artifact files from old schema format to new format |

### Schemas

Each spec has two files:

- **Agent instructions** (`skills/blueprint/instructions/`) — human-readable agent guidance for producing each spec artifact
- **JSON schema** (`skills/blueprint/schemas/`) — machine-validation schema, source of truth for structure

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
| `lint_schemas.py` | Schema validation utility — JSON schema validation for all specs |

<details>
<summary>Linter details</summary>

#### `lint_all.py`
Unified orchestrator. Runs all individual linters in dependency order, then cross-spec validation, then completeness gates. Outputs a combined report with per-layer pass/fail and an overall suite score.

<details>
<summary>lint_goalspec.py</summary>


**Checks:**
- `check_duplicates` — Duplicate IDs, sequential numbering gaps
- `check_sequential` — Non-sequential ID numbering (gaps)
- `check_objective` — Objective present and re-confirmed
- `check_functional_requirements` — FR content validation
- `check_nfrs` — NFR completeness (TBD Scale/Meter flagged)
- `check_user_stories` — User story validation and actor consistency
- `check_success_criteria` — Success criteria validation
- `check_coverage` — Every FR referenced by a story and gated by a criterion
- `check_non_goals` — Non-goal quality (vague exclusions, weak reasoning)
- `check_glossary_refs` — Glossary reference validation

**Completeness gates (10):**
- `draft` — objective present, ≥1 FR, ≥1 story, ≥1 criterion, ≥1 non-goal
- `review` — all FRs covered by stories, all FRs gated by criteria, no TBD NFRs
- `confirmed` — objective re-confirmed, status is confirmed
</details>

<details>
<summary>lint_glossary.py</summary>


**Checks:**
- `check_gl_ids` — Glossary ID format validation
- `check_duplicates` — Duplicate term IDs
- `check_self_reference` — Terms referencing themselves
- `check_circular_definitions` — Circular definition chains
- `check_related_terms` — Related terms completeness
- `check_synonym_conflicts` — Synonym conflict detection
- `check_definition_quality` — Definition quality (≥10 chars, examples/related terms)
- `check_cross_spec_coverage` — Cross-spec coverage (terms referenced in other specs)

**Completeness gates (5):**
- `draft` — ≥3 terms, all definitions ≥10 chars
- `review` — ≥5 terms, has domain-category terms
- `confirmed` — all terms have examples or related terms
</details>

<details>
<summary>lint_designspec.py</summary>


**Checks:**
- `check_duplicates` — Duplicate IDs, sequential numbering gaps
- `check_project_and_version` — Project and version pins
- `check_design_goals` — Design goals validation
- `check_personas` — Persona validation
- `check_journeys` — Journey validation and user story coverage
- `check_ia` — Information architecture validation
- `check_screen_inventory` — Screen inventory completeness
- `check_screen_specs` — Screen spec validation
- `check_interaction_patterns` — Interaction patterns present
- `check_uxac` — UXAC completeness (all screens have acceptance criteria)
- `check_us_journey_coverage` — Journey coverage (all journeys reference user stories)
- `check_forbidden_content` — Implementation leaks in design goals
- `check_screens_reachable` — Screen reachability
- `check_glossary_refs` — Glossary reference validation

**Completeness gates (12):**
- `draft` — design goals, ≥1 persona, ≥1 journey, ≥1 screen
- `review` — all screens specced, patterns present, UXAC present, visual design requirements, accessibility requirements
- `confirmed` — design system components present, all journeys reference stories
</details>

<details>
<summary>lint_archspec.py</summary>


**Checks:**
- `check_duplicates` — Duplicate IDs, sequential numbering gaps
- `check_project_match` — Project name and version pins
- `check_version_pins` — Version pin validation
- `check_components` — Component validation
- `check_subsystems` — Subsystem validation
- `check_data_flows` — Data flow validation
- `check_constraints` — Constraint validation
- `check_req_nfr_refs` — REQ/NFR resolution (every requirement assigned to a component)
- `check_fr_coverage` — Functional requirement coverage
- `check_nfr_coverage` — Non-functional requirement coverage
- `check_subsystem_empty` — Empty subsystem detection
- `check_subsystem_overlap` — Overlapping responsibilities (components sharing REQ refs)
- `check_data_ref_valid` — Data reference validation
- `check_component_responsibility_count` — Component responsibility count
- `check_data_flow_step_count` — Data flow step count
- `check_external_component_count` — External component count
- `check_dependency_depth` — Dependency depth validation
- `check_isolated_components` — Isolated components (no dependency participation)
- `check_flow_descriptions` — Flow descriptions present
- `check_flow_data_refs` — Flow data reference validation

**Completeness gates (10):**
- `draft` — overview summary, ≥1 subsystem, ≥2 components, ≥1 data flow, ≥1 constraint
- `review` — all components have REQ refs, all components in dependencies, goalSpecVersion set
- `confirmed` — dataSpecVersion set, apiSpecVersion set
</details>

<details>
<summary>lint_dataspec.py</summary>


**Checks:**
- `check_duplicates` — Duplicate IDs, sequential numbering gaps
- `check_entities` — Entity naming (PascalCase), field naming (camelCase)
- `check_enums` — Enum formatting (PascalCase names, SCREAMING_SNAKE_CASE values)
- `check_abstract_entity_relationships` — Abstract entity relationship validation
- `check_relationships` — Relationship endpoints (valid entities, valid types, warns on self-references)
- `check_relationship_label_keywords` — Label keyword matching
- `check_enum_entity_conflict` — Enum-entity collision (same name as entity and enum)
- `check_field_type_kinds` — Type resolution (primitives, entities, enums)
- `check_duplicate_fields` — Duplicate field names within entities
- `check_entity_should_be_field` — Entity→field heuristic (≤3 fields, all primitives, ≤1 relationship, ≤1 referrer)
- `check_field_should_be_entity` — Field→entity heuristic (>5 fields, has identity, ≥2 referrers, ≥1 relationship, ≥2 API functions)
- `check_methods_coverage` — Methods coverage (entity with ≥2 API functions but 0 methods defined)
- `check_entity_similarity` — Entity similarity (similar names + high field overlap)
- `check_similar_entities_connected` — Similar entities disconnected (similar names but no relationship)
- `check_bidirectional_relationships` — Bidirectional relationships (warns when A → B and B → A both exist)
- `check_entity_list_fields` — Entity list fields (warns when entity has `Entity[]` field)
- `check_primitives` — Primitives completeness (checks for missing primitives like `void`), quality (warns on "any")
- `check_pk_naming` — Primary key naming
- `check_duplicate_relationships` — Duplicate relationship detection
- `check_missing_descriptions` — Missing descriptions

**Completeness gates (7):**
- `draft` — ≥1 entity, ≥1 relationship
- `review` — all entities have descriptions, no orphan entities, orphan percentage <20%
- `confirmed` — all entities have field examples
</details>

<details>
<summary>lint_apispec.py</summary>


**Checks:**
- `check_duplicates` — Duplicate IDs, sequential numbering gaps
- `check_functions` — Function ID format (FN-<camelCase>), parameter naming (camelCase)
- `check_errors` — Error code format (SCREAMING_SNAKE_CASE)
- `check_visibility` — Visibility validation
- `check_duplicate_names` — Duplicate function names
- `check_missing_descriptions` — Missing descriptions
- `check_unused_functions` — Unused functions detection
- `check_cross_spec_types` — Entity/type references (cross-checked against data spec)
- `check_required_parameter_description` — Required parameter descriptions
- `check_internal_function_visibility` — Internal function visibility enforcement
- `check_entity_refs` — Entity reference validation
- `check_module_match` — Module match (against data spec)
- `check_version_match` — Version match (against data spec)

**Completeness gates (6):**
- `draft` — ≥1 function
- `review` — all functions have descriptions, all have error conditions, all declare entity affinity, dataSpecVersion set
- `confirmed` — all functions declare pure/impure
</details>

<details>
<summary>lint_testspec.py</summary>


**Checks:**
- `check_duplicate_ids` — Duplicate test IDs
- `check_id_fn_consistency` — ID consistency (TST-<name>-NNN format), fnRef resolution
- `check_category_rules` — Category balance (error-path and edge-case tests present)
- `check_placeholder_values` — Placeholder detection (TODO/empty descriptions)
- `check_api_refs` — API reference validation
- `check_api_coverage` — Error coverage (every documented error has a test)
- `check_function_coverage_summary` — Function coverage summary present
- `check_glossary_refs` — Glossary reference validation
- `check_lifecycle` — Lifecycle validation

**Completeness gates (9):**
- `draft` — ≥1 test, functionCoverage summary present
- `review` — error-path tests exist, all API functions tested, all coverage entries have outOfScope, coverage includes all tested functions, apiSpecVersion set
- `confirmed` — independent verification passed
</details>

<details>
<summary>lint_taskplan.py</summary>


**Checks:**
- `run_lint` — Requirement coverage (every REQ/NFR/US covered by tasks), dependency ordering (no circular or forward references), milestone outcomes (measurable, not just task lists)

**Completeness gates:** None defined — taskplan coverage is derived from spec completeness.
</details>

<details>
<summary>lint_issues.py</summary>


**Checks:**
- `run_lint` — ID sequencing (IS-NNN gaps), dependency consistency (epic/issue parent references), epic coverage (all epics have issues)

**Completeness gates:** None defined — issue lint is optional and epic-specific.
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
| `/skill:lint` | — | Quick check all artifacts in `artifacts/` |
| `/skill:lint data` | DataSpec | Lint only DataSpec |
| `/skill:lint data api` | DataSpec, ApiSpec | Lint DataSpec + ApiSpec |
| `/skill:lint --strict` | — | All artifacts, warnings as errors |
| `/skill:lint data --strict` | DataSpec | Lint DataSpec, warnings as errors |

## Output Layout

After running a command, artifacts appear in the target project. JSON is the
single source of truth; Markdown is derived from JSON.

```
project/
├── artifacts/              ← generated artifacts (JSON is authoritative)
│   ├── GoalSpec.json + .md
│   ├── Glossary.json + .md
│   ├── DesignSpec.json + .md
│   ├── ArchitectureSpec.json + .md
│   ├── DataSpec.json + .md
│   ├── ApiSpec.json + .md
│   ├── TestSpec.json + .md
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
| `write_spec_fields` | `filePath, field, content, updates[{jsonPath, jsonValue}]` | Surgically updates one or more JSON fields atomically; loads existing JSON, merges, writes back |
| `lint` | `artifacts?[], mode?, epic?, epicsDir?` | Structural linting (`assess` for decisions, `raw` for full report) |
| `handoff` | `{}` | Checks artifact availability against DEPS, produces handoff table |
| `generate_tests` | `apiSpecPath?, goalSpecPath?, testSpecPath?, reqMappingPath?` | Auto-generate TestSpec from ApiSpec (happy/edge/error paths, reqRefs) |
| `generate_diagrams` | `dataSpecPath?, formats?, outputDir?` | Generate data model diagrams (puml, mermaid, drawio, dbml, d2) |
| `generate_artifact_markdown` | `artifactType, jsonPath` | Convert JSON artifact to Markdown (derived, zero drift) |
| `spec_upgrade` | `artifactType, filePath` | Migrate artifact from old schema format to new format |

## ID Naming Conventions

All IDs follow the format `PREFIX-NNN-suffix` where NNN is a 3-digit zero-padded number. All suffixes use **PascalCase**.

| Spec | Pattern | Abbreviation | Example |
|------|---------|--------------|----------|
| GoalSpec | `REQ-NNN-PascalCase` | **REQ** — Requirement | `REQ-001-CreateAccount` |
| | `NFR-NNN-PascalCase` | **NFR** — Non-Functional Requirement | `NFR-001-ResponseTime` |
| | `US-NNN-PascalCase` | **US** — User Story | `US-001-Login` |
| | `SC-NNN-PascalCase` | **SC** — Scenario | `SC-001-DataIntegrity` |
| | `NG-NNN-PascalCase` | **NG** — Non-Goal | `NG-001-WebSearch` |
| Glossary | `GL-NNN-PascalCase` | **GL** — Glossary Term | `GL-001-Authentication` |
| DesignSpec | `DG-NNN-PascalCase` | **DG** — Design Guideline | `DG-001-MinimizeCognitiveLoad` |
| | `SCR-NNN-PascalCase` | **SCR** — Screen | `SCR-001-LandingPage` |
| | `DT-NNN-PascalCase` | **DT** — Design Token | `DT-001-PrimaryColor` |
| | `PAT-NNN-PascalCase` | **PAT** — Pattern | `PAT-001-KeyboardNavigation` |
| | `PRS-NNN-PascalCase` | **PRS** — Persona | `PRS-001-PowerDeveloper` |
| | `SPC-NNN` | **SPC** — Screen Pattern | `SPC-001` |
| | `UJ-NNN-PascalCase` | **UJ** — User Journey | `UJ-001-FindProduct` |
| | `UXAC-NNN-PascalCase` | **UXAC** — UX Acceptance Criterion | `UXAC-001-TouchTarget` |
| | `VDR-NNN` | **VDR** — Visual Design Requirement | `VDR-001` |
| ArchitectureSpec | `COMP-NNN-PascalCase` | **COMP** — Component | `COMP-001-AuthService` |
| | `CON-NNN-PascalCase` | **CON** — Constraint | `CON-001-AuthenticationRequired` |
| | `FLW-NNN-PascalCase` | **FLW** — Data Flow | `FLW-001-SessionCreation` |
| DataSpec | `ENT-NNN-PascalCase` | **ENT** — Entity | `ENT-001-User` |
| | `NUM-NNN-PascalCase` | **NUM** — Enum | `NUM-001-Status` |
| | `PRIM-NNN-PascalCase` | **PRIM** — Primitive | `PRIM-001-UserId` |
| | `REL-NNN-PascalCase` | **REL** — Relationship | `REL-001-UserOrders` |
| ApiSpec | `FN-NNN-PascalCase` | **FN** — Function | `FN-001-Authenticate` |
| TestSpec | `TST-NNN-PascalCase` | **TST** — Test Case | `TST-001-ExportReportAsPDF` |
| | `FC-NNN-PascalCase` | **FC** — Failure Case | `FC-001-Authenticate` |
| TaskPlan | `EP-NNN-PascalCase` | **EP** — Epic | `EP-001-UserOnboarding` |
| | `MIL-NNN-PascalCase` | **MIL** — Milestone | `MIL-001-Setup` |
| Issues | `IS-NNN-PascalCase` | **IS** — Implementation Story | `IS-001-ImplementLogin` |
| | `SI-NNN-PascalCase` | **SI** — Sub-Issue | `SI-001-CreateLoginSchema` |

**Suffix rules:**
- `PascalCase`: starts uppercase, e.g. `Authentication`, `CreateAccount`, `MinimizeCognitiveLoad`
- No suffix: just `PREFIX-NNN` (3-digit zero-padded), e.g. `VDR-001`

## Design Principles

1. **JSON-first** — the JSON artifact is the single source of truth at all
   times. `write_spec_fields` writes JSON directly during the interview.
   Markdown is derived from JSON via `generate_artifact_markdown` after
   lint passes. Zero risk of format drift.
2. **Enforceable** — schemas define strict structure. Linters validate
   cross-spec consistency. No free-form gaps.
3. **Composable** — each skill has a single responsibility. The orchestrator
   composes them. Skills can be extended independently.
4. **Resumable** — artifacts track their sections and status. Sessions can be
   resumed from the last incomplete section.
5. **Read-only schemas** — schema files define the rules for artifacts but are
   never modified by artifact commands. To change a schema, edit it directly.
   Artifact commands only create new files in `artifacts/`.
6. **Automation-ready** — `generate_tests` and `generate_diagrams` tools provide
   programmatic generation from ApiSpec and DataSpec, with post-generation
   review required.
