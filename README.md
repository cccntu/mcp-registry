# MCP Registry

A tool that solves key challenges when working with multiple [Model Context Protocol (MCP)](https://modelcontextprotocol.io) servers:

## Key Problems Solved

### 1. Simplified MCP Server Configuration Management
**Problem**: Managing MCP server configurations typically requires manual JSON editing, which is error-prone and tedious.  
**Solution**: MCP Registry provides an intuitive CLI interface to add, remove, and edit server configurations without directly editing JSON files.

### 2. Selective Server and Tool Exposure
**Problem**: When you have a large configuration with many MCP servers and tools, there's no easy way to expose only a subset without creating and maintaining multiple configuration files.  
**Solution**: MCP Registry lets you run a compound server that includes only specific servers and tools from your main configuration, without creating separate config files.

### 3. Synchronized Settings Across Tools
**Problem**: Different MCP clients (Claude Desktop, Cursor, Claude Code) each maintain their own configurations, requiring duplicate setup.  
**Solution**: Configure servers once using MCP Registry and reference them from any client, ensuring consistent settings everywhere.

MCP Registry serves as both a command-line tool for configuration management and a Python library for programmatic access to your MCP servers.

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
  - [CLI Tool](#1-as-a-cli-tool)
    - [Basic Commands](#basic-commands)
    - [Advanced Server Configuration](#advanced-server-configuration)
    - [Integration with MCP Clients](#integration-with-mcp-clients)
  - [Configuration](#configuration)
    - [Config File Location](#config-file-location)
    - [Connection Management](#connection-management)
  - [Library](#2-as-a-library)
- [Testing](#testing)
  - [Quick Server Test](#quick-server-test)
  - [Testing Tools](#testing-tools)
- [Development](#development)
- [Documentation](#documentation)
- [License](#license)

## Installation

From PyPI:
```bash
pip install mcp-registry
```

From source:
```bash
git clone https://github.com/your-username/mcp-registry.git
cd mcp-registry
git submodule update --init --recursive  # Required for testing
pip install -e .
```

## Usage

### 1. As a CLI Tool

The command-line interface provides an intuitive way to manage your MCP server configurations:

#### Basic Commands

```bash
# Initialize config
mcp-registry init

# Add servers to your configuration
mcp-registry add everything npx -y @modelcontextprotocol/server-everything
mcp-registry add filesystem npx -y @modelcontextprotocol/server-filesystem

# List all configured servers
mcp-registry list

# Edit configuration directly with your preferred editor
# (validates JSON when saving and keeps a backup)
mcp-registry edit

# List tools provided by configured servers
mcp-registry list-tools                # List all tools from all servers
mcp-registry list-tools everything     # List tools from a specific server
mcp-registry list-tools -v             # Show parameter information 
mcp-registry list-tools -vv            # Show full details without truncation

# Test specific tools interactively or programmatically
mcp-registry test-tool everything__add     # Interactive mode
mcp-registry test-tool everything__add --input '{"a": 5, "b": 3}'  # With JSON input
echo '{"a": 10, "b": 20}' | mcp-registry test-tool everything__add  # With piped input

# Run a compound server that exposes ALL configured servers
# (tools will be available as "server_name__tool_name")
mcp-registry serve

# Run a compound server with ONLY SPECIFIC servers from your config
# This is key for selectively exposing only certain servers!
mcp-registry serve everything filesystem

# Test your compound server with the inspector tool
npx -y @modelcontextprotocol/inspector mcp-registry serve
```

#### Advanced Server Configuration

When adding servers with complex commands:

```bash
# Method 1: Use -- to separate mcp-registry options from the command's own flags
mcp-registry add myserver -- node server.js --port 3000 --verbose

# Method 2: Use quotes around the command with its arguments
mcp-registry add myserver "npm run server --port 8080"

# Method 3: Use the interactive mode for complex commands
mcp-registry add
# Then enter details when prompted
```

#### Integration with MCP Clients

A key benefit of MCP Registry is the ability to maintain one configuration and reference it from multiple clients:

```bash
# Add ALL your configured servers to Claude Code
claude mcp add servers mcp-registry serve

# Add ONLY SPECIFIC servers to Claude Code 
# (selective exposure without creating a separate config!)
claude mcp add servers mcp-registry serve everything filesystem

# Similarly for other MCP-compatible clients
# This ensures synchronized server configurations across all your tools
```

### Configuration

The config file format is the same as Claude Desktop / Claude Code:

```json
{
  "mcpServers": {
    "everything": {
      "type": "stdio", 
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-everything"]
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem"]
      // type defaults to "stdio" when not specified
    },
    "remote": {
      "type": "sse",
      "url": "http://localhost:8000/sse"
    }
  }
}
```

The `type` field is optional and defaults to "stdio" if not specified.

#### Config File Location

By default, the config file is located at `~/.config/mcp_registry/mcp_registry_config.json`.

You can customize the location using the `MCP_REGISTRY_CONFIG` environment variable:
```bash
export MCP_REGISTRY_CONFIG=$HOME/'Library/Application Support/Claude/claude_desktop_config.json'
```

To check the current config file location:
```bash
mcp-registry show-config-path
```

#### Connection Management

MCP Registry supports two connection modes:

1. **Temporary Connections (default)**:
   - Creates and destroys connections for each tool call
   - Simple and ensures clean resource management
   - Optimized to only load the specific server needed for each call
   - Less efficient for multiple calls to the same server

2. **Persistent Connections**:
   - Maintains connections for multiple tool calls
   - Significantly improves performance when making multiple calls, especially for servers with costly initialization
   - Uses the context manager pattern (`async with`) for proper resource management
   - Automatically closes connections when the context is exited

The library examples below demonstrate both connection modes. For a detailed comparison, see the [persistent connections example](examples/persistent_connections_example.py).

### 2. As a Library

Use MCP Registry in your code to load and interact with multiple servers:

```python
from mcp_registry import ServerRegistry, MCPAggregator, get_config_path
import asyncio

async def main():
    # Load servers from config (using the current config path)
    registry = ServerRegistry.from_config(get_config_path())

    # Method 1: Temporary connections (default)
    # Each tool call creates and destroys a new connection
    aggregator = MCPAggregator(registry)
    tools = await aggregator.list_tools()
    result = await aggregator.call_tool(
        tool_name="everything__add",  # Format: "server_name__tool_name"
        arguments={"a": 5, "b": 3}
    )
    
    # Method 2: With server and tool filtering
    # Filter servers - only connect to specific servers
    filtered_registry = registry.filter_servers(["memory", "everything"])
    
    # Filter tools - only expose specific tools from each server
    tool_filter = {
        "memory": ["get", "set"],  # Only include get/set from memory
        "everything": None,  # Include all tools from everything server
    }
    
    # Create aggregator with both filtering levels
    filtered_aggregator = MCPAggregator(filtered_registry, tool_filter=tool_filter)
    filtered_tools = await filtered_aggregator.list_tools()  # Only shows filtered tools
    
    # Method 3: Persistent connections using context manager
    # Maintains connections for the duration of the context
    async with MCPAggregator(registry) as persistent_aggregator:
        # Connections established when entering context
        tools = await persistent_aggregator.list_tools()
        
        # Multiple tool calls use the same connections
        result1 = await persistent_aggregator.call_tool(
            tool_name="everything__add",
            arguments={"a": 10, "b": 20}
        )
        
        result2 = await persistent_aggregator.call_tool(
            tool_name="everything__echo",
            arguments={"input": "Hello world"}
        )
        
        # Can also specify server and tool separately
        result3 = await persistent_aggregator.call_tool(
            tool_name="echo",
            server_name="everything",
            arguments={"input": "Testing server connection"}
        )
        # Connections closed automatically when exiting context

asyncio.run(main())
```

For more examples, see the [persistent connections example](examples/persistent_connections_example.py).

For an in-depth explanation of the async connection management patterns used in this project, see [Async Connection Management Patterns](docs/async-connection-management.md).

## Testing

### Quick Server Test

The repository includes a test script `tests/test_mcp_aggregator.py` that demonstrates how to:

1. Configure a server registry
2. Create an MCP aggregator
3. List available tools from servers
4. Call tools with parameters

To run the test script, you'll need to:

1. Initialize and update the python-sdk submodule (if you haven't already):
   ```bash
   git submodule update --init --recursive
   ```

2. Install the required dependencies:
   ```bash
   pip install -e .
   pip install -e ./python-sdk
   pip install -e ".[dev]"  # For pytest
   ```

3. Run the test script:
   ```bash
   pytest tests/test_mcp_aggregator.py -v
   ```

This test creates a temporary server configuration, starts a simple tool server, and makes tool calls through the aggregator. The script automatically uses the example server from the python-sdk submodule.

### Testing Tools

MCP Registry provides a dedicated command for testing individual tools:

```bash
# Test a tool interactively
mcp-registry test-tool everything__add

# Test with provided parameters
mcp-registry test-tool everything__add --input '{"a": 5, "b": 10}'

# Get raw output
mcp-registry test-tool everything__echo --input '{"input": "Hello world"}' --raw
```

The test-tool command:
- Guides you through parameter input in interactive mode
- Validates input against the tool's schema
- Formats output for readability
- Supports timeouts for long-running operations

For detailed information, see the [Testing MCP Tools with the CLI](docs/cli_test_tool.md) guide.

## Development

Clone the repository and set up the development environment:

```bash
# Clone the repository with submodules
git clone https://github.com/your-username/mcp-registry.git
cd mcp-registry
git submodule update --init --recursive

# Install dev dependencies
pip install -e ".[dev]"
pip install -e ./python-sdk  # Required for running tests

# Run all tests
pytest

# Format code
ruff format .

# Check code style and lint
ruff check .
```

## Documentation

Comprehensive documentation is available in the `docs/` directory:

- [Getting Started Guide](docs/getting_started.md) - A step-by-step introduction to MCP Registry
- [API Reference](docs/api_reference.md) - Detailed reference for the MCP Registry API
- [Async Connection Management](docs/async-connection-management.md) - Explanation of connection patterns
- [Selective Loading](docs/selective_loading.md) - Examples and best practices for server and tool filtering
- [Integration Tutorial](docs/tutorial_integrating_servers.md) - Tutorial on integrating MCP servers with AI tools

For practical examples, see the [examples](examples/) directory.

## License

Apache 2.0