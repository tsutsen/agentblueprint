#!/usr/bin/env python3
"""
json_to_all.py
Converts a DataSpec JSON to five diagram formats:
  .puml    — PlantUML class diagram (with inheritance, composition, aggregation)
  .md      — Mermaid class diagram (inside ```mermaid fence)
  .drawio  — draw.io XML (import at app.diagrams.net)
  .dbml    — DBML (import at dbdiagram.io)
  .d2      — D2 diagram (render with: d2 file.d2 file.svg)

Usage:
    python json_to_all.py [input.json] [formats] [output_stem]

    formats  — comma-separated list of formats, or "all" (default)
               choices: puml, mermaid, drawio, dbml, d2, all

Examples:
    python json_to_all.py DataSpec.json                  # all formats → DataSpec.*
    python json_to_all.py DataSpec.json all              # same
    python json_to_all.py DataSpec.json puml,mermaid     # only those two
    python json_to_all.py DataSpec.json all output/MyModel # custom output stem
"""

import json
import math
import sys
import textwrap
import uuid
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# I/O helpers
# ─────────────────────────────────────────────────────────────────────────────

def load(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"  ✓ {path}  ({len(text.splitlines())} lines)")


# ─────────────────────────────────────────────────────────────────────────────
# PlantUML
# ─────────────────────────────────────────────────────────────────────────────

_PUML_ARROW = {
    "composition": "*--",
    "aggregation": "o--",
    "association": "--",
    "dependency":  "..>",
    "realization": "..|>",
    "inheritance": "--|>",
}

_PUML_VIS = {
    "public":    "+",
    "protected": "#",
    "private":   "-",
    "internal":  "~",
}


def _puml_field(field: dict, vis: str) -> str:
    prefix = _PUML_VIS.get(vis, "+")
    marker = "" if field.get("required", False) else " {optional}"
    return f"    {prefix} {field['name']} : {field['type']}{marker}"


def _puml_enum(enum: dict) -> list[str]:
    lines = [f"enum {enum['name']} {{"]
    for v in enum.get("values", []):
        lines.append(f"    {v['name']}")
    return lines + ["}", ""]


def _puml_entity(entity: dict) -> list[str]:
    vis   = entity.get("visibility", "public")
    lines = [f"class {entity['name']} <<{vis}>> {{"]
    for field in entity.get("fields", []):
        lines.append(_puml_field(field, vis))
    for method in entity.get("methods", []):
        lines.append(f"    + {method['name']}() : void")
    return lines + ["}", ""]


def _puml_rel(rel: dict) -> str:
    arrow  = _PUML_ARROW.get(rel.get("type", "association"), "--")
    card   = rel.get("cardinality", {})
    fc     = f"\"{card.get('fromLabel', '')}\" " if card.get("fromLabel") else ""
    tc     = f" \"{card.get('toLabel', '')}\"" if card.get("toLabel") else ""
    label  = f" : {rel['label']}" if rel.get("label") else ""
    return f"{rel['from']} {fc}{arrow}{tc} {rel['to']}{label}"


def to_plantuml(data: dict) -> str:
    title, version = data.get("module", "Data Model"), data.get("version", "")
    lines = [
        "@startuml",
        f"' {title}  v{version}",
        f"' {data.get('description', '')}",
        "",
        "skinparam classAttributeIconSize 0",
        "skinparam monochrome false",
        "skinparam shadowing false",
        "skinparam classFontSize 12",
        "skinparam classHeaderBackgroundColor #DDEEFF",
        "skinparam classBorderColor #336699",
        "skinparam ArrowColor #336699",
        "hide empty members",
        "",
        f"title {title} — Domain Model v{version}",
        "",
        "' ── Enumerations ─────────────────────────────",
    ]
    for enum in data.get("enums", []):
        lines += _puml_enum(enum)

    lines.append("' ── Entities ─────────────────────────────────")
    groups: dict[str, list] = {}
    for e in data.get("entities", []):
        groups.setdefault(e.get("visibility", "public"), []).append(e)
    for vis_key in ("public", "protected", "internal", "private"):
        for entity in groups.get(vis_key, []):
            lines += _puml_entity(entity)

    lines += ["' ── Relationships ────────────────────────────"]
    for rel in data.get("relationships", []):
        lines.append(_puml_rel(rel))

    lines += ["' ── Inheritance ─────────────────────────────"]
    entity_map = {e["name"]: e for e in data.get("entities", [])}
    for entity in data.get("entities", []):
        parent = entity.get("extends")
        if parent and parent in entity_map:
            lines.append(f"{entity['name']} --|> {parent}")

    lines += ["", "@enduml"]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Mermaid
# ─────────────────────────────────────────────────────────────────────────────

_MMD_ARROW = {
    "composition": "*--",
    "aggregation": "o--",
    "association": "<-->",
    "dependency":  "..>",
    "realization": "..|>",
    "inheritance": "<|--",
}

_MMD_VIS = {
    "public":    "+",
    "protected": "#",
    "private":   "-",
    "internal":  "~",
}


def _mmd_type(t: str) -> str:
    return f"List~{t[:-2]}~" if t.endswith("[]") else t


def _mmd_field(field: dict, mod: str) -> str:
    suffix = "" if field.get("required", False) else "$"
    return f"        {mod}{_mmd_type(field['type'])} {field['name']}{suffix}"


def _mmd_enum(enum: dict) -> list[str]:
    lines = [f"    class {enum['name']} {{", "        <<enumeration>>"]
    for v in enum.get("values", []):
        lines.append(f"        {v['name']}")
    return lines + ["    }", ""]


def _mmd_entity(entity: dict) -> list[str]:
    vis   = entity.get("visibility", "public")
    mod   = _MMD_VIS.get(vis, "+")
    lines = [f"    class {entity['name']} {{"]
    if vis != "public":
        lines.append(f"        <<{vis}>>")
    for field in entity.get("fields", []):
        lines.append(_mmd_field(field, mod))
    for method in entity.get("methods", []):
        lines.append(f"        + {method['name']}()")
    return lines + ["    }", ""]


def _mmd_rel(rel: dict) -> str:
    arrow = _MMD_ARROW.get(rel.get("type", "association"), "--")
    card  = rel.get("cardinality", {})
    fc    = f"\"{card.get('fromLabel', '')}\" " if card.get("fromLabel") else ""
    tc    = f" \"{card.get('toLabel', '')}\"" if card.get("toLabel") else ""
    label = f" : {rel['label'].replace(' ', '_')}" if rel.get("label") else ""
    return f"    {rel['from']} {fc}{arrow}{tc} {rel['to']}{label}"


def to_mermaid(data: dict) -> str:
    title, version = data.get("module", "Data Model"), data.get("version", "")
    lines = [
        "---",
        f"title: {title} — Domain Model v{version}",
        "---",
        "",
        "```mermaid",
        f"%% {data.get('description', '')}",
        "%% Fields marked with $ are optional",
        "",
        "classDiagram",
        "    direction TB",
        "",
        "    %% ── Enumerations ──────────────────────────────",
    ]
    for enum in data.get("enums", []):
        lines += _mmd_enum(enum)

    lines.append("    %% ── Entities ──────────────────────────────────")
    groups: dict[str, list] = {}
    for e in data.get("entities", []):
        groups.setdefault(e.get("visibility", "public"), []).append(e)
    for vis_key in ("public", "protected", "internal", "private"):
        for entity in groups.get(vis_key, []):
            lines += _mmd_entity(entity)

    lines.append("    %% ── Relationships ─────────────────────────────")
    for rel in data.get("relationships", []):
        lines.append(_mmd_rel(rel))

    lines.append("    %% ── Inheritance ─────────────────────────────")
    entity_map = {e["name"]: e for e in data.get("entities", [])}
    for entity in data.get("entities", []):
        parent = entity.get("extends")
        if parent and parent in entity_map:
            lines.append(f"    {entity['name']} <|-- {parent}")

    lines.append("```")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# draw.io XML
# ─────────────────────────────────────────────────────────────────────────────

_DRAWIO_REL_STYLE = {
    "composition": "endArrow=ERmany;startArrow=ERmandOne;",
    "aggregation": "endArrow=ERmany;startArrow=ERzeroToOne;",
    "association": "endArrow=ERzeroToMany;startArrow=ERzeroToOne;",
    "dependency":  "endArrow=open;dashed=1;",
    "realization": "endArrow=block;dashed=1;",
    "inheritance": "endArrow=block;",
}

_DRAWIO_VIS_FILL = {
    "public":   "#dae8fc",
    "internal": "#d5e8d4",
    "private":  "#f8cecc",
}


def _uid() -> str:
    return str(uuid.uuid4())


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def _drawio_entity(entity: dict, x: int, y: int, cell_ids: dict) -> list[str]:
    name   = entity["name"]
    eid    = _uid()
    cell_ids[name] = eid
    fill   = _DRAWIO_VIS_FILL.get(entity.get("visibility", "public"), "#dae8fc")
    fields = entity.get("fields", [])
    row_h, hdr_h, width = 26, 34, 220
    cells  = [
        f'<mxCell id="{eid}" value="{_esc(name)}" style="'
        f'shape=table;startSize={hdr_h};container=1;collapsible=1;childLayout=tableLayout;'
        f'fillColor={fill};strokeColor=#6c8ebf;fontStyle=1;fontSize=12;" '
        f'vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{width}" '
        f'height="{hdr_h + row_h * len(fields)}" as="geometry"/></mxCell>'
    ]
    for i, f in enumerate(fields):
        label = f"{f['name']} : {f['type']}{'  ✱' if f.get('required') else ''}"
        fill2 = "#ffffff" if i % 2 == 0 else "#f5f5f5"
        cells.append(
            f'<mxCell id="{_uid()}" value="{_esc(label)}" style="'
            f'shape=tableRow;horizontal=0;startSize=0;swimlaneHead=0;swimlaneBody=0;'
            f'fillColor={fill2};collapsible=0;dropTarget=0;'
            f'points=[[0,0.5],[1,0.5]];portConstraint=eastwest;'
            f'fontSize=11;fontColor=#333333;strokeColor=#d0d0d0;" '
            f'vertex="1" parent="{eid}">'
            f'<mxGeometry y="{hdr_h + i * row_h}" width="{width}" height="{row_h}" as="geometry"/>'
            f'</mxCell>'
        )
    return cells


def _drawio_enum(enum: dict, x: int, y: int, cell_ids: dict) -> list[str]:
    name   = enum["name"]
    eid    = _uid()
    cell_ids[name] = eid
    values = enum.get("values", [])
    row_h, hdr_h, width = 22, 30, 180
    cells  = [
        f'<mxCell id="{eid}" value="«enumeration»&#xa;{_esc(name)}" style="'
        f'shape=table;startSize={hdr_h};container=1;collapsible=1;childLayout=tableLayout;'
        f'fillColor=#fff2cc;strokeColor=#d6b656;fontStyle=3;fontSize=11;" '
        f'vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{width}" '
        f'height="{hdr_h + row_h * len(values)}" as="geometry"/></mxCell>'
    ]
    for i, v in enumerate(values):
        fill2 = "#fffde7" if i % 2 == 0 else "#fff8e1"
        cells.append(
            f'<mxCell id="{_uid()}" value="{_esc(v["name"])}" style="'
            f'shape=tableRow;horizontal=0;startSize=0;'
            f'fillColor={fill2};collapsible=0;dropTarget=0;'
            f'points=[[0,0.5],[1,0.5]];portConstraint=eastwest;'
            f'fontSize=11;strokeColor=#e0d0a0;" '
            f'vertex="1" parent="{eid}">'
            f'<mxGeometry y="{hdr_h + i * row_h}" width="{width}" height="{row_h}" as="geometry"/>'
            f'</mxCell>'
        )
    return cells


def _drawio_rel(rel: dict, cell_ids: dict) -> str | None:
    frm, to = rel["from"], rel["to"]
    if frm not in cell_ids or to not in cell_ids:
        return None
    style = _DRAWIO_REL_STYLE.get(rel.get("type", "association"), "endArrow=open;")
    label = rel.get("label", "")
    return (
        f'<mxCell id="{_uid()}" value="{_esc(label)}" style="'
        f'edgeStyle=orthogonalEdgeStyle;{style}exitX=1;exitY=0.5;entryX=0;entryY=0.5;" '
        f'edge="1" source="{cell_ids[frm]}" target="{cell_ids[to]}" parent="1">'
        f'<mxGeometry relative="1" as="geometry"/></mxCell>'
    )


def to_drawio(data: dict) -> str:
    entities, enums = data.get("entities", []), data.get("enums", [])
    cell_ids: dict[str, str] = {}
    cells: list[str] = []
    cols, gap_x, gap_y = 4, 30, 40
    for i, entity in enumerate(entities):
        x = 40 + (i % cols) * (250 + gap_x)
        y = 40 + (i // cols) * (200 + gap_y)
        cells += _drawio_entity(entity, x, y, cell_ids)
    base_y = 40 + math.ceil(len(entities) / cols) * (200 + gap_y) + 60
    for j, enum in enumerate(enums):
        x = 40 + (j % 5) * (200 + gap_x)
        y = base_y + (j // 5) * (160 + gap_y)
        cells += _drawio_enum(enum, x, y, cell_ids)
    for rel in data.get("relationships", []):
        cell = _drawio_rel(rel, cell_ids)
        if cell:
            cells.append(cell)
    cells_xml = "\n        ".join(cells)
    title     = _esc(data.get("module", "Data Model"))
    return textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <mxfile host="app.diagrams.net" version="21.0.0">
          <diagram name="{title}">
            <mxGraphModel dx="1422" dy="762" grid="0" gridSize="10" guides="1"
                          tooltips="1" connect="1" arrows="1" fold="1"
                          page="1" pageScale="1" pageWidth="1654" pageHeight="1169"
                          math="0" shadow="0">
              <root>
                <mxCell id="0"/>
                <mxCell id="1" parent="0"/>
                {cells_xml}
              </root>
            </mxGraphModel>
          </diagram>
        </mxfile>
        """)


# ─────────────────────────────────────────────────────────────────────────────
# DBML
# ─────────────────────────────────────────────────────────────────────────────

_DBML_TYPE = {
    "string": "varchar", "number": "float",
    "boolean": "boolean", "null": "null", "any": "text",
}

_DBML_REF = {
    "composition": "<", "aggregation": "<",
    "association": "<>", "dependency": ">",
}


def _dbml_type(t: str, enum_names: set) -> str:
    if t.endswith("[]"):
        return "text"
    return t if t in enum_names else _DBML_TYPE.get(t, "text")


def _dbml_safe_name(name: str) -> str:
    """Convert a module name to a valid DBML project identifier."""
    return name.replace(" ", "_").replace("-", "_").replace(".", "_")


def _find_pk(entity: dict) -> str:
    """Find a primary key field for a DBML table.

    Priority: 'id' > first field with 'Id'/'id' in name > first field.
    Returns the field name to use as the primary key reference.
    """
    fields = entity.get("fields", [])
    # Check for 'id' field
    for f in fields:
        if f["name"].lower() == "id":
            return f["name"]
    # Check for field with 'Id' in the name
    for f in fields:
        if "Id" in f["name"] or "id" in f["name"]:
            return f["name"]
    # Fall back to first field
    if fields:
        return fields[0]["name"]
    return "id"  # last resort


def to_dbml(data: dict) -> str:
    enums      = data.get("enums", [])
    enum_names = {e["name"] for e in enums}
    module     = data.get("module", "Data Model")
    lines      = [
        f"// {module}  v{data.get('version', '')}",
        f"// {data.get('description', '')}",
        "",
        f"Project {_dbml_safe_name(module)} {{",
        f"  database_type: 'JSON/Document'",
        f"  Note: '{data.get('description', '')}'",
        "}",
        "",
    ]
    for enum in enums:
        lines.append(f"Enum {enum['name']} {{")
        for v in enum.get("values", []):
            note = v.get("description", "")
            lines.append(f"  {v['name']}" + (f' [note: "{note}"]' if note else ""))
        lines += ["}", ""]

    # Build entity lookup for PK resolution
    entity_map = {e["name"]: e for e in data.get("entities", [])}

    for entity in data.get("entities", []):
        note = entity.get("description", "").replace("'", "\\'")
        pk = _find_pk(entity)
        lines.append(f"Table {entity['name']} [note: '{note}'] {{")
        lines.append(f"  {pk} [pk, note: 'Primary key']")
        for f in entity.get("fields", []):
            # Skip if this is the pk field we already added
            if f["name"] == pk:
                continue
            ftype = _dbml_type(f["type"], enum_names)
            parts = []
            if not f.get("required", False):
                parts.append("null")
            note_parts = []
            if f.get("description"):
                note_parts.append(f["description"])
            if f.get("example"):
                note_parts.append(f"e.g. {f['example']}")
            if note_parts:
                parts.append(f'note: "{"; ".join(note_parts)}"')
            constraint = f" [{', '.join(parts)}]" if parts else ""
            lines.append(f"  {f['name']} {ftype}{constraint}")
        lines += ["}", ""]

    lines.append("// Relationships")
    for rel in data.get("relationships", []):
        sym   = _DBML_REF.get(rel.get("type", "association"), "<>")
        label = rel.get("label", "")
        comment = f"  // {label}" if label else ""
        from_entity = entity_map.get(rel["from"], {})
        to_entity = entity_map.get(rel["to"], {})
        from_pk = _find_pk(from_entity)
        to_pk = _find_pk(to_entity)
        lines.append(f"Ref: {rel['from']}.{from_pk} {sym} {rel['to']}.{to_pk}{comment}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# D2
# ─────────────────────────────────────────────────────────────────────────────

_D2_ARROW = {
    "composition": "->", "aggregation": "->",
    "association": "<->", "dependency": "->",
    "realization": "->", "inheritance": "->",
}

_D2_STYLE = {
    "composition": "style.stroke-dash: 0\nstyle.stroke-width: 2",
    "aggregation": "style.stroke-dash: 3",
    "association": "style.stroke-dash: 0",
    "dependency":  "style.stroke-dash: 5\nstyle.stroke-width: 1",
    "realization": "style.stroke-dash: 5",
    "inheritance": "style.stroke-dash: 0",
}

_D2_VIS_STYLE = {
    "public":   ('"#e8f4fd"', '"#6c8ebf"'),
    "internal": ('"#d5e8d4"', '"#82b366"'),
    "private":  ('"#f8cecc"', '"#b85450"'),
}


def to_d2(data: dict) -> str:
    enums    = data.get("enums", [])
    enum_set = {e["name"] for e in enums}
    lines    = [
        f"# {data.get('module', 'Data Model')}  v{data.get('version', '')}",
        f"# {data.get('description', '')}",
        "",
        "direction: right",
        "",
    ]

    if enums:
        lines += [
            "enums: {",
            '  label: Enumerations',
            '  style.fill: "#fff9e6"',
            '  style.stroke: "#d6b656"',
            "  style.border-radius: 8",
            "",
        ]
        for enum in enums:
            lines += [f"  {enum['name']}: {{", "    shape: class",
                      '    style.fill: "#fff2cc"', '    style.stroke: "#d6b656"']
            for v in enum.get("values", []):
                desc = v.get("description", "").replace('"', "'")
                lines.append(f'    {v["name"]}: "{desc}"')
            lines += ["  }", ""]
        lines += ["}", ""]

    groups: dict[str, list] = {}
    for e in data.get("entities", []):
        groups.setdefault(e.get("visibility", "public"), []).append(e)

    entity_group: dict[str, str] = {}
    for e in data.get("entities", []):
        entity_group[e["name"]] = e.get("visibility", "public") + "_entities"

    for vis_key in ("public", "internal", "private"):
        grp = groups.get(vis_key, [])
        if not grp:
            continue
        fill, stroke = _D2_VIS_STYLE.get(vis_key, ('"#f5f5f5"', '"#666"'))
        lines += [
            f"{vis_key}_entities: {{",
            f'  label: "{vis_key.capitalize()} entities"',
            f"  style.fill: {fill}",
            f"  style.stroke: {stroke}",
            "  style.border-radius: 8",
            "",
        ]
        for entity in grp:
            desc = entity.get("description", "").replace('"', "'")
            lines += [f"  {entity['name']}: {{", "    shape: class", f'    tooltip: "{desc}"']
            for f in entity.get("fields", []):
                suffix = "" if f.get("required", False) else "?"
                lines.append(f"    {f['name']}{suffix}: {f['type']}")
            for method in entity.get("methods", []):
                lines.append(f"    + {method['name']}()")
            lines += ["  }", ""]
        lines += ["}", ""]

    lines.append("# Relationships")
    for i, rel in enumerate(data.get("relationships", [])):
        frm, to  = rel["from"], rel["to"]
        arrow    = _D2_ARROW.get(rel.get("type", "association"), "->")
        card     = rel.get("cardinality", {})
        fl, tl   = card.get("fromLabel", ""), card.get("toLabel", "")
        label    = rel.get("label", "")
        full_lbl = " ".join(filter(None, [fl, label, tl]))
        lbl_str  = f": {full_lbl}" if full_lbl else ""
        frm_path = f"enums.{frm}" if frm in enum_set else f"{entity_group.get(frm, 'public_entities')}.{frm}"
        to_path  = f"enums.{to}"  if to  in enum_set else f"{entity_group.get(to,  'public_entities')}.{to}"
        style_block = _D2_STYLE.get(rel.get("type", "association"), "")
        if style_block:
            lines.append(f"rel_{i}: {frm_path} {arrow} {to_path} {lbl_str} {{")
            for sl in style_block.splitlines():
                lines.append(f"  {sl}")
            lines.append("}")
        else:
            lines.append(f"{frm_path} {arrow} {to_path} {lbl_str}")

    lines.append("# Inheritance")
    entity_map = {e["name"]: e for e in data.get("entities", [])}
    for entity in data.get("entities", []):
        parent = entity.get("extends")
        if parent and parent in entity_map:
            frm_path = f"{entity_group.get(entity['name'], 'public_entities')}.{entity['name']}"
            to_path  = f"{entity_group.get(parent, 'public_entities')}.{parent}"
            lines.append(f"{frm_path} --|> {to_path}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

# Format names → (output extension, converter)
FORMATS = {
    "puml":    (".puml",   to_plantuml),
    "mermaid": (".md",     to_mermaid),
    "drawio":  (".drawio", to_drawio),
    "dbml":    (".dbml",   to_dbml),
    "d2":      (".d2",     to_d2),
}

# Output file name templates — {format}_data_diagram.{ext}
OUTPUT_TEMPLATE = "{format}_data_diagram{ext}"


def main() -> None:
    args = sys.argv[1:]

    # Positional: input [formats] [output_dir]
    input_path = Path(args[0]) if args else Path("DataSpec.json")

    # Second arg: format list or "all"
    fmt_arg  = "all"
    output_dir = None
    if len(args) >= 2:
        candidate = args[1]
        known_keys = set(FORMATS.keys()) | {"all"}
        if any(k in candidate.split(",") for k in known_keys):
            fmt_arg = candidate
            output_dir = args[2] if len(args) >= 3 else None
        else:
            output_dir = candidate

    selected = list(FORMATS.keys()) if fmt_arg == "all" else [
        f.strip() for f in fmt_arg.split(",") if f.strip() in FORMATS
    ]

    if not selected:
        print(f"Unknown format(s): {fmt_arg}")
        print(f"Available: {', '.join(FORMATS)} or 'all'")
        sys.exit(1)

    data = load(input_path)
    print(f"Converting {input_path}  →  {', '.join(selected)}")
    for fmt in selected:
        ext, converter = FORMATS[fmt]
        out_name = OUTPUT_TEMPLATE.format(format=fmt, ext=ext)
        out_path = Path(output_dir) / out_name if output_dir else Path(out_name)
        write(out_path, converter(data))


if __name__ == "__main__":
    main()
