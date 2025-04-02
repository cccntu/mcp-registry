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
| `edit` | Edit the configuration file with your default editor |
| `serve` | Run a compound server with all or selected servers |
| `show-config-path` | Show the current configuration file path |

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

### `serve`

Run a compound server with all or selected servers.

```bash
mcp-registry serve [server_names...]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `server_names` | (Optional) Names of specific servers to include |

**Examples:**

```bash
# Run all configured servers
mcp-registry serve

# Run only specific servers
mcp-registry serve memory filesystem
```

When running, tools from the servers will be available with namespaced names in the format `server_name__tool_name`. For example, a tool called `get` from the `memory` server would be available as `memory__get`.

### `show-config-path`

Show the current configuration file path.

```bash
mcp-registry show-config-path
```

This command displays the path to the configuration file being used, taking into account the `MCP_REGISTRY_CONFIG` environment variable if set.

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

4. **Permission issues**:
   - Make sure the configuration directory has the correct permissions
   - Try running with elevated privileges if necessary