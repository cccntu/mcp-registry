"""Common CLI utilities."""

import functools
from pathlib import Path
import click

from mcp_registry.utils.config import CONFIG_FILE


def requires_config(func):
    """Decorator to check if config file exists before executing a command.
    
    This ensures consistent error messaging across commands.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not CONFIG_FILE.exists():
            click.echo("Configuration file not found. Run 'mcp-registry init' first.", err=True)
            return None
        return func(*args, **kwargs)
    return wrapper


def requires_servers(func):
    """Decorator to check if servers exist in the config.
    
    This ensures consistent error messaging across commands.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        from mcp_registry.utils.config import load_config
        
        config = load_config()
        if not config["mcpServers"]:
            click.echo("No servers registered.", err=True)
            return None
        return func(*args, **kwargs)
    return wrapper