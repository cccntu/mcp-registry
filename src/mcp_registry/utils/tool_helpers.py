"""Helper functions for working with MCP tools."""

import asyncio
import json
import sys
import click

from mcp_registry.compound import MCPAggregator, ServerRegistry, MCPServerSettings
from mcp_registry.utils.formatters import truncate_text


async def get_server_tools(registry, timeout: int = 15) -> dict:
    """Connect to servers and get tools with proper error handling.
    
    Args:
        registry: ServerRegistry instance
        timeout: Timeout in seconds
        
    Returns:
        Dictionary mapping server names to their tools
    """
    try:
        # Use context manager for reliable persistent connections
        async with MCPAggregator(registry) as aggregator:
            async with asyncio.timeout(timeout):
                # Get tools with server mapping
                return await aggregator.list_tools(return_server_mapping=True)
    except Exception:
        # Return empty dict on any error
        return {}


def get_filtered_servers(config, specified_servers=None):
    """Get filtered servers from config based on server names.
    
    Args:
        config: Configuration dictionary with mcpServers section
        specified_servers: List of server names to include (None for all)
        
    Returns:
        Dictionary of server name to MCPServerSettings
    """
    return {
        name: MCPServerSettings(**settings)
        for name, settings in config["mcpServers"].items()
        if not specified_servers or name in specified_servers
    }


async def json_output_handler(registry):
    """Handle JSON output format for tool listing.
    
    Args:
        registry: ServerRegistry instance
    
    Returns:
        JSON string of tools organized by server
    """
    from mcp_registry.utils.formatters import format_tools_as_json
    
    server_tools = await get_server_tools(registry)
    json_result = format_tools_as_json(server_tools)
    return json.dumps(json_result, indent=2)


async def text_output_handler(registry, servers=None, verbose=0):
    """Handle text output format for tool listing.
    
    Args:
        registry: ServerRegistry instance
        servers: List of server names to include
        verbose: Verbosity level (0-2)
        
    Returns:
        Tuple of (output_text, success_flag)
    """
    from mcp_registry.utils.formatters import truncate_text, extract_parameters
    
    connected_servers = []
    output_lines = []
    
    try:
        # Use temporary connections for text output
        aggregator = MCPAggregator(registry)
        server_tools = await aggregator.list_tools(return_server_mapping=True)
        
        # Handle empty results
        if not server_tools:
            return "No tools found from any server.", False
            
        # Process each server's tools
        for server_name, tools in server_tools.items():
            connected_servers.append(server_name)
            output_lines.append(f"\nServer: {server_name}")
            
            if not tools:
                output_lines.append("  No tools available")
                continue
            
            # Different display formats based on verbosity
            if verbose >= 2:  # Full details
                for tool in tools:
                    output_lines.append(f"  Tool: {tool.name}")
                    
                    if hasattr(tool, 'description') and tool.description:
                        output_lines.append(f"    Description: {tool.description}")
                    
                    if hasattr(tool, 'inputSchema') and tool.inputSchema:
                        parameters = extract_parameters(tool.inputSchema)
                        if parameters:
                            output_lines.append("    Parameters:")
                            for param in parameters:
                                required = "required" if param["required"] else "optional"
                                desc = f": {param['description']}" if param['description'] else ""
                                output_lines.append(f"      - {param['name']} ({param['type']}, {required}){desc}")
                    output_lines.append("")  # Empty line between tools
                    
            elif verbose == 1:  # Parameters with truncation
                for tool in tools:
                    output_lines.append(f"  Tool: {tool.name}")
                    
                    if hasattr(tool, 'description') and tool.description:
                        desc = truncate_text(tool.description)
                        output_lines.append(f"    Description: {desc}")
                    
                    if hasattr(tool, 'inputSchema') and tool.inputSchema:
                        parameters = extract_parameters(tool.inputSchema)
                        if parameters:
                            output_lines.append("    Parameters:")
                            for param in parameters:
                                required = "required" if param["required"] else "optional"
                                param_desc = param['description']
                                if param_desc and len(param_desc) > 40:
                                    param_desc = truncate_text(param_desc, 40)
                                desc = f": {param_desc}" if param_desc else ""
                                output_lines.append(f"      - {param['name']} ({param['type']}, {required}){desc}")
                    output_lines.append("")  # Empty line between tools
                    
            else:  # Simple view
                for tool in tools:
                    desc = ""
                    if hasattr(tool, 'description') and tool.description:
                        desc = f": {truncate_text(tool.description)}"
                    output_lines.append(f"  - {tool.name}{desc}")
        
        # Show any missing servers
        if servers:
            missing_servers = [s for s in servers if s not in connected_servers]
            if missing_servers:
                output_lines.append("\nWarning: Could not connect to the following servers:")
                for server in missing_servers:
                    output_lines.append(f"  - {server}")
        
        return "\n".join(output_lines), True
        
    except Exception as e:
        return f"Error fetching tools: {e}", False


async def display_server_tools(server_name, registry):
    """Display tools for a specific server.
    
    Args:
        server_name: Name of the server to display tools for
        registry: ServerRegistry instance
        
    Returns:
        Boolean indicating success
    """
    from mcp_registry.utils.formatters import truncate_text
    
    try:
        # Use a simple aggregator
        aggregator = MCPAggregator(registry)
        server_tools = await aggregator.list_tools(return_server_mapping=True)
        
        if not server_tools or server_name not in server_tools or not server_tools[server_name]:
            click.echo(f"No tools found for server '{server_name}'.", err=True)
            return False
        
        # Display tools with descriptions
        separator = "__"
        click.echo("")  # Empty line for readability
        tools = server_tools[server_name]
        for tool in tools:
            tool_name = getattr(tool, 'name', 'unknown')
            desc = ""
            if hasattr(tool, 'description') and tool.description:
                desc = f": {truncate_text(tool.description)}"
            
            # Show namespaced tool name and description
            click.echo(f"  {server_name}{separator}{tool_name}{desc}")
        
        return True
            
    except Exception as e:
        click.echo(f"Error getting tools: {e}", err=True)
        return False


def load_parameters(input_str=None, input_file=None):
    """Load parameters from a string, file, or stdin.
    
    Args:
        input_str: JSON string input
        input_file: Path to JSON file
        
    Returns:
        Tuple of (parameters_dict, use_interactive_flag)
    """
    parameters = {}
    use_interactive = False
    
    # Try loading from input string
    if input_str:
        try:
            parameters = json.loads(input_str)
        except json.JSONDecodeError:
            click.echo("Error: Input string contains invalid JSON", err=True)
            sys.exit(1)
    
    # Try loading from input file
    elif input_file:
        try:
            with open(input_file, 'r') as f:
                parameters = json.load(f)
        except FileNotFoundError:
            click.echo(f"Error: Input file '{input_file}' not found", err=True)
            sys.exit(1)
        except json.JSONDecodeError:
            click.echo(f"Error: Input file '{input_file}' contains invalid JSON", err=True)
            sys.exit(1)
    
    # Try loading from stdin
    elif not sys.stdin.isatty():
        try:
            stdin_data = sys.stdin.read().strip()
            if stdin_data:
                parameters = json.loads(stdin_data)
            else:
                use_interactive = True
        except json.JSONDecodeError:
            click.echo("Error: Stdin contains invalid JSON", err=True)
            sys.exit(1)
    
    # Default to interactive mode
    else:
        use_interactive = True
        
    return parameters, use_interactive