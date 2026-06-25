---
name: TestSpec
type: schema
version: 3.0.0
---

## Test Spec

Defines what correct behaviour looks like for every API function. TestSpec
is produced before any implementation code is written. It becomes the source
of truth for test authorship and independent verification.

A TestSpec is NOT test code. It is a precise natural-language and structured
description of what each test must verify.

The TestSpec does NOT define:

* Implementation logic
* How a function produces its output — only what the output must be
* Test framework configuration — that is implementation

---

---

---

### Test Cases

All test cases for every API function. Tests are organized into three
categories per function: happy path, edge case, and error path.

#### Happy Path Tests

Cover the primary successful execution path.

Each test must have:

* **glossaryRefs** (array of GL-NNN): Domain concepts in the test's description and contractClause

#### Edge Case Tests

Cover boundary and unusual-but-valid inputs. At minimum:

* Empty / zero / null inputs where the type allows
* Boundary values (min, max, first, last element)
* Inputs that are valid type but semantically unusual

#### Error Path Tests

Cover every documented error condition from ApiSpec. Each error code on
every function must have at least one test.

Each error test must additionally have:

**Rule:** A function with documented error conditions that has no error path
tests is incomplete. This is an error, not a warning.

---

## Workflow

TestSpec is produced in three confirmation-gated stages. Do not advance
to the next stage without explicit user confirmation.

### Stage 1 — API surface review

Load `artifacts/ApiSpec.json`. Present the full function list to the user:

> "Here are all functions in the API surface. We will write tests for each.
> Please confirm this list is complete before we begin — changes after this
> point require revisiting tests."

Wait for explicit confirmation. If the user identifies missing functions,
stop and direct them to update ApiSpec first.

---

### Stage 2 — Contract definition

For each function, confirm the precise contract before writing any tests:

* Input types and valid ranges (from ApiSpec)
* Output type and shape (from ApiSpec)
* All documented error conditions (from ApiSpec)
* Any invariants not explicit in the signature

Present the contract to the user function by function. Confirm each before
moving to the next. Do not infer unstated behaviour.

---

### Stage 3 — Test case definition

For each confirmed function contract, produce test cases in three categories
(happy path, edge case, error path). See the **Test Cases** section above
for the full structure and rules.

#### REQ/NFR Traceability

Every test must be traceable back to at least one requirement:

1. **Happy-path tests** → must reference the REQ-IDs they validate via `reqRefs`.
   Cross-reference the GoalSpec's `functionalRequirements` to find which
   requirement each test exercises.

2. **Error-path tests** → typically do NOT need `reqRefs` (they verify
   error handling, not business requirements). Leave `reqRefs` as `null`.

3. **Edge-case tests** → may reference REQ-IDs if the edge case is
   explicitly called out in a requirement. Otherwise leave `reqRefs` as `null`.

4. **NFR linkage**: If a test validates a non-functional requirement
   (e.g., performance, security), add the NFR-ID to the test's `nfrRefs`
   array. NFRs are not directly testable via unit tests — they require
   separate load/security tests. The TestSpec should still document the
   NFR reference for traceability.

5. **SC linkage**: If a test validates a success criterion, add the
   SC-ID to the test's `scRefs` array.

#### Glossary Reference Validation

The linter checks that domain concepts in test descriptions and contract clauses
are linked to glossary terms. If a test's description or contractClause contains
a glossary term (e.g., "report", "query"), it must have the corresponding GL-NNN
in its `glossaryRefs` array. This ensures every domain concept used in tests is
explicitly defined in the glossary.

> "For each test, identify which REQ-IDs it validates. Add them to the
> `reqRefs` array. If a test doesn't validate a specific requirement,
> set `reqRefs` to null. Do not guess — refer to the GoalSpec."

After all tests are written, verify traceability:

* Every REQ-ID in GoalSpec should be covered by at least one test in at
  least one function's test block.
* Every test with `reqRefs` set must have those REQ-IDs exist in GoalSpec
  (the linter will check this).
* If a REQ has no covering test, flag it as a gap.

---

## Rules

**Rule 1: Trace to contract.**
Every test must reference which contract clause it verifies. If no clause
can be identified, the test should not exist.

**Rule 2: Concrete values only.**
Write `input: userId = "usr_48291"`, not `input: a valid userId`.
The verifier must be able to trace the input through the logic without ambiguity.

**Rule 3: Error paths are mandatory.**
Every documented error condition must have a test. No exceptions.

**Rule 4: No implementation detail.**
Tests specify *what* the output must be, not *how* the function produces it.

**Rule 5: No combinatorial explosion.**
Identify the minimal set: one happy path, each distinct edge case, each
distinct error condition. Prefer 4–8 tests per function over 20+.

**Rule 6: Out-of-scope declaration.**
Each function's test block must include an explicit list of behaviours the
tests do NOT verify. This prevents false failures during verification.

Each out-of-scope item is a structured object: `{description: string, glossaryRefs: GL-NNN[]}`.
If the description contains a glossary term, include it in `glossaryRefs`.

---

## Independent Verification Step

After the test spec is confirmed, a separate agent with a clean context
will verify it:

1. Read the TestSpec and DesignSpec independently, without access to ApiSpec
2. Describe in plain language what each test verifies
3. Compare that description to the ApiSpec contract
4. Flag any test whose described behaviour does not match the contract

The test spec must be written clearly enough that this verification can be
performed without any implementation context. Write for the verifier.

The verification prompt is:

> "Read the following test spec entry. Describe in plain language what
> this test verifies. Then state whether the described behaviour matches
> the contract: [paste contract]. If there is a mismatch, describe it."

---

## Confirmation Gate

Before this skill completes, present the full test spec to the user:

> "Here is the test specification. Please review each function's happy path,
> edge cases, and error paths. Confirm if these correctly capture the intended
> behaviour, or let me know what needs to change."

Do not proceed to implementation or handoff until confirmed.


