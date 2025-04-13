"""Configuration utilities for MCP Registry."""

import json
import os
from pathlib import Path

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
            config = json.load(f)
            
            # Ensure expected sections exist
            if "mcpServers" not in config:
                config["mcpServers"] = {}
            if "aliases" not in config:
                config["aliases"] = {}
                
            return config
    return {"mcpServers": {}, "aliases": {}}


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


# Tool filtering and alias management functions

def parse_tool_filter(filter_str: str):
    """
    Parse a command-line tool filter specification into a dictionary.
    
    Format: "server1:tool1,tool2;server2;server3:-tool1,-tool2"
    
    Args:
        filter_str: String in server:tools format, semicolon-separated for multiple servers
        
    Returns:
        dict: Dictionary mapping server names to lists of tools
    """
    if not filter_str:
        return {}
        
    result = {}
    segments = filter_str.split(";")
    
    for segment in segments:
        if ":" in segment:
            # Server with specific tools
            server_name, tools_str = segment.split(":", 1)
            result[server_name] = tools_str.split(",") if tools_str else []
        else:
            # Simple server with no tool filters
            for part in segment.split(","):
                if part:  # Skip empty parts
                    result[part] = None
    
    return result
    
def get_aliases():
    """Get all configured aliases."""
    config = load_config()
    return config.get("aliases", {})

def add_alias(alias_name: str, tool_name: str):
    """Add or update an alias for a tool."""
    config = load_config()
    if "aliases" not in config:
        config["aliases"] = {}
    config["aliases"][alias_name] = tool_name
    save_config(config)
    return alias_name

def remove_alias(alias_name: str):
    """Remove an alias."""
    config = load_config()
    if "aliases" in config and alias_name in config["aliases"]:
        del config["aliases"][alias_name]
        save_config(config)
        return True
    return False

def validate_alias(alias_name: str, tool_name: str):
    """
    Validate that an alias name is valid and doesn't conflict with existing tools.
    
    Args:
        alias_name: The alias to validate
        tool_name: The tool this alias maps to
        
    Returns:
        tuple: (is_valid, error_message)
    """
    # Make sure the alias isn't empty
    if not alias_name or not alias_name.strip():
        return False, "Alias name cannot be empty"
        
    # Make sure the tool name is provided
    if not tool_name or not tool_name.strip():
        return False, "Tool name cannot be empty"
        
    # Check that the tool name includes a separator unless it's another alias
    config = load_config()
    separator = "__"  # Default separator
    
    # Check if tool_name is an existing alias (which is allowed)
    if tool_name in config.get("aliases", {}):
        return True, ""
    
    # Otherwise verify it has server__tool format
    if separator not in tool_name:
        return False, f"Tool name must be in 'server{separator}tool' format or an existing alias"
        
    return True, ""