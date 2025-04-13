"""Commands related to MCP tools and functions."""

import asyncio
import click
import json
import sys
import logging

from mcp_registry.compound import ServerRegistry, MCPAggregator
from mcp_registry.utils.cli import requires_config, requires_servers
from mcp_registry.utils.config import load_config
from mcp_registry.utils.formatters import truncate_text, format_tool_result
from mcp_registry.utils.tool_helpers import (
    get_filtered_servers,
    get_server_tools,
    json_output_handler,
    text_output_handler,
    display_server_tools
)
from mcp_registry.utils.parameter_collectors import collect_parameters_interactively


@click.command(name="list-tools")
@click.argument("servers", nargs=-1)
@click.option("--verbose", "-v", count=True, help="Verbosity level: -v for parameters, -vv for full descriptions")
@click.option("--json", "-j", is_flag=True, help="Output as JSON for machine processing")
@requires_config
@requires_servers
def list_tools(servers, verbose, json):
    """List all tools/functions provided by MCP servers.

    If server names are provided, only shows tools from those servers.
    Otherwise, shows tools from all registered servers.
    
    Verbosity levels:
      (default): Shows tool names with truncated descriptions
      -v: Also shows parameter information with truncated descriptions
      -vv: Shows everything with full descriptions (no truncation)
    
    Output format:
      (default): Human-readable text
      --json: Machine-readable JSON format of server-to-tools mapping
    
    Examples:
        mcp-registry list-tools  # lists tools from all servers
        mcp-registry list-tools memory github  # lists tools from specific servers
        mcp-registry list-tools -v  # shows parameter information
        mcp-registry list-tools -vv  # shows full descriptions
        mcp-registry list-tools --json  # output as JSON
    """
    # Suppress logs for JSON output
    if json:
        logging.getLogger("mcp_registry").setLevel(logging.ERROR)

    # Get filtered servers
    config = load_config()
    available_servers = get_filtered_servers(config, servers)
    
    if not available_servers:
        if json:
            click.echo("{}")
        else:
            msg = f"No matching servers found for: {', '.join(servers)}" if servers else "No servers available"
            click.echo(msg, err=True)
        return

    # Create registry
    registry = ServerRegistry(available_servers)
    
    # Handle the request based on output format
    async def process_request():
        if json:
            # JSON output - use the dedicated handler
            result = await json_output_handler(registry)
            click.echo(result)
        else:
            # Text output
            result, success = await text_output_handler(registry, servers, verbose)
            click.echo(result, err=not success)

    # Error handling wrapper
    try:
        asyncio.run(process_request())
    except KeyboardInterrupt:
        if json:
            click.echo("{}")
        else:
            click.echo("\nOperation cancelled by user.", err=True)
    except Exception as e:
        if json:
            click.echo("{}")
        else:
            click.echo(f"Error: {e}", err=True)


@click.command(name="list-tools-json")
@click.argument("servers", nargs=-1)
@requires_config
@requires_servers
def list_tools_json(servers):
    """List all tools/functions from MCP servers in JSON format.

    If server names are provided, only shows tools from those servers.
    Otherwise, shows tools from all registered servers.

    The output is a structured JSON object mapping server names to their tools,
    including tool parameters and descriptions. This is useful for:
    
    - Filtering tools with external tools like jq
    - Creating configuration files for tool filtering
    - Script automation and parsing
    
    Examples:
        mcp-registry list-tools-json  # lists all servers and tools
        mcp-registry list-tools-json memory github  # specific servers only
        mcp-registry list-tools-json | jq '.memory'  # filter specific server
        mcp-registry list-tools-json | jq '.memory | map(select(.name == "read_graph"))'  # filter tools
    """
    # Suppress logs to avoid interfering with JSON output
    logging.getLogger("mcp_registry").setLevel(logging.ERROR)
    
    # Get filtered servers
    config = load_config()
    available_servers = get_filtered_servers(config, servers)
    
    if not available_servers:
        click.echo("{}")
        return

    # Process and output JSON
    async def process_request():
        registry = ServerRegistry(available_servers)
        result = await json_output_handler(registry)
        click.echo(result)

    # Simple error handling - always output valid JSON
    try:
        asyncio.run(process_request())
    except:
        click.echo("{}")


class CustomCommand(click.Command):
    """Custom Click command class that shows available tools when invoked without arguments."""
    
    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        """Override parse_args to handle the case of no arguments."""
        # Check if no arguments were provided and handle it specially
        if not args and ctx.command.name == "test-tool":
            self.show_available_tools(ctx)
            ctx.exit(1)
        return super().parse_args(ctx, args)
        
    def show_available_tools(self, ctx: click.Context) -> None:
        """Display available tools and exit."""
        click.echo("Error: Missing tool path. You must specify a tool in the format 'server__tool'.", err=True)
        click.echo("\nAvailable tools:", err=True)
        
        try:
            # Load config
            config = load_config()
            
            if not config or not config.get("mcpServers"):
                click.echo("No servers available. Add servers first using 'mcp-registry add'.", err=True)
                return

            # Create registry with all servers
            registry = ServerRegistry(get_filtered_servers(config))
            
            # Run with simple error handling and timeout
            async def run_with_timeout():
                try:
                    async with asyncio.timeout(10):
                        # Use our helper function to show all available tools
                        aggregator = MCPAggregator(registry)
                        server_tools = await aggregator.list_tools(return_server_mapping=True)
                        
                        if not server_tools:
                            click.echo("No tools found from any server.", err=True)
                            return False
                        
                        # Display tools by server with server__tool format
                        for server_name, tools in server_tools.items():
                            click.echo(f"\nServer: {server_name}", err=True)
                            
                            if not tools:
                                click.echo("  No tools available", err=True)
                                continue
                            
                            # Simple format with server__tool naming
                            for tool in tools:
                                desc = ""
                                if hasattr(tool, 'description') and tool.description:
                                    desc = f": {truncate_text(tool.description)}"
                                click.echo(f"  {server_name}__{tool.name}{desc}", err=True)
                        
                        return True
                except asyncio.TimeoutError:
                    click.echo("Timeout while fetching tools.", err=True)
                    return False
                except Exception as e:
                    click.echo(f"Error fetching tools: {e}", err=True)
                    return False
            
            success = asyncio.run(run_with_timeout())
            
            # Show usage hint
            if success:    
                click.echo("\nTo test a specific tool, run:", err=True)
                click.echo("  mcp-registry test-tool SERVER__TOOL", err=True)
            else:
                click.echo("\nPlease use 'mcp-registry list-tools' to see available tools.", err=True)
                
        except Exception as e:
            click.echo(f"Error listing tools: {e}", err=True)
            click.echo("\nUse 'mcp-registry list-tools' to see all available tools.", err=True)






@click.command(name="test-tool", cls=CustomCommand)
@click.argument("tool_path")
@click.option("--input", "-i", help="Input parameters as JSON string")
@click.option("--input-file", "-f", help="Read input parameters from file")
@click.option("--raw", "-r", is_flag=True, help="Output raw JSON response")
@click.option("--timeout", "-t", type=int, default=30, help="Timeout in seconds (default: 30)")
@click.option("--non-interactive", "-n", is_flag=True, help="Disable interactive mode")
@requires_config
@requires_servers
def test_tool(tool_path: str, input: str = None, input_file: str = None, 
             raw: bool = False, timeout: int = 30, non_interactive: bool = False) -> None:
    """Test an MCP tool with provided input.
    
    TOOL_PATH should be in the format 'server__tool' (e.g., 'memory__get').
    
    If no input is provided, and stdin is a terminal, interactive mode will
    be enabled automatically to help you construct the parameters.
    
    Input can be provided in several ways:
      - Interactive mode (default when no other input is provided)
      - As a JSON string with --input
      - From a file with --input-file
      - From stdin (pipe or redirect)
    
    Non-interactive usage (for scripts and testing):
      - Provide parameters via --input or --input-file
      - Pipe JSON to stdin
      - Use --non-interactive flag to ensure no prompts appear
      - For automated testing, consider using the MCPAggregator class directly:
        ```python
        from mcp_registry.compound import MCPServerSettings, ServerRegistry, MCPAggregator
        
        # Create registry with required server
        server_settings = MCPServerSettings(type="stdio", command="...", args=["..."])
        registry = ServerRegistry({"server_name": server_settings})
        aggregator = MCPAggregator(registry)
        
        # Call tool programmatically
        result = await aggregator.call_tool("server_name__tool_name", {"param": "value"})
        ```
    
    Examples:
        mcp-registry test-tool memory__get  # interactive mode
        mcp-registry test-tool memory__get --input '{"key": "foo"}'
        mcp-registry test-tool memory__set --input-file params.json
        cat params.json | mcp-registry test-tool memory__set
        echo '{"key": "foo", "value": "bar"}' | mcp-registry test-tool memory__set
        mcp-registry test-tool memory__get --non-interactive  # use empty parameters
    """
    # Config existence and servers already checked by decorators
    config = load_config()
    
    # Import alias functionality
    from mcp_registry.utils.config import get_aliases
    
    # Parse server and tool names
    separator = "__"
    
    # Check if this is an alias
    aliases = get_aliases()
    if tool_path in aliases:
        # Resolve the alias to its actual tool path
        click.echo(f"Using alias: {tool_path} -> {aliases[tool_path]}", err=True)
        tool_path = aliases[tool_path]
    
    if separator not in tool_path:
        # Check if this is a server name
        if tool_path in config["mcpServers"]:
            click.echo(f"You specified a server name without a tool name.", err=True)
            click.echo(f"Here are the available tools for server '{tool_path}':", err=True)
            
            # Create registry with just this server
            server_settings = get_filtered_servers(config, [tool_path])
            registry = ServerRegistry(server_settings)
            
            # Display tools for this server
            try:
                success = asyncio.run(display_server_tools(tool_path, registry))
                if success:
                    click.echo("\nTo test a specific tool, use:", err=True)
                    click.echo(f"  mcp-registry test-tool {tool_path}{separator}TOOL_NAME", err=True)
                else:
                    click.echo(f"\nPlease use 'mcp-registry list-tools {tool_path}' to see available tools.", err=True)
            except Exception as e:
                click.echo(f"Error: {e}", err=True)
                click.echo(f"\nPlease use 'mcp-registry list-tools {tool_path}' to see available tools.", err=True)
            return
        
        # Not a valid tool path
        click.echo(f"Error: Tool path must be in format 'server{separator}tool' or a valid alias", err=True)
        sys.exit(1)
    
    # Split into server and tool names
    server_name, tool_name = tool_path.split(separator, 1)
    
    # Verify the server exists
    if server_name not in config["mcpServers"]:
        click.echo(f"Error: Server '{server_name}' not found in configuration", err=True)
        click.echo("\nTo see available servers and tools, use:", err=True)
        click.echo("  mcp-registry list-tools", err=True)
        sys.exit(1)
    
    # Create registry with just the needed server
    server_settings = get_filtered_servers(config, [server_name])
    registry = ServerRegistry(server_settings)
    
    # Load parameters from the utils module
    from mcp_registry.utils.tool_helpers import load_parameters
    parameters, use_interactive = load_parameters(input, input_file)
    
    # If interactive mode is explicitly disabled
    if use_interactive and non_interactive:
        use_interactive = False
    
    # Execute the tool call
    async def execute_tool_call():
        nonlocal parameters, use_interactive
        
        # Create aggregator
        aggregator = MCPAggregator(registry)
        
        try:
            # Collect parameters interactively if needed
            if use_interactive:
                parameters = await collect_parameters_interactively(
                    tool_path, server_name, tool_name, aggregator)
            
            # Call the tool with timeout
            async with asyncio.timeout(timeout):
                result = await aggregator.call_tool(tool_path, parameters)
                
                # Format and display the result
                output = format_tool_result(result, raw)
                click.echo(output)
                
                # Exit with error if the tool returned an error
                if hasattr(result, 'isError') and result.isError:
                    sys.exit(1)
                
        except asyncio.TimeoutError:
            click.echo(f"Error: Timeout after {timeout} seconds while calling tool", err=True)
            sys.exit(1)
        except Exception as e:
            click.echo(f"Error calling tool: {e}", err=True)
            sys.exit(1)
    
    # Run with error handling
    try:
        asyncio.run(execute_tool_call())
    except KeyboardInterrupt:
        click.echo("\nOperation cancelled by user.", err=True)
        sys.exit(130)  # Standard exit code for SIGINT


@click.group()
def alias():
    """Manage tool aliases for easier access."""
    pass

@alias.command("list")
@requires_config
def list_aliases():
    """List all configured tool aliases."""
    from mcp_registry.utils.config import get_aliases
    
    aliases = get_aliases()
    
    if not aliases:
        click.echo("No aliases configured.")
        return
        
    click.echo(f"Configured aliases ({len(aliases)}):")
    for alias_name, target in sorted(aliases.items()):
        click.echo(f"  {alias_name} -> {target}")

@alias.command("add")
@click.argument("alias_name")
@click.argument("tool_name")
@requires_config
def add_alias(alias_name, tool_name):
    """Add or update an alias for a tool.
    
    ALIAS_NAME is the short name you want to use.
    TOOL_NAME is the actual tool in 'server__tool' format.
    
    Examples:
        mcp-registry alias add get memory__get
        mcp-registry alias add search google__search
    """
    from mcp_registry.utils.config import validate_alias, add_alias
    
    # Validate alias name and tool name
    is_valid, error = validate_alias(alias_name, tool_name)
    if not is_valid:
        click.echo(f"Error: {error}", err=True)
        return
    
    # Add the alias
    try:
        add_alias(alias_name, tool_name)
        click.echo(f"Added alias: {alias_name} -> {tool_name}")
    except Exception as e:
        click.echo(f"Error adding alias: {e}", err=True)

@alias.command("remove")
@click.argument("alias_name")
@requires_config
def remove_alias(alias_name):
    """Remove an alias.
    
    ALIAS_NAME is the name of the alias to remove.
    
    Example:
        mcp-registry alias remove get
    """
    from mcp_registry.utils.config import remove_alias, get_aliases
    
    # Check if the alias exists
    aliases = get_aliases()
    if alias_name not in aliases:
        click.echo(f"Error: Alias '{alias_name}' not found", err=True)
        return
    
    # Remove the alias
    try:
        remove_alias(alias_name)
        click.echo(f"Removed alias: {alias_name}")
    except Exception as e:
        click.echo(f"Error removing alias: {e}", err=True)


def register_commands(cli_group):
    """Register all tool-related commands with the CLI group."""
    cli_group.add_command(list_tools)
    cli_group.add_command(list_tools_json)
    cli_group.add_command(test_tool)
    cli_group.add_command(alias)