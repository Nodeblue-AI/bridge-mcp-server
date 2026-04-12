# Changelog

## [0.4.0] - 2026-04-12

### Added
- Initial release of bridge-mcp-server
- **`correlate_projects`** — build full correlation map between Ignition SCADA and Studio 5000 L5X projects, matching OPC tags to PLC tags
- **`trace_tag`** — deep end-to-end trace of a single tag from Ignition config through OPC path to every line of PLC logic
- **`find_unmapped_tags`** — identify commissioning gaps (Ignition OPC tags with no PLC match, L5X tags with no Ignition reference)
- Convention-based OPC path → L5X tag name normalization (strips `ns=N;s=` prefix and `[ServerName]` brackets)
- Optional JSON mapping file for explicit overrides on complex setups
- Correlation index caching per project pair
- stdio and SSE transport support
- MIT license
