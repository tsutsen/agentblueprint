#!/usr/bin/env python3
"""
Graph Visualization Tool

Generates an interactive force-directed graph of glossary term relationships
and cross-specification references from artifact JSON files.

Uses graph_metrics.py as the primary data source for the unified graph,
then enriches it with glossary metadata for visualization.

Usage:
    python3 graph-visualize.py [artifacts-dir] [--port PORT] [--no-server]

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
import signal
from pathlib import Path
import re
import time

# Try to find the extension directory
SCRIPT_DIR = Path(__file__).parent
VISUALIZE_DIR = SCRIPT_DIR / "graph-visualize"
GRAPH_METRICS_SCRIPT = SCRIPT_DIR / "graph_metrics.py"


def debug(msg: str):
    """Print debug message to stderr."""
    print(f"[DEBUG] {msg}", file=sys.stderr, flush=True)


def run_graph_metrics(artifacts_dir: str) -> dict | None:
    """Run graph_metrics.py and return the JSON results."""
    if not GRAPH_METRICS_SCRIPT.exists():
        print(f"WARNING: graph_metrics.py not found at {GRAPH_METRICS_SCRIPT}", file=sys.stderr)
        return None

    debug(f"Running graph_metrics.py with artifacts={artifacts_dir}")
    try:
        result = subprocess.run(
            ["python3", str(GRAPH_METRICS_SCRIPT), "--artifacts", artifacts_dir, "--format", "json"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0 and result.returncode != 1:
            print(f"WARNING: graph_metrics.py failed (exit {result.returncode}): {result.stderr.strip()}", file=sys.stderr)
            return None

        output = result.stdout.strip()
        if not output:
            print("WARNING: graph_metrics.py produced no output", file=sys.stderr)
            return None

        data = json.loads(output)
        debug(f"graph_metrics.py returned: {data.get('graph_stats', {}).get('nodes', 0)} nodes, {data.get('graph_stats', {}).get('edges', 0)} edges")
        return data
    except subprocess.TimeoutExpired:
        print("WARNING: graph_metrics.py timed out", file=sys.stderr)
        return None
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

    debug(f"Loaded {len(term_map)} glossary terms")
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

    debug(f"Found glossary refs in {len(spec_term_refs)} specs")
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
    Build the visualization graph data from graph_metrics.py raw graph output + glossary metadata.
    Shows the FULL architecture graph, not just glossary terms.
    """
    debug(f"Step 1: Getting full graph from metrics...")

    # Run graph_metrics with --dump-graph to get raw node/edge data
    if not GRAPH_METRICS_SCRIPT.exists():
        print(f"ERROR: graph_metrics.py not found at {GRAPH_METRICS_SCRIPT}", file=sys.stderr)
        return None

    try:
        result = subprocess.run(
            ["python3", str(GRAPH_METRICS_SCRIPT), "--artifacts", artifacts_dir, "--dump-graph"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            print(f"WARNING: graph_metrics.py --dump-graph failed: {result.stderr.strip()}", file=sys.stderr)
            return None

        graph_data = json.loads(result.stdout)
        raw_nodes = graph_data.get("nodes", [])
        raw_edges = graph_data.get("edges", [])
        debug(f"Raw graph: {len(raw_nodes)} nodes, {len(raw_edges)} edges")
    except Exception as e:
        print(f"WARNING: Failed to dump graph: {e}", file=sys.stderr)
        return None

    debug(f"Step 2: Loading glossary metadata...")
    term_map, related_map = load_glossary(artifacts_dir)

    # Node type display names and categories
    TYPE_INFO = {
        "REQ": {"label": "Requirement", "cat": "req", "color": "#38bdf8"},
        "NFR": {"label": "Non-Functional Req", "cat": "req", "color": "#7dd3fc"},
        "CON": {"label": "Component", "cat": "con", "color": "#a78bfa"},
        "FN": {"label": "Function", "cat": "fn", "color": "#34d399"},
        "IS": {"label": "Integration Test", "cat": "test", "color": "#fb923c"},
        "TST": {"label": "Test", "cat": "test", "color": "#f87171"},
        "FN": {"label": "Function", "cat": "fn", "color": "#34d399"},
        "GL": {"label": "Glossary Term", "cat": "gl", "color": "#fbbf24"},
        "UJ": {"label": "User Journey", "cat": "design", "color": "#c084fc"},
        "US": {"label": "User Story", "cat": "design", "color": "#a78bfa"},
        "UXAC": {"label": "UX Acceptance Criteria", "cat": "design", "color": "#8b5cf6"},
        "DG": {"label": "Design Goal", "cat": "design", "color": "#60a5fa"},
        "SC": {"label": "Screen", "cat": "design", "color": "#38bdf8"},
        "Entity": {"label": "Entity", "cat": "data", "color": "#4ade80"},
        "Enum": {"label": "Enum", "cat": "data", "color": "#22d3ee"},
        "API": {"label": "API Endpoint", "cat": "api", "color": "#f472b6"},
        "EP": {"label": "Epic", "cat": "plan", "color": "#facc15"},
        "TASK": {"label": "Task", "cat": "plan", "color": "#f59e0b"},
        "ISSUE": {"label": "Issue", "cat": "plan", "color": "#ef4444"},
    }

    # Build enriched nodes
    nodes = []
    for node in raw_nodes:
        nid = node["id"]
        ntype = node["type"]
        info = TYPE_INFO.get(ntype, {"label": ntype, "cat": "other", "color": "#94a3b8"})

        # Enrich GL nodes with glossary metadata
        if ntype == "GL" and nid in term_map:
            tinfo = term_map[nid]
            nodes.append({
                "id": nid,
                "term": tinfo.get("term", nid),
                "definition": tinfo.get("definition", ""),
                "category": tinfo.get("category", "technical"),
                "type": ntype,
                "typeLabel": info["label"],
                "typeCat": info["cat"],
                "color": info["color"],
                "relatedCount": len(related_map.get(nid, [])),
                "label": tinfo.get("term", nid),
            })
        else:
            nodes.append({
                "id": nid,
                "term": node.get("label", nid),
                "definition": "",
                "category": info["cat"],
                "type": ntype,
                "typeLabel": info["label"],
                "typeCat": info["cat"],
                "color": info["color"],
                "relatedCount": 0,
                "label": node.get("label", nid),
            })

    # Build edges
    edges = []
    for edge in raw_edges:
        edges.append({
            "source": edge["source"],
            "target": edge["target"],
            "type": "architecture",
        })

    # Count by type
    type_counts = {}
    for node in nodes:
        t = node["type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    output = {
        "summary": {
            "totalNodes": len(nodes),
            "totalEdges": len(edges),
            "typeCounts": type_counts,
        },
        "nodes": nodes,
        "edges": edges,
    }

    debug(f"Built visualization graph: {len(nodes)} nodes, {len(edges)} edges")
    debug(f"Node types: {json.dumps(type_counts)}")
    return output


def write_graph_data(graph_data: dict) -> str:
    """Write graph-data.json and return the path."""
    output_path = VISUALIZE_DIR / "graph-data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(graph_data, f, indent=2, ensure_ascii=False)
    debug(f"Wrote graph data to {output_path}")
    return str(output_path)


def kill_port(port: int):
    """Kill any process running on the given port."""
    try:
        # Use lsof to find processes on the port
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        pids = result.stdout.strip().split('\n')
        pids = [p.strip() for p in pids if p.strip()]
        if pids:
            for pid in pids:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    debug(f"Killed process {pid} on port {port}")
                except ProcessLookupError:
                    pass  # Process already gone
            # Wait a moment for port to be released
            time.sleep(0.5)
            return True
    except FileNotFoundError:
        # lsof not available, try fuser
        try:
            subprocess.run(["fuser", "-k", f"{port}/tcp"], timeout=5)
            debug(f"Killed process on port {port} via fuser")
            time.sleep(0.5)
            return True
        except FileNotFoundError:
            pass  # Neither lsof nor fuser available
    return False


def serve_graph(artifacts_dir: str, port: int, no_server: bool = False, open_browser: bool = False) -> bool:
    """Generate graph data and optionally serve the visualization."""
    print(f"Building glossary graph from {artifacts_dir}...", file=sys.stderr, flush=True)

    graph_data = build_graph_data(artifacts_dir)
    if graph_data is None:
        print("ERROR: Failed to build glossary graph.", file=sys.stderr)
        return False

    output_path = write_graph_data(graph_data)
    summary = graph_data["summary"]

    print(f"\nGraph data written to: {output_path}", file=sys.stderr, flush=True)
    print(f"  {summary['totalNodes']} nodes, {summary['totalEdges']} edges", file=sys.stderr, flush=True)
    print(f"  Types: {json.dumps(summary['typeCounts'])}", file=sys.stderr, flush=True)

    if no_server:
        return True

    # Kill any existing process on the port
    if not no_server:
        debug(f"Checking port {port}...")
        kill_port(port)

    # Start server in a detached subprocess so the main process can exit
    def start_server():
        debug(f"Starting HTTP server on port {port}...")
        os.chdir(str(VISUALIZE_DIR))

        class QuietHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(VISUALIZE_DIR), **kwargs)

            def log_message(self, format, *args):
                pass

        try:
            httpd = socketserver.TCPServer(("", port), QuietHandler)
            debug(f"Server listening on port {port}")
            httpd.serve_forever()
        except OSError as e:
            print(f"WARNING: Could not start server on port {port}: {e}", file=sys.stderr)

    # Start server as a background process
    server_proc = subprocess.Popen(
        [sys.executable, "-c", """
import http.server, socketserver, os, sys
os.chdir(sys.argv[1])
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=sys.argv[1], **k)
    def log_message(self, *a): pass
socketserver.TCPServer(("", int(sys.argv[2])), H).serve_forever()
""", str(VISUALIZE_DIR), str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # Detach from parent process
    )

    # Wait a moment for server to start
    time.sleep(0.5)

    # Verify server is running
    import urllib.request
    try:
        urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
        debug("Server verified running")
    except Exception as e:
        print(f"WARNING: Server may not have started: {e}", file=sys.stderr)

    print(f"\n✓ Graph visualization ready!", file=sys.stderr, flush=True)
    print(f"  Open: http://localhost:{port}", file=sys.stderr, flush=True)
    print(f"  Server running in background (PID: {server_proc.pid})", file=sys.stderr, flush=True)

    # Open browser if requested
    if open_browser:
        import webbrowser
        url = f"http://localhost:{port}"
        try:
            webbrowser.open(url)
            debug(f"Opened {url} in browser")
        except Exception as e:
            print(f"WARNING: Could not open browser: {e}", file=sys.stderr)

    # Exit immediately - server keeps running in background
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Graph Visualization Tool")
    parser.add_argument("artifacts_dir", nargs="?", default="artifacts",
                        help="Path to artifacts directory (default: artifacts)")
    parser.add_argument("--port", type=int, default=3001,
                        help="HTTP server port (default: 3001)")
    parser.add_argument("--no-server", action="store_true",
                        help="Only generate graph-data.json, don't start server")
    parser.add_argument("--no-open", action="store_true",
                        help="Don't open browser (enabled by default)")
    args = parser.parse_args()

    artifacts_dir = os.path.abspath(args.artifacts_dir)
    if not os.path.isdir(artifacts_dir):
        print(f"ERROR: Artifacts directory not found: {artifacts_dir}", file=sys.stderr)
        sys.exit(1)

    success = serve_graph(artifacts_dir, args.port, args.no_server, not args.no_open)
    sys.exit(0 if success else 1)
