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
| `gh_create_issue` | Issue | Decompose epic into issues |
| `gh_create_sub_issue` | Sub-Issue | Decompose issue into sub-issues |
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
| `gh_create_epic` | `jsonPath` | Create GitHub Issue + EP branch from main |
| `gh_create_issue` | `jsonPath, parentBranch` | Create GitHub Issue + IS branch from EP branch |
| `gh_create_sub_issue` | `epId, issueId, data` | Create local SI-NNN.json + SI-NNN.md |
| `gh_create_pr` | `siId, epBranch?, targetBranch?, jsonPath?` | Create PR from SI branch targeting IS branch |
| `gh_merge_pr` | `prNumber, jsonPath?` | Merge PR and update local JSON |
| `gh_update_issue` | `issueNumber, status?, labels?, comment?` | Update issue status/labels/comments |
| `gh_get_issue` | `issueNumber` | Fetch GitHub issue state |
| `gh_list_issues` | `labels?, state?` | List issues by label/milestone |
| `gh_cleanup_branches` | `dryRun?` | Find and delete orphaned branches |
| `gh_update_sub_issue` | `jsonPath, status?, files?` | Mark SI complete, populate files audit trail |
| `gh_list_sub_issues` | `epId, issueId` | List sub-issues for an issue |

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
| | `SPC-NNN-PascalCase` | **SPC** — Screen Pattern | `SPC-001-LoginScreen` |
| | `UJ-NNN-PascalCase` | **UJ** — User Journey | `UJ-001-FindProduct` |
| | `UXAC-NNN-PascalCase` | **UXAC** — UX Acceptance Criterion | `UXAC-001-TouchTarget` |
| | `VDR-NNN-PascalCase` | **VDR** — Visual Design Requirement | `VDR-001-ContrastRatio` |
| | `AR-NNN-PascalCase` | **AR** — Accessibility Requirement | `AR-001-ScreenReaderSupport` |
| ArchitectureSpec | `COMP-NNN-PascalCase` | **COMP** — Component | `COMP-001-AuthService` |
| | `CON-NNN-PascalCase` | **CON** — Constraint | `CON-001-AuthenticationRequired` |
| | `FLW-NNN-PascalCase` | **FLW** — Data Flow | `FLW-001-SessionCreation` |
| DataSpec | `ENT-NNN-PascalCase` | **ENT** — Entity | `ENT-001-User` |
| | `NUM-NNN-PascalCase` | **NUM** — Enum | `NUM-001-Status` |
| | `REL-NNN-PascalCase` | **REL** — Relationship | `REL-001-UserOrders` |
| | `FLD-NNN-PascalCase` | **FLD** — Entity Field | `FLD-001-createdAt` |
| | `FUNC-NNN-PascalCase` | **FUNC** — Function | `FUNC-001-Authenticate` |
| ApiSpec | `ENDP-NNN-PascalCase` | **ENDP** — Endpoint | `ENDP-001-Authenticate` |
| TestSpec | `TST-NNN-PascalCase` | **TST** — Test Case | `TST-001-ExportReportAsPDF` |
| | `FC-NNN-PascalCase` | **FC** — Failure Case | `FC-001-Authenticate` |
| TaskPlan | `EP-NNN-PascalCase` | **EP** — Epic | `EP-001-UserOnboarding` |
| | `MIL-NNN-PascalCase` | **MIL** — Milestone | `MIL-001-Setup` |
| Issues | `IS-NNN-PascalCase` | **IS** — Implementation Story | `IS-001-ImplementLogin` |
| | `SI-NNN-PascalCase` | **SI** — Sub-Issue | `SI-001-CreateLoginSchema` |

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
