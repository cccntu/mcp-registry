# MCP Registry CLI Reference

This document provides a comprehensive reference for all available command-line interface (CLI) commands in MCP Registry.

## Command Overview

MCP Registry provides the following commands:

| Command | Description |
|---------|-------------|
| `init` | Initialize a new configuration file |
| `add` | Add a new server to the configuration |
| `remove` | Remove a server from the configuration |
| `list` | List all configured servers |
| `list-tools` | List all tools provided by MCP servers |
| `list-tools-json` | List tools in machine-readable JSON format |
| `test-tool` | Test an MCP tool with provided input |
| `edit` | Edit the configuration file with your default editor |
| `serve` | Run a compound server with all or selected servers |
| `show-config-path` | Show the current configuration file path |
| `alias` | Manage tool aliases for easier access |

## Global Options

The following options are available for all commands:

| Option | Description |
|--------|-------------|
| `--help` | Show help message and exit |
| `--version` | Show version and exit |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_REGISTRY_CONFIG` | Path to the configuration file | `~/.config/mcp_registry/mcp_registry_config.json` |

## Command Details

### `init`

Initialize a new configuration file.

```bash
mcp-registry init
```

This command creates a new configuration file at the location specified by `MCP_REGISTRY_CONFIG` or the default location. If the file already exists, it will ask for confirmation before overwriting.

### `add`

Add a new server to the configuration.

```bash
mcp-registry add <name> [command] [args...]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `name` | Name of the server to add |
| `command` | Command to run the server (for stdio servers) |
| `args` | Arguments for the command |

**Examples:**

```bash
# Add a stdio server
mcp-registry add memory npx -y @modelcontextprotocol/server-memory

# Add a stdio server with complex arguments
mcp-registry add myserver -- node server.js --port 3000 --verbose

# Add a stdio server with quoted command
mcp-registry add myserver "npm run server --port 8080"

# Add an SSE server (will prompt for URL)
mcp-registry add remote
```

**Interactive Mode:**

If you run `mcp-registry add` without a command, it will enter interactive mode and prompt you for:

1. Server type (stdio or sse)
2. Command and arguments (for stdio) or URL (for sse)
3. Description (optional)

### `remove`

Remove a server from the configuration.

```bash
mcp-registry remove <name>
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `name` | Name of the server to remove |

**Example:**

```bash
mcp-registry remove memory
```

### `list`

List all configured servers.

```bash
mcp-registry list
```

This command displays all servers in the configuration file along with their types, commands/URLs, and descriptions.

**Example output:**

```
Configured servers:
memory: stdio: npx -y @modelcontextprotocol/server-memory - Memory server
filesystem: stdio: npx -y @modelcontextprotocol/server-filesystem - Filesystem server
remote: sse: http://localhost:3000/sse - Remote API server
```

### `edit`

Edit the configuration file with your default editor.

```bash
mcp-registry edit
```

This command:
1. Opens the configuration file in your default editor (determined by the `EDITOR` environment variable)
2. Validates the JSON when you save
3. Creates a backup of the previous version before saving

### `list-tools`

List all tools provided by MCP servers.

```bash
mcp-registry list-tools [server_names...] [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `server_names` | (Optional) Names of specific servers to include (filters the registry) |

**Options:**

| Option | Description |
|--------|-------------|
| `--verbose`, `-v` | Increase verbosity level (can be used multiple times) |
| `--json`, `-j` | Output in JSON format (deprecated, use `list-tools-json` command instead) |

**Verbosity Levels:**

- Default: Tool names with truncated descriptions
- `-v`: Also shows parameter information with truncated descriptions
- `-vv`: Shows full details with complete descriptions

**Examples:**

```bash
# List tools from all servers
mcp-registry list-tools

# List tools from specific servers
mcp-registry list-tools memory filesystem

# Show detailed parameter information
mcp-registry list-tools -v

# Show full details without truncation
mcp-registry list-tools -vv

# Output as JSON (deprecated, use list-tools-json instead)
mcp-registry list-tools --json
```

**Example Output (Default):**

```
Server: memory
  - get: Retrieve a value from memory
  - set: Store a value in memory
  - delete: Delete a value from memory

Server: filesystem
  - read: Read a file from the filesystem
  - write: Write to a file in the filesystem
```

### `list-tools-json`

List all tools from MCP servers in JSON format.

```bash
mcp-registry list-tools-json [server_names...]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `server_names` | (Optional) Names of specific servers to include (filters the registry) |

This command outputs a structured JSON object mapping server names to their tools, including tool parameters and descriptions. It's useful for:

- Filtering tools with external tools like jq
- Creating configuration files for tool filtering
- Script automation and parsing

**Examples:**

```bash
# List all servers and tools
mcp-registry list-tools-json

# List specific servers only
mcp-registry list-tools-json memory github

# Filter specific server with jq
mcp-registry list-tools-json | jq '.memory'

# Filter specific tools with jq
mcp-registry list-tools-json | jq '.memory | map(select(.name == "read_graph"))'
```

**Example Output Structure:**

```json
{
  "memory": [
    {
      "name": "get",
      "description": "Retrieve a value from memory",
      "parameters": [
        {
          "name": "key",
          "type": "string",
          "required": true,
          "description": "The key to retrieve"
        }
      ]
    },
    ...
  ],
  "filesystem": [
    ...
  ]
}
```

### `test-tool`

Test an MCP tool with provided input.

```bash
mcp-registry test-tool TOOL_PATH [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `TOOL_PATH` | Path to the tool in the format `server__tool` |

**Options:**

| Option | Description |
|--------|-------------|
| `--input`, `-i` | Input parameters as JSON string |
| `--input-file`, `-f` | Read input parameters from file |
| `--raw`, `-r` | Output raw JSON response |
| `--timeout`, `-t` | Timeout in seconds (default: 30) |
| `--non-interactive`, `-n` | Disable interactive mode |

**Input Methods:**

1. Interactive mode (default when no input is provided)
2. JSON string with the `--input` option
3. JSON file with the `--input-file` option
4. Piped JSON data from stdin

**Examples:**

```bash
# Interactive mode
mcp-registry test-tool memory__get

# JSON string input
mcp-registry test-tool memory__get --input '{"key": "foo"}'

# File input
mcp-registry test-tool memory__set --input-file params.json

# Piped input
echo '{"key": "foo", "value": "bar"}' | mcp-registry test-tool memory__set

# Raw output
mcp-registry test-tool memory__get --input '{"key": "foo"}' --raw

# Increased timeout
mcp-registry test-tool slow_server__long_process --timeout 120
```

For detailed information about this command, see the [Testing MCP Tools with the CLI](cli_test_tool.md) guide.

### `serve`

Run a compound server with all or selected servers.

```bash
mcp-registry serve [server_names...] [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `server_names` | (Optional) Names of specific servers to include (filters the registry) |

**Options:**

| Option | Description |
|--------|-------------|
| `--project`, `-p` | Project name to serve servers for |
| `--filter`, `-f` | Filter tools by server, e.g. 'memory:get,set' or 'memory:-delete,-clear' |
| `--alias`, `-a` | Tool alias in format 'alias=actual_tool' (can be specified multiple times) |

**Examples:**

```bash
# Run all configured servers
mcp-registry serve

# Run only specific servers
mcp-registry serve memory filesystem

# Run with project-enabled servers
mcp-registry serve --project myproject

# Run with tool filtering (include only certain tools)
mcp-registry serve --filter 'memory:get,set,github'

# Run with negative filtering (exclude specific tools)
mcp-registry serve --filter 'memory:-delete,-clear'

# Run with aliases for tools
mcp-registry serve --alias get=memory__get --alias set=memory__set
```

When running, tools from the servers will be available with namespaced names in the format `server_name__tool_name` (e.g., `memory__get`). You can create aliases for more intuitive or shorter tool names.

### `show-config-path`

Show the current configuration file path.

```bash
mcp-registry show-config-path
```

This command displays the path to the configuration file being used, taking into account the `MCP_REGISTRY_CONFIG` environment variable if set.

### `alias`

Manage tool aliases for easier access.

```bash
mcp-registry alias COMMAND [options]
```

**Commands:**

| Command | Description |
|---------|-------------|
| `list` | List all configured aliases |
| `add` | Add or update an alias for a tool |
| `remove` | Remove an alias |

**Examples:**

```bash
# List all configured aliases
mcp-registry alias list

# Add an alias (allows using 'get' instead of 'memory__get')
mcp-registry alias add get memory__get

# Remove an alias
mcp-registry alias remove get
```

Aliases can be used with any command that accepts tool names. For example, after creating an alias, you can use:

```bash
# Test the tool using the alias
mcp-registry test-tool get --input '{"key": "foo"}'
```

## Configuration File Format

The configuration file uses the following JSON format:

```json
{
  "mcpServers": {
    "server_name": {
      "type": "stdio",
      "command": "command",
      "args": ["arg1", "arg2"],
      "description": "Optional description"
    },
    "another_server": {
      "type": "sse",
      "url": "http://localhost:3000/sse",
      "description": "Optional description"
    }
  },
  "aliases": {
    "get": "memory__get",
    "set": "memory__set",
    "search": "github__search"
  }
}
```

## Integration with Other Tools

### Claude Code

Add MCP Registry servers to Claude Code:

```bash
# Add all servers
claude mcp add servers mcp-registry serve

# Add only specific servers
claude mcp add servers mcp-registry serve memory filesystem
```

### Claude Desktop

Similarly for Claude Desktop:

```bash
# Add all servers
claude desktop mcp add servers mcp-registry serve

# Add only specific servers
claude desktop mcp add servers mcp-registry serve memory
```

## Troubleshooting

### Common Issues

1. **Configuration file not found**:
   - Check the path with `mcp-registry show-config-path`
   - Run `mcp-registry init` to create a new configuration file

2. **Server launch errors**:
   - Make sure the command and arguments are correct
   - Check if the required dependencies are installed

3. **Tool not found errors**:
   - Ensure you're using the correct namespaced format (`server_name__tool_name`)
   - Verify that the server is running with `mcp-registry list`
   - Check available tools with `mcp-registry list-tools`
   - Try running `mcp-registry test-tool server_name` to see tools for a specific server

4. **Permission issues**:
   - Make sure the configuration directory has the correct permissions
   - Try running with elevated privileges if necessary