# Getting Started with MCP Registry

This guide will walk you through the process of setting up and using MCP Registry to manage and interact with your MCP servers.

## What is MCP Registry?

MCP Registry is a tool that simplifies working with multiple [Model Context Protocol (MCP)](https://modelcontextprotocol.io) servers. It solves three key challenges:

1. **Simplified Configuration Management**: Replace manual JSON editing with intuitive CLI commands
2. **Selective Server Exposure**: Run only specific servers from your configuration without maintaining multiple files
3. **Synchronized Settings**: Configure servers once and access them from multiple MCP clients

## Installation

### From PyPI

```bash
pip install mcp-registry
```

### From Source

```bash
git clone https://github.com/your-username/mcp-registry.git
cd mcp-registry
pip install -e .
```

## Quick Start

### Initialize Configuration

Start by initializing your MCP Registry configuration:

```bash
mcp-registry init
```

This creates a configuration file at `~/.config/mcp_registry/mcp_registry_config.json` (or at the location specified by the `MCP_REGISTRY_CONFIG` environment variable).

### Add Servers

Add some MCP servers to your configuration:

```bash
# Add a memory server
mcp-registry add memory npx -y @modelcontextprotocol/server-memory

# Add a filesystem server
mcp-registry add filesystem npx -y @modelcontextprotocol/server-filesystem
```

### List Configured Servers

View the servers you've configured:

```bash
mcp-registry list
```

### Run a Compound Server

Start a compound server that includes all your configured servers:

```bash
mcp-registry serve
```

Or run a selective compound server with only specific servers:

```bash
mcp-registry serve memory
```

### Test with the Inspector

You can test your compound server using the MCP inspector:

```bash
npx -y @modelcontextprotocol/inspector mcp-registry serve
```

## Managing Server Configurations

### Adding Servers with Complex Commands

For servers that require complex command-line arguments:

```bash
# Method 1: Use -- to separate mcp-registry options from server command flags
mcp-registry add myserver -- node server.js --port 3000 --verbose

# Method 2: Use quotes around the command with its arguments
mcp-registry add myserver "npm run server --port 8080"

# Method 3: Use the interactive mode
mcp-registry add
# Then enter details when prompted
```

### Editing the Configuration

Edit your configuration directly with your preferred editor:

```bash
mcp-registry edit
```

This opens your configuration file in your default editor, validates JSON when saving, and keeps a backup of the previous version.

### Using a Different Configuration Location

You can specify a different location for your configuration file using an environment variable:

```bash
export MCP_REGISTRY_CONFIG=$HOME/my-custom-config.json
```

To check the current configuration path:

```bash
mcp-registry show-config-path
```

## Integration with MCP Clients

### Claude Code

Add your MCP Registry servers to Claude Code:

```bash
# Add all servers
claude mcp add servers mcp-registry serve

# Add only specific servers
claude mcp add servers mcp-registry serve memory filesystem
```

### Using with Other Clients

Other MCP-compatible clients can similarly reference your MCP Registry servers. This ensures synchronized settings across all your tools.

## Using as a Python Library

### Basic Usage

```python
from mcp_registry import ServerRegistry, MCPAggregator, get_config_path
import asyncio

async def main():
    # Load servers from config
    registry = ServerRegistry.from_config(get_config_path())
    
    # Create an aggregator
    aggregator = MCPAggregator(registry)
    
    # List available tools
    tools_result = await aggregator.list_tools()
    print(f"Available tools: {[t.name for t in tools_result.tools]}")
    
    # Call a tool (format: "server_name__tool_name")
    result = await aggregator.call_tool("memory__set", {"key": "test", "value": "Hello"})
    
    # Get the result
    if not result.isError:
        print(f"Success: {result.content[0].text if result.content else ''}")
    else:
        print(f"Error: {result.message}")

asyncio.run(main())
```

### Using Persistent Connections

For better performance when making multiple calls to the same servers:

```python
from mcp_registry import ServerRegistry, MCPAggregator, get_config_path
import asyncio

async def main():
    registry = ServerRegistry.from_config(get_config_path())
    
    # Use MCPAggregator as a context manager for persistent connections
    async with MCPAggregator(registry) as aggregator:
        # Connections are established when entering the context
        
        # Multiple tool calls use the same connections
        result1 = await aggregator.call_tool("memory__set", {"key": "test", "value": "Hello"})
        result2 = await aggregator.call_tool("memory__get", {"key": "test"})
        
        # Connections automatically closed when exiting the context

asyncio.run(main())
```

### Creating a Custom Registry Programmatically

```python
from mcp_registry import ServerRegistry, MCPServerSettings, MCPAggregator
import asyncio

async def main():
    # Create server settings
    memory_server = MCPServerSettings(
        type="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-memory"],
        description="Memory server"
    )
    
    # Create a registry
    registry = ServerRegistry({"memory": memory_server})
    
    # Save the configuration
    registry.save_config("./my_config.json")
    
    # Use the registry
    aggregator = MCPAggregator(registry)
    tools = await aggregator.list_tools()
    print(f"Available tools: {[t.name for t in tools.tools]}")

asyncio.run(main())
```

## Next Steps

- Check the [API Reference](api_reference.md) for detailed information about the MCP Registry API
- Explore the [examples directory](../examples/) for more usage examples
- Learn about [async connection management patterns](async-connection-management.md) used in MCP Registry
- Run a [test script](../tests/test_mcp_aggregator.py) to see MCP aggregation in action

For any questions or issues, please create an issue on the [GitHub repository](https://github.com/your-username/mcp-registry/issues).