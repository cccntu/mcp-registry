# Selective Server and Tool Loading

This document provides examples and best practices for using the new server and tool filtering capabilities in MCP Registry.

## Server-level Filtering

Server-level filtering allows you to work with a subset of the configured servers. This is more efficient than filtering during operations, as it prevents loading unnecessary server configurations.

### Using ServerRegistry.filter_servers

```python
from mcp_registry.compound import ServerRegistry, MCPAggregator

# Create or load a registry with all servers
full_registry = ServerRegistry.from_config(config_path)

# Create a filtered registry with only specified servers
memory_github_registry = full_registry.filter_servers(["memory", "github"])

# Create an aggregator with the filtered registry
aggregator = MCPAggregator(memory_github_registry)

# Use the aggregator normally - only has access to specified servers
tools = await aggregator.list_tools()
result = await aggregator.call_tool("memory__get", {"key": "test"})
```

### CLI Usage

The `mcp-registry serve` command uses server filtering when you specify server names:

```bash
# Serve all servers
mcp-registry serve

# Serve only specific servers
mcp-registry serve memory github
```

## Tool-level Filtering

Tool-level filtering allows you to expose only specific tools from each server. This doesn't reduce connection overhead but simplifies the exposed API and can be useful for security and organization.

### Basic Tool Filtering

```python
from mcp_registry.compound import ServerRegistry, MCPAggregator

# Create or load a registry
registry = ServerRegistry.from_config(config_path)

# Define which tools to expose from each server
tool_filter = {
    "memory": ["get", "set"],  # Only include get/set from memory
    "github": ["list_repos", "create_issue"],  # Only specific github tools
    "everything": None,  # Include all tools from 'everything' server
}

# Create an aggregator with the tool filter
aggregator = MCPAggregator(registry, tool_filter=tool_filter)

# Only the specified tools will be visible and callable
tools = await aggregator.list_tools()
```

### Tool Filter Configurations

```python
# Include all tools from all servers (default behavior)
tool_filter = {}  # or None

# Include no tools from a server (empty list)
tool_filter = {
    "unsafe_server": []  # No tools from this server will be exposed
}

# Include all tools from specific servers
tool_filter = {
    "memory": None,  # All tools from memory server
    "github": None   # All tools from github server
}

# Mix of specific tools and all tools
tool_filter = {
    "memory": ["get", "set", "delete"],
    "github": None,
    "filesystem": ["read_file", "list_directory"]
}

# Filter just one server, include all tools from other servers
tool_filter = {
    "memory": ["get", "set"]  # Only filter memory server
}
# Result: 
# - For memory: Only get and set tools included
# - For all other servers: ALL tools included (no filtering)
```

**Important**: If a server is not included in the tool_filter dictionary, ALL tools from that server will be included without filtering. This means you only need to specify filters for the servers you want to restrict.

## Combining Both Filtering Levels

For maximum control, you can combine both filtering levels:

```python
# Step 1: Filter at the server level (which servers to connect to)
filtered_registry = full_registry.filter_servers(["memory", "github", "filesystem"])

# Step 2: Filter at the tool level (which tools to expose)
tool_filter = {
    "memory": ["get", "set"],
    "github": ["list_repos", "create_issue"],
    "filesystem": ["read_file", "list_directory"]
}

# Create aggregator with both filtering levels
aggregator = MCPAggregator(filtered_registry, tool_filter=tool_filter)
```

## Best Practices

1. **Use server-level filtering for efficiency**: When you know which servers you need, use `filter_servers` to avoid loading unnecessary configurations.

2. **Use tool-level filtering for API simplification**: Use tool filters when you want to expose a clean, simplified API or restrict access to certain tools.

3. **Use registry filtering for server selection**: Filter servers at the registry level using `filter_servers()` before creating an aggregator.

4. **Document your filtering**: When building applications that filter tools, consider documenting which tools you're exposing to make it clear to users.

## Usage with Persistent Connections

Both filtering techniques work with persistent connections:

```python
# Create filtered registry and tool filter
filtered_registry = full_registry.filter_servers(["memory", "github"])
tool_filter = {
    "memory": ["get", "set"],
    "github": ["list_repos"]
}

# Use with persistent connections
async with MCPAggregator(filtered_registry, tool_filter=tool_filter) as aggregator:
    # All tool calls use persistent connections
    # Only the filtered tools are available
    result1 = await aggregator.call_tool("memory__get", {"key": "test"})
    result2 = await aggregator.call_tool("memory__set", {"key": "test", "value": "hello"})
```