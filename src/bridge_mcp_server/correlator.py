"""Cross-platform correlator — map Ignition OPC tags to L5X PLC tags."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ignition_mcp_server.project_source import ProjectSource
from studio5000_mcp_server.l5x_parser import L5XProject
from studio5000_mcp_server.parsers import tags as l5x_tags, xref

# ── OPC Path Normalization ──────────────────────────────────

_OPC_NS_PREFIX = re.compile(r"^ns=\d+;s=")


def normalize_opc_path(opc_item_path: str) -> str:
    """Convert an Ignition OPC item path to an L5X tag reference.

    Examples:
        "ns=1;s=[PLC]Motor_1.Running" → "Motor_1.Running"
        "[PLC]Motor_1.Running"        → "Motor_1.Running"
        "[PLC]Program:MainProgram.X"  → "Program:MainProgram.X"
        "Motor_1.Running"             → "Motor_1.Running"  (passthrough)
    """
    path = _OPC_NS_PREFIX.sub("", opc_item_path)
    # Strip [ServerName] prefix
    bracket_end = path.rfind("]")
    if bracket_end >= 0:
        path = path[bracket_end + 1:]
    return path


def load_mapping(path: str) -> dict[str, str]:
    """Load an explicit OPC→L5X tag mapping from a JSON file."""
    return json.loads(Path(path).read_text())


def resolve_tag(opc_item_path: str, mapping: dict[str, str] | None = None) -> str:
    """Resolve an OPC item path to an L5X tag name. Mapping overrides convention."""
    if mapping and opc_item_path in mapping:
        return mapping[opc_item_path]
    return normalize_opc_path(opc_item_path)


# ── Ignition Tag Tree Walker ────────────────────────────────


def _walk_opc_tags(
    source: ProjectSource, provider: str = "default"
) -> list[dict[str, Any]]:
    """Walk the Ignition tag tree and extract all OPC-sourced tags with their paths."""
    try:
        data = source.read_json(f"tags/{provider}/tags.json")
    except (FileNotFoundError, KeyError):
        return []

    tag_list = data.get("tags", data) if isinstance(data, dict) else data
    if not isinstance(tag_list, list):
        return []

    results: list[dict[str, Any]] = []
    _walk_recursive(tag_list, "", results)
    return results


def _walk_recursive(
    tags: list[dict[str, Any]], prefix: str, out: list[dict[str, Any]]
) -> None:
    for tag in tags:
        name = tag.get("name", "")
        path = f"{prefix}/{name}" if prefix else name
        if tag.get("valueSource") == "opc" and "opcItemPath" in tag:
            out.append({
                "ignitionPath": path,
                "name": name,
                "dataType": tag.get("dataType", ""),
                "opcItemPath": tag["opcItemPath"],
                "opcServer": tag.get("opcServer", ""),
            })
        children = tag.get("tags", [])
        if children:
            _walk_recursive(children, path, out)


# ── L5X Tag Index ───────────────────────────────────────────


def _build_l5x_tag_set(project: L5XProject) -> dict[str, dict[str, Any]]:
    """Build a lookup of all L5X tags (controller + program-scoped) keyed by name."""
    all_tags = l5x_tags.list_tags(project)
    index: dict[str, dict[str, Any]] = {}
    for t in all_tags:
        index[t["name"]] = t
    return index


# ── Correlation Engine ──────────────────────────────────────

_correlation_cache: dict[tuple[int, int], dict[str, Any]] = {}


def build_correlation(
    ignition_source: ProjectSource,
    l5x_project: L5XProject,
    mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build the full correlation index between Ignition and L5X projects."""
    key = (id(ignition_source), id(l5x_project))
    if key in _correlation_cache and mapping is None:
        return _correlation_cache[key]

    opc_tags = _walk_opc_tags(ignition_source)
    l5x_index = _build_l5x_tag_set(l5x_project)

    matched: list[dict[str, Any]] = []
    ignition_only: list[dict[str, Any]] = []
    matched_l5x_names: set[str] = set()

    for opc_tag in opc_tags:
        l5x_name = resolve_tag(opc_tag["opcItemPath"], mapping)
        # Try exact match first, then try base tag (before the dot)
        l5x_tag = l5x_index.get(l5x_name)
        base_name = l5x_name.split(".")[0] if "." in l5x_name else l5x_name
        if l5x_tag is None:
            l5x_tag = l5x_index.get(base_name)

        if l5x_tag is not None:
            matched.append({
                "ignitionPath": opc_tag["ignitionPath"],
                "opcItemPath": opc_tag["opcItemPath"],
                "l5xTag": base_name,
                "l5xMember": l5x_name if l5x_name != base_name else None,
                "l5xDataType": l5x_tag.get("dataType", ""),
                "l5xScope": l5x_tag.get("scope", ""),
            })
            matched_l5x_names.add(base_name)
        else:
            ignition_only.append({
                "ignitionPath": opc_tag["ignitionPath"],
                "opcItemPath": opc_tag["opcItemPath"],
                "resolvedL5xName": l5x_name,
            })

    l5x_only = [
        {"name": t["name"], "dataType": t.get("dataType", ""), "scope": t.get("scope", "")}
        for t in l5x_index.values()
        if t["name"] not in matched_l5x_names
    ]

    result = {
        "matched": matched,
        "ignitionOnly": ignition_only,
        "l5xOnly": l5x_only,
        "stats": {
            "matched": len(matched),
            "ignitionOnly": len(ignition_only),
            "l5xOnly": len(l5x_only),
            "totalIgnitionOpc": len(opc_tags),
            "totalL5x": len(l5x_index),
        },
    }

    if mapping is None:
        _correlation_cache[key] = result
    return result


# ── Trace Tag ───────────────────────────────────────────────


def _find_ignition_tag(
    source: ProjectSource, tag_name: str
) -> dict[str, Any] | None:
    """Find an Ignition tag by name (searches recursively through all OPC tags)."""
    opc_tags = _walk_opc_tags(source)
    # Try exact name match first, then path match
    for t in opc_tags:
        if t["name"] == tag_name:
            return t
    for t in opc_tags:
        if t["ignitionPath"] == tag_name or t["ignitionPath"].endswith(f"/{tag_name}"):
            return t
    return None


def trace_tag(
    ignition_source: ProjectSource,
    l5x_project: L5XProject,
    tag_name: str,
    mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Trace a single tag end-to-end from Ignition through to PLC logic."""
    ign_tag = _find_ignition_tag(ignition_source, tag_name)
    if ign_tag is None:
        return {"error": f"Tag '{tag_name}' not found in Ignition project (OPC tags only)"}

    result: dict[str, Any] = {"ignitionTag": ign_tag}

    opc_path = ign_tag.get("opcItemPath", "")
    if not opc_path:
        result["note"] = "Tag is not OPC-sourced — no PLC mapping available"
        return result

    result["opcPath"] = opc_path
    l5x_name = resolve_tag(opc_path, mapping)
    result["l5xTagName"] = l5x_name

    # Look up L5X tag details
    l5x_index = _build_l5x_tag_set(l5x_project)
    base_name = l5x_name.split(".")[0] if "." in l5x_name else l5x_name
    l5x_tag = l5x_index.get(l5x_name) or l5x_index.get(base_name)

    if l5x_tag is None:
        result["note"] = f"No PLC tag match found for '{l5x_name}'"
        return result

    result["l5xTag"] = l5x_tag

    # Find all PLC logic references
    refs = xref.search_xref(l5x_project, re.escape(base_name))
    if refs:
        result["plcReferences"] = refs

    return result


# ── Find Unmapped ───────────────────────────────────────────


def find_unmapped(
    ignition_source: ProjectSource,
    l5x_project: L5XProject,
    mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Find tags that exist on one side but not the other."""
    corr = build_correlation(ignition_source, l5x_project, mapping)
    return {
        "ignitionUnmapped": corr["ignitionOnly"],
        "l5xUnmapped": corr["l5xOnly"],
        "stats": {
            "ignitionUnmapped": corr["stats"]["ignitionOnly"],
            "l5xUnmapped": corr["stats"]["l5xOnly"],
        },
    }
