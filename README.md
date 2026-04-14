# bridge-mcp-server

> Cross-platform intelligence bridge — correlate Ignition SCADA tags with Studio 5000 PLC logic end-to-end.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/protocol-MCP-green.svg)](https://modelcontextprotocol.io/)

---

## What This Does

`bridge-mcp-server` connects [ignition-mcp-server](https://github.com/nodeblue-ai/ignition-mcp-server) and [studio5000-mcp-server](https://github.com/nodeblue-ai/studio5000-mcp-server) to answer questions like:

- "Give me a full correlation map between the Ignition project and the PLC export so I can see what's linked."
- "Which PLC tags exist in the L5X but have no corresponding Ignition tag?"
- "Trace this Ignition alarm back to the PLC logic so I can see what's actually triggering it."

It maps Ignition OPC tag paths to L5X tag names using convention-based normalization (with optional explicit mapping file override), then leverages the Studio 5000 cross-reference engine to find every line of PLC logic that references the matched tag.

Part of [Project Automate](https://github.com/nodeblue-ai/project-automate) by [Nodeblue](https://www.nodeblue.ai).

---

## Installation

```bash
pip install bridge-mcp-server
```

This automatically installs both `ignition-mcp-server` and `studio5000-mcp-server` as dependencies.

---

## Quick Start

### stdio (local)

```bash
bridge-mcp-server
```

### SSE (remote)

```bash
bridge-mcp-server --transport sse --port 8082
```

---

## Configuration

### kiro-cli

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
  "stats": {"matched": 3, "ignitionOnly": 0, "l5xOnly": 5}
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

## Example Conversation

```
You: What PLC logic drives the Conveyors/Line1/Running tag in Ignition?

Agent calls: trace_tag("/projects/MyPlant", "/plc/MainPLC.l5x", "Running")

Agent: The Ignition tag Conveyors/Line1/Running maps to PLC tag Motor_1.Running
via OPC path ns=1;s=[SampleController]Motor_1.Running.

Motor_1 is a Motor_UDT instance. Motor_1.Running is referenced in:
- MainProgram/MainRoutine rung 1: Motor_Control AOI call
- MainProgram/MainRoutine rung 2: Fault detection branch
- MainProgram/FaultHandler line 1: IF Motor_1.Faulted THEN...

The Motor_Control AOI sets Running from MotorFeedback (rung 4).
```

---

## Project Structure

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

## Development

```bash
git clone https://github.com/nodeblue-ai/bridge-mcp-server.git
cd bridge-mcp-server
pip install -e .
pip install pytest
pytest tests/ -v
```

---

## License

[MIT](LICENSE)

---

<p align="center">
  <i>Built by <a href="https://www.nodeblue.ai">Nodeblue</a> — Engineering-driven technology across software, industrial automation, and applied research.</i>
</p>
