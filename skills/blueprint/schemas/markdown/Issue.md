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

Each issue has two files: `IS-NNN.md` (human-readable) and `IS-NNN.json` (machine-readable).

### Front Matter (YAML in `.md`, fields only in `.json`)

```yaml
---
artifact: Issue
id: IS-<NNN>           # IS-NNN (3-digit zero-padded)
title: <short title>   # action-oriented
type: AFK | HITL       # Prefer AFK; HITL only when human judgment is required
status: not_started | in_progress | needs_review | complete
epic: EP-<NNN>         # 3-digit zero-padded
blocked_by: [IS-NNN]   # or []
milestone: M1 | M2 | ...
titleGlossaryRefs: [GL-NNN]  # [] if none
inScope:
  - description: <scope item>
    glossaryRefs: [GL-NNN]
outOfScope:
  - description: <excluded item>
    glossaryRefs: [GL-NNN]
acceptanceCriteria:
  - description: <verifiable criterion>
    glossaryRefs: [GL-NNN]
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

### Body (Markdown in `.md` only)

```markdown
# IS-NNN: <title>

## What to build
<End-to-end behaviour description. Do not describe layer-by-layer implementation.>

## Acceptance criteria
- [ ] <Independently verifiable criterion>
- [ ] <Independently verifiable criterion>

## Blocked by
<IS-NNN reference, or "None — can start immediately.">
```

**Rules:**
- **What to build**: Describe end-to-end behaviour. Each slice must deliver a narrow but complete path through every relevant layer.
- **Acceptance criteria**: Each must be independently verifiable and binary (pass/fail) where possible.
- **Blocked by**: Must reference real IS-NNN identifiers in the same epic folder, or state "None — can start immediately."

---

## Process Override

This artifact uses a custom flow instead of the standard blueprint flow.

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

---


