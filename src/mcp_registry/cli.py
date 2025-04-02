# src/mcp_registry/cli.py
import asyncio
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import click

from mcp_registry.compound import MCPServerSettings, ServerRegistry, run_registry_server

# Default config location with override via environment variable
def get_default_config_path():
    """Get the default config path respecting XDG_CONFIG_HOME."""
    xdg_config_home = os.getenv("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    return Path(xdg_config_home) / "mcp_registry" / "mcp_registry_config.json"

CONFIG_FILE = Path(os.getenv("MCP_REGISTRY_CONFIG", str(get_default_config_path())))

def get_config_path():
    """Get the current config path."""
    return CONFIG_FILE

def set_config_path(path):
    """Set the config path globally."""
    global CONFIG_FILE
    CONFIG_FILE = Path(path).resolve()
    return CONFIG_FILE


def load_config():
    """Load the configuration file or return an empty config if it doesn't exist."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {"mcpServers": {}}


def save_config(config):
    """Save the configuration to the file, creating the directory if needed."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def find_claude_desktop_config():
    """Find the Claude Desktop config file path if it exists."""
    claude_config_path = None
    if os.name == "posix":  # Mac or Linux
        claude_config_path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif os.name == "nt":  # Windows
        appdata = os.getenv("APPDATA")
        if appdata:
            claude_config_path = Path(appdata) / "Claude" / "claude_desktop_config.json"

    if claude_config_path and claude_config_path.exists():
        return claude_config_path
    return None


def get_project_mappings_path():
    """Get the path to the project mappings file."""
    xdg_config_home = os.getenv("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    return Path(xdg_config_home) / "mcp_registry" / "project_mappings.json"

def load_project_mappings():
    """Load project-to-server mappings."""
    path = get_project_mappings_path()
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"projects": {}}  # Map of project names to list of server names

def save_project_mappings(mappings):
    """Save project-to-server mappings."""
    path = get_project_mappings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(mappings, f, indent=2)

def get_project_servers(project: str):
    """Get list of servers enabled for a project."""
    mappings = load_project_mappings()
    return mappings["projects"].get(project, [])

def add_server_to_project(server_name: str, project: str):
    """Add a server to a project's enabled servers."""
    mappings = load_project_mappings()
    if "projects" not in mappings:
        mappings["projects"] = {}
    if project not in mappings["projects"]:
        mappings["projects"][project] = []
    if server_name not in mappings["projects"][project]:
        mappings["projects"][project].append(server_name)
        save_project_mappings(mappings)

def remove_server_from_project(server_name: str, project: str):
    """Remove a server from a project's enabled servers."""
    mappings = load_project_mappings()
    if project in mappings.get("projects", {}) and server_name in mappings["projects"][project]:
        mappings["projects"][project].remove(server_name)
        save_project_mappings(mappings)


@click.group()
def cli():
    """MCP Registry CLI tool for managing and serving MCP servers.

    Configuration file location can be set via MCP_REGISTRY_CONFIG environment variable.
    Use 'show-config-path' command to see current location.
    """
    pass


@cli.command()
@click.option("--force", is_flag=True, help="Override existing configuration if it exists")
def init(force):
    """Initialize the MCP Registry configuration.

    This command creates a new configuration file and offers to import
    settings from Claude Desktop if available.
    """
    click.echo(f"Using config file: {CONFIG_FILE}", err=True)

    if CONFIG_FILE.exists() and not force:
        if not click.confirm("Configuration file already exists. Do you want to overwrite it?", default=False, err=True):
            click.echo("Keeping existing configuration.", err=True)
            return

    # Create a new empty config
    config = {"mcpServers": {}}

    # Check for Claude Desktop config
    claude_config_path = find_claude_desktop_config()
    if claude_config_path:
        if click.confirm(f"Found Claude Desktop config at {claude_config_path}. Do you want to import it?", default=True, err=True):
            try:
                with open(claude_config_path) as f:
                    claude_config = json.load(f)

                # Import servers from Claude Desktop config
                if "mcpServers" in claude_config:
                    config["mcpServers"] = claude_config["mcpServers"]
                    click.echo(f"Imported {len(config['mcpServers'])} servers from Claude Desktop config.", err=True)
            except Exception as e:
                click.echo(f"Error importing Claude Desktop config: {e}", err=True)

    # Save the config
    save_config(config)
    click.echo(f"Initialized configuration at {CONFIG_FILE}", err=True)


@cli.command(context_settings=dict(
    help_option_names=['-h', '--help'],
    # Make help output more compact
    max_content_width=100
))
@click.argument("name", required=False, metavar="[name]")
@click.argument("command", required=False, metavar="[command]")
@click.argument("args", nargs=-1, type=click.UNPROCESSED, metavar="[args...]")
@click.option("--project", "-p", metavar="<project>", help='Project name to add the server to (default: "global")')
@click.option("--env", "-e", metavar="<env...>", multiple=True, help="Set environment variables (e.g. -e KEY=value)")
def add(name, command, args, project, env):
    """Add a stdio server (run without arguments for interactive wizard)

Examples:

  mcp-registry add --project project-name server-name command args

  mcp-registry add  # starts interactive wizard
  """
    # Start interactive wizard if no name provided
    if not name:
        name = click.prompt("Server name")
        command = click.prompt("Command")
        args_str = click.prompt("Arguments (space-separated)", default="")
        args = tuple(args_str.split())
        project = click.prompt("Project name (optional)", default="")

    # Load global config
    if not CONFIG_FILE.exists():
        click.echo("Global configuration file not found. Run 'mcp-registry init' first.", err=True)
        return

    config = load_config()

    # Process environment variables
    env_dict = {}
    if env:
        for env_var in env:
            if "=" in env_var:
                key, value = env_var.split("=", 1)
                env_dict[key] = value
            else:
                click.echo(f"Warning: Ignoring invalid environment variable format: {env_var}", err=True)

    # For stdio transport, try to find the full path of the command
    shell = os.environ.get("SHELL", "/bin/sh")

    # Skip command lookup if command is None (interactive mode will handle it)
    if not command:
        return  # Exit if no command provided (helps with --help handling)

    # Use the shell to find the command
    try:
        import subprocess
        full_command = subprocess.check_output([shell, "-c", f"which {command}"], text=True).strip()
        click.echo(f"Found command at: {full_command}", err=True)
    except subprocess.CalledProcessError:
        click.echo(f"Warning: Could not find '{command}' using shell, using as is", err=True)
        full_command = command

    # STDIO transport
    server_settings = {
        "type": "stdio",
        "command": shell,
        "args": ["-c", f"{full_command} " + " ".join(args)],
    }
    if env_dict:  # Only add env if variables were passed
        server_settings["env"] = env_dict

    # Check if server already exists
    if name in config["mcpServers"]:
        if not click.confirm(f"Server '{name}' already exists. Overwrite?", default=False, err=True):
            return

    # Store in mcpServers format
    config["mcpServers"][name] = server_settings
    save_config(config)
    click.echo(f"Added server '{name}' to global config", err=True)

    # If project is specified, add to project mappings
    if project:
        add_server_to_project(name, project)
        click.echo(f"Enabled server '{name}' for project '{project}'", err=True)

    # Show final configuration
    click.echo("\nFinal server configuration:", err=True)
    click.echo(json.dumps(server_settings, indent=2), err=True)


@cli.command()
@click.argument("server_name")
@click.option("--project", "-p", help="Project name to remove the server from")
def remove(server_name, project):
    """Remove a server from the registry or project.

    If --project is specified, only removes the server from that project.
    Otherwise, removes the server entirely from the global config.
    """
    if project:
        # Only remove from project
        remove_server_from_project(server_name, project)
        click.echo(f"Removed server '{server_name}' from project '{project}'", err=True)
        return

    # Remove from global config
    if not CONFIG_FILE.exists():
        click.echo("Global configuration file not found. Run 'mcp-registry init' first.", err=True)
        return

    config = load_config()

    removed = False
    if server_name in config["mcpServers"]:
        del config["mcpServers"][server_name]
        removed = True

    if removed:
        save_config(config)
        click.echo(f"Removed server '{server_name}' from global config", err=True)

        # Also remove from all projects
        mappings = load_project_mappings()
        for project in mappings.get("projects", {}):
            if server_name in mappings["projects"][project]:
                mappings["projects"][project].remove(server_name)
                click.echo(f"Also removed from project '{project}'", err=True)
        save_project_mappings(mappings)
    else:
        click.echo(f"Server '{server_name}' not found in global config", err=True)


@cli.command(name="list")
@click.option("--project", "-p", help="Project name to list servers for")
def list_servers(project):
    """List all registered servers.

    If --project is specified, only shows servers enabled for that project.
    Otherwise, shows all servers with their project associations.
    """
    if not CONFIG_FILE.exists():
        click.echo("Global configuration file not found. Run 'mcp-registry init' first.", err=True)
        return

    config = load_config()
    if not config["mcpServers"]:
        click.echo("No servers registered.", err=True)
        return

    # Get project mappings
    mappings = load_project_mappings()
    projects = mappings.get("projects", {})

    # If project specified, only show servers for that project
    if project:
        project_servers = set(get_project_servers(project))
        if not project_servers:
            click.echo(f"No servers enabled for project '{project}'", err=True)
            return
        click.echo(f"\nServers enabled for project '{project}':", err=True)
    else:
        click.echo("\nRegistered servers:", err=True)

    for name, settings in sorted(config["mcpServers"].items()):
        # Skip if not in project when project is specified
        if project and name not in project_servers:
            continue

        desc = f" - {settings.get('description')}" if settings.get('description') else ""
        enabled_projects = [p for p, servers in projects.items() if name in servers]
        project_tag = f" [projects: {', '.join(enabled_projects)}]" if enabled_projects else ""

        if settings["type"] == "stdio":
            cmd = f"{settings['command']} {' '.join(settings['args'])}"
            click.echo(f"  {name}: stdio ({cmd}){desc}{project_tag}", err=True)
        elif settings["type"] == "sse":
            click.echo(f"  {name}: sse ({settings['url']}){desc}{project_tag}", err=True)
        else:
            click.echo(f"  {name}: unknown type {settings['type']}{desc}{project_tag}", err=True)


@cli.command()
@click.argument("servers", nargs=-1)
@click.option("--project", "-p", help="Project name to serve servers for")
def serve(servers, project):
    """Start the MCP Registry compound server.

    If no servers are specified, all registered servers will be served.
    Use --project to only serve servers enabled for a specific project.

    Examples:
        mcp-registry serve  # serves all servers
        mcp-registry serve memory github  # serves specific servers
        mcp-registry serve --project myproject  # serves project-enabled servers
    """
    if not CONFIG_FILE.exists():
        click.echo("Global configuration file not found. Run 'mcp-registry init' first.", err=True)
        return

    config = load_config()
    if not config["mcpServers"]:
        click.echo("No servers registered.", err=True)
        return

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

    # Check if all specified servers exist
    if server_names:
        missing_servers = [s for s in server_names if s not in available_servers]
        if missing_servers:
            click.echo(f"Error: Servers not found: {', '.join(missing_servers)}", err=True)
            return

        click.echo(f"Serving {len(server_names)} servers: {', '.join(server_names)}", err=True)
    else:
        click.echo(f"Serving all {len(available_servers)} available servers", err=True)

    # Run the compound server
    asyncio.run(run_registry_server(registry, server_names))


@cli.command(name="show-config-path")
def show_config_path():
    """Show the current config file path."""
    click.echo(f"Current config file: {get_config_path()}", err=True)
    if os.getenv("MCP_REGISTRY_CONFIG"):
        click.echo("(Set via MCP_REGISTRY_CONFIG environment variable)", err=True)
    else:
        click.echo("(Using default config location)", err=True)


@cli.command()
@click.option("--restore", is_flag=True, help="Restore from backup without editing if it exists")
@click.option("--force", is_flag=True, help="Force edit even if the file doesn't exist (will create it)")
def edit(restore, force):
    """Edit the configuration file with your default editor.
    
    The editor is determined by the EDITOR or VISUAL environment variables.
    After editing, the file is validated to ensure it contains valid JSON.
    If validation fails, the original file is restored.
    """
    config_path = get_config_path()
    backup_path = Path(f"{config_path}.bak")
    
    # Check if config exists
    if not config_path.exists() and not force:
        click.echo(f"Configuration file not found at {config_path}.", err=True)
        click.echo("Run 'mcp-registry init' first or use --force to create it.", err=True)
        return
    
    # Ensure parent directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # If the file doesn't exist but --force is used, create empty config
    if not config_path.exists() and force:
        with open(config_path, 'w') as f:
            json.dump({"mcpServers": {}}, f, indent=2)
        click.echo(f"Created new configuration file at {config_path}", err=True)
    
    # Create backup of current config
    if config_path.exists():
        shutil.copy2(config_path, backup_path)
        click.echo(f"Created backup at {backup_path}", err=True)
    
    if restore:
        if backup_path.exists():
            shutil.copy2(backup_path, config_path)
            click.echo(f"Restored from backup {backup_path}", err=True)
            backup_path.unlink()  # Remove backup after restore
            return
        else:
            click.echo("No backup file found to restore from.", err=True)
            return
    
    # Find appropriate editor
    editor = os.environ.get('EDITOR') or os.environ.get('VISUAL')
    if not editor:
        if os.name == 'nt':  # Windows
            editor = 'notepad'
        else:  # Unix-like
            for potential_editor in ['nano', 'vim', 'vi', 'emacs']:
                try:
                    # Check if editor exists in PATH
                    subprocess.run(['which', potential_editor], 
                                   check=True, 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE)
                    editor = potential_editor
                    break
                except subprocess.CalledProcessError:
                    continue
            
            if not editor:
                editor = 'vi'  # Default to vi if nothing else is found
    
    click.echo(f"Opening configuration with {editor}...", err=True)
    
    try:
        # Open editor and wait for it to close
        result = subprocess.run([editor, str(config_path)], check=True)
        
        if result.returncode != 0:
            click.echo(f"Editor exited with error code {result.returncode}", err=True)
            if click.confirm("Do you want to restore from backup?", default=True, err=True):
                shutil.copy2(backup_path, config_path)
                click.echo("Restored from backup.", err=True)
            return
        
        # Validate JSON after editing
        try:
            with open(config_path) as f:
                config = json.load(f)
            
            # Verify structure
            if not isinstance(config, dict):
                raise ValueError("Config must be a JSON object")
            
            if "mcpServers" not in config:
                raise ValueError("Config must contain 'mcpServers' key")
            
            if not isinstance(config["mcpServers"], dict):
                raise ValueError("'mcpServers' must be a JSON object")
            
            click.echo("Configuration validated successfully.", err=True)
            
            # Remove backup if validation succeeds
            if backup_path.exists():
                backup_path.unlink()
                
        except (json.JSONDecodeError, ValueError) as e:
            click.echo(f"Error in configuration file: {e}", err=True)
            if backup_path.exists() and click.confirm("Do you want to restore from backup?", default=True, err=True):
                shutil.copy2(backup_path, config_path)
                click.echo("Restored from backup.", err=True)
            else:
                click.echo("Kept invalid configuration. Please fix it manually.", err=True)
    
    except subprocess.CalledProcessError:
        click.echo("Error launching editor.", err=True)
        if backup_path.exists():
            click.echo(f"Your backup is at {backup_path}", err=True)


@cli.command()
@click.argument("server_name")
def get(server_name):
    """Get details about an MCP server."""
    # Ensure config file exists
    if not CONFIG_FILE.exists():
        click.echo("Configuration file not found. Run 'mcp-registry init' first.", err=True)
        return

    config = load_config()

    if server_name not in config["mcpServers"]:
        click.echo(f"Server '{server_name}' not found.", err=True)
        return

    settings = config["mcpServers"][server_name]
    click.echo(f"\nServer: {server_name}")
    click.echo("Settings:")
    click.echo(json.dumps(settings, indent=2))


if __name__ == "__main__":
    cli()
