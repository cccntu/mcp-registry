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