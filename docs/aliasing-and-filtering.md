# Tool Aliasing and Negative Filtering

## Overview

This document outlines the implementation plan for two features to improve tool management in MCP Registry:

1. **Tool Aliasing** - Create user-defined names for tools
2. **Negative Tool Filtering** - Exclude specific tools from servers

## 1. Tool Aliasing

### Motivation

Currently, all tools follow the `server_name__tool_name` namespace pattern. Aliasing allows:
- More intuitive, shorter tool names
- Migration-friendly tool renaming
- Consistent interfaces across different MCP servers

### Implementation

#### Core Changes

1. Update `MCPAggregator` to accept aliases:
   ```python
   class MCPAggregator:
       def __init__(self, registry, tool_filter=None, aliases=None):
           self.registry = registry
           self.tool_filter = tool_filter
           self.aliases = aliases or {}
   ```

2. Modify `call_tool` to resolve aliases:
   ```python
   async def call_tool(self, tool_name, arguments=None, server_name=None):
       # Resolve alias if exists
       resolved_name = self.aliases.get(tool_name, tool_name)
       # Continue with existing logic...
   ```

#### CLI Integration

Add CLI commands for managing aliases:

```python
@cli.group()
def alias():
    """Manage tool aliases."""
    pass
    
@alias.command("add")
@click.argument("alias_name")
@click.argument("tool_name")
def add_alias(alias_name, tool_name):
    """Add an alias for a tool."""
    # Implementation...

@alias.command("list")
def list_aliases():
    """List all defined aliases."""
    # Implementation...

@alias.command("remove")
@click.argument("alias_name")
def remove_alias(alias_name):
    """Remove an alias."""
    # Implementation...
```

Add option to `serve` command:
```python
@click.option("--alias", "-a", multiple=True, help="Tool alias in format 'alias=actual_tool'")
def serve(ctx, server_names, alias, port, host):
    # Parse aliases from format: alias=actual_tool
```

#### Configuration

Store aliases in the MCP Registry config file:
```json
{
  "servers": { ... },
  "aliases": {
    "get": "memory__get",
    "set": "memory__set",
    "search": "github__search"
  }
}
```

## 2. Negative Tool Filtering

### Motivation

Currently, tool filtering only supports inclusion lists. Negative filtering allows:
- Including most tools while excluding a few problematic ones
- Cleaner specifications when most tools are desired
- More intuitive filtering for large tool sets

### Implementation

#### Core Changes

1. Update tool filtering logic in `MCPAggregator`:
   ```python
   async def list_tools(self):
       # When processing tool_filter
       if self.tool_filter is not None and server_name in self.tool_filter:
           server_filter = self.tool_filter[server_name]
           
           # Check if all are negative filters (starting with -)
           if server_filter and all(t.startswith('-') for t in server_filter):
               exclude_tools = {t[1:] for t in server_filter}
               if tool_name in exclude_tools:
                   continue  # Skip this tool
           elif server_filter:
               # Positive filtering (existing behavior)
               if tool_name not in server_filter:
                   continue  # Skip this tool
   ```

2. Add validation to ensure filter consistency:
   ```python
   def validate_tool_filter(tool_filter):
       for server, filters in tool_filter.items():
           if filters is None:
               continue
               
           if filters and any(t.startswith('-') for t in filters):
               # If any negative, all must be negative
               if not all(t.startswith('-') for t in filters):
                   raise ValueError(f"Mixed filter types for '{server}'. Use either all positive or all negative filters.")
   ```

#### CLI Integration

Extend the `--filter` option in the `serve` command:
```python
@click.option("--filter", help="Filter tools by server, e.g. 'memory:-delete,-purge,github'")
```

#### Examples

```bash
# Exclude specific tools from memory server
mcp-registry serve --filter "memory:-delete,-purge"

# Mixed server filtering (include all memory tools except delete/purge, include github)
mcp-registry serve --filter "memory:-delete,-purge,github"

# Using aliases
mcp-registry serve --alias get=memory__get --alias delete=memory__delete
```

## Implementation Phases

1. Add alias support to `MCPAggregator`
2. Update CLI to support aliases in `serve`
3. Add alias command group for management
4. Implement negative tool filtering
5. Add validation for filter consistency
6. Update documentation and examples