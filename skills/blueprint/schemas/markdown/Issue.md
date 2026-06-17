---
name: Issue
type: schema
version: 1.0.0
---

# Issue

An Issue is a single vertical slice (tracer bullet) decomposed from an Epic.
Each issue cuts end-to-end through all relevant integration layers and is
independently implementable.

Issues live inside their parent epic's directory: `tasks/epics/EP-NNN/IS-NNN/`.
Each issue has two files: `IS-NNN.md` (human-readable) and `IS-NNN.json`
(machine-readable).

---

## Directory Structure

```
tasks/epics/
  EP-001-document-ingestion/
    EP-001-document-ingestion.md    ← epic file
    EP-001-document-ingestion.json
    IS-001/
      IS-001.md                    ← issue file
      IS-001.json                  ← issue JSON
    IS-002/
      IS-002.md
      IS-002.json
```

Issue IDs are **project-global**, sequential (`IS-001`, `IS-002`, ...), and
never restart per epic. Always scan `tasks/epics/*/IS-*/` for the highest
existing IS-NNN before creating new issues.

---

## Issue File Structure

### Front Matter (YAML)

```yaml
---
artifact: Issue
id: IS-<NNN>
title: <short title>
type: <AFK | HITL>
status: <not_started | in_progress | needs_review | complete>
epic: <EP-NNN>
blocked_by:
  - <IS-NNN>        # or empty list []
milestone: <M1 | M2 | ...>
titleGlossaryRefs:
  - GL-NNN          # glossary terms in title; [] if none
inScope:
  - description: <scope item description>
    glossaryRefs:
      - GL-NNN      # glossary terms in this item; [] if none
outOfScope:
  - description: <excluded item description>
    glossaryRefs:
      - GL-NNN      # glossary terms in this item; [] if none
acceptanceCriteria:
  - description: <verifiable criterion>
    glossaryRefs:
      - GL-NNN      # glossary terms in this criterion; [] if none
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
---
```

**Field definitions:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `artifact` | string | Yes | Always `"Issue"` |
| `id` | string | Yes | Format `IS-NNN` (3-digit zero-padded) |
| `title` | string | Yes | Short, action-oriented title |
| `type` | string | Yes | `AFK` (agent can implement without human interaction) or `HITL` (requires human input at some point) |
| `status` | string | Yes | `not_started`, `in_progress`, `needs_review`, or `complete` |
| `epic` | string | Yes | Format `EP-NNN` (3-digit zero-padded) |
| `blocked_by` | array | Yes | List of IS-NNN strings; `[]` if none |
| `milestone` | string | Yes | Format `M1`, `M2`, ... |
| `titleGlossaryRefs` | array | No | GL-NNN identifiers for domain concepts in the title |
| `inScope` | array | No | Structured scope items, each with `description` and `glossaryRefs` |
| `outOfScope` | array | No | Structured out-of-scope items, each with `description` and `glossaryRefs` |
| `acceptanceCriteria` | array | No | Structured acceptance criteria, each with `description` and `glossaryRefs` |
| `created` | string | Yes | Date string `YYYY-MM-DD` |
| `updated` | string | Yes | Date string `YYYY-MM-DD` |

**Type definitions:**

| Type | Meaning |
|------|---------|
| `AFK` | Can be implemented and merged by an agent without human interaction. |
| `HITL` | Requires human input at some point — design decision, review gate, external dependency. |

Prefer `AFK` over `HITL`. Only mark `HITL` when human judgment is genuinely
required, not just because the task is complex.

### Body (Markdown)

```markdown
# IS-NNN: <title>

## What to build

<Concise description of this vertical slice. Describe end-to-end behaviour,
not layer-by-layer implementation. A completed slice is independently
demoable or verifiable.>

<Include specific file paths or code snippets only when a prototype produced
a decision-encoding snippet — state machine, reducer, schema, type shape.
If included, note it came from a prototype and trim to the decision-rich
parts only.>

## Acceptance criteria

- [ ] <independently verifiable criterion>
- [ ] <independently verifiable criterion>

## Blocked by

<IS-NNN reference, or "None — can start immediately.">
```

**Body section rules:**

- **What to build**: Describe end-to-end behaviour. Do not describe
  layer-by-layer implementation. Each slice must deliver a narrow but
  complete path through every relevant layer.
- **Acceptance criteria**: Each criterion must be independently verifiable
  and binary (pass/fail) where possible. Describes observable behaviour,
  not implementation.
- **Blocked by**: Must reference real IS-NNN identifiers that exist in the
  same epic folder, or state "None — can start immediately."

---

## Issue JSON Structure

Each issue has a parallel JSON file (`IS-NNN.json`) with the same data:

```json
{
  "artifact": "Issue",
  "id": "IS-001",
  "title": "Create research session with input validation",
  "type": "AFK",
  "status": "not_started",
  "epic": "EP-001",
  "blocked_by": [],
  "milestone": "M1",
  "titleGlossaryRefs": ["GL-001", "GL-004"],
  "inScope": [
    {
      "description": "Session creation with free-text research question",
      "glossaryRefs": ["GL-001", "GL-004"]
    }
  ],
  "outOfScope": [
    {
      "description": "Session sharing or collaboration",
      "glossaryRefs": ["GL-001"]
    }
  ],
  "acceptanceCriteria": [
    {
      "description": "User can create a session by entering a free-text research question",
      "glossaryRefs": ["GL-001", "GL-004"]
    }
  ],
  "created": "2026-06-15",
  "updated": "2026-06-15"
}
```

The JSON file contains only the front matter fields — no body content.
The body content lives exclusively in the `.md` file.

**Scope item structure:**

```json
{
  "description": "<scope item description>",
  "glossaryRefs": ["GL-NNN", ...]
}
```

Each scope item (inScope/outOfScope) and each acceptance criterion has its
description and inline `glossaryRefs`. The linter validates that domain
concepts in the description have corresponding GL-NNN references.

---

## Process Override

This artifact uses a custom flow instead of the standard blueprint flow.

### Step 1 — Load epic

Determine the epic ID from the command argument (e.g., `EP-001` from
`/skill:blueprint issues EP-001`).

Load the following:

- `tasks/PLAN.md` — milestone context
- `tasks/epics/EP-NNN/EP-NNN-slug.md` — the target epic (required; abort if not found)
- `tasks/epics/EP-NNN/` — scan for existing IS-NNN directories to find highest issue ID
- `artifacts/Glossary.md` — domain vocabulary (if present)
- `artifacts/ArchitectureSpec.json` — architectural constraints (if present)

Report the highest existing issue ID (next new issue will be IS-NNN+1).

If the epic is not found, abort and ask the user to run `/skill:blueprint plan` first.

### Step 2 — Lint issues

Run `lint_issues.py` for the target epic. Report any blocking errors.

If blocking errors exist, report them to the user before proceeding:

> "The linter found <N> error(s) in existing issues. These must be
> resolved before proceeding."

List each error with its category, message, and hint.

Ask the user: "Fix these now before continuing, or proceed with the
issues and address them in the affected issues?"

If the user chooses to fix now: do not proceed with the issues. Help
the user correct the affected issues, re-run the linter, and confirm clean
before proceeding.

### Step 3 — Orientation

Report a brief orientation summary:

- Epic title, objective, and scope
- Relevant architectural constraints from ArchitectureSpec
- Current highest issue ID (next will be IS-NNN+1)
- Any open questions noted in the epic's Notes section

### Step 4 — Quiz

Analyze the epic and draft vertical slices. Each issue must be a thin
vertical slice that cuts through ALL relevant integration layers end-to-end.

A slice is horizontal (wrong) if it only touches one layer (e.g., "add
database migration"). Split or reframe horizontal slices as end-to-end
behaviour.

Present the proposed issues as a numbered list. For each slice show:

- **ID**: IS-NNN (proposed)
- **Title**: short descriptive name using domain vocabulary
- **Type**: AFK or HITL
- **Blocked by**: which other proposed issues (if any)
- **Accepts**: which epic acceptance criteria this addresses

Then ask:

1. Granularity — too coarse or too fine?
2. Dependencies — are the blocking relationships correct?
3. Coverage — does every acceptance criterion have at least one issue?
4. HITL/AFK — are the assignments correct?
5. Scope — should any slices be merged or split?

Iterate until the user explicitly approves the issues. Do not write any
files before approval.

### Step 5 — Instruction

After the user approves the issues, present a brief instruction for each
issue. For each issue show:

- **ID**: IS-NNN
- **Title**: short descriptive name
- **Type**: AFK or HITL
- **What**: one-sentence description of end-to-end behaviour
- **Accepts**: which epic acceptance criteria this addresses
- **Blocked by**: which other issues (or "None")

Then ask: "Ready to write these <N> issues? Reply 'write' to proceed."

Do not write any files until the user explicitly confirms.

### Step 6 — Write

Write each issue file in dependency order (blockers first, so that
`blocked_by` references real IS-NNN identifiers):

- `tasks/epics/EP-NNN/IS-NNN/IS-NNN.md`
- `tasks/epics/EP-NNN/IS-NNN/IS-NNN.json`

For each issue, write the markdown file with the full front matter and body,
then write the parallel JSON file with front matter fields only.

After writing each file, verify the write by reading it back. Report each
written file to the user as it completes.

After all issue files are written, update the parent epic file's front matter
with the issue list:

```yaml
issues:
  - IS-NNN
  - IS-NNN
```

Also update the `updated` date. Do not modify any other part of the epic file.

Verify the update by reading back the front matter.

### Step 7 — Validate

Validate each issue's JSON file against the schema. Report any validation
errors.

If validation fails, show the errors to the user and suggest fixes. Do not
modify the JSON without explicit user approval. After user confirms, apply
the fix and re-validate.

### Step 8 — Handoff

Summarize the issues created and suggest next steps:

```
issues complete for EP-NNN: <epic title>
Issues created:
  IS-NNN  <title>  [AFK]
  IS-NNN  <title>  [HITL]
  ...
Total: X issues (Y AFK, Z HITL)
Next steps:
  - Run /skill:blueprint issues EP-NNN for other epics that are ready
  - Pick up any AFK issue and begin implementation
```

Do not automatically invoke any other skill or open any session.

---

## Validation Rules

Enforce these rules when writing and validating issues:

1. **ID sequencing**: Issue IDs are sequential and project-global. Never
   restart from IS-001 per epic. Always continue from the highest existing
   IS-NNN.
2. **Dependency consistency**: Every `blocked_by` reference must point to a
   real IS-NNN file that exists in the same epic folder.
3. **Epic coverage**: Every epic acceptance criterion must be addressed by
   at least one issue. Flag any criterion that has no covering issue.
4. **Epic scope**: No issue objective may implement a GoalSpec non-goal.
5. **File naming**: Issue files must follow the pattern `IS-NNN.md` and
   `IS-NNN.json` inside the `IS-NNN/` directory.
6. **HITL/AFK**: Prefer AFK. Only mark HITL when human judgment is genuinely
   required.

## Output

After the interview is complete and the JSON artifact has been written via
`write_section`, the Markdown file must be regenerated from the JSON to
ensure zero drift between formats.


 ```
tool: generate_artifact_markdown
args:
  artifactType: <type>
  jsonPath: artifacts/<Type>.json
 ```

This overwrites the Markdown file with content derived from the JSON.
The JSON is the single source of truth; the Markdown is derived.
