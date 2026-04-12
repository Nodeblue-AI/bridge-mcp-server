"""Bridge MCP Server — FastMCP server for cross-platform SCADA/PLC intelligence."""

from __future__ import annotations

import json

from fastmcp import FastMCP

from ignition_mcp_server.project_source import open_project
from studio5000_mcp_server.l5x_parser import load_l5x

from bridge_mcp_server.correlator import (
    build_correlation,
    find_unmapped,
    load_mapping,
    trace_tag as _trace_tag,
)


def _error(msg: str) -> str:
    return json.dumps({"error": msg})


mcp = FastMCP(
    "Project Automate Bridge",
    instructions=(
        "This server correlates Ignition SCADA projects with Studio 5000 L5X PLC projects. "
        "It maps Ignition OPC tags to their corresponding PLC tags and traces signals "
        "end-to-end from SCADA through to PLC ladder logic and structured text. "
        "Use correlate_projects for a full mapping, trace_tag for deep single-tag analysis, "
        "and find_unmapped_tags to identify commissioning gaps."
    ),
)


@mcp.tool
def ping() -> str:
    """Health check — verify the server is running."""
    return "pong"


@mcp.tool
def correlate_projects(ignition_path: str, l5x_path: str, mapping_file: str = "") -> str:
    """Build a full correlation map between an Ignition project and an L5X PLC project.

    Walks all Ignition OPC tags, maps each to its L5X counterpart via OPC item path
    normalization, and returns matched pairs plus unmatched tags on both sides.

    Args:
        ignition_path: Path to Ignition project directory or .zip export.
        l5x_path: Path to Studio 5000 .l5x file.
        mapping_file: Optional JSON file with explicit tag mappings (overrides convention).
    """
    try:
        ign = open_project(ignition_path)
        l5x = load_l5x(l5x_path)
        mapping = load_mapping(mapping_file) if mapping_file else None
        result = build_correlation(ign, l5x, mapping)
        return json.dumps(result, indent=2)
    except FileNotFoundError as e:
        return _error(str(e))
    except Exception as e:
        return _error(f"Failed to correlate projects: {e}")


@mcp.tool
def trace_tag(ignition_path: str, l5x_path: str, tag_name: str, mapping_file: str = "") -> str:
    """Trace a single tag end-to-end: Ignition config → OPC path → L5X tag → PLC logic.

    Returns the complete signal chain showing where the tag is defined in Ignition,
    what PLC tag it maps to, and every rung/line of PLC logic that references it.

    Args:
        ignition_path: Path to Ignition project directory or .zip export.
        l5x_path: Path to Studio 5000 .l5x file.
        tag_name: Ignition tag name to trace (e.g. "Running", "Conveyors/Line1/Speed").
        mapping_file: Optional JSON file with explicit tag mappings.
    """
    try:
        ign = open_project(ignition_path)
        l5x = load_l5x(l5x_path)
        mapping = load_mapping(mapping_file) if mapping_file else None
        result = _trace_tag(ign, l5x, tag_name, mapping)
        return json.dumps(result, indent=2)
    except FileNotFoundError as e:
        return _error(str(e))
    except Exception as e:
        return _error(f"Failed to trace tag: {e}")


@mcp.tool
def find_unmapped_tags(ignition_path: str, l5x_path: str, mapping_file: str = "") -> str:
    """Find tags that exist on one side but not the other — commissioning gap analysis.

    Returns Ignition OPC tags with no L5X match and L5X tags with no Ignition reference.

    Args:
        ignition_path: Path to Ignition project directory or .zip export.
        l5x_path: Path to Studio 5000 .l5x file.
        mapping_file: Optional JSON file with explicit tag mappings.
    """
    try:
        ign = open_project(ignition_path)
        l5x = load_l5x(l5x_path)
        mapping = load_mapping(mapping_file) if mapping_file else None
        result = find_unmapped(ign, l5x, mapping)
        return json.dumps(result, indent=2)
    except FileNotFoundError as e:
        return _error(str(e))
    except Exception as e:
        return _error(f"Failed to find unmapped tags: {e}")
