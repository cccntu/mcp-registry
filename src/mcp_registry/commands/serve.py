"""Commands for running MCP servers."""

import asyncio
import click

from mcp_registry.compound import MCPServerSettings, ServerRegistry, MCPAggregator, run_registry_server
from mcp_registry.utils.cli import requires_config, requires_servers


def format_filter_descriptions(tool_filter):
    """Format tool filter descriptions for display."""
    filter_desc = []
    for server, tools in tool_filter.items():
        if tools is None:
            filter_desc.append(f"{server} (all tools)")
        elif not tools:
            filter_desc.append(f"{server} (no tools)")
        elif tools[0].startswith("-"):
            excluded = [t[1:] for t in tools]
            filter_desc.append(f"{server} (excluding: {', '.join(excluded)})")
        else:
            filter_desc.append(f"{server} (only: {', '.join(tools)})")
    return filter_desc


@click.command()
@click.argument("servers", nargs=-1)
@click.option("--project", "-p", help="Project name to serve servers for")
@click.option("--filter", "-f", help="Filter tools by server, e.g. 'memory:get,set;github' or 'memory:-delete,-clear'")
@click.option("--alias", "-a", multiple=True, help="Tool alias in format 'alias=actual_tool'")
@requires_config
@requires_servers
def serve(servers, project, filter, alias):
    """Start the MCP Registry compound server.

    If no servers are specified, all registered servers will be served.
    
    You can filter which servers and tools are exposed:
      - Specify server names directly as arguments to include only those servers
      - Use --project to only serve servers enabled for a specific project
      - Use --filter to control which tools are included/excluded from servers
      - Use --alias to create custom names for specific tools
    
    Filter syntax examples:
      - 'memory:get,set' - only include get/set tools from memory server
      - 'memory:-delete,-clear' - include all tools from memory EXCEPT delete/clear
      - 'memory;github' - include all tools from memory and github servers
      - 'memory:get,set;github:-delete' - complex filtering across servers

    Alias examples:
      - 'get=memory__get' - allows calling the tool as just 'get'
      - 'chat=llm__chat' - creates a more intuitive name

    Examples:
        mcp-registry serve  # serves all servers
        mcp-registry serve memory github  # serves specific servers
        mcp-registry serve --project myproject  # serves project-enabled servers
        mcp-registry serve --filter 'memory:get,set,github'  # filtered tools
        mcp-registry serve --filter 'memory:-delete,-clear'  # negative filtering
        mcp-registry serve --alias get=memory__get --alias set=memory__set  # with aliases
    """
    # Import from utils config
    from mcp_registry.utils.config import load_config, get_project_servers, parse_tool_filter, get_aliases
    
    # Config existence and servers already checked by decorators
    config = load_config()

    # Filter servers based on project
    available_servers = {}
    if project:
        project_servers = set(get_project_servers(project))
        available_servers = {
            name: MCPServerSettings(**settings)
            for name, settings in config["mcpServers"].items()
            if name in project_servers
        }
    else:
        available_servers = {
            name: MCPServerSettings(**settings)
            for name, settings in config["mcpServers"].items()
        }

    if not available_servers:
        if project:
            click.echo(f"No servers enabled for project '{project}'", err=True)
        else:
            click.echo("No servers available", err=True)
        return

    # Create registry from available servers
    registry = ServerRegistry(available_servers)

    # Determine which servers to use
    server_names = list(servers) if servers else None

    # Filter the registry if specific servers are requested
    if server_names:
        try:
            registry = registry.filter_servers(server_names)
            click.echo(f"Serving {len(registry.registry)} servers: {', '.join(registry.registry.keys())}", err=True)
        except ValueError as e:
            click.echo(f"Error: {str(e)}", err=True)
            return
    else:
        click.echo(f"Serving all {len(registry.registry)} available servers", err=True)
    
    # Parse tool filters if provided
    tool_filter = None
    if filter:
        try:
            tool_filter = parse_tool_filter(filter)
            if tool_filter:
                # Format the filter description for display
                descriptions = format_filter_descriptions(tool_filter)
                click.echo(f"Tool filtering enabled: {'; '.join(descriptions)}", err=True)
        except Exception as e:
            click.echo(f"Error parsing tool filter: {e}", err=True)
            return
    
    # Process aliases
    aliases = {}
    
    # First load existing aliases from config
    if not alias:
        # If no command-line aliases provided, use all from config
        aliases = get_aliases()
        if aliases:
            click.echo(f"Using {len(aliases)} configured aliases", err=True)
    
    # Then add any command-line aliases
    for a in alias:
        try:
            alias_name, target = a.split("=", 1)
            aliases[alias_name] = target
        except ValueError:
            click.echo(f"Invalid alias format: {a}. Use 'alias=tool_name'", err=True)
            return
    
    if alias:
        click.echo(f"Using {len(aliases)} aliases", err=True)
    
    # Create aggregator with the filtered registry, tool filter, and aliases
    aggregator = MCPAggregator(registry, tool_filter=tool_filter, aliases=aliases)
    
    # Run the compound server with pre-filtered registry
    asyncio.run(run_registry_server(aggregator))


def register_commands(cli_group):
    """Register all serve-related commands with the CLI group."""
    cli_group.add_command(serve)