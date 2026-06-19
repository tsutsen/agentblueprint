#!/usr/bin/env python3
"""
graph_metrics.py — Architecture Graph Metrics

Builds a unified graph from all artifact JSON files and computes
10 architecture quality metrics: orphan detection, traceability,
blast radius, risk scores, component load, interface pressure,
test density, epic coherence, layer violations, and health index.

Usage:
    python graph_metrics.py --artifacts <path> [--report <path>] [--format json|text]
"""

import argparse
import json
import math
import os
import re
import sys
from collections import defaultdict, deque
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Node Type Registry
# ─────────────────────────────────────────────────────────────────────────────

def node_type(id_str: str) -> str:
    """Infer node type from ID prefix."""
    if re.match(r'^REQ-\d+$', id_str):
        return "REQ"
    if re.match(r'^NFR-\d+$', id_str):
        return "NFR"
    if re.match(r'^SC-\d+$', id_str):
        return "SC"
    if re.match(r'^US-\d+$', id_str):
        return "US"
    if re.match(r'^GL-\d+$', id_str):
        return "GL"
    if re.match(r'^DG-\d+$', id_str):
        return "DG"
    if re.match(r'^UXAC-\d+$', id_str):
        return "UXAC"
    if re.match(r'^VDR-\d+$', id_str):
        return "VDR"
    if re.match(r'^AR-\d+$', id_str):
        return "AR"
    if re.match(r'^UJ-\d+$', id_str):
        return "UJ"
    if re.match(r'^CON-\d+$', id_str):
        return "CON"
    if re.match(r'^FN-', id_str):
        return "FN"
    if re.match(r'^TST-', id_str):
        return "TST"
    if re.match(r'^EP-\d+$', id_str):
        return "EP"
    if re.match(r'^IS-\d+$', id_str):
        return "IS"
    if re.match(r'^M\d+$', id_str):
        return "M"
    return None  # Not a known prefix — could be Entity/Enum (PascalCase)


def _load_entity_enum_lists(dataspec_path: str):
    """Load entity and enum name lists from dataspec.json."""
    entities = set()
    enums = set()
    if not os.path.exists(dataspec_path):
        return entities, enums
    try:
        d = json.load(open(dataspec_path))
        for e in d.get("entities", []):
            if isinstance(e, dict) and "name" in e:
                entities.add(e["name"])
        for e in d.get("enums", []):
            if isinstance(e, dict) and "name" in e:
                enums.add(e["name"])
    except Exception:
        pass
    return entities, enums


_NODE_TYPE_CACHE = {}
_ENTITY_ENUMS = None


def resolve_node_type(id_str: str, dataspec_path: str = None) -> str:
    """Resolve node type, handling Entity/Enum for PascalCase."""
    global _NODE_TYPE_CACHE, _ENTITY_ENUMS
    if id_str in _NODE_TYPE_CACHE:
        return _NODE_TYPE_CACHE[id_str]
    t = node_type(id_str)
    if t:
        _NODE_TYPE_CACHE[id_str] = t
        return t
    # PascalCase: check dataspec for Entity vs Enum
    if dataspec_path and not _ENTITY_ENUMS:
        _ENTITY_ENUMS = _load_entity_enum_lists(dataspec_path)
    if _ENTITY_ENUMS:
        if id_str in _ENTITY_ENUMS[0]:
            _NODE_TYPE_CACHE[id_str] = "Entity"
            return "Entity"
        if id_str in _ENTITY_ENUMS[1]:
            _NODE_TYPE_CACHE[id_str] = "Enum"
            return "Enum"
    # Default for unknown PascalCase
    if id_str and id_str[0].isupper() and not '-' in id_str:
        _NODE_TYPE_CACHE[id_str] = "Entity"
        return "Entity"
    _NODE_TYPE_CACHE[id_str] = "Unknown"
    return "Unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Graph Construction
# ─────────────────────────────────────────────────────────────────────────────


class Graph:
    def __init__(self):
        self.nodes = {}  # id -> {type, label, source_artifact}
        self.edges = []  # list of (from_id, to_id)
        self.adj = defaultdict(set)  # outgoing
        self.radj = defaultdict(set)  # incoming

    def add_node(self, node_id: str, ntype: str, label: str, source: str):
        if node_id not in self.nodes:
            self.nodes[node_id] = {"type": ntype, "label": label, "source_artifact": source}
        else:
            # Update label if more descriptive
            if label and self.nodes[node_id].get("label") != label:
                self.nodes[node_id]["label"] = label
        _NODE_TYPE_CACHE[node_id] = ntype

    def add_edge(self, from_id: str, to_id: str):
        self.edges.append((from_id, to_id))
        self.adj[from_id].add(to_id)
        self.radj[to_id].add(from_id)

    def bfs_reachable(self, start: str, direction: str = "out", max_depth: int = None) -> set:
        """BFS from start, following edges. direction: 'out' or 'in'."""
        visited = set()
        if start not in self.nodes:
            return visited
        queue = deque([(start, 0)])
        visited.add(start)
        while queue:
            node, depth = queue.popleft()
            if max_depth and depth >= max_depth:
                continue
            if direction == "out":
                neighbors = self.adj.get(node, set())
            else:
                neighbors = self.radj.get(node, set())
            for nb in neighbors:
                if nb not in visited:
                    visited.add(nb)
                    queue.append((nb, depth + 1))
        return visited

    def reachable_by_type(self, start: str, target_type: str, direction: str = "out",
                          max_depth: int = None) -> set:
        """BFS from start, return nodes of target_type reachable."""
        reachable = self.bfs_reachable(start, direction, max_depth)
        return {n for n in reachable if n in self.nodes and self.nodes[n]["type"] == target_type}

    def degree(self, node_id: str, direction: str = "total") -> int:
        if direction == "out":
            return len(self.adj.get(node_id, set()))
        elif direction == "in":
            return len(self.radj.get(node_id, set()))
        return len(self.adj.get(node_id, set())) + len(self.radj.get(node_id, set()))

    def degree_centrality(self, node_id: str) -> float:
        n = len(self.nodes)
        if n <= 1:
            return 0.0
        return self.degree(node_id) / (n - 1)

    def nodes_of_type(self, ntype: str) -> list:
        return [nid for nid, n in self.nodes.items() if n["type"] == ntype]


def _collect_id_refs(value, known_ids: set):
    """Recursively collect any string values that match known ID prefixes."""
    if isinstance(value, str):
        t = node_type(value)
        if t:
            known_ids.add(value)
    elif isinstance(value, list):
        for item in value:
            _collect_id_refs(item, known_ids)
    elif isinstance(value, dict):
        for v in value.values():
            _collect_id_refs(v, known_ids)


def _extract_id_refs_from_value(value, known_ids: set):
    """Extract ID references from a single value (string or list of strings)."""
    if isinstance(value, str):
        if node_type(value):
            known_ids.add(value)
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str) and node_type(item):
                known_ids.add(item)


def load_graph(artifacts_dir: str):
    """Build a unified graph from all artifact JSON files."""
    g = Graph()
    dataspec_path = os.path.join(artifacts_dir, "DataSpec.json")
    _ENTITY_ENUMS = _load_entity_enum_lists(dataspec_path)

    def add_entity_node(name: str):
        """Add a PascalCase entity node."""
        ntype = "Entity"
        if name in _ENTITY_ENUMS[1]:
            ntype = "Enum"
        elif name in _ENTITY_ENUMS[0]:
            ntype = "Entity"
        elif name and name[0].isupper() and not '-' in name:
            ntype = "Entity"
        g.add_node(name, ntype, name, "DataSpec.json")

    def ensure_gl_node(gl_id: str):
        """Ensure a GL node exists (create placeholder if referenced but not in glossary)."""
        if gl_id not in g.nodes:
            g.add_node(gl_id, "GL", f"{gl_id} (referenced)", "Glossary.json")

    # ── GoalSpec.json ──────────────────────────────────────────────────
    path = os.path.join(artifacts_dir, "GoalSpec.json")
    if os.path.exists(path):
        d = json.load(open(path))
        # functional_requirements
        for fr in d.get("functionalRequirements", []):
            if not isinstance(fr, dict):
                continue
            rid = fr.get("id", "")
            label = fr.get("description", rid)
            g.add_node(rid, "REQ", label, "GoalSpec.json")
            _extract_id_refs_from_value(fr.get("glossaryRefs"), set())
            # Collect edges from glossaryRefs
            for gl in (fr.get("glossaryRefs") or []):
                if isinstance(gl, str):
                    g.add_edge(rid, gl)
        # non_functional_requirements
        for nfr in d.get("nonFunctionalRequirements", []):
            if not isinstance(nfr, dict):
                continue
            nid = nfr.get("id", "")
            g.add_node(nid, "NFR", nfr.get("category", nid), "GoalSpec.json")
            for gl in (nfr.get("glossaryRefs") or []):
                if isinstance(gl, str):
                    g.add_edge(nid, gl)
        # user_stories
        for us in d.get("userStories", []):
            if not isinstance(us, dict):
                continue
            uid = us.get("id", "")
            g.add_node(uid, "US", us.get("capability", uid), "GoalSpec.json")
            for gl in (us.get("glossaryRefs") or []):
                if isinstance(gl, str):
                    g.add_edge(uid, gl)
            for rr in (us.get("reqRefs") or []):
                if isinstance(rr, str):
                    g.add_edge(uid, rr)
        # success_criteria
        for sc in d.get("successCriteria", []):
            if not isinstance(sc, dict):
                continue
            sid = sc.get("id", "")
            g.add_node(sid, "SC", sc.get("description", sid), "GoalSpec.json")
            for gl in (sc.get("glossaryRefs") or []):
                if isinstance(gl, str):
                    g.add_edge(sid, gl)

    # ── Glossary.json ──────────────────────────────────────────────────
    path = os.path.join(artifacts_dir, "Glossary.json")
    if os.path.exists(path):
        d = json.load(open(path))
        for t in d.get("terms", []):
            if not isinstance(t, dict):
                continue
            tid = t.get("id", "")
            term_name = t.get("term", tid)
            g.add_node(tid, "GL", term_name, "Glossary.json")
            # related_terms → GL-GL edges
            for rt in (t.get("relatedTerms") or []):
                if isinstance(rt, str) and node_type(rt):
                    g.add_edge(tid, rt)

    # ── ArchitectureSpec.json ──────────────────────────────────────────
    path = os.path.join(artifacts_dir, "ArchitectureSpec.json")
    if os.path.exists(path):
        d = json.load(open(path))
        # components
        for comp in d.get("components", []):
            if not isinstance(comp, dict):
                continue
            cid = comp.get("id", "")
            g.add_node(cid, "CON", comp.get("name", cid), "ArchitectureSpec.json")
            for rr in (comp.get("reqRefs") or []):
                if isinstance(rr, str):
                    g.add_edge(cid, rr)
            for nr in (comp.get("nfrRefs") or []):
                if isinstance(nr, str):
                    g.add_edge(cid, nr)
            for gl in (comp.get("glossaryRefs") or []):
                if isinstance(gl, str):
                    g.add_edge(cid, gl)
        # data_flows
        for df in d.get("dataFlow", []):
            if not isinstance(df, dict):
                continue
            did = df.get("id", "")
            g.add_node(did, "CON", df.get("name", did), "ArchitectureSpec.json")
            for rr in (df.get("reqRefs") or []):
                if isinstance(rr, str):
                    g.add_edge(did, rr)
            for gl in (df.get("glossaryRefs") or []):
                if isinstance(gl, str):
                    g.add_edge(did, gl)
        # constraints
        for con in d.get("constraints", []):
            if not isinstance(con, dict):
                continue
            cid = con.get("id", "")
            g.add_node(cid, "CON", con.get("description", cid), "ArchitectureSpec.json")
            for nr in (con.get("nfrRefs") or []):
                if isinstance(nr, str):
                    g.add_edge(cid, nr)
            for gl in (con.get("glossaryRefs") or []):
                if isinstance(gl, str):
                    g.add_edge(cid, gl)

    # ── ApiSpec.json ───────────────────────────────────────────────────
    path = os.path.join(artifacts_dir, "ApiSpec.json")
    if os.path.exists(path):
        d = json.load(open(path))
        # functions
        for fn in d.get("functions", []):
            if not isinstance(fn, dict):
                continue
            fid = fn.get("id", "")
            g.add_node(fid, "FN", fn.get("name", fid), "ApiSpec.json")
            # entity (singular string)
            entity = fn.get("entity")
            if isinstance(entity, str) and entity:
                add_entity_node(entity)
                g.add_edge(fid, entity)
            for gl in (fn.get("glossaryRefs") or []):
                if isinstance(gl, str):
                    g.add_edge(fid, gl)
        # top-level glossaryRefs
        for gl in (d.get("glossaryRefs") or []):
            if isinstance(gl, str):
                pass  # no clear "from" node for top-level refs

    # ── TestSpec.json ──────────────────────────────────────────────────
    path = os.path.join(artifacts_dir, "TestSpec.json")
    if os.path.exists(path):
        d = json.load(open(path))
        # tests
        for test in d.get("tests", []):
            if not isinstance(test, dict):
                continue
            tid = test.get("id", "")
            g.add_node(tid, "TST", test.get("description", tid), "TestSpec.json")
            fn_ref = test.get("fnRef")
            if isinstance(fn_ref, str) and fn_ref:
                g.add_edge(tid, fn_ref)
            for gl in (test.get("glossaryRefs") or []):
                if isinstance(gl, str):
                    g.add_edge(tid, gl)
        # requirementsTests
        for rt in d.get("requirementsTests", []):
            if not isinstance(rt, dict):
                continue
            req_ref = rt.get("reqRef")
            if isinstance(req_ref, str):
                for test_id in (rt.get("testIds") or []):
                    if isinstance(test_id, str):
                        # Add node if not already present (may be from requirementsTests only)
                        if test_id not in g.nodes:
                            g.add_node(test_id, "TST", f"Test {test_id}", "TestSpec.json")
                        g.add_edge(test_id, req_ref)
            for gl in (rt.get("glossaryRefs") or []):
                if isinstance(gl, str):
                    pass  # no clear from node

    # ── DesignSpec.json ────────────────────────────────────────────────
    path = os.path.join(artifacts_dir, "DesignSpec.json")
    if os.path.exists(path):
        d = json.load(open(path))
        # userJourneys
        for uj in d.get("userJourneys", []):
            if not isinstance(uj, dict):
                continue
            uid = uj.get("id", "")
            g.add_node(uid, "UJ", uj.get("name", uid), "DesignSpec.json")
            for us in (uj.get("usRefs") or []):
                if isinstance(us, str):
                    g.add_edge(uid, us)
            for gl in (uj.get("glossaryRefs") or []):
                if isinstance(gl, str):
                    g.add_edge(uid, gl)
        # uxAcceptanceCriteria
        for uxac in d.get("uxAcceptanceCriteria", []):
            if not isinstance(uxac, dict):
                continue
            uid = uxac.get("id", "")
            g.add_node(uid, "UXAC", uxac.get("description", uid), "DesignSpec.json")
            refs = uxac.get("refs")
            if isinstance(refs, dict):
                for us in (refs.get("usRefs") or []):
                    if isinstance(us, str):
                        g.add_edge(uid, us)
            for gl in (uxac.get("glossaryRefs") or []):
                if isinstance(gl, str):
                    g.add_edge(uid, gl)
        # screenInventory
        for si in d.get("screenInventory", []):
            if not isinstance(si, dict):
                continue
            sid = si.get("id", "")
            g.add_node(sid, "DG", si.get("name", sid), "DesignSpec.json")
            for us in (si.get("usRefs") or []):
                if isinstance(us, str):
                    g.add_edge(sid, us)
            for gl in (si.get("glossaryRefs") or []):
                if isinstance(gl, str):
                    g.add_edge(sid, gl)
        # top-level glossaryRefs
        for gl in (d.get("glossaryRefs") or []):
            if isinstance(gl, str):
                pass  # no clear from node

    # ── DataSpec.json ──────────────────────────────────────────────────
    path = os.path.join(artifacts_dir, "DataSpec.json")
    if os.path.exists(path):
        d = json.load(open(path))
        # entities
        for ent in d.get("entities", []):
            if not isinstance(ent, dict):
                continue
            name = ent.get("name", "")
            add_entity_node(name)
            for gl in (ent.get("glossaryRefs") or []):
                if isinstance(gl, str):
                    g.add_edge(name, gl)
        # enums
        for en in d.get("enums", []):
            if not isinstance(en, dict):
                continue
            name = en.get("name", "")
            add_entity_node(name)
            for gl in (en.get("glossaryRefs") or []):
                if isinstance(gl, str):
                    g.add_edge(name, gl)
        # relationships (Entity → Entity)
        for rel in d.get("relationships", []):
            if not isinstance(rel, dict):
                continue
            from_e = rel.get("from", "")
            to_e = rel.get("to", "")
            if isinstance(from_e, str) and from_e and isinstance(to_e, str) and to_e:
                add_entity_node(from_e)
                add_entity_node(to_e)
                g.add_edge(from_e, to_e)
        # top-level glossaryRefs
        for gl in (d.get("glossaryRefs") or []):
            if isinstance(gl, str):
                pass  # no clear from node

    # Post-process: ensure all GL IDs referenced in edges have nodes
    for frm, to in g.edges:
        if to.startswith("GL-"):
            ensure_gl_node(to)
        if frm.startswith("GL-"):
            ensure_gl_node(frm)

    return g


# ─────────────────────────────────────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────────────────────────────────────


def metric_orphan_nodes(g: Graph) -> dict:
    """Detect orphaned nodes."""
    result = {
        "orphan_req": [],
        "orphan_fn": [],
        "orphan_is": [],
        "orphan_gl": [],
        "orphan_con": [],
    }

    goal_types = {"REQ", "NFR", "US"}

    # Count GL appearances across specs
    gl_appearance_count = defaultdict(int)
    for frm, to in g.edges:
        if g.nodes.get(to, {}).get("type") == "GL":
            gl_appearance_count[to] += 1
    # Also count edges going TO GL
    for frm, to in g.edges:
        if g.nodes.get(to, {}).get("type") == "GL":
            gl_appearance_count[to] += 1

    # orphan_req: REQ with no CON node connected (either direction)
    for rid in g.nodes_of_type("REQ"):
        connected = g.adj.get(rid, set()) | g.radj.get(rid, set())
        has_con = any(g.nodes.get(t, {}).get("type") == "CON" for t in connected)
        if not has_con:
            result["orphan_req"].append(rid)

    # orphan_fn: FN with no incoming IS and no TST edge
    for fid in g.nodes_of_type("FN"):
        has_tst = any(g.nodes.get(t, {}).get("type") == "TST" for t in g.radj.get(fid, set()))
        if not has_tst:
            result["orphan_fn"].append(fid)

    # orphan_is: IS with no REQ or US in its reachable ancestors
    for iid in g.nodes_of_type("IS"):
        ancestors = g.bfs_reachable(iid, direction="in", max_depth=5)
        has_goal = any(g.nodes.get(a, {}).get("type") in goal_types for a in ancestors)
        if not has_goal:
            result["orphan_is"].append(iid)

    # orphan_gl: GL term that appears in only one spec (edge source)
    gl_sources = defaultdict(set)
    for frm, to in g.edges:
        if g.nodes.get(to, {}).get("type") == "GL":
            src_type = g.nodes.get(frm, {}).get("type", "Unknown")
            gl_sources[to].add(src_type)
    for gl_id, sources in gl_sources.items():
        if len(sources) <= 1:
            result["orphan_gl"].append(gl_id)

    # orphan_con: CON with no REQ refs (either direction)
    for cid in g.nodes_of_type("CON"):
        connected = g.adj.get(cid, set()) | g.radj.get(cid, set())
        has_req = any(g.nodes.get(t, {}).get("type") == "REQ" for t in connected)
        if not has_req:
            result["orphan_con"].append(cid)

    return result


def _severity_orphan(class_name: str) -> str:
    return "ERROR" if class_name in ("orphan_req", "orphan_con") else "WARN"


def metric_traceability(g: Graph) -> dict:
    """Traceability score for each REQ.

    Chain: REQ → CON → FN → TST → IS
    Since edges may go in either direction (e.g. CON → REQ means
    components reference requirements), we follow edges bidirectionally
    at each hop.
    """
    CHAIN = ["CON", "FN", "TST", "IS"]
    reqs = g.nodes_of_type("REQ")
    per_req = {}
    for req_id in sorted(reqs):
        score = 0
        missing = []
        current = {req_id}
        for i, target_type in enumerate(CHAIN):
            # Follow edges in both directions from current nodes
            next_nodes = set()
            for node in current:
                # Outgoing
                for nb in g.adj.get(node, set()):
                    next_nodes.add(nb)
                # Incoming
                for nb in g.radj.get(node, set()):
                    next_nodes.add(nb)
            # Check if any node of target_type is reachable within remaining hops
            found = False
            for node in next_nodes:
                if g.nodes.get(node, {}).get("type") == target_type:
                    found = True
                    break
            if found:
                score += 1
            else:
                missing.append(target_type)
            current = next_nodes
        per_req[req_id] = {"score": score, "max": len(CHAIN), "missing": missing}

    total = len(reqs)
    full = sum(1 for r in per_req.values() if r["score"] == r["max"])
    global_ratio = full / max(total, 1)

    return {
        "per_req": per_req,
        "total": total,
        "full": full,
        "global_ratio": global_ratio,
        "global_pct": round(global_ratio * 100, 1),
    }


def metric_blast_radius(g: Graph, node_ids: list = None) -> dict:
    """Blast radius: reachable descendants from given nodes."""
    if node_ids is None:
        node_ids = g.nodes_of_type("REQ") + g.nodes_of_type("GL")

    results = []
    for nid in node_ids:
        reachable = g.bfs_reachable(nid, direction="out")
        by_type = defaultdict(int)
        for r in reachable:
            if r != nid:
                by_type[g.nodes.get(r, {}).get("type", "Unknown")] += 1
        results.append({
            "node": nid,
            "total": len(reachable) - 1,  # exclude self
            "by_type": dict(by_type),
            "nodes": sorted(reachable - {nid}),
        })

    results.sort(key=lambda x: x["total"], reverse=True)

    # Flag top 20% as load-bearing
    top_n = max(1, len(results) // 5)
    for i, r in enumerate(results):
        if i < top_n:
            r["load_bearing"] = True
        else:
            r["load_bearing"] = False

    return results


def metric_risk_score(g: Graph) -> list:
    """Requirement risk score."""
    reqs = g.nodes_of_type("REQ")
    results = []
    for rid in reqs:
        vol = len(g.bfs_reachable(rid, direction="out")) - 1
        deg = g.degree_centrality(rid)
        tst = len(g.reachable_by_type(rid, "TST", direction="out"))
        risk = (vol * deg) / (tst + 1)
        results.append({
            "node": rid,
            "risk": round(risk, 4),
            "volume": vol,
            "centrality": round(deg, 4),
            "tests": tst,
        })
    results.sort(key=lambda x: x["risk"], reverse=True)
    return results[:10]


def metric_responsibility_load(g: Graph) -> dict:
    """Component responsibility load."""
    results = {}
    con_ids = g.nodes_of_type("CON")
    if not con_ids:
        return results

    loads = []
    for cid in con_ids:
        load = {
            "req_count": len(g.reachable_by_type(cid, "REQ", direction="in")),
            "fn_count": len(g.reachable_by_type(cid, "FN", direction="out")),
            "entity_count": len(g.reachable_by_type(cid, "Entity", direction="out")),
            "is_count": len(g.reachable_by_type(cid, "IS", direction="in")),
        }
        loads.append(load)
        results[cid] = load

    # God Component detection
    if loads:
        req_counts = [l["req_count"] for l in loads]
        mean_req = sum(req_counts) / len(req_counts)
        threshold = mean_req * 3
        god_components = [
            cid for cid, l in results.items() if l["req_count"] > threshold
        ]
    else:
        threshold = 0
        god_components = []

    return {
        "per_component": results,
        "god_component_threshold": round(threshold, 2),
        "god_component_candidates": god_components,
    }


def metric_interface_pressure(g: Graph) -> dict:
    """Interface pressure per component."""
    con_ids = g.nodes_of_type("CON")
    total_fns = len(g.nodes_of_type("FN"))
    results = {}
    high_pressure = []

    for cid in con_ids:
        fn_for_con = sum(1 for e in g.edges if e[0] == cid and g.nodes.get(e[1], {}).get("type") == "FN")
        pressure = fn_for_con / max(total_fns, 1)
        results[cid] = {
            "fn_count": fn_for_con,
            "pressure": round(pressure, 4),
        }
        if pressure > 0.30:
            high_pressure.append(cid)

    return {
        "per_component": results,
        "high_pressure": high_pressure,
    }


def metric_test_density(g: Graph, scope_id: str = None) -> dict:
    """Test density for a scope or globally."""
    if scope_id:
        fns = g.reachable_by_type(scope_id, "FN", direction="out")
        reqs = g.reachable_by_type(scope_id, "REQ", direction="in")
        tsts = g.reachable_by_type(scope_id, "TST", direction="out")
    else:
        fns = set(g.nodes_of_type("FN"))
        reqs = set(g.nodes_of_type("REQ"))
        tsts = set(g.nodes_of_type("TST"))

    density = len(tsts) / max(len(fns) + len(reqs), 1)
    return {
        "scope": scope_id or "global",
        "fn_count": len(fns),
        "req_count": len(reqs),
        "tst_count": len(tsts),
        "density": round(density, 4),
    }


def metric_epic_coherence(g: Graph) -> dict:
    """Epic coherence: ratio of intra-epic GL edges."""
    eps = g.nodes_of_type("EP")
    if not eps:
        return {"per_epic": {}, "flagged": [], "note": "No EP nodes found (taskplan.json not present)"}

    results = {}
    flagged = []
    for ep_id in eps:
        # Collect all REQ nodes this EP delivers
        ep_reqs = g.reachable_by_type(ep_id, "REQ", direction="out")
        # Collect GL terms referenced by those REQs
        ep_gl = set()
        for req_id in ep_reqs:
            for edge_to in g.adj.get(req_id, set()):
                if g.nodes.get(edge_to, {}).get("type") == "GL":
                    ep_gl.add(edge_to)

        # Count intra vs cross GL edges
        intra = 0
        cross = 0
        for frm, to in g.edges:
            if g.nodes.get(to, {}).get("type") != "GL":
                continue
            # Check if from node is in ep_reqs or another EP's REQs
            from_type = g.nodes.get(frm, {}).get("type")
            if from_type == "REQ" and frm in ep_reqs:
                # This GL edge is from this EP's REQ
                continue  # Don't count this way — instead check if GL connects to other EP REQs
            elif from_type == "US":
                # Check if US references this EP's REQs
                us_reqs = g.reachable_by_type(frm, "REQ", direction="out", max_depth=2)
                if us_reqs & ep_reqs:
                    intra += 1
                else:
                    cross += 1

        # Simpler approach: count GL edges from this EP's REQs
        intra_gl = set()
        cross_gl = set()
        for req_id in ep_reqs:
            for gl_id in g.adj.get(req_id, set()):
                if g.nodes.get(gl_id, {}).get("type") == "GL":
                    intra_gl.add(gl_id)

        # Check if any GL from this EP also appears in other EPs
        other_reqs = set()
        for other_ep in eps:
            if other_ep != ep_id:
                other_reqs |= g.reachable_by_type(other_ep, "REQ", direction="out")

        cross_gl = set()
        for other_req in other_reqs:
            for gl_id in g.adj.get(other_req, set()):
                if g.nodes.get(gl_id, {}).get("type") == "GL":
                    cross_gl.add(gl_id)

        cross_gl -= intra_gl
        total_gl = len(intra_gl) + len(cross_gl)
        coherence = len(intra_gl) / max(total_gl, 1) if total_gl > 0 else 1.0

        results[ep_id] = {
            "coherence": round(coherence, 4),
            "intra_gl": len(intra_gl),
            "cross_gl": len(cross_gl),
        }
        if coherence < 0.5:
            flagged.append(ep_id)

    return {"per_epic": results, "flagged": flagged}


ALLOWED_EDGES = {
    # Requirement → architecture
    ("REQ", "CON"), ("REQ", "GL"),
    ("NFR", "CON"), ("NFR", "GL"),
    ("US", "REQ"), ("US", "GL"),
    # Architecture → requirements (reverse refs)
    ("CON", "REQ"), ("CON", "NFR"),
    # Architecture → implementation
    ("CON", "FN"), ("CON", "Entity"),
    ("FN", "Entity"), ("FN", "GL"),
    ("FN", "CON"), ("FN", "REQ"), ("FN", "NFR"), ("FN", "US"),
    # Issues → implementation
    ("IS", "FN"), ("IS", "REQ"), ("IS", "US"), ("IS", "EP"),
    # Tests
    ("TST", "FN"), ("TST", "GL"),
    ("TST", "REQ"), ("TST", "NFR"), ("TST", "TST"),
    # User journeys
    ("UJ", "US"), ("UJ", "GL"),
    # Epics
    ("EP", "REQ"), ("EP", "US"),
    # UX
    ("UJ", "US"),
    ("UXAC", "US"),
    ("UXAC", "NFR"), ("UXAC", "REQ"), ("UXAC", "GL"),
    ("UXAC", "FN"), ("UXAC", "CON"),
    ("UXAC", "Entity"), ("UXAC", "TST"),
    ("UXAC", "US"), ("UXAC", "SC"),
    ("UXAC", "DG"), ("UXAC", "VDR"), ("UXAC", "AR"),
    # Data
    ("Entity", "Entity"), ("Entity", "GL"),
    ("Entity", "FN"),
    ("Enum", "GL"),
    ("GL", "GL"),
    # Misc
    ("SC", "REQ"), ("SC", "GL"), ("SC", "SC"),
    ("DG", "US"), ("DG", "GL"), ("DG", "NFR"),
    ("VDR", "NFR"), ("VDR", "GL"), ("VDR", "REQ"),
    ("AR", "GL"), ("AR", "CON"), ("AR", "NFR"),
    ("AR", "US"), ("AR", "REQ"),
    # Self-loops
    ("FN", "FN"), ("CON", "CON"),
    ("REQ", "NFR"), ("NFR", "REQ"),
    ("REQ", "US"), ("US", "US"),
    ("NFR", "NFR"),
    ("CON", "GL"),
}


def metric_layer_violations(g: Graph) -> list:
    """Detect edges that violate allowed type adjacency."""
    violations = []
    seen = set()
    for frm, to in g.edges:
        frm_type = g.nodes.get(frm, {}).get("type", "Unknown")
        to_type = g.nodes.get(to, {}).get("type", "Unknown")
        pair = (frm_type, to_type)
        edge_key = (frm, to)
        if edge_key in seen:
            continue
        seen.add(edge_key)

        # Check if this pair is allowed
        if pair not in ALLOWED_EDGES:
            # Allow some common cross-cutting patterns
            reason = f"({frm_type} → {to_type}) not in allowed adjacency matrix"
            violations.append({
                "from": frm,
                "to": to,
                "from_type": frm_type,
                "to_type": to_type,
                "reason": reason,
            })

    return violations


def metric_health_index(g: Graph, trace_report: dict, orphans: dict,
                        layer_violations: list) -> dict:
    """Architecture Health Index."""
    total_nodes = max(len(g.nodes), 1)

    # Coverage = traceability global ratio
    coverage = trace_report.get("global_ratio", 0.0)

    # Verifiability: fraction of REQs with at least one TST reachable
    reqs = g.nodes_of_type("REQ")
    reqs_with_tests = sum(
        1 for r in reqs
        if g.reachable_by_type(r, "TST", direction="out")
    )
    verifiability = reqs_with_tests / max(len(reqs), 1)

    # Traceability = same as coverage
    traceability = coverage

    # Orphan rate
    all_orphans = sum(len(v) for v in orphans.values())
    orphan_rate = all_orphans / max(total_nodes, 1)

    # Layer OK
    total_edges = max(len(g.edges), 1)
    layer_ok = 1 - (len(layer_violations) / total_edges)

    score = (
        0.30 * coverage +
        0.20 * verifiability +
        0.20 * traceability +
        0.15 * (1 - orphan_rate) +
        0.15 * layer_ok
    ) * 100

    return {
        "score": round(score, 1),
        "breakdown": {
            "coverage": round(coverage, 4),
            "verifiability": round(verifiability, 4),
            "traceability": round(traceability, 4),
            "orphan_rate": round(orphan_rate, 4),
            "layer_ok": round(layer_ok, 4),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Report Generation
# ─────────────────────────────────────────────────────────────────────────────


def _bar(value: float, width: int = 10) -> str:
    """Render a bar: █ filled, ░ empty."""
    filled = round(value * width)
    return "█" * filled + "░" * (width - filled)


def format_text_report(results: dict) -> str:
    """Format results as human-readable text."""
    lines = []
    w = 62  # total width of report

    lines.append(f"══ Architecture Graph Metrics ══{'=' * (w - 30)}")
    lines.append("")

    # Health Index
    hi = results.get("health_index", {})
    bd = hi.get("breakdown", {})
    lines.append(f"Health Index: {hi.get('score', 'N/A')} / 100")
    lines.append(f"  Coverage      {_bar(bd.get('coverage', 0), 12)}  {bd.get('coverage', 0):.2f}")
    lines.append(f"  Verifiability {_bar(bd.get('verifiability', 0), 12)}  {bd.get('verifiability', 0):.2f}")
    lines.append(f"  Traceability  {_bar(bd.get('traceability', 0), 12)}  {bd.get('traceability', 0):.2f}")
    orphan_total = sum(len(v) for v in results.get("orphans", {}).values())
    lines.append(f"  Orphan Rate   {_bar(1 - bd.get('orphan_rate', 0), 12)}  {1 - bd.get('orphan_rate', 0):.2f}  ({orphan_total} orphans)")
    lines.append(f"  Layer OK      {_bar(bd.get('layer_ok', 0), 12)}  {bd.get('layer_ok', 0):.2f}")
    lines.append("")

    # Traceability
    lines.append(f"── Traceability ───────────────────────────────────────────")
    tr = results.get("traceability", {})
    per_req = tr.get("per_req", {})
    for req_id, info in sorted(per_req.items()):
        score = info["score"]
        full_bar = "█" * score + "░" * (info["max"] - score)
        status = "✓" if score == info["max"] else "✗"
        missing_str = f"  missing: {', '.join(info['missing'])}" if info["missing"] else ""
        lines.append(f"{req_id}  {full_bar}  {score}/{info['max']}  {status}{missing_str}")
    lines.append(f"Global: {tr.get('full', 0)}/{tr.get('total', 0)} ({tr.get('global_pct', 0)}%)")
    lines.append("")

    # Orphans
    lines.append(f"── Orphans ─────────────────────────────────────────────────")
    orphans = results.get("orphans", {})
    orphan_found = False
    for class_name, nodes in orphans.items():
        sev = _severity_orphan(class_name)
        for nid in sorted(nodes):
            lines.append(f"{sev:<6} {class_name:<12} {nid}")
            orphan_found = True
    if not orphan_found:
        lines.append("  (none)")
    lines.append("")

    # Blast Radius
    lines.append(f"── Blast Radius (top 10) ───────────────────────────────────")
    br = results.get("blast_radius", [])
    for item in br[:10]:
        star = " ★ load-bearing" if item.get("load_bearing") else ""
        lines.append(f"{item['node']}  radius={item['total']}{star}")
    lines.append("")

    # Risk Scores
    lines.append(f"── Risk Scores (top 10) ────────────────────────────────────")
    rs = results.get("risk_scores", [])
    for item in rs:
        lines.append(f"{item['node']}  risk={item['risk']:.1f}  vol={item['volume']} centrality={item['centrality']:.4f} tests={item['tests']}")
    lines.append("")

    # God Component Candidates
    lines.append(f"── God Component Candidates ────────────────────────────────")
    rl = results.get("responsibility_load", {})
    god = rl.get("god_component_candidates", [])
    if god:
        for cid in god:
            load = rl.get("per_component", {}).get(cid, {})
            lines.append(f"{cid}  REQ:{load.get('req_count', 0)} FN:{load.get('fn_count', 0)} Entity:{load.get('entity_count', 0)} IS:{load.get('is_count', 0)}")
    else:
        lines.append("  (none)")
    lines.append("")

    # Interface Pressure
    lines.append(f"── Interface Pressure ──────────────────────────────────────")
    ip = results.get("interface_pressure", {})
    high = ip.get("high_pressure", [])
    if high:
        for cid in high:
            info = ip.get("per_component", {}).get(cid, {})
            lines.append(f"{cid}  pressure={info.get('pressure', 0):.4f}  fn_count={info.get('fn_count', 0)}")
    else:
        lines.append("  (none)")
    lines.append("")

    # Test Density
    lines.append(f"── Test Density ────────────────────────────────────────────")
    td = results.get("test_density", {})
    lines.append(f"Scope: {td.get('scope', 'global')}  "
                 f"Fns: {td.get('fn_count', 0)}  "
                 f"Reqs: {td.get('req_count', 0)}  "
                 f"Tsts: {td.get('tst_count', 0)}  "
                 f"Density: {td.get('density', 0):.4f}")
    lines.append("")

    # Epic Coherence
    lines.append(f"── Epic Coherence ──────────────────────────────────────────")
    ec = results.get("epic_coherence", {})
    if ec.get("per_epic"):
        for ep_id, info in sorted(ec.get("per_epic", {}).items()):
            coh = info.get("coherence", 0)
            status = "✓" if coh >= 0.5 else "✗  consider splitting"
            lines.append(f"{ep_id}  {coh:.2f}  {status}")
    else:
        lines.append(f"  {ec.get('note', 'No EP nodes found')}")
    lines.append("")

    # Layer Violations
    lines.append(f"── Layer Violations ────────────────────────────────────────")
    lv = results.get("layer_violations", [])
    if lv:
        for v in lv[:20]:
            lines.append(f"  [{v['from_type']} → {v['to_type']}] {v['from']} → {v['to']}")
        if len(lv) > 20:
            lines.append(f"  ... and {len(lv) - 20} more")
    else:
        lines.append("  (none)")
    lines.append("")

    return "\n".join(lines)


def format_json_report(results: dict) -> str:
    """Format results as JSON."""
    # Make everything JSON-serializable
    serializable = {}
    for k, v in results.items():
        if isinstance(v, dict):
            serializable[k] = {
                str(kk): vv if not isinstance(vv, (set, frozenset)) else list(vv)
                for kk, vv in v.items()
            }
        elif isinstance(v, list):
            serializable[k] = v
        else:
            serializable[k] = v
    return json.dumps(serializable, indent=2, default=str)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Architecture Graph Metrics")
    parser.add_argument("--artifacts", required=True, help="Path to artifacts directory")
    parser.add_argument("--report", default=None, help="Path to write report file")
    parser.add_argument("--format", choices=["json", "text"], default="text",
                        help="Output format (default: text)")
    parser.add_argument("--dump-graph", action="store_true",
                        help="Dump raw graph nodes/edges as JSON (for visualization)")
    args = parser.parse_args()

    artifacts_dir = args.artifacts
    if not os.path.isdir(artifacts_dir):
        print(f"ERROR: Artifacts directory not found: {artifacts_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Building graph from {artifacts_dir}...", file=sys.stderr)
    g = load_graph(artifacts_dir)
    print(f"  Nodes: {len(g.nodes)}, Edges: {len(g.edges)}", file=sys.stderr)

    # Compute all metrics
    print("Computing metrics...", file=sys.stderr)

    orphans = metric_orphan_nodes(g)
    traceability = metric_traceability(g)
    blast_radius = metric_blast_radius(g)
    risk_scores = metric_risk_score(g)
    resp_load = metric_responsibility_load(g)
    iface_pressure = metric_interface_pressure(g)
    test_density = metric_test_density(g)
    epic_coh = metric_epic_coherence(g)
    layer_viols = metric_layer_violations(g)
    health = metric_health_index(g, traceability, orphans, layer_viols)

    results = {
        "graph_stats": {
            "nodes": len(g.nodes),
            "edges": len(g.edges),
            "node_types": {t: len(g.nodes_of_type(t)) for t in set(n["type"] for n in g.nodes.values())},
        },
        "health_index": health,
        "traceability": traceability,
        "orphans": orphans,
        "blast_radius": blast_radius,
        "risk_scores": risk_scores,
        "responsibility_load": resp_load,
        "interface_pressure": iface_pressure,
        "test_density": test_density,
        "epic_coherence": epic_coh,
        "layer_violations": layer_viols,
    }

    # Dump raw graph if requested
    if args.dump_graph:
        graph_dump = {
            "nodes": [
                {"id": nid, "type": info["type"], "label": info.get("label", nid), "source": info.get("source", "")}
                for nid, info in g.nodes.items()
            ],
            "edges": [
                {"source": frm, "target": to}
                for frm, to in g.edges
            ],
        }
        print(json.dumps(graph_dump, indent=2))
        sys.exit(0)

    # Output
    if args.format == "json":
        output = format_json_report(results)
    else:
        output = format_text_report(results)

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report written to {args.report}", file=sys.stderr)

    print(output)

    # Exit code: 1 if there are ERROR-level orphans or layer violations
    error_orphans = sum(len(orphans.get(k, [])) for k in ["orphan_req", "orphan_con"])
    if error_orphans > 0 or len(layer_viols) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
