# Claude's Reference Guide for MCP Registry

## Core Architecture

- **MCP Registry**: Manages MCP servers, provides CLI tools, and aggregates server tools
- **Server configuration**: Stored in `~/.config/mcp_registry/mcp_registry_config.json` (configurable via `MCP_REGISTRY_CONFIG`)

## Key Components

1. **ServerRegistry** (`compound.py`)
   - Loads/saves server configurations from JSON
   - Maps server names to `MCPServerSettings` objects
   - Creates client sessions for connecting to servers
   - Supports filtering to create subsets with `filter_servers()`

2. **MCPAggregator** (`compound.py`)
   - Namespaces tools as `server_name__tool_name`
   - Supports temporary and persistent connections
   - Handles tool listing and calling across servers
   - Implements the `list_tools()` and `call_tool()` methods
   - Key entrypoint for programmatic tool calls
   - Supports tool-level filtering with `tool_filter` parameter

3. **MCPConnectionManager** (`connection.py`)
   - Handles concurrent persistent connections
   - Uses async context managers for proper lifecycle
   - More efficient for multiple tool calls

4. **CLI Commands** (`cli.py`, `commands/*.py`)
   - **init**: Create config file and import Claude Desktop settings
   - **add/remove/list**: Manage server configurations 
   - **serve**: Run compound server with all/selected servers
   - **list-tools**: Display tools from servers with 3 verbosity levels
   - **test-tool**: Test tools interactively or programmatically

## Core Files

- `src/mcp_registry/compound.py`: Server registry, settings, and aggregator
- `src/mcp_registry/connection.py`: Persistent connection management
- `src/mcp_registry/cli.py`: Main CLI entrypoint
- `src/mcp_registry/commands/tools.py`: Tool-related commands (list-tools, test-tool)
- `src/mcp_registry/commands/serve.py`: Server command
- `src/mcp_registry/utils/config.py`: Configuration utilities
- `src/mcp_registry/utils/cli.py`: CLI decorators and helpers

## Important Code Patterns

1. **Server Settings**
   ```python
   settings = MCPServerSettings(
       type="stdio",                  # or "sse"
       command="/bin/zsh",            # for stdio
       args=["-c", "npm run server"], # for stdio
       url="http://localhost:3000",   # for sse
   )
   ```

2. **Creating an Aggregator**
   ```python
   # Basic usage
   registry = ServerRegistry({"server_name": server_settings})
   aggregator = MCPAggregator(registry)
   
   # With server filtering
   filtered_registry = full_registry.filter_servers(["memory", "github"])
   aggregator = MCPAggregator(filtered_registry)
   
   # With tool filtering
   tool_filter = {
       "memory": ["get", "set"],  # Only include specific tools
       "github": None,  # Include all tools from this server
   }
   aggregator = MCPAggregator(registry, tool_filter=tool_filter)
   ```

3. **Listing Tools**
   ```python
   # Get all tools from all servers
   tools_result = await aggregator.list_tools()
   
   # Get tools grouped by server
   server_tools = await aggregator.list_tools(return_server_mapping=True)
   ```

4. **Calling Tools**
   ```python
   # Using namespaced format
   result = await aggregator.call_tool("server_name__tool_name", {"param": "value"})
   
   # Alternative format
   result = await aggregator.call_tool(tool_name="tool_name", 
                                       arguments={"param": "value"}, 
                                       server_name="server_name")
   ```

5. **Persistent Connections**
   ```python
   async with MCPAggregator(registry) as aggregator:
       result1 = await aggregator.call_tool("memory__get", {"key": "test"})
       result2 = await aggregator.call_tool("memory__set", {"key": "test", "value": "hello"})
   ```

## CLI Command Examples

```bash
# Initialize config
mcp-registry init

# Add servers
mcp-registry add memory npx -y @modelcontextprotocol/server-memory
mcp-registry add filesystem npx -y @modelcontextprotocol/server-filesystem

# List configured servers
mcp-registry list

# List available tools
mcp-registry list-tools  # all servers
mcp-registry list-tools memory  # specific server
mcp-registry list-tools -v  # with parameter info

# Test a tool interactively
mcp-registry test-tool memory__get  # interactive mode
mcp-registry test-tool memory__set --input '{"key": "foo", "value": "bar"}'  # with JSON
echo '{"key": "foo"}' | mcp-registry test-tool memory__get  # piped input

# Run a compound server
mcp-registry serve  # all servers
mcp-registry serve memory filesystem  # specific servers
```

## Testing Conventions

- **Unit tests**: Focus on isolated component functionality (files in `/tests`)
- **Mock server connections** for tests to avoid external dependencies
- Mocking click commands requires careful handling of Context objects
- Use `click.testing.CliRunner` to test CLI functions

## Documentation Guidelines

- Keep examples in docstrings, including parameter types
- Use type annotations throughout the codebase
- Document CLI commands in `docs/cli_reference.md`
- Use `docs/cli_test_tool.md` for test-tool documentation

## Error Handling Standards

- Use correct exit codes (1 for errors, 0 for success)
- Provide detailed, but concise error messages
- Use `err=True` with `click.echo()` for error messages
- Handle both expected exceptions and fallbacks

## Development Principles

- **KISS (Keep It Simple, Stupid)**: Favor simple, straightforward implementations over complex ones
- Prioritize maintainability and readability over clever solutions
- Avoid premature optimization or unnecessary abstraction
- Each function or class should have a single, clear responsibility