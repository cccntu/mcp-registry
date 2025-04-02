"""MCP Registry - A simplified MCP server aggregator and compound server implementation."""

from importlib.metadata import version

from .compound import (
    MCPAggregator,
    MCPServerSettings,
    ServerRegistry,
    run_registry_server,
)

from .connection import (
    MCPConnectionManager,
    ServerConnection,
    ConnectionState,
)

from .utils.config import (
    get_config_path,
    get_default_config_path,
)

try:
    __version__ = version("mcp-registry")
except Exception:
    __version__ = "unknown"  # Fallback if package is not installed

__all__ = [
    "MCPServerSettings",
    "ServerRegistry",
    "MCPAggregator",
    "run_registry_server",
    "get_config_path",
    "get_default_config_path",
    "MCPConnectionManager",
    "ServerConnection",
    "ConnectionState",
]
