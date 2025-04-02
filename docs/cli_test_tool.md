# Testing MCP Tools with the CLI

The `mcp-registry test-tool` command provides a powerful interface for testing MCP tools either interactively or programmatically. This guide explains how to use this command effectively.

## Overview

MCP tools are functions exposed by MCP servers that can be called with specific parameters. The `test-tool` command allows you to:

1. Discover available tools
2. Interactively input parameters with guidance
3. Test tools with pre-defined parameters
4. Format and view tool results

## Command Syntax

```bash
mcp-registry test-tool [OPTIONS] TOOL_PATH
```

Where `TOOL_PATH` is in the format `server__tool` (e.g., `exa__search`).

### Options

| Option | Description |
|--------|-------------|
| `--input`, `-i` | Input parameters as JSON string |
| `--input-file`, `-f` | Read input parameters from file |
| `--raw`, `-r` | Output raw JSON response |
| `--timeout`, `-t` | Timeout in seconds (default: 30) |
| `--non-interactive`, `-n` | Disable interactive mode |

## Usage Examples

### Discovering Available Tools

To see all available tools across all servers:

```bash
mcp-registry test-tool
```

To see all tools for a specific server:

```bash
mcp-registry test-tool exa
```

### Interactive Mode

When no input is provided, the command enters interactive mode:

```bash
mcp-registry test-tool exa__search
```

Output:
```
Interactive mode for tool: exa__search
Please enter values for the following parameters:
query (string, required): what is MCP protocol
numResults (number, optional):

Parameters to be sent:
{
  "query": "what is MCP protocol"
}
Send these parameters? [Y/n]:
```

The interactive mode:
- Shows parameter types and requirements
- Guides you through input for each parameter
- Provides a preview of parameters before sending
- Allows confirmation or cancellation

### Non-Interactive Mode

#### Using JSON String

```bash
mcp-registry test-tool exa__search --input '{"query": "what is MCP protocol", "numResults": 3}'
```

#### Using Input File

First, create a JSON file with parameters:

```bash
echo '{"query": "what is MCP protocol", "numResults": 3}' > params.json
```

Then use it with the command:

```bash
mcp-registry test-tool exa__search --input-file params.json
```

#### Using Stdin

```bash
echo '{"query": "what is MCP protocol"}' | mcp-registry test-tool exa__search
```

#### Force Non-Interactive Mode

```bash
mcp-registry test-tool exa__search --non-interactive
```

This will use empty parameters if no input is provided.

## Raw Output

By default, the command formats the output for readability. To get the raw JSON response:

```bash
mcp-registry test-tool exa__search --input '{"query": "test"}' --raw
```

## Programmatic Tool Calling

For developers who need to call tools programmatically in their own Python code:

```python
from mcp_registry.compound import MCPServerSettings, ServerRegistry, MCPAggregator

# Create registry with required server
server_settings = MCPServerSettings(type="stdio", command="...", args=["..."])
registry = ServerRegistry({"server_name": server_settings})
aggregator = MCPAggregator(registry)

# Call tool programmatically
result = await aggregator.call_tool("server_name__tool_name", {"param": "value"})
```

## Troubleshooting

### Tool Not Found

If you see an error like:
```
Error: Tool path must be in format 'server__tool'
```

Make sure:
1. You're using the correct format: `server__tool`
2. The server name is correct
3. The tool exists on that server

Run `mcp-registry list-tools` to see all available tools.

### Server Not Found

If you see an error like:
```
Error: Server 'nonexistent' not found in configuration
```

Make sure the server is registered. Run `mcp-registry list` to see all registered servers.

### Parameter Validation Errors

When using non-interactive mode, if your parameters don't match the tool's schema, you'll see an error from the server. Use interactive mode first to understand the required parameters.

## Advanced Usage

### Timeouts

For long-running tools, you can increase the timeout:

```bash
mcp-registry test-tool slow_server__long_process --timeout 120
```

This sets a 2-minute timeout instead of the default 30 seconds.

### Persistent Connections

By default, the `test-tool` command uses temporary connections. For more efficient testing of multiple tools from the same server, consider writing a script that uses the MCPAggregator with persistent connections.

## Next Steps

- Explore available tools with `mcp-registry list-tools`
- Try interactive mode to understand tool parameters
- Create scripts for frequently used tool calls
- Read the API documentation for programmatic tool calling