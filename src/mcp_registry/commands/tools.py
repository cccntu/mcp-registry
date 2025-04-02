"""Commands related to MCP tools and functions."""

import asyncio
import click
import json
import sys

from mcp_registry.compound import MCPServerSettings, ServerRegistry, MCPAggregator
from mcp_registry.utils.cli import requires_config, requires_servers


# Helper functions
def truncate_text(text: str, max_length: int = 60) -> str:
    """Truncate text to a specified maximum length with a smart break point.
    
    Args:
        text: The text to truncate
        max_length: Maximum length of the truncated text
        
    Returns:
        Truncated text with ellipsis if needed
    """
    if not text or len(text) <= max_length:
        return text
        
    # Try to find a sentence break
    break_point = text[:max_length].rfind('. ')
    if break_point > 30:  # Ensure we don't cut too short
        return text[:break_point+1]
    else:
        # Otherwise break at max_length
        return text[:max_length-3] + "..."


def extract_parameters(schema: dict) -> list[dict]:
    """Extract parameter information from a JSON schema.
    
    Args:
        schema: The JSON schema to extract parameters from
        
    Returns:
        List of parameter dictionaries with name, type, required status, and description
    """
    parameters = []
    if not schema or not isinstance(schema, dict):
        return parameters
        
    props = schema.get("properties", {})
    required = schema.get("required", [])
    
    for name, prop in props.items():
        param_type = prop.get("type", "any")
        is_required = name in required
        description = prop.get("description", "")
        
        parameters.append({
            "name": name,
            "type": param_type,
            "required": is_required,
            "description": description
        })
    
    return parameters


def format_tool_result(result, raw: bool = False) -> str:
    """Format a tool call result for display.
    
    Args:
        result: The result object from an MCP tool call
        raw: Whether to return raw JSON output or formatted text
        
    Returns:
        Formatted string representation of the result
    """
    if raw:
        return json.dumps(result.model_dump() if hasattr(result, 'model_dump') else result, indent=2)
    
    # Process different result types
    if not result:
        return "No result returned"
    
    if hasattr(result, 'isError') and result.isError:
        return f"Error: {result.message}"
    
    if hasattr(result, 'content') and result.content:
        output_parts = []
        for item in result.content:
            if hasattr(item, 'type') and item.type == 'text' and hasattr(item, 'text'):
                output_parts.append(item.text)
            elif hasattr(item, 'type') and item.type == 'image':
                output_parts.append("[IMAGE CONTENT]")
            elif hasattr(item, 'type') and item.type == 'embedded_resource':
                output_parts.append(f"[RESOURCE: {getattr(item, 'resourceId', 'unknown')}]")
            else:
                output_parts.append(str(item))
        return "\n".join(output_parts)
    
    # Fallback for unknown result formats
    return str(result)


@click.command(name="list-tools")
@click.argument("servers", nargs=-1)
@click.option("--verbose", "-v", count=True, help="Verbosity level: -v for parameters, -vv for full descriptions")
@requires_config
@requires_servers
def list_tools(servers, verbose):
    """List all tools/functions provided by MCP servers.

    If server names are provided, only shows tools from those servers.
    Otherwise, shows tools from all registered servers.
    
    Verbosity levels:
      (default): Shows tool names with truncated descriptions
      -v: Also shows parameter information with truncated descriptions
      -vv: Shows everything with full descriptions (no truncation)
    
    Examples:
        mcp-registry list-tools  # lists tools from all servers
        mcp-registry list-tools memory github  # lists tools from specific servers
        mcp-registry list-tools -v  # shows parameter information
        mcp-registry list-tools -vv  # shows full descriptions
    """
    # Import from utils config
    from mcp_registry.utils.config import load_config
    
    # Config existence and servers already checked by decorators
    config = load_config()

    # Filter servers if specified
    available_servers = {
        name: MCPServerSettings(**settings)
        for name, settings in config["mcpServers"].items()
        if not servers or name in servers
    }

    if not available_servers:
        if servers:
            click.echo(f"No matching servers found for: {', '.join(servers)}", err=True)
        else:
            click.echo("No servers available", err=True)
        return

    # Create registry and aggregator
    registry = ServerRegistry(available_servers)
    aggregator = MCPAggregator(registry)

    # Fetch and display tools from all servers
    async def fetch_and_display_tools():
        try:
            # Track connected servers
            connected_servers = []
            
            # Get tools grouped by server with a timeout
            async with asyncio.timeout(10):  # 10-second timeout
                try:
                    server_tools = await aggregator.list_tools(return_server_mapping=True)
                except Exception as e:
                    # If we hit a general error, log it and show what we can
                    click.echo(f"Warning: Error connecting to some servers: {e}", err=True)
                    # Try to get any servers that succeeded
                    server_tools = {}
            
            if not server_tools:
                click.echo("No tools found from any server.", err=True)
                return
                
            # Display results for each server
            for server_name, tools in server_tools.items():
                connected_servers.append(server_name)
                click.echo(f"\nServer: {server_name}")
                
                if not tools:
                    click.echo("  No tools available", err=True)
                    continue
                
                # Display tools based on verbosity level
                if verbose >= 2:  # -vv: Full details without truncation
                    for tool in tools:
                        click.echo(f"  Tool: {tool.name}")
                        
                        if hasattr(tool, 'description') and tool.description:
                            click.echo(f"    Description: {tool.description}")
                        
                        if hasattr(tool, 'inputSchema') and tool.inputSchema:
                            parameters = extract_parameters(tool.inputSchema)
                            if parameters:
                                click.echo("    Parameters:")
                                for param in parameters:
                                    required = "required" if param["required"] else "optional"
                                    desc = f": {param['description']}" if param['description'] else ""
                                    click.echo(f"      - {param['name']} ({param['type']}, {required}){desc}")
                        click.echo("")  # Empty line between tools
                        
                elif verbose == 1:  # -v: Parameters with truncated descriptions
                    for tool in tools:
                        click.echo(f"  Tool: {tool.name}")
                        
                        if hasattr(tool, 'description') and tool.description:
                            desc = truncate_text(tool.description)
                            click.echo(f"    Description: {desc}")
                        
                        if hasattr(tool, 'inputSchema') and tool.inputSchema:
                            parameters = extract_parameters(tool.inputSchema)
                            if parameters:
                                click.echo("    Parameters:")
                                for param in parameters:
                                    required = "required" if param["required"] else "optional"
                                    param_desc = param['description']
                                    if param_desc and len(param_desc) > 40:
                                        param_desc = truncate_text(param_desc, 40)
                                    desc = f": {param_desc}" if param_desc else ""
                                    click.echo(f"      - {param['name']} ({param['type']}, {required}){desc}")
                        click.echo("")  # Empty line between tools
                        
                else:  # Default: Simple view with truncated description
                    for tool in tools:
                        desc = ""
                        if hasattr(tool, 'description') and tool.description:
                            desc = f": {truncate_text(tool.description)}"
                        click.echo(f"  - {tool.name}{desc}")
                
            # Show any servers that were requested but not connected
            if servers:
                missing_servers = [s for s in servers if s not in connected_servers]
                if missing_servers:
                    click.echo("\nWarning: Could not connect to the following servers:", err=True)
                    for server in missing_servers:
                        click.echo(f"  - {server}", err=True)
        
        except Exception as e:
            click.echo(f"Error fetching tools: {e}", err=True)

    # Run the async function
    try:
        asyncio.run(fetch_and_display_tools())
    except KeyboardInterrupt:
        click.echo("\nOperation cancelled by user.", err=True)
    except asyncio.TimeoutError:
        click.echo("Timeout while fetching tools from servers. Try again or specify specific servers.", err=True)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


class CustomCommand(click.Command):
    """Custom Click command class that shows available tools when invoked without arguments."""
    
    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        """Override parse_args to handle the case of no arguments.
        
        Args:
            ctx: The Click context object
            args: Command line arguments
            
        Returns:
            Processed arguments for Click
        """
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
            # Run the mcp-registry list-tools command by executing it as a subprocess
            # This ensures all the proper CLI environment and handlers are used
            from mcp_registry.utils.config import load_config
            
            # Config existence and servers already checked by decorators
            config = load_config()
            
            if not config or not config.get("mcpServers"):
                click.echo("No servers available. Add servers first using 'mcp-registry add'.", err=True)
                return

            # Create registry and aggregator
            registry = ServerRegistry({
                name: MCPServerSettings(**settings)
                for name, settings in config["mcpServers"].items()
            })
            
            aggregator = MCPAggregator(registry)

            # Fetch and display tools from all servers
            async def fetch_and_display_tools():
                try:
                    # Track connected servers
                    connected_servers = []
                    
                    # Get tools grouped by server with a timeout
                    async with asyncio.timeout(10):  # 10-second timeout
                        try:
                            server_tools = await aggregator.list_tools(return_server_mapping=True)
                        except Exception as e:
                            click.echo(f"Warning: Error connecting to some servers: {e}", err=True)
                            server_tools = {}
                    
                    if not server_tools:
                        click.echo("No tools found from any server.", err=True)
                        return
                        
                    # Display results for each server
                    for server_name, tools in server_tools.items():
                        connected_servers.append(server_name)
                        click.echo(f"\nServer: {server_name}")
                        
                        if not tools:
                            click.echo("  No tools available", err=True)
                            continue
                            
                        # Simple view with truncated description
                        for tool in tools:
                            desc = ""
                            if hasattr(tool, 'description') and tool.description:
                                desc = f": {truncate_text(tool.description)}"
                            click.echo(f"  {server_name}__{tool.name}{desc}")
                        
                except Exception as e:
                    click.echo(f"Error fetching tools: {e}", err=True)
                    return False
                return True
            
            # Run the async function
            success = False
            try:
                success = asyncio.run(fetch_and_display_tools())
            except (KeyboardInterrupt, asyncio.TimeoutError, Exception) as e:
                click.echo(f"\nError: {e}", err=True)
                success = False
                
            if success:    
                # Add a helpful message about what to do next
                click.echo("\nTo test a specific tool, run:", err=True)
                click.echo("  mcp-registry test-tool SERVER__TOOL", err=True)
            else:
                # Fallback message if something went wrong
                click.echo("\nPlease use 'mcp-registry list-tools' to see available tools.", err=True)
                
        except Exception as e:
            # If anything fails, show a helpful message
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
    # Import from utils config
    from mcp_registry.utils.config import load_config
    
    # Config existence and servers already checked by decorators
    config = load_config()
    
    # Parse server and tool names
    separator = "__"
    if separator not in tool_path:
        # Check if the provided string could be a server name
        if tool_path in config["mcpServers"]:
            # User provided just a server name - show tools for this server
            click.echo(f"You specified a server name without a tool name.", err=True)
            click.echo(f"Here are the available tools for server '{tool_path}':", err=True)
            
            # Create registry with just the needed server
            server_settings = MCPServerSettings(**config["mcpServers"][tool_path])
            registry = ServerRegistry({tool_path: server_settings})
            aggregator = MCPAggregator(registry)
            
            # Define async function to list tools
            async def show_server_tools():
                try:
                    # Get tool list 
                    server_tools = await aggregator.list_tools(return_server_mapping=True)
                    
                    if not server_tools or tool_path not in server_tools or not server_tools[tool_path]:
                        click.echo(f"No tools found for server '{tool_path}'.", err=True)
                        return False
                    
                    click.echo("")  # Empty line for readability
                    tools = server_tools[tool_path]
                    for tool in tools:
                        tool_name = getattr(tool, 'name', 'unknown')
                        desc = ""
                        if hasattr(tool, 'description') and tool.description:
                            desc = f": {truncate_text(tool.description)}"
                        
                        # Show namespaced tool name and description
                        click.echo(f"  {tool_path}{separator}{tool_name}{desc}")
                    return True
                        
                except Exception as e:
                    click.echo(f"Error getting tools: {e}", err=True)
                    return False
            
            # Run the async function
            try:
                success = asyncio.run(show_server_tools())
                if success:
                    click.echo("\nTo test a specific tool, use:", err=True)
                    click.echo(f"  mcp-registry test-tool {tool_path}{separator}TOOL_NAME", err=True)
                else:
                    click.echo(f"\nPlease use 'mcp-registry list-tools {tool_path}' to see available tools.", err=True)
                return
            except Exception as e:
                click.echo(f"Error: {e}", err=True)
                click.echo(f"\nPlease use 'mcp-registry list-tools {tool_path}' to see available tools.", err=True)
                return
        
        # If we got here, it's not a valid server or we couldn't list the tools
        click.echo(f"Error: Tool path must be in format 'server{separator}tool'", err=True)
        sys.exit(1)
    
    server_name, tool_name = tool_path.split(separator, 1)
    
    # Check if server exists
    if server_name not in config["mcpServers"]:
        click.echo(f"Error: Server '{server_name}' not found in configuration", err=True)
        click.echo("\nTo see available servers and tools, use:", err=True)
        click.echo("  mcp-registry list-tools", err=True)
        sys.exit(1)
    
    # Create registry with just the needed server
    server_settings = MCPServerSettings(**config["mcpServers"][server_name])
    registry = ServerRegistry({server_name: server_settings})
    aggregator = MCPAggregator(registry)
    
    # Helper function to get tool schema
    async def get_tool_schema():
        try:
            # Get tool list to find the schema
            server_tools = await aggregator.list_tools(return_server_mapping=True)
            if server_name not in server_tools:
                return None
                
            # Find the specific tool
            for tool in server_tools[server_name]:
                if tool.name == tool_name:
                    return getattr(tool, 'inputSchema', {})
            
            return None
        except Exception:
            return None
    
    # Interactive parameter collection
    async def collect_parameters_interactively():
        click.echo(f"Interactive mode for tool: {tool_path}")
        
        # Get the tool schema
        schema = await get_tool_schema()
        if not schema:
            click.echo(f"Could not retrieve schema for tool '{tool_name}'.", err=True)
            click.echo(f"The tool '{tool_name}' may not exist on server '{server_name}'.", err=True)
            click.echo("\nTo see available tools for this server, use:", err=True)
            click.echo(f"  mcp-registry list-tools {server_name}", err=True)
            if click.confirm("Continue with an empty parameter object?", default=False):
                return {}
            else:
                sys.exit(1)
            
        parameters = {}
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        if not properties:
            click.echo("This tool does not require any parameters.")
            return {}
            
        click.echo("Please enter values for the following parameters:")
        
        for name, prop in properties.items():
            param_type = prop.get("type", "any")
            is_required = name in required
            description = prop.get("description", "")
            default = prop.get("default", None)
            
            # Display parameter info
            req_text = "required" if is_required else "optional"
            default_text = f" (default: {default})" if default is not None else ""
            desc_text = f"\n  {description}" if description else ""
            
            prompt_text = f"{name} ({param_type}, {req_text}){default_text}{desc_text}: "
            
            # Handle different types
            if param_type == "boolean":
                # Handle boolean with y/n prompt
                if default is not None:
                    default_val = "y" if default else "n"
                    value = click.prompt(prompt_text, default=default_val, show_default=True)
                    value = value.lower() in ("y", "yes", "true", "t", "1")
                else:
                    if is_required:
                        value = click.prompt(prompt_text, type=click.BOOL)
                    else:
                        value_str = click.prompt(prompt_text, default="", show_default=False)
                        if not value_str:
                            continue  # Skip this optional parameter
                        value = value_str.lower() in ("y", "yes", "true", "t", "1")
            
            elif param_type == "number" or param_type == "integer":
                # Handle numeric types
                type_class = int if param_type == "integer" else float
                if default is not None:
                    value = click.prompt(prompt_text, default=default, type=type_class, show_default=True)
                else:
                    if is_required:
                        value = click.prompt(prompt_text, type=type_class)
                    else:
                        value_str = click.prompt(prompt_text, default="", show_default=False)
                        if not value_str:
                            continue  # Skip this optional parameter
                        try:
                            value = type_class(value_str)
                        except ValueError:
                            click.echo(f"Invalid {param_type}. Skipping parameter.")
                            continue
            
            elif param_type == "object":
                # For objects, ask for JSON string
                click.echo(f"  Enter a JSON object for '{name}':")
                if is_required:
                    json_str = click.prompt("  JSON", default="{}")
                else:
                    json_str = click.prompt("  JSON", default="")
                    if not json_str:
                        continue
                
                try:
                    value = json.loads(json_str)
                except json.JSONDecodeError:
                    click.echo("  Invalid JSON. Using empty object.")
                    value = {}
            
            elif param_type == "array":
                # For arrays, ask for JSON string
                click.echo(f"  Enter a JSON array for '{name}':")
                if is_required:
                    json_str = click.prompt("  JSON", default="[]")
                else:
                    json_str = click.prompt("  JSON", default="")
                    if not json_str:
                        continue
                
                try:
                    value = json.loads(json_str)
                except json.JSONDecodeError:
                    click.echo("  Invalid JSON. Using empty array.")
                    value = []
            
            else:  # Default to string for other types
                if default is not None:
                    value = click.prompt(prompt_text, default=default, show_default=True)
                else:
                    if is_required:
                        value = click.prompt(prompt_text)
                    else:
                        value = click.prompt(prompt_text, default="", show_default=False)
                        if not value:
                            continue  # Skip this optional parameter
            
            parameters[name] = value
        
        # Show the final parameters and confirm
        click.echo("\nParameters to be sent:")
        click.echo(json.dumps(parameters, indent=2))
        if not click.confirm("Send these parameters?", default=True):
            if click.confirm("Start over?", default=False):
                return await collect_parameters_interactively()
            else:
                sys.exit(0)
        
        return parameters
    
    # Parse input parameters
    parameters = {}
    
    # Determine which input mode to use
    use_interactive = False
    
    if input_file:
        try:
            with open(input_file, 'r') as f:
                parameters = json.load(f)
        except FileNotFoundError:
            click.echo(f"Error: Input file '{input_file}' not found", err=True)
            return
        except json.JSONDecodeError:
            click.echo(f"Error: Input file '{input_file}' contains invalid JSON", err=True)
            return
    elif input:
        try:
            parameters = json.loads(input)
        except json.JSONDecodeError:
            click.echo("Error: Input string contains invalid JSON", err=True)
            return
    else:
        # Check if we have data on stdin
        if not sys.stdin.isatty():
            try:
                stdin_data = sys.stdin.read().strip()
                if stdin_data:
                    parameters = json.loads(stdin_data)
                else:
                    use_interactive = True
            except json.JSONDecodeError:
                click.echo("Error: Stdin contains invalid JSON", err=True)
                return
        else:
            # No input provided and we're in a terminal - use interactive mode
            use_interactive = True
    
    # If we should be interactive but it's explicitly disabled, use empty params
    if use_interactive and non_interactive:
        use_interactive = False
    
    # Call the tool
    async def call_and_display_result():
        nonlocal parameters
        
        try:
            # Use interactive mode if selected
            if use_interactive:
                parameters = await collect_parameters_interactively()
            
            # Set timeout
            async with asyncio.timeout(timeout):
                result = await aggregator.call_tool(tool_path, parameters)
                
                # Display the result
                output = format_tool_result(result, raw)
                click.echo(output)
                
                # If there was an error, exit with non-zero status
                if hasattr(result, 'isError') and result.isError:
                    sys.exit(1)
                
        except asyncio.TimeoutError:
            click.echo(f"Error: Timeout after {timeout} seconds while calling tool", err=True)
            sys.exit(1)
        except Exception as e:
            click.echo(f"Error calling tool: {e}", err=True)
            sys.exit(1)
    
    # Run the async function
    try:
        asyncio.run(call_and_display_result())
    except KeyboardInterrupt:
        click.echo("\nOperation cancelled by user.", err=True)
        sys.exit(130)  # Standard exit code for SIGINT


def register_commands(cli_group):
    """Register all tool-related commands with the CLI group."""
    cli_group.add_command(list_tools)
    cli_group.add_command(test_tool)