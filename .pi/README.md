# AgentBlueprint

Drop this `.pi/` folder into any project to get enforceable, structured
documentation. It produces structured artifacts (GoalSpec, Glossary, DesignSpec,
ArchitectureSpec, DataSpec, ApiSpec, TestSpec) through guided interviews,
validates them with a cross-spec linter, and manages their state transitions.

## Quick Start

```bash
# Drop .pi/ into your project
cp -r .pi /path/to/project/.pi

# Start with the first artifact
/skill:blueprint goal
```

Then follow the guided interview. Each artifact produces both a human-readable
Markdown document and a machine-readable JSON file.

## Structure

```
.pi/
├── README.md
├── skills/
│   ├── interview/SKILL.md          ← structured questioning
│   └── blueprint/
│       ├── SKILL.md                ← orchestrator
│       └── schemas/
│           ├── markdown/           ← interview schemas (human-readable)
│           │   ├── GoalSpec.md
│           │   ├── Glossary.md
│           │   ├── DesignSpec.md
│           │   ├── ArchitectureSpec.md
│           │   ├── DataSpec.md
│           │   ├── ApiSpec.md
│           │   ├── TestSpec.md
│           │   └── TaskPlan.md
│           └── json/               ← JSON validation schemas
│               ├── goalspec.schema.json
│               ├── glossary.schema.json
│               ├── designspec.schema.json
│               ├── archspec.schema.json
│               ├── dataspec.schema.json
│               ├── apispec.schema.json
│               ├── testspec.schema.json
│               ├── example.goalspec.json
│               ├── example.glossary.json
│               ├── example.designspec.json
│               ├── example.archspec.json
│               ├── example.dataspec.json
│               ├── example.apispec.json
│               ├── example.testspec.json
│               └── suite.json
└── extensions/
    └── blueprint/
        ├── index.ts                ← registers all tools
        ├── linters/
        │   ├── lint_all.py         ← unified cross-spec linter
        │   ├── lint_goalspec.py
        │   ├── lint_glossary.py
        │   ├── lint_designspec.py
        │   ├── lint_archspec.py
        │   ├── lint_testspec.py
        │   └── lint_cross.py
        └── skills/                 ← bundled for distribution via init_workspace
            ├── blueprint/
            │   └── schemas/        ← (same as .pi/skills/blueprint/schemas/)
            └── interview/
```

### Skills

| Skill | Purpose |
|-------|---------|
| `blueprint` | Orchestrator — loads schemas, manages dependencies, runs linters, delegates |
| `interview` | Conducts schema-driven interviews with structured questioning |

### Schemas

Each spec has two files:

- **Interview schema** (`.pi/skills/blueprint/schemas/markdown/`) — human-readable instructions for the blueprint orchestrator
- **JSON schema** (`.pi/skills/blueprint/schemas/json/`) — machine-validation schema

### Linters

| File | Purpose |
|------|---------|
| `lint_all.py` | Unified cross-spec linter — runs all individual linters, cross-checks, completeness gates |
| `lint_goalspec.py` | GoalSpec — duplicate IDs, reference resolution, Planguage enforcement |
| `lint_glossary.py` | Glossary — circular definitions, cross-spec coverage, definition quality |
| `lint_designspec.py` | DesignSpec — IA/screen consistency, journey coverage, forbidden content |
| `lint_archspec.py` | ArchitectureSpec — dependency cycles, REQ/NFR resolution, overlapping responsibilities |
| `lint_testspec.py` | TestSpec — fnRef resolution, error coverage, placeholder detection |
| `lint_taskplan.py` | TaskPlan — requirement coverage, dependency ordering, milestone outcomes |
| `lint_cross.py` | Cross-spec — all inter-spec reference validation (REQ/NFR/US/FN entity/api refs) |

## Artifact Dependency Graph

```
Dependency resolution order:
  goal → glossary → design → arch → data → api → test → plan
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
```

## Commands

| Command | Artifact | Description |
|---------|----------|-------------|
| `/skill:blueprint goal` | GoalSpec | Define project objectives and scope |
| `/skill:blueprint glossary` | Glossary | Define domain terminology |
| `/skill:blueprint design` | DesignSpec | Define user-facing design |
| `/skill:blueprint architecture` | ArchitectureSpec | Define system structure |
| `/skill:blueprint data` | Data | Define data model |
| `/skill:blueprint api` | Api | Define API contracts |
| `/skill:blueprint test` | Test | Define test cases |
| `/skill:blueprint plan` | TaskPlan | Generate task breakdown |


## Output Layout

After running a command, artifacts appear in the target project:

```
project/
├── .pi/                    ← this folder (read-only)
├── artifacts/              ← generated artifacts
│   ├── GoalSpec.md + .json
│   ├── Glossary.md + .json
│   ├── DesignSpec.md + .json
│   ├── ArchitectureSpec.md + .json
│   ├── DataSpec.md + .json
│   ├── ApiSpec.md + .json
│   ├── TestSpec.md + .json
└── tasks/                  ← generated tasks
    ├── PLAN.md
    ├── epics/
    └── reviews/
```

## Tool Signatures

| Tool | Parameters | Purpose |
|------|-----------|---------|
| `load_artifact` | `artifactType` | Loads schema + dependencies, prefers JSON, validates required deps |
| `write_section` | `filePath, section, content, sections_complete, sections_pending, jsonContent?` | Writes a confirmed section; optionally writes JSON artifact |
| `dual_output` | `artifactType, filePath` | Validates existing JSON, sets status from frontmatter, finalizes JSON |
| `lint` | `artifacts?[], mode?` | Structural linting (`assess` for decisions, `raw` for full report) |
| `handoff` | `{}` | Checks artifact availability against DEPS, produces handoff table |

## ID Naming Conventions

| Spec | Pattern | Examples |
|------|---------|----------|
| GoalSpec | `REQ-NNN`, `NFR-NNN`, `SC-NNN`, `US-NNN` | `REQ-001`, `NFR-001`, `SC-001`, `US-001` |
| DesignSpec | `DG-NNN`, `UXAC-NNN`, `VDR-NNN`, `AR-NNN`, `UJ-NNN` | `DG-001`, `UXAC-001`, `AR-001` |
| ArchitectureSpec | `CON-NNN` | `CON-001` |
| TaskPlan | `EP-NNN`, `M\d+` | `EP-001`, `M1` |
| ApiSpec | `FN-<camelCase>` | `FN-createUser`, `FN-placeOrder` |
| TestSpec | `TST-<name>-NNN` | `TST-createUser-001`, `TST-placeOrder-002` |
| DataSpec | PascalCase entities, camelCase fields | `User`, `orderItem` |
| DataSpec enums | SCREAMING_SNAKE_CASE | `PENDING`, `SHIPPED` |
| Screens/flows/components | kebab-case | `library-screen`, `query-flow` |

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
