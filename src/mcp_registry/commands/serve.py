"""Commands for running MCP servers."""

import asyncio
import click

from mcp_registry.compound import MCPServerSettings, ServerRegistry, run_registry_server
from mcp_registry.utils.cli import requires_config, requires_servers


@click.command()
@click.argument("servers", nargs=-1)
@click.option("--project", "-p", help="Project name to serve servers for")
@requires_config
@requires_servers
def serve(servers, project):
    """Start the MCP Registry compound server.

    If no servers are specified, all registered servers will be served.
    Use --project to only serve servers enabled for a specific project.

    Examples:
        mcp-registry serve  # serves all servers
        mcp-registry serve memory github  # serves specific servers
        mcp-registry serve --project myproject  # serves project-enabled servers
    """
    # Import from utils config
    from mcp_registry.utils.config import load_config, get_project_servers
    
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

    # Run the compound server with pre-filtered registry
    asyncio.run(run_registry_server(registry))


def register_commands(cli_group):
    """Register all serve-related commands with the CLI group."""
    cli_group.add_command(serve)