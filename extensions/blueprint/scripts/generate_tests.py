#!/usr/bin/env python3
"""
Generate tests for all ApiSpec functions that don't have tests yet.

Usage:
    python3 scripts/generate_tests.py [--goal GoalSpec.json] [--api ApiSpec.json] [--test TestSpec.json]

This script:
1. Reads artifacts/ApiSpec.json for function definitions
2. Reads artifacts/GoalSpec.json (optional) for REQ/NFR mapping
3. Reads artifacts/TestSpec.json for existing tests
4. Generates tests for functions without tests
5. Saves updated tests to artifacts/TestSpec.json

Test ID format: TST-{functionName}-{NNN} (e.g. TST-createSession-001)
fnRef format: FN-{camelCase} (e.g. FN-createSession)

Requirements mapping:
  Tests are generated with reqRefs populated from GoalSpec if:
  - The ApiSpec function has a 'reqRefs' field (added during ApiSpec creation), OR
  - A manual mapping file is provided at artifacts/req_fn_mapping.json
  Otherwise reqRefs are left empty and must be filled in manually.
"""

import json
import sys
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
API_SPEC_PATH = PROJECT_ROOT / "artifacts" / "ApiSpec.json"
GOAL_SPEC_PATH = PROJECT_ROOT / "artifacts" / "GoalSpec.json"
TEST_SPEC_PATH = PROJECT_ROOT / "artifacts" / "TestSpec.json"
REQ_MAPPING_PATH = PROJECT_ROOT / "artifacts" / "req_fn_mapping.json"


def load_json(path):
    with open(path) as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def get_existing_fn_refs(tests):
    """Get set of fnRef values that already have tests."""
    return {t["fnRef"] for t in tests}


def get_input_value(param_name, param_type="string"):
    """Generate a concrete example value for a parameter."""
    name_lower = param_name.lower()
    # Type-aware defaults
    if param_type in ("integer", "int"):
        return 0
    if param_type in ("boolean", "bool"):
        return False
    if param_type in ("number", "float"):
        return 0.0
    # Array types (e.g. 'string[]', 'User[]') — check before entity types
    if param_type and param_type.endswith("[]"):
        inner = param_type[:-2]
        if inner in ("integer", "int", "number", "float"):
            return [0]
        if inner in ("boolean", "bool"):
            return [False]
        return [f"{inner.lower()}-001"]
    # Entity types (PascalCase) — generate a reference ID
    if param_type and param_type[0].isupper():
        return f"{param_type.lower()}-001"
    # Name-based defaults
    if "session" in name_lower:
        return "session-123"
    if "report" in name_lower:
        return "report-123"
    if "source" in name_lower:
        return "source-123"
    if "query" in name_lower:
        return "query-123"
    if "brief" in name_lower:
        return "brief-123"
    if "doi" in name_lower:
        return "10.1234/test"
    if "text" in name_lower:
        return "test text"
    if "field" in name_lower:
        return "hypothesis"
    if "format" in name_lower:
        return "pdf"
    if "offset" in name_lower:
        return 0
    if "limit" in name_lower or "count" in name_lower:
        return 10
    if "sources" in name_lower:
        return ["source-123"]
    if "ids" in name_lower:
        return ["id-001"]
    return "test-value"


def get_req_refs_for_function(fn, goal_spec=None, req_mapping=None):
    """Determine which REQ-IDs this function's tests should reference.

    Priority:
    1. fn['reqRefs'] if present in ApiSpec (explicit mapping)
    2. req_mapping[fn['id']] if a mapping file exists
    3. Empty list (must be filled manually)
    """
    if "reqRefs" in fn and fn["reqRefs"]:
        return fn["reqRefs"]
    if req_mapping and fn["id"] in req_mapping:
        return req_mapping[fn["id"]]
    if goal_spec:
        # Fallback: return all REQ-IDs as TBD — user must refine
        return [r["id"] for r in goal_spec.get("functionalRequirements", [])]
    return []


def generate_test_for_function(fn, test_num, base_id, goal_spec=None, req_mapping=None):
    """Generate tests for a single API function."""
    tests = []
    fn_name = fn["name"]
    fn_id = fn["id"]

    # Build input from function inputs using type-aware defaults
    input_data = {}
    if "inputs" in fn and fn["inputs"]:
        for inp in fn["inputs"]:
            param_type = inp.get("type", "string")
            input_data[inp["name"]] = get_input_value(inp["name"], param_type)

    # Determine REQ refs for traceability
    req_refs = get_req_refs_for_function(fn, goal_spec, req_mapping)

    # Generate happy-path test
    happy_test = {
        "id": f"TST-{fn_name}-{test_num:03d}",
        "fnRef": fn_id,
        "category": "happy-path",
        "description": f"Call {fn_name} with valid input",
        "input": input_data if input_data else {},
        "expectedOutput": fn.get("output", {}).get("type", "void") if fn.get("output") else "void",
        "contractClause": fn.get("description", f"Call {fn_name}"),
        "reqRefs": req_refs if req_refs else None,
    }
    tests.append(happy_test)
    test_num += 1

    # Generate error-path tests for functions with error codes
    if "errors" in fn and fn["errors"]:
        for error in fn["errors"]:
            error_test = {
                "id": f"TST-{fn_name}-{test_num:03d}",
                "fnRef": fn_id,
                "category": "error-path",
                "description": f"Call {fn_name} when {error['condition'].lower()}",
                "input": input_data if input_data else {},
                "errorCode": error["code"],
                "expectedError": {
                    "code": error["code"],
                    "returnType": error.get("returnType", "Error"),
                    "messageContains": error["condition"].lower()[:30],
                },
                "contractClause": f"Returns {error['code']} when {error['condition'].lower()}",
            }
            tests.append(error_test)
            test_num += 1

    # Generate edge-case test for functions with inputs
    if input_data and len(input_data) > 0:
        edge_test = {
            "id": f"TST-{fn_name}-{test_num:03d}",
            "fnRef": fn_id,
            "category": "edge-case",
            "description": f"Call {fn_name} with empty or minimal input",
            "input": {k: "" if isinstance(v, str) else (0 if isinstance(v, int) else []) for k, v in input_data.items()},
            "expectedOutput": "void",  # TBD — user must verify against actual output type
            "contractClause": f"Handles empty input gracefully",
            "reqRefs": req_refs if req_refs else None,
        }
        tests.append(edge_test)
        test_num += 1

    return tests, test_num


def generate_out_of_scope(fn):
    """Generate outOfScope declaration for a function.

    Returns a generic template — the user must refine per-project.
    """
    fn_name = fn["name"]
    fn_input = fn.get("inputs", [])
    has_inputs = len(fn_input) > 0
    has_errors = bool(fn.get("errors"))

    out_of_scope = []

    if has_inputs:
        out_of_scope.append(
            f"Input validation edge cases not covered by specific tests "
            f"(e.g., types, lengths, formats for {', '.join(p['name'] for p in fn_input[:3])})"
        )
    if has_errors:
        out_of_scope.append(
            "Error handling when errors interact with each other or with concurrent operations"
        )
    out_of_scope.append(
        "Performance, security, and concurrency aspects — these require separate non-functional tests"
    )
    return out_of_scope


def main():
    # Load ApiSpec (required)
    print("Loading ApiSpec...")
    api = load_json(API_SPEC_PATH)
    print(f"  Found {len(api['functions'])} functions")

    # Load GoalSpec (optional — for REQ/NFR traceability)
    goal_spec = None
    req_mapping = None
    if GOAL_SPEC_PATH.exists():
        print("Loading GoalSpec...")
        goal_spec = load_json(GOAL_SPEC_PATH)
        print(f"  Found {len(goal_spec.get('functionalRequirements', []))} REQ, "
              f"{len(goal_spec.get('nonFunctionalRequirements', []))} NFR")
    if REQ_MAPPING_PATH.exists():
        print("Loading REQ→Fn mapping...")
        req_mapping = load_json(REQ_MAPPING_PATH)

    print("Loading TestSpec...")
    ts = load_json(TEST_SPEC_PATH)
    existing_tests = ts.get("tests", [])
    existing_fn_refs = get_existing_fn_refs(existing_tests)
    print(f"  Found {len(existing_tests)} existing tests")
    print(f"  Functions with tests: {len(existing_fn_refs)}")

    # Find functions without tests
    all_fn_ids = {fn["id"] for fn in api["functions"]}
    missing_fn_ids = all_fn_ids - existing_fn_refs
    print(f"  Functions without tests: {len(missing_fn_ids)}")

    if not missing_fn_ids:
        print("All functions already have tests. Nothing to generate.")
        return

    # Generate tests for missing functions
    new_tests = []
    test_num = 1
    functions_without_tests = [fn for fn in api["functions"] if fn["id"] in missing_fn_ids]

    for fn in functions_without_tests:
        fn_name = fn["name"]
        tests, test_num = generate_test_for_function(fn, test_num, fn_name,
                                                     goal_spec, req_mapping)
        new_tests.extend(tests)
        print(f"  Generated {len(tests)} tests for {fn_name}")

    # Add new tests to existing tests
    ts["tests"].extend(new_tests)

    # Add function coverage entries for new functions
    for fn in functions_without_tests:
        fn_name = fn["name"]
        fn_tests = [t for t in new_tests if t["fnRef"] == fn["id"]]
        happy_count = len([t for t in fn_tests if t["category"] == "happy-path"])
        edge_count = len([t for t in fn_tests if t["category"] == "edge-case"])
        error_count = len([t for t in fn_tests if t["category"] == "error-path"])

        fc = {
            "fnRef": fn["id"],
            "happyPathCount": happy_count,
            "edgeCaseCount": edge_count,
            "errorPathCount": error_count,
            "outOfScope": generate_out_of_scope(fn),
        }
        ts["functionCoverage"].append(fc)

    # Save updated TestSpec
    save_json(TEST_SPEC_PATH, ts)
    print(f"\n✓ Saved {len(new_tests)} new tests to {TEST_SPEC_PATH}")
    print(f"  Total tests: {len(ts['tests'])}")
    print(f"  Total function coverage entries: {len(ts['functionCoverage'])}")

    # Warn about reqRefs that need manual refinement
    tests_with_all_reqs = [t for t in new_tests
                           if t.get("reqRefs")
                           and goal_spec
                           and len(t["reqRefs"]) > len(goal_spec.get("functionalRequirements", []))]
    if tests_with_all_reqs:
        print(f"\n⚠ {len(tests_with_all_reqs)} test(s) have reqRefs set to ALL REQ-IDs.")
        print("  These are placeholders — refine each test's reqRefs to reference")
        print("  only the specific requirements it validates.")
        print("  Tip: Create artifacts/req_fn_mapping.json for automatic mapping.")


if __name__ == "__main__":
    main()
