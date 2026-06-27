#!/usr/bin/env python3
"""
path.py — Dot-path navigation through spec JSON.

Provides resolve_path() which navigates a dot-separated path through spec
JSON and returns a Resolved object with values, parent IDs, and labels.

All linters import resolve_path from shared.py which re-exports it.
"""

import re

from linter_types import Resolved


def _normalize_ref(ref_value: str | list[str] | None) -> list[str]:
    """Normalize a ref value to a list of strings.

    Handles string refs, list refs, and None.

    Args:
        ref_value: A ref string, list of refs, or None.

    Returns:
        List of ref strings (empty list if None).

    Examples:
        >>> _normalize_ref("REQ-001")
        ["REQ-001"]
        >>> _normalize_ref(["REQ-001", "REQ-002"])
        ["REQ-001", "REQ-002"]
        >>> _normalize_ref(None)
        []
    """
    if isinstance(ref_value, str):
        return [ref_value]
    return ref_value or []


def resolve_path(path: str, spec: dict, extra_specs: dict) -> Resolved:
    """Navigate a dot-path through spec JSON and return resolved values with parent context.

    Segments:
      - First segment: top-level key in spec or extra_spec
      - Subsequent segments: properties on items, or nested lists (flattened)
      - Prefix `spec:` on first segment to use an extra_spec

    Examples:
      "components.reqRefs"          → each component's reqRefs list
      "dataFlow.steps.componentRef" → each step's componentRef string
      "goal:functionalRequirements" → functionalRequirements from extra_specs["goal"]
    """
    segments = path.split(".")
    if not segments:
        return Resolved([], [], "")

    # Parse path: handle "spec:key" prefix
    first_segment = segments[0]
    extra_spec_name = None
    if ":" in first_segment:
        extra_spec_name, first_segment = first_segment.split(":", 1)

    # Navigate first segment → root list
    root = (extra_specs.get(extra_spec_name) or {}) if extra_spec_name else spec
    items = root.get(first_segment, [])
    if not isinstance(items, list):
        items = [items] if items else []

    label = re.sub(r"([A-Z])", r" \1", first_segment).title().replace("_", " ").strip()

    # Navigate remaining segments (segments[1:])
    return _traverse_segments(
        segments[1:],
        items,
        label,
        parent_ids=[],
        parent_items=[],
        group_sizes=[],
    )


def _traverse_segments(
    segments: list[str],
    items: list,
    label: str,
    parent_ids: list[str],
    parent_items: list[dict],
    group_sizes: list[int],
) -> Resolved:
    """Walk remaining path segments, flattening lists and navigating dicts.

    Uses a result builder pattern to avoid early returns:
    accumulates state through the loop and produces a single result.
    """
    current_items = items
    terminal_seg = None  # Set when we hit a scalar extraction point

    for seg_idx, seg in enumerate(segments):
        if not current_items:
            break

        first_item = current_items[0]
        if isinstance(first_item, str):
            break  # items are already scalars

        if isinstance(first_item, dict):
            if seg in first_item:
                val = first_item[seg]
                if isinstance(val, list):
                    current_items, parent_ids, parent_items, group_sizes = (
                        _flatten_list_segment(current_items, seg, parent_ids, parent_items)
                    )
                elif seg_idx + 1 < len(segments) and isinstance(val, dict):
                    current_items, parent_ids, parent_items, group_sizes = (
                        _navigate_dict_segment(current_items, seg, parent_ids, parent_items)
                    )
                else:
                    # Terminal: scalar value at this segment
                    terminal_seg = seg
            else:
                # Terminal: segment key missing on items
                terminal_seg = seg

    if terminal_seg is not None:
        return _extract_scalars(
            current_items, terminal_seg, parent_ids, parent_items, label
        )

    return _resolve_final(current_items, parent_ids, parent_items, group_sizes, label)


def _get_item_id(item: dict, fallback: str = "?") -> str:
    """Derive identifier from an item dict."""
    if not isinstance(item, dict):
        return fallback
    return item.get("id", item.get("name", fallback))


def _get_parent_context(
    i: int, item: dict, parent_ids: list[str], parent_items: list[dict]
) -> tuple[str, dict]:
    """Resolve parent_id and parent_item for index i.

    Propagates existing parent context, or derives from the item itself.
    """
    if parent_ids and i < len(parent_ids):
        return parent_ids[i], (parent_items[i] if i < len(parent_items) else item)
    return _get_item_id(item, "?"), item


def _flatten_list_segment(
    items: list, seg: str, parent_ids: list[str], parent_items: list[dict]
) -> tuple[list, list[str], list[dict], list[int]]:
    """Flatten a nested list segment (e.g. components.reqRefs).

    Each nested item inherits the parent's id.
    """
    new_items, new_ids, new_parents, new_sizes = [], [], [], []
    for i, item in enumerate(items):
        nested = item.get(seg, [])
        if not isinstance(nested, list):
            continue
        pi = parent_items[i] if i < len(parent_items) else item
        pid = _get_item_id(pi, _get_item_id(item, "?"))
        for nested_item in nested:
            new_items.append(nested_item)
            new_ids.append(pid)
            new_parents.append(pi)
            new_sizes.append(len(nested))
    return new_items, new_ids, new_parents, new_sizes


def _navigate_dict_segment(
    items: list, seg: str, parent_ids: list[str], parent_items: list[dict]
) -> tuple[list, list[str], list[dict], list[int]]:
    """Navigate into a dict segment and continue traversing.

    Preserves existing parent context or derives from current item.
    Returns None for missing keys so downstream checks can detect absence.
    """
    new_items = [item.get(seg) if isinstance(item, dict) and seg in item else None
                 for item in items]
    new_ids, new_parents, new_sizes = [], [], []
    for i, item in enumerate(items):
        pid, pi = _get_parent_context(i, item, parent_ids, parent_items)
        new_ids.append(pid)
        new_parents.append(pi)
        new_sizes.append(1)
    return new_items, new_ids, new_parents, new_sizes


def _extract_scalars(
    items: list, seg: str, parent_ids: list[str], parent_items: list[dict], label: str
) -> Resolved:
    """Extract scalar values from the terminal segment."""
    values, new_ids, new_parents, new_sizes = [], [], [], []
    for i, item in enumerate(items):
        values.append(item.get(seg) if isinstance(item, dict) else item)
        pid, pi = _get_parent_context(i, item, parent_ids, parent_items)
        new_ids.append(pid)
        new_parents.append(pi)
        new_sizes.append(1)
    return Resolved(values, new_ids, label, new_parents, new_sizes)


def _resolve_final(
    items: list,
    parent_ids: list[str],
    parent_items: list[dict],
    group_sizes: list[int],
    label: str,
) -> Resolved:
    """Finalize after loop — handle empty or unresolved parent_ids."""
    if not items:
        return Resolved([], [], label, [], [])

    first = items[0]
    if isinstance(first, dict):
        if not parent_ids:
            # Single-segment path: use items' own identifiers
            for item in items:
                parent_ids.append(_get_item_id(item, "?"))
                parent_items.append(item)
                group_sizes.append(1)
        elif all(pid == "?" for pid in parent_ids):
            # Dict-nesting where parent has no id (e.g. overview.subsystems)
            for i, item in enumerate(items):
                parent_ids[i] = _get_item_id(item, "?")
                parent_items[i] = item
    elif isinstance(first, str):
        if not parent_ids:
            parent_ids = list(items)
            parent_items = list(items)
            group_sizes = [1] * len(items)

    return Resolved(items, parent_ids, label, parent_items, group_sizes)
