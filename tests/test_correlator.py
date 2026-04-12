"""Tests for bridge-mcp-server."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bridge_mcp_server.correlator import (
    build_correlation,
    find_unmapped,
    load_mapping,
    normalize_opc_path,
    resolve_tag,
    trace_tag,
    _correlation_cache,
)
from ignition_mcp_server.project_source import open_project
from studio5000_mcp_server.l5x_parser import load_l5x

# Fixtures from both servers
IGN_FIXTURE = Path(__file__).parent / "../../ignition-mcp-server/tests/fixtures/sample-project"
L5X_FIXTURE = Path(__file__).parent / "../../studio5000-mcp-server/tests/fixtures/sample.l5x"


@pytest.fixture(autouse=True)
def _clear_caches():
    open_project.cache_clear()
    load_l5x.cache_clear()
    _correlation_cache.clear()


# ── OPC Path Normalization ──────────────────────────────────


class TestNormalizeOpcPath:
    def test_full_ns_prefix(self):
        assert normalize_opc_path("ns=1;s=[PLC]Motor_1.Running") == "Motor_1.Running"

    def test_bracket_only(self):
        assert normalize_opc_path("[PLC]Motor_1.Running") == "Motor_1.Running"

    def test_program_scoped(self):
        assert normalize_opc_path("[PLC]Program:MainProgram.StartPB") == "Program:MainProgram.StartPB"

    def test_passthrough(self):
        assert normalize_opc_path("Motor_1.Running") == "Motor_1.Running"

    def test_ns2_prefix(self):
        assert normalize_opc_path("ns=2;s=[Controller]Tag") == "Tag"

    def test_nested_brackets(self):
        assert normalize_opc_path("ns=1;s=[My PLC]Motor_1") == "Motor_1"

    def test_empty_string(self):
        assert normalize_opc_path("") == ""


class TestResolveTag:
    def test_no_mapping(self):
        assert resolve_tag("ns=1;s=[PLC]Motor_1.Running") == "Motor_1.Running"

    def test_mapping_override(self):
        mapping = {"ns=1;s=[PLC]Custom": "Motor_1.Running"}
        assert resolve_tag("ns=1;s=[PLC]Custom", mapping) == "Motor_1.Running"

    def test_mapping_miss_falls_through(self):
        mapping = {"other_path": "other_tag"}
        assert resolve_tag("ns=1;s=[PLC]Motor_1.Running", mapping) == "Motor_1.Running"

    def test_none_mapping(self):
        assert resolve_tag("[PLC]Tag", None) == "Tag"


class TestLoadMapping:
    def test_load_mapping(self, tmp_path):
        f = tmp_path / "map.json"
        f.write_text('{"a": "b"}')
        assert load_mapping(str(f)) == {"a": "b"}


# ── Correlation Engine ──────────────────────────────────────


class TestCorrelation:
    @pytest.fixture
    def ign(self):
        return open_project(str(IGN_FIXTURE))

    @pytest.fixture
    def l5x(self):
        return load_l5x(str(L5X_FIXTURE))

    def test_finds_matches(self, ign, l5x):
        result = build_correlation(ign, l5x)
        assert result["stats"]["matched"] > 0
        matched_l5x = {m["l5xTag"] for m in result["matched"]}
        assert "Motor_1" in matched_l5x

    def test_matched_has_opc_path(self, ign, l5x):
        result = build_correlation(ign, l5x)
        for m in result["matched"]:
            assert "opcItemPath" in m
            assert "ignitionPath" in m

    def test_l5x_only_has_unmatched(self, ign, l5x):
        result = build_correlation(ign, l5x)
        l5x_only_names = {t["name"] for t in result["l5xOnly"]}
        # EmergencyStop exists in L5X but has no Ignition OPC tag
        assert "EmergencyStop" in l5x_only_names

    def test_stats_totals(self, ign, l5x):
        result = build_correlation(ign, l5x)
        s = result["stats"]
        assert s["matched"] + s["ignitionOnly"] == s["totalIgnitionOpc"]

    def test_caching(self, ign, l5x):
        r1 = build_correlation(ign, l5x)
        r2 = build_correlation(ign, l5x)
        assert r1 is r2


# ── Trace Tag ───────────────────────────────────────────────


class TestTraceTag:
    @pytest.fixture
    def ign(self):
        return open_project(str(IGN_FIXTURE))

    @pytest.fixture
    def l5x(self):
        return load_l5x(str(L5X_FIXTURE))

    def test_trace_opc_tag(self, ign, l5x):
        result = trace_tag(ign, l5x, "Running")
        assert "ignitionTag" in result
        assert "opcPath" in result
        assert "l5xTag" in result
        assert "plcReferences" in result
        assert len(result["plcReferences"]) > 0

    def test_trace_by_path(self, ign, l5x):
        result = trace_tag(ign, l5x, "Conveyors/Line1/Speed")
        assert result["ignitionTag"]["name"] == "Speed"
        assert "l5xTagName" in result

    def test_tag_not_found(self, ign, l5x):
        result = trace_tag(ign, l5x, "NonexistentTag")
        assert "error" in result

    def test_trace_returns_l5x_details(self, ign, l5x):
        result = trace_tag(ign, l5x, "Faulted")
        assert "l5xTag" in result
        assert result["l5xTag"]["name"] == "Motor_1"


# ── Find Unmapped ───────────────────────────────────────────


class TestFindUnmapped:
    @pytest.fixture
    def ign(self):
        return open_project(str(IGN_FIXTURE))

    @pytest.fixture
    def l5x(self):
        return load_l5x(str(L5X_FIXTURE))

    def test_finds_l5x_unmapped(self, ign, l5x):
        result = find_unmapped(ign, l5x)
        l5x_names = {t["name"] for t in result["l5xUnmapped"]}
        assert "EmergencyStop" in l5x_names

    def test_stats(self, ign, l5x):
        result = find_unmapped(ign, l5x)
        assert result["stats"]["l5xUnmapped"] > 0

    def test_structure(self, ign, l5x):
        result = find_unmapped(ign, l5x)
        assert "ignitionUnmapped" in result
        assert "l5xUnmapped" in result
        assert "stats" in result


# ── Server Integration ──────────────────────────────────────


class TestServerIntegration:
    def test_ping(self):
        from bridge_mcp_server.server import ping
        assert ping() == "pong"

    def test_correlate_tool(self):
        from bridge_mcp_server.server import correlate_projects
        result = json.loads(correlate_projects(str(IGN_FIXTURE), str(L5X_FIXTURE)))
        assert "stats" in result
        assert result["stats"]["matched"] > 0

    def test_trace_tool(self):
        from bridge_mcp_server.server import trace_tag as trace_tool
        result = json.loads(trace_tool(str(IGN_FIXTURE), str(L5X_FIXTURE), "Running"))
        assert "ignitionTag" in result

    def test_find_unmapped_tool(self):
        from bridge_mcp_server.server import find_unmapped_tags
        result = json.loads(find_unmapped_tags(str(IGN_FIXTURE), str(L5X_FIXTURE)))
        assert "l5xUnmapped" in result

    def test_bad_ignition_path(self):
        from bridge_mcp_server.server import correlate_projects
        result = json.loads(correlate_projects("/nonexistent", str(L5X_FIXTURE)))
        assert "error" in result

    def test_bad_l5x_path(self):
        from bridge_mcp_server.server import trace_tag as trace_tool
        result = json.loads(trace_tool(str(IGN_FIXTURE), "/nonexistent.l5x", "Running"))
        assert "error" in result
