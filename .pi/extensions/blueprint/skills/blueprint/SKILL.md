---
name: blueprint
description: >
  Orchestrates creation of software lifecycle artifacts (GoalSpec, Glossary,
  DesignSpec, ArchitectureSpec, DataSpec, ApiSpec, TestSpec). Loads schema and
  dependencies, runs structural linting on existing artifacts, delegates
  interviewing to the interview skill. Writes sections via the write_section
  tool. Use when the user wants to create or continue a project artifact.
version: 1.0.0
---

# Blueprint

Blueprint is the project artifact orchestrator.

It delegates:

- interview mechanics → `/skill:interview`

---

## Responsibilities

Blueprint is responsible for:

1. Determining which artifact is being created.
2. Loading the artifact schema.
3. Loading dependency artifacts.
4. Running structural lint on existing artifacts and surfacing findings.
5. Invoking interview workflows and writing sections via tools.
7. Producing JSON and Markdown output for every completed artifact.
8. Producing handoff recommendations.

Blueprint is NOT responsible for:

- interview methodology

Those belong to dedicated skills.

---

## Suite Overview

| Concern              | Skill                   |
|----------------------|-------------------------|
| Artifact orchestration | `/skill:blueprint`    |
| Interview mechanics  | `/skill:interview`      |

---

## Session Orientation

**Every time a command is invoked at the start of a session**, perform the
following steps before anything else. Do not skip them or read any files
beyond what is listed.

> **Resumption exception:** If the current session already contains a partial
> interview for this artifact type, skip orientation and resume from the first
> unanswered question.

### Artifact Table

| # | Command        | Artifact         | Schema                        | Dependencies                                                                                              | Output (Markdown + JSON)                                          |
|---|----------------|------------------|-------------------------------|-----------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------|
| 0 | `goal`         | GoalSpec         | `.pi/skills/blueprint/schemas/markdown/GoalSpec.md`         | (none)                                                                                                  | `artifacts/GoalSpec.md` + `artifacts/GoalSpec.json`              |
| 1 | `glossary`     | Glossary         | `.pi/skills/blueprint/schemas/markdown/Glossary.md`         | `artifacts/GoalSpec.json`                                                                                 | `artifacts/Glossary.md` + `artifacts/Glossary.json`              |
| 2 | `design`       | DesignSpec       | `.pi/skills/blueprint/schemas/markdown/DesignSpec.md`       | `artifacts/GoalSpec.json`, `artifacts/Glossary.json`                                                      | `artifacts/DesignSpec.md` + `artifacts/DesignSpec.json`          |
| 3 | `architecture` | ArchitectureSpec | `.pi/skills/blueprint/schemas/markdown/ArchitectureSpec.md` | `artifacts/GoalSpec.json`, `artifacts/Glossary.json`                                                      | `artifacts/ArchitectureSpec.md` + `artifacts/ArchitectureSpec.json` |
| 4 | `dataspec`     | DataSpec         | `.pi/skills/blueprint/schemas/markdown/DataSpec.md`         | `artifacts/GoalSpec.json`, `artifacts/ArchitectureSpec.json`                                              | `artifacts/DataSpec.md` + `artifacts/DataSpec.json`              |
| 5 | `apispec`      | ApiSpec          | `.pi/skills/blueprint/schemas/markdown/ApiSpec.md`          | `artifacts/GoalSpec.json`, `artifacts/ArchitectureSpec.json`, `artifacts/DataSpec.json`                   | `artifacts/ApiSpec.md` + `artifacts/ApiSpec.json`   |
| 6 | `testspec`     | TestSpec         | `.pi/skills/blueprint/schemas/markdown/TestSpec.md`         | `artifacts/GoalSpec.json`, `artifacts/ApiSpec.json`, `artifacts/DataSpec.json`                            | `artifacts/TestSpec.md` + `artifacts/TestSpec.json` |
| 7 | `plan`         | TaskPlan         | `.pi/skills/blueprint/schemas/markdown/TaskPlan.md`         | `artifacts/GoalSpec.json`, `artifacts/DesignSpec.json`, `artifacts/ArchitectureSpec.json`, `artifacts/DataSpec.json`, `artifacts/ApiSpec.json`, `artifacts/TestSpec.json` | `tasks/PLAN.md` + `tasks/epics/` |
`plan` produces multiple files. All behaviour is defined in `.pi/skills/blueprint/schemas/markdown/TaskPlan.md`.

**Dependency note:** JSON artifacts are preferred over Markdown as dependencies
because they are machine-readable and can be validated. When loading dependencies,
prefer `.json` over `.md` when both exist. Load `.md` only when `.json` is absent.

---

### Step 1 — Load artifact (schema + dependencies)

Call the `load_artifact` tool:

```
tool: load_artifact
args:
  artifactType: <goal|glossary|design|arch|data|api|test|plan>
```

The tool resolves the schema and all dependencies (preferring JSON over Markdown),
validates that required dependencies exist, and returns a structured result.



**If required dependencies are missing:** the tool returns an error. Do not proceed.
Ask the user to create the missing artifacts first.

---

### Step 2 — Lint existing artifacts

Call the `lint` tool with `mode: "assess"` (default) to run the suite linter
and get a decision:

```
tool: lint
args:
  artifacts: ["goal", "design", "arch", "data", "api", "test", "glossary"]
  mode: "assess"
```

Only include artifacts whose JSON files exist on disk.

**If `decision: "block"`:**

Report the blocking errors to the user before starting the interview:

> "The linter found <N> error(s) in existing artifacts before we begin.
> These must be resolved for the suite to remain consistent."

List each error with its category, message, and hint.

Ask the user: "Fix these now before continuing, or proceed with the interview
and address them in the affected artifact's own session?"

If the user chooses to fix now: do not start the interview. Help the user
correct the affected artifacts, re-run the linter, and confirm clean before
proceeding.

**If `decision: "proceed"` with warnings:**

Briefly note the warning count but do not block:

> "Linter passed. <N> warning(s) noted — see lint report for details."

**If `decision: "proceed"` with no warnings:**

Proceed silently.



---

### Step 3 — Orientation

Read the artifact's markdown file (e.g., `artifacts/GoalSpec.md`) if it exists.
Inspect its frontmatter fields: `status`, `sections_complete`, `sections_pending`.

- **File absent:** proceed normally.
- **`status: in_progress`:** report which sections are complete and pending.
  Ask: resume from first pending section, or restart? Wait for answer.
- **`status: needs_review` or `status: complete`:** warn that the artifact is already finished.
  Ask: re-open for revision, or abort? Wait for answer.

Output before the first interview question:

- artifact being produced and its sections
- dependencies loaded; any missing
- sections already complete (if resuming)

---

### Step 4 — Interview

Invoke `/skill:interview` with a task that includes:

```
/skill:interview Interview for <ArtifactName>.

Dependencies:
- <DepName>: <resolved|missing>
- ...

Schema sections: <Section1>, <Section2>, ...

Resume from: <FirstPendingSection> (omit if fresh start)
```

The blueprint skill constructs this task from the results of Steps 1–3:
- **Dependencies** come from `load_artifact` result
- **Sections** come from the schema loaded in Step 1
- **Resume point** comes from the artifact state checked in Step 3

The interview skill generates structured questions from the schema. The blueprint
skill uses dependency content (JSON parsed or Markdown text) as context when
asking questions that reference another artifact.

---

### Step 5 — Section persistence

After each section is confirmed, write it to disk using the `write_section`
tool:

```
tool: write_section
args:
  filePath: artifacts/<ArtifactType>.md
  section: <SectionName>
  content: <validated section content>
  sections_complete: ["<Section1>", "<Section2>", ...]
  sections_pending: ["<Section3>", ...]
```

`write_section` writes the section, updates frontmatter (status=in_progress,
auto-generated date), and verifies by read-back — all in one call.

On success, show the verified content and ask:
"Does this capture it correctly, or would you like to revise?"

On revision request: re-interview affected sections, rewrite, re-verify.

After the last section:
1. Call `update_frontmatter` with `status: needs_review`,
   `sections_pending: []`.
2. Tell the user: "All sections are written. Please review and reply
   with 'approve' when you are satisfied, or tell me what to change."
3. Wait for explicit approval.
4. On approval: call `update_frontmatter` with `status: complete`,
   `sections_pending: []`, then proceed to dual output.

---

### Step 6 — Dual output

By this point, both files should already exist:

- **Markdown** (`artifacts/<ArtifactType>.md`) — written incrementally during
  the interview via `write_section` calls.
- **JSON** (`artifacts/<ArtifactType>.json`) — written incrementally during
  the interview via `write_section` with the `jsonContent` parameter.

Now validate and finalize the JSON:

```
tool: dual_output
args:
  artifactType: <goal|design|arch|data|api|test|glossary>
  filePath: artifacts/<ArtifactType>.md
```

The tool reads the existing JSON, validates against the schema, sets the
`status` field from frontmatter, and writes the final JSON file.

If validation fails, show the errors to the user and suggest fixes. Do
not modify the JSON without explicit user approval. After user confirms,
apply the fix and re-validate before invoking handoff. Do not write an
invalid JSON artifact.

---

### Step 7 — Handoff

Call the `handoff` tool to produce a handoff table:

```
tool: handoff
args: {}
```

The tool checks all artifacts' dependencies against the DEPS constant,
reads frontmatter for accurate status, and returns a formatted table
of available next steps.

Display the tool's output to the user. Do not modify the table — the
tool produces the authoritative list of available next steps.

---

## Session Hygiene

Each artifact interview should be conducted in its own dedicated session.

After handoff completes, remind the user:

> "Open a fresh session for the next artifact and run the corresponding
> command — the skill orients itself automatically from `artifacts/`."
