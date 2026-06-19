#!/usr/bin/env python3
"""
Glossary Graph Visualization Tool

Generates an interactive force-directed graph of glossary term relationships
and cross-specification references from artifact JSON files.

Uses graph_metrics.py as the primary data source for the unified graph,
then enriches it with glossary metadata for visualization.

Usage:
    python3 glossary_graph.py [artifacts-dir] [--port PORT] [--no-server]

Arguments:
    artifacts-dir    Path to artifacts directory (default: artifacts/)
    --port PORT      HTTP server port (default: 3001)
    --no-server      Only generate graph-data.json, don't start server
    --help           Show this help message
"""

import sys
import os
import json
import subprocess
import threading
import http.server
import socketserver
import argparse
from pathlib import Path
import re

# Try to find the extension directory
SCRIPT_DIR = Path(__file__).parent
VISUALIZE_DIR = SCRIPT_DIR / "graph-visualize"
GRAPH_METRICS_SCRIPT = SCRIPT_DIR / "graph_metrics.py"


def run_graph_metrics(artifacts_dir: str) -> dict | None:
    """Run graph_metrics.py and return the JSON results."""
    if not GRAPH_METRICS_SCRIPT.exists():
        print(f"WARNING: graph_metrics.py not found at {GRAPH_METRICS_SCRIPT}", file=sys.stderr)
        return None

    try:
        result = subprocess.run(
            ["python3", str(GRAPH_METRICS_SCRIPT), "--artifacts", artifacts_dir, "--format", "json"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0 and result.returncode != 1:
            print(f"WARNING: graph_metrics.py failed: {result.stderr.strip()}", file=sys.stderr)
            return None

        output = result.stdout.strip()
        if not output:
            print("WARNING: graph_metrics.py produced no output", file=sys.stderr)
            return None

        return json.loads(output)
    except subprocess.TimeoutExpired:
        print("WARNING: graph_metrics.py timed out", file=sys.stderr)
        return False
    except json.JSONDecodeError as e:
        print(f"WARNING: graph_metrics.py output is not valid JSON: {e}", file=sys.stderr)
        return None
    except FileNotFoundError:
        print("WARNING: python3 not found", file=sys.stderr)
        return None


def load_glossary(artifacts_dir: str) -> tuple[dict, dict]:
    """Load Glossary.json and return (term_map, related_terms_map)."""
    glossary_path = os.path.join(artifacts_dir, "Glossary.json")
    if not os.path.exists(glossary_path):
        print(f"WARNING: Glossary.json not found at {glossary_path}", file=sys.stderr)
        return {}, {}

    with open(glossary_path) as f:
        data = json.load(f)

    term_map = {}
    related_map = {}
    for t in data.get("terms", []):
        tid = t.get("id", "")
        term_map[tid] = t
        related_map[tid] = t.get("relatedTerms", [])

    return term_map, related_map


def collect_spec_refs(artifacts_dir: str) -> dict:
    """
    Scan all spec JSON files to find which specs reference which GL IDs.
    Returns { specName: Set(GL_IDs) }.
    """
    spec_files = [
        "GoalSpec.json", "DesignSpec.json", "ApiSpec.json",
        "ArchitectureSpec.json", "DataSpec.json", "TestSpec.json",
    ]
    spec_term_refs = {}

    for spec_file in spec_files:
        spec_path = os.path.join(artifacts_dir, spec_file)
        if not os.path.exists(spec_path):
            continue

        with open(spec_path) as f:
            data = json.load(f)

        refs = set()
        _extract_glossary_refs(data, refs)
        if refs:
            spec_term_refs[spec_file.replace(".json", "")] = refs

    return spec_term_refs


def _extract_glossary_refs(obj, refs: set):
    """Recursively find all glossaryRefs in a JSON object."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if "glossary" in key.lower() and isinstance(value, (list, str)):
                if isinstance(value, str) and re.match(r"^GL-\d+$", value):
                    refs.add(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str) and re.match(r"^GL-\d+$", item):
                            refs.add(item)
            _extract_glossary_refs(value, refs)
    elif isinstance(obj, list):
        for item in obj:
            _extract_glossary_refs(item, refs)


def build_graph_data(artifacts_dir: str) -> dict:
    """
    Build the visualization graph data from graph_metrics.py output + glossary metadata.

    This is the main function that:
    1. Runs graph_metrics.py to get the unified graph
    2. Loads Glossary.json for term metadata
    3. Scans specs for GL references
    4. Builds the D3-compatible graph-data.json format
    """
    # Step 1: Get graph from metrics
    metrics = run_graph_metrics(artifacts_dir)
    if not metrics:
        print("ERROR: Could not get graph data from graph_metrics.py", file=sys.stderr)
        return None

    graph_stats = metrics.get("graph_stats", {})
    node_types = graph_stats.get("node_types", {})

    # Count nodes by type
    gl_count = node_types.get("GL", 0)
    total_nodes = graph_stats.get("nodes", 0)
    total_edges = graph_stats.get("edges", 0)

    print(f"Graph from metrics: {total_nodes} nodes, {total_edges} edges, {gl_count} GL terms")

    # Step 2: Load glossary metadata
    term_map, related_map = load_glossary(artifacts_dir)
    print(f"Glossary loaded: {len(term_map)} terms")

    # Step 3: Collect spec references
    spec_term_refs = collect_spec_refs(artifacts_dir)
    print(f"Spec references found in {len(spec_term_refs)} specs")

    # Step 4: Build termSpecRefs (GL ID -> Set of spec names)
    term_spec_refs = {}
    for spec_name, gl_ids in spec_term_refs.items():
        for gl_id in gl_ids:
            if gl_id not in term_spec_refs:
                term_spec_refs[gl_id] = set()
            term_spec_refs[gl_id].add(spec_name)

    # Step 5: Build nodes
    nodes = []

    # Glossary term nodes
    for tid, tinfo in term_map.items():
        specs = term_spec_refs.get(tid, set())
        nodes.append({
            "id": tid,
            "term": tinfo.get("term", tid),
            "definition": tinfo.get("definition", ""),
            "category": tinfo.get("category", "technical"),
            "relatedCount": len(related_map.get(tid, [])),
            "specRefCount": len(specs),
            "specs": sorted(specs),
        })

    # Spec nodes (only those that reference glossary terms)
    spec_nodes = []
    for spec_name, gl_ids in spec_term_refs.items():
        spec_nodes.append({
            "id": f"SPEc:{spec_name}",
            "term": spec_name,
            "definition": f"Specification: {spec_name}.json",
            "category": "spec",
            "relatedCount": len(gl_ids),
            "specRefCount": 0,
            "specs": [],
        })

    # Step 6: Build edges
    edges = []
    edge_set = set()

    # relatedTerms edges (between glossary terms)
    for tid, related in related_map.items():
        for related_id in related:
            key = tuple(sorted([tid, related_id]))
            edge_key = f"{key[0]}→{key[1]}"
            if edge_key not in edge_set:
                edge_set.add(edge_key)
                edges.append({
                    "source": tid,
                    "target": related_id,
                    "type": "relatedTerms",
                })

    # specRef edges (spec -> term)
    for sn in spec_nodes:
        spec_id = sn["id"]
        spec_name = sn["term"]
        for gl_id in spec_term_refs.get(spec_name, set()):
            edge_key = f"{spec_id}→{gl_id}"
            if edge_key not in edge_set:
                edge_set.add(edge_key)
                edges.append({
                    "source": spec_id,
                    "target": gl_id,
                    "type": "specRef",
                })

    # crossSpec edges (specs that share glossary references)
    spec_names = sorted(spec_term_refs.keys())
    for i in range(len(spec_names)):
        for j in range(i + 1, len(spec_names)):
            set_a = spec_term_refs[spec_names[i]]
            set_b = spec_term_refs[spec_names[j]]
            shared = sorted(set_a & set_b)
            if shared:
                edges.append({
                    "source": f"SPEc:{spec_names[i]}",
                    "target": f"SPEc:{spec_names[j]}",
                    "type": "crossSpec",
                    "sharedTerms": shared,
                    "sharedCount": len(shared),
                })

    # Build categories summary
    categories = {}
    for node in nodes:
        cat = node["category"]
        categories[cat] = categories.get(cat, 0) + 1

    # Step 7: Output
    output = {
        "summary": {
            "totalTerms": len(term_map),
            "totalEdges": len(edges),
            "totalSpecs": len(spec_term_refs),
            "categories": categories,
        },
        "nodes": nodes + spec_nodes,
        "edges": edges,
    }

    return output


def write_graph_data(graph_data: dict) -> str:
    """Write graph-data.json and return the path."""
    output_path = VISUALIZE_DIR / "graph-data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(graph_data, f, indent=2, ensure_ascii=False)
    return str(output_path)


def serve_graph(artifacts_dir: str, port: int, no_server: bool = False) -> bool:
    """Generate graph data and optionally serve the visualization."""
    # Step 1: Build graph data from graph_metrics.py output
    print(f"Building glossary graph from {artifacts_dir}...")
    graph_data = build_graph_data(artifacts_dir)

    if graph_data is None:
        print("ERROR: Failed to build glossary graph.", file=sys.stderr)
        return False

    # Step 2: Write graph-data.json
    output_path = write_graph_data(graph_data)
    print(f"\nGraph data written to: {output_path}")

    # Show summary
    summary = graph_data["summary"]
    print(f"  {summary['totalTerms']} terms, {summary['totalEdges']} edges, {summary['totalSpecs']} specs")
    print(f"  Categories: {json.dumps(summary['categories'])}")

    if no_server:
        return True

    # Step 3: Serve the visualization
    def run_server():
        os.chdir(str(VISUALIZE_DIR))

        class QuietHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(VISUALIZE_DIR), **kwargs)

            def log_message(self, format, *args):
                pass  # Suppress request logs

        with socketserver.TCPServer(("", port), QuietHandler) as httpd:
            httpd.serve_forever()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    url = f"http://localhost:{port}"
    print(f"\n✓ Glossary Graph visualization ready!")
    print(f"  Open: {url}")
    print(f"  (Server running in background)")

    # Keep alive
    try:
        while True:
            import time
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        print("\nServer stopped.")

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Glossary Graph Visualization Tool")
    parser.add_argument("artifacts_dir", nargs="?", default="artifacts",
                        help="Path to artifacts directory (default: artifacts)")
    parser.add_argument("--port", type=int, default=3001,
                        help="HTTP server port (default: 3001)")
    parser.add_argument("--no-server", action="store_true",
                        help="Only generate graph-data.json, don't start server")
    args = parser.parse_args()

    artifacts_dir = os.path.abspath(args.artifacts_dir)
    if not os.path.isdir(artifacts_dir):
        print(f"ERROR: Artifacts directory not found: {artifacts_dir}", file=sys.stderr)
        sys.exit(1)

    success = serve_graph(artifacts_dir, args.port, args.no_server)
    sys.exit(0 if success else 1)
