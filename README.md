# bridge-mcp-server

> Cross-platform intelligence bridge — correlate Ignition SCADA tags with Studio 5000 PLC logic end-to-end.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/protocol-MCP-green.svg)](https://modelcontextprotocol.io/)

---

## What This Does

`bridge-mcp-server` connects [ignition-mcp-server](https://github.com/Nodeblue-AI/ignition-mcp-server) and [studio5000-mcp-server](https://github.com/Nodeblue-AI/studio5000-mcp-server) via the [Model Context Protocol](https://modelcontextprotocol.io/). It gives AI agents the ability to:

- **Correlate** — build a full tag-by-tag map between an Ignition SCADA project and a Studio 5000 L5X PLC export
- **Trace** — follow a single tag end-to-end from Ignition config → OPC item path → L5X tag → every rung of PLC logic that references it
- **Find gaps** — identify commissioning mismatches: Ignition OPC tags with no PLC counterpart, and L5X tags with no Ignition reference

It maps Ignition OPC tag paths to L5X tag names using convention-based normalization (with optional explicit mapping file override), then leverages the Studio 5000 cross-reference engine to find every line of PLC logic that references the matched tag.

## Why This Exists

Ignition and Studio 5000 are the two most common platforms in North American industrial automation, and they almost always exist together — yet there's no tooling that connects them. Commissioning engineers manually cross-reference tag databases in spreadsheets. This server automates that.

Part of [Project Automate](https://github.com/md-automation/project-automate) by [Nodeblue](https://www.nodeblue.ai).

---

## Installation

Install from source:

```bash
git clone https://github.com/Nodeblue-AI/bridge-mcp-server.git
cd bridge-mcp-server
pip install -e .
```

This also installs `ignition-mcp-server` and `studio5000-mcp-server` as dependencies.

Requires Python 3.10+.

> **Note:** `pip install bridge-mcp-server` from PyPI is coming soon. For now, install from source as shown above.

---

## Quick Start

### stdio (local — kiro-cli, Claude Desktop, Claude Code)

```bash
bridge-mcp-server
```

### SSE (remote — server on one machine, agent on another)

```bash
bridge-mcp-server --transport sse --port 8082
```

---

## Configuration

### kiro-cli

Add to your `~/.kiro/settings.json`:

```json
{
  "mcpServers": {
    "bridge": {
      "command": "bridge-mcp-server",
      "args": []
    }
  }
}
```

### Claude Desktop

Add to your Claude Desktop MCP config:

```json
{
  "mcpServers": {
    "bridge": {
      "command": "bridge-mcp-server",
      "args": []
    }
  }
}
```

### SSE (remote)

Start the server on your engineering workstation:

```bash
bridge-mcp-server --transport sse --host 0.0.0.0 --port 8082
```

Connect from any MCP client using the SSE URL: `http://<host>:8082/sse`

---

## Available Tools

### `ping`
Health check. Returns `"pong"`.

### `correlate_projects(ignition_path, l5x_path, mapping_file?)`
Build a full correlation map between an Ignition project and an L5X PLC project.

```
correlate_projects("/path/to/ignition-project", "/path/to/plc.l5x")
```

Returns:
```json
{
  "matched": [
    {
      "ignitionPath": "Conveyors/Line1/Running",
      "opcItemPath": "ns=1;s=[PLC]Motor_1.Running",
      "l5xTag": "Motor_1",
      "l5xMember": "Motor_1.Running",
      "l5xDataType": "Motor_UDT",
      "l5xScope": "controller"
    }
  ],
  "ignitionOnly": [],
  "l5xOnly": [
    {"name": "EmergencyStop", "dataType": "BOOL", "scope": "controller"}
  ],
  "stats": {"matched": 3, "ignitionOnly": 0, "l5xOnly": 5, "totalIgnitionOpc": 3, "totalL5x": 8}
}
```

### `trace_tag(ignition_path, l5x_path, tag_name, mapping_file?)`
Deep end-to-end trace of a single tag from SCADA to PLC logic.

```
trace_tag("/path/to/ignition-project", "/path/to/plc.l5x", "Running")
```

Returns the complete signal chain: Ignition tag config → OPC item path → L5X tag details → every rung/line of PLC logic that references it.

### `find_unmapped_tags(ignition_path, l5x_path, mapping_file?)`
Identify commissioning gaps — tags that exist on one side but not the other.

```
find_unmapped_tags("/path/to/ignition-project", "/path/to/plc.l5x")
```

---

## OPC Path Mapping

The bridge uses convention-based mapping by default:

| Ignition OPC Item Path | L5X Tag Name |
|---|---|
| `ns=1;s=[PLC]Motor_1.Running` | `Motor_1.Running` |
| `[PLC]Motor_1.Running` | `Motor_1.Running` |
| `[PLC]Program:MainProgram.StartPB` | `Program:MainProgram.StartPB` |
| `Motor_1.Running` | `Motor_1.Running` (passthrough) |

For complex setups (aliased tags, scaled values), provide a JSON mapping file:

```json
{
  "ns=1;s=[PLC]Custom_Alias": "Motor_1.Running",
  "ns=1;s=[PLC]Scaled_Speed": "LineSpeed"
}
```

Pass it via `mapping_file` parameter on any tool.

---

## Use Cases

### Pre-commissioning validation
> "Show me every Ignition OPC tag and its matching PLC tag — I need to verify the full correlation before we go live."

```
Agent calls: correlate_projects("/projects/MyPlant", "/plc/MainPLC.l5x")
```

### Alarm root-cause analysis
> "The Conveyors/Line1/Running tag is triggering an alarm in Ignition. What PLC logic drives it?"

```
Agent calls: trace_tag("/projects/MyPlant", "/plc/MainPLC.l5x", "Running")

Agent: The Ignition tag Conveyors/Line1/Running maps to PLC tag Motor_1.Running
via OPC path ns=1;s=[SampleController]Motor_1.Running.

Motor_1 is a Motor_UDT instance. Motor_1.Running is referenced in:
- MainProgram/MainRoutine rung 1: Motor_Control AOI call
- MainProgram/MainRoutine rung 2: Fault detection branch
- MainProgram/FaultHandler line 1: IF Motor_1.Faulted THEN...

The Motor_Control AOI sets Running from MotorFeedback (rung 4).
```

### Commissioning gap analysis
> "Which PLC tags exist in the L5X but aren't wired up in Ignition yet? We need to close gaps before FAT."

```
Agent calls: find_unmapped_tags("/projects/MyPlant", "/plc/MainPLC.l5x")
```

---

## Roadmap

### v0.4 — Cross-Platform Correlation ✅
- [x] `correlate_projects` — full tag-by-tag map between Ignition and L5X
- [x] `trace_tag` — end-to-end signal chain from SCADA to PLC logic
- [x] `find_unmapped_tags` — commissioning gap detection
- [x] Convention-based OPC path → L5X tag name normalization
- [x] Optional JSON mapping file for explicit overrides
- [x] Correlation index caching per project pair
- [x] stdio and SSE transport support

### Future
- [ ] Multi-PLC correlation (multiple L5X files against one Ignition project)
- [ ] Alarm pipeline → PLC tag tracing (alarm source → trigger logic)
- [ ] Mapping file auto-generation from correlation results
- [ ] Local LLM support for air-gapped deployments

---

## Development

```bash
git clone https://github.com/Nodeblue-AI/bridge-mcp-server.git
cd bridge-mcp-server
pip install -e .
pip install pytest
pytest tests/ -v
```

### Project Structure

```
src/bridge_mcp_server/
├── __init__.py       # v0.4.0
├── __main__.py       # CLI entry point (stdio/SSE)
├── server.py         # FastMCP with 4 tools (ping + 3 correlation tools)
└── correlator.py     # OPC path normalizer + correlation engine

tests/
└── test_correlator.py
```

---

## License

MIT — see [LICENSE](LICENSE).

---

<p align="center">
  <i>Built by <a href="https://www.nodeblue.ai">Nodeblue</a> — Engineering-driven technology across software, industrial automation, and applied research.</i>
</p>
