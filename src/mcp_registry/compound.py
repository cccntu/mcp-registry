"""
Core functionality for managing and aggregating MCP servers.

This module provides the main components for managing server configurations and
aggregating multiple MCP servers into a single interface. It includes:

- MCPServerSettings: Configuration settings for individual MCP servers
- ServerRegistry: Registry for managing multiple server configurations
- MCPAggregator: Aggregator for combining multiple servers into a single interface
- run_registry_server: Function to run a compound MCP server
"""

import asyncio
import json
import sys
import logging
import anyio
from asyncio import gather
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import (
    StdioServerParameters,
    get_default_environment,
    stdio_client,
)
from mcp.server.lowlevel.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolResult,
    EmbeddedResource,
    GetPromptResult,
    ImageContent,
    ListToolsResult,
    Prompt,
    ResourceTemplate,
    TextContent,
    Tool,
)
from pydantic import BaseModel

# Set up logging for debugging purposes.
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class MCPServerSettings(BaseModel):
    """
    Configuration settings for an individual MCP server.
    
    This class defines the settings needed to connect to and interact with an MCP server.
    It supports both stdio and SSE transport types.
    
    Attributes:
        type: Transport type ("stdio" or "sse")
        command: Command to run for stdio servers
        args: Command arguments for stdio servers
        url: URL for sse servers
        env: Environment variables to set for the server process
        description: Optional description of the server
    """
    type: str = "stdio"  # "stdio" or "sse"
    command: str | None = None  # for stdio
    args: list[str] | None = None  # for stdio
    url: str | None = None  # for sse
    env: dict | None = None
    description: str | None = None

    @property
    def transport(self) -> str:
        """
        Get the transport type.
        
        Returns:
            str: The transport type ("stdio" or "sse")
        """
        return self.type

    @transport.setter
    def transport(self, value: str) -> None:
        """
        Set the transport type.
        
        Args:
            value: The new transport type ("stdio" or "sse")
        """
        self.type = value


class ServerRegistry:
    """
    Registry for managing MCP server configurations.
    
    This class provides functionality to manage multiple server configurations,
    including loading from and saving to a configuration file, creating client
    sessions for servers, and retrieving server information.
    
    Attributes:
        registry: Dictionary mapping server names to their configuration settings
    """
    def __init__(self, servers: dict[str, MCPServerSettings]):
        """
        Initialize a ServerRegistry with a dictionary of server configurations.
        
        Args:
            servers: Dictionary mapping server names to their configuration settings
        """
        self.registry = servers
        
    def filter_servers(self, server_names: list[str]) -> "ServerRegistry":
        """
        Create a new ServerRegistry containing only the specified servers.
        
        Args:
            server_names: List of server names to include in the filtered registry
            
        Returns:
            ServerRegistry: A new registry containing only the specified servers
            
        Raises:
            ValueError: If any of the specified servers are not in the registry
        """
        missing = [name for name in server_names if name not in self.registry]
        if missing:
            raise ValueError(f"Servers not found: {', '.join(missing)}")
            
        filtered = {
            name: settings for name, settings in self.registry.items()
            if name in server_names
        }
        return ServerRegistry(filtered)

    @classmethod
    def from_dict(cls, config: dict) -> "ServerRegistry":
        """
        Create a ServerRegistry from a dictionary of server configurations.

        Args:
            config: A dictionary where keys are server names and values are server configuration dictionaries.
                   Each server configuration should contain fields matching MCPServerSettings.

        Returns:
            ServerRegistry: A new registry instance with the configured servers.

        Example:
            config = {
                "server1": {
                    "type": "stdio",
                    "command": "python",
                    "args": ["-m", "server"],
                    "description": "Python server"
                },
                "server2": {
                    "type": "sse",
                    "url": "http://localhost:8000/sse",
                    "description": "SSE server"
                }
            }
            registry = ServerRegistry.from_dict(config)
        """
        servers = {
            name: MCPServerSettings(**settings)
            for name, settings in config.items()
        }
        return cls(servers)

    def save_config(self, path: Path | str) -> None:
        """
        Save the registry configuration to a file.
        
        This method saves the current registry configuration to a JSON file
        with the standard MCP server configuration format. It creates parent
        directories if they don't exist and formats the JSON with indentation.
        
        Args:
            path: Path where the configuration file should be saved
                (can be a string or Path object)
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        config = {
            "mcpServers": {
                name: settings.model_dump(exclude_none=True)
                for name, settings in self.registry.items()
            }
        }
        with open(path, "w") as f:
            json.dump(config, f, indent=2)

    @classmethod
    def from_config(cls, path: Path | str) -> "ServerRegistry":
        """
        Load a ServerRegistry from a configuration file.
        
        This method loads server configurations from a JSON file and creates
        a new ServerRegistry instance with those configurations. The file must
        contain a 'mcpServers' section with server configurations.
        
        Args:
            path: Path to the configuration file (JSON format)
                (can be a string or Path object)
            
        Returns:
            ServerRegistry: A new registry instance with the configured servers
            
        Raises:
            FileNotFoundError: If the configuration file does not exist
            KeyError: If the configuration file does not have a 'mcpServers' section
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(path) as f:
            config = json.load(f)
        if "mcpServers" not in config:
            raise KeyError("Config file must have a 'mcpServers' section")
        servers = {
            name: MCPServerSettings(**settings)
            for name, settings in config["mcpServers"].items()
        }
        return cls(servers)

    @asynccontextmanager
    async def get_client(self, server_name: str) -> AsyncGenerator[ClientSession, None]:
        """
        Get a client session for a specific server.
        
        This async context manager creates a temporary connection to the specified
        server and yields a client session that can be used to interact with it.
        The connection is automatically closed when exiting the context.
        
        Args:
            server_name: Name of the server to connect to
            
        Yields:
            ClientSession: A session connected to the specified server
            
        Raises:
            ValueError: If the server is not found in the registry or has invalid configuration
            
        Example:
            ```python
            registry = ServerRegistry.from_config("config.json")
            async with registry.get_client("memory") as client:
                result = await client.call_tool("get", {"key": "test"})
            ```
        """
        if server_name not in self.registry:
            raise ValueError(f"Server '{server_name}' not found in registry")
        config = self.registry[server_name]
        if config.type == "stdio":
            if not config.command or not config.args:
                raise ValueError(f"Command and args required for stdio type: {server_name}")
            params = StdioServerParameters(
                command=config.command,
                args=config.args,
                env={**get_default_environment(), **(config.env or {})},
            )
            async with stdio_client(params) as (read_stream, write_stream):
                session = ClientSession(read_stream, write_stream)
                async with session:
                    await session.initialize()
                    yield session
        elif config.type == "sse":
            if not config.url:
                raise ValueError(f"URL required for SSE type: {server_name}")
            async with sse_client(config.url) as (read_stream, write_stream):
                session = ClientSession(read_stream, write_stream)
                async with session:
                    await session.initialize()
                    yield session
        else:
            raise ValueError(f"Unsupported type: {config.type}")

    def list_servers(self) -> list[str]:
        """
        Get a list of all server names in the registry.
        
        Returns:
            list[str]: List of server names
        """
        return list(self.registry.keys())

    def get_server_info(self, server_name: str) -> str:
        """
        Get human-readable information about a specific server.
        
        This method returns a formatted string with information about the
        specified server, including its type, command/URL, and description.
        
        Args:
            server_name: Name of the server to get information about
            
        Returns:
            str: Human-readable information about the server
        """
        if server_name not in self.registry:
            return f"Server '{server_name}' not found"
        config = self.registry[server_name]
        desc = f" - {config.description}" if config.description else ""
        type_info = (
            f"stdio: {config.command} {' '.join(config.args or [])}"
            if config.type == "stdio"
            else f"sse: {config.url}"
        )
        return f"{server_name}: {type_info}{desc}"


class NamespacedTool(BaseModel):
    """
    A tool that is namespaced by server name.
    
    This class represents a tool from a specific server, with its name
    prefixed by the server name (e.g., "server_name__tool_name").
    
    Attributes:
        tool: The tool object with its name updated to include the server prefix
        server_name: Name of the server that provides this tool
        namespaced_tool_name: The tool name with server prefix
        original_name: The original tool name without server prefix
    """
    tool: Tool
    server_name: str
    namespaced_tool_name: str
    original_name: str


class MCPAggregator:
    """
    Aggregates multiple MCP servers into a single interface.

    This class allows you to interact with multiple MCP servers through a unified interface,
    with tools from different servers namespaced by their server name. It supports two
    connection modes:
    
    1. Temporary connections (default): Creates new connections for each tool call
    2. Persistent connections: Maintains connections for multiple tool calls when used as
       an async context manager

    Examples:
        ```python
        # Method 1: Temporary connections (default behavior)
        aggregator = MCPAggregator(registry)
        result = await aggregator.call_tool("memory__get", {"key": "test"})

        # Method 2: Filtered registry - only include specific servers
        filtered_registry = registry.filter_servers(["memory", "github"])
        aggregator = MCPAggregator(filtered_registry)
        result = await aggregator.call_tool("memory__get", {"key": "test"})

        # Method 3: Filtered tools - only expose certain tools from servers
        tool_filter = {
            "memory": ["get", "set"],  # Only include get/set from memory
            "github": ["list_repos", "create_issue"],  # Only specific github tools
        }
        aggregator = MCPAggregator(registry, tool_filter=tool_filter)
        result = await aggregator.call_tool("memory__get", {"key": "test"})

        # Method 4: Persistent connections with context manager
        async with MCPAggregator(registry) as aggregator:
            # All tool calls in this block will use persistent connections
            result1 = await aggregator.call_tool("memory__get", {"key": "test"})
            result2 = await aggregator.call_tool("memory__set", {"key": "test", "value": "hello"})
        ```
    
    Attributes:
        registry: The ServerRegistry containing server configurations
        server_names: List of all server names in the registry (convenience reference)
        tool_filter: Dictionary mapping server names to lists of tool names to include
        separator: Character(s) used to separate server name from tool name
        _namespaced_tool_map: Internal mapping of namespaced tool names to tool information
        _connection_manager: Connection manager for persistent connections (when used as context manager)
        _in_context_manager: Flag indicating if the aggregator is being used as a context manager
    """
    def __init__(
        self, 
        registry: ServerRegistry, 
        tool_filter: dict[str, list[str] | None] | None = None,
        separator: str = "__",
        aliases: dict[str, str] | None = None
    ):
        """
        Initialize the aggregator.
        
        Args:
            registry: ServerRegistry containing server configurations
            tool_filter: Optional dict mapping server names to lists of tool names to include.
                        If a server is mapped to None, all tools from that server are included.
                        If a server is not in the dict, all tools from that server are included.
                        If tool names start with "-", they are excluded (negative filtering).
            separator: Separator string between server name and tool name
                      (defaults to "__")
            aliases: Optional dict mapping alias names to actual tool names.
                    Allows custom names for tools without server prefixes.
        """
        self.registry = registry
        self.server_names = registry.list_servers()
        
        # Validate and initialize tool_filter
        if tool_filter is not None:
            # Validate tool_filter contains only lists or None
            for server, tools in tool_filter.items():
                if tools is not None and not isinstance(tools, list):
                    raise ValueError(
                        f"Invalid tool_filter for server '{server}': "
                        f"value must be a list or None, got {type(tools).__name__}"
                    )
                
                # Validate consistent filter type (all positive or all negative)
                if tools is not None and any(t.startswith("-") for t in tools) and any(not t.startswith("-") for t in tools):
                    raise ValueError(
                        f"Mixed filter types for server '{server}'. "
                        f"Use either all positive filters or all negative filters."
                    )
                    
            self.tool_filter = tool_filter
        else:
            self.tool_filter = {}
            
        # Initialize aliases
        self.aliases = aliases or {}
        
        self._namespaced_tool_map: dict[str, NamespacedTool] = {}
        self._connection_manager = None
        self._in_context_manager = False
        self.separator = separator

    async def __aenter__(self):
        """
        Enter the context manager - initialize persistent connections.
        
        This method is called when the aggregator is used as an async context manager.
        It initializes the connection manager, establishes persistent connections to
        all servers, and preloads the tools.
        
        Returns:
            MCPAggregator: This instance with initialized connections
            
        Example:
            ```python
            async with MCPAggregator(registry) as aggregator:
                # Connections are now established
                result = await aggregator.call_tool("memory__get", {"key": "test"})
            ```
        """
        # Import here to avoid circular imports
        from mcp_registry.connection import MCPConnectionManager

        self._in_context_manager = True
        self._connection_manager = MCPConnectionManager(self.registry)
        await self._connection_manager.__aenter__()

        # Preload the tools
        await self.load_servers()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the context manager - close all persistent connections.
        
        This method is called when exiting the async context manager scope.
        It ensures that all persistent connections are properly closed,
        even if an exception occurred within the context.
        
        Args:
            exc_type: Exception type if an exception was raised, None otherwise
            exc_val: Exception value if an exception was raised, None otherwise
            exc_tb: Exception traceback if an exception was raised, None otherwise
        """
        if self._connection_manager:
            await self._connection_manager.__aexit__(exc_type, exc_val, exc_tb)
            self._connection_manager = None
        self._in_context_manager = False

    async def load_servers(self, specific_servers: list[str] | None = None):
        """
        Discover and namespace tools from sub-servers.
        
        This method connects to the specified servers (or all servers if none specified),
        retrieves their available tools, and creates namespaced versions of those tools
        that can be called through the aggregator.
        
        Args:
            specific_servers: Optional list of specific server names to load.
                             If None, loads all servers in the registry.
                             
        Returns:
            None
            
        Note:
            This method is called automatically when listing tools or calling a tool,
            so you typically don't need to call it directly unless you want to
            preload the tools.
        """
        # Determine which servers to load
        servers_to_load = specific_servers or self.server_names

        # Only log when loading multiple servers
        if len(servers_to_load) > 1:
            logger.info(f"Loading tools from servers: {servers_to_load}")
        elif len(servers_to_load) == 1:
            logger.info(f"Loading tools from server: {servers_to_load[0]}")
        else:
            logger.info("No servers to load")
            return

        # Only clear tools for servers we're loading
        if specific_servers:
            # Selectively remove tools from specific servers
            for name, tool in list(self._namespaced_tool_map.items()):
                if tool.server_name in specific_servers:
                    del self._namespaced_tool_map[name]
        else:
            # Clear all tools if loading everything
            self._namespaced_tool_map.clear()

        async def load_server_tools(server_name: str):
            """Helper function to load tools from a single server."""
            try:
                async with asyncio.timeout(10):
                    # Use persistent connection if available, otherwise create temporary one
                    if self._in_context_manager and self._connection_manager:
                        server_conn = await self._connection_manager.get_server(server_name)
                        if server_conn and server_conn.session:
                            result: ListToolsResult = await server_conn.session.list_tools()
                            tools = result.tools or []
                            logger.info(f"Loaded {len(tools)} tools from {server_name} (persistent)")
                            return server_name, tools

                    # Fallback to temporary connection
                    async with self.registry.get_client(server_name) as client:
                        result: ListToolsResult = await client.list_tools()
                        tools = result.tools or []
                        logger.info(f"Loaded {len(tools)} tools from {server_name} (temporary)")
                        return server_name, tools
            except Exception as e:
                logger.error(f"Error loading tools from {server_name}: {e}")
                return server_name, []

        # Load tools from all servers concurrently
        results = await gather(*(load_server_tools(name) for name in servers_to_load))
        
        # Helper function to check if a tool should be included based on the filter settings
        def should_include_tool(server_name: str, tool_name: str) -> bool:
            """Determine if a tool should be included based on the filter settings."""
            # No filter defined for this server - include all tools
            if server_name not in self.tool_filter:
                return True
                
            # Filter is None - include all tools from this server
            if self.tool_filter[server_name] is None:
                return True
            
            # Get the tool list for this server
            tool_list = self.tool_filter[server_name]
            
            # Empty list means include nothing
            if not tool_list:
                return False
                
            # Determine if we're using negative filtering
            is_negative_filter = tool_list[0].startswith("-")
            
            if is_negative_filter:
                # Negative filtering: include tool if NOT in the exclusion list
                return not any(t[1:] == tool_name for t in tool_list)
            else:
                # Positive filtering: include tool if in the inclusion list
                return tool_name in tool_list
            
        # Process and namespace the tools with filtering
        for server_name, tools in results:
            for tool in tools:
                original_name = tool.name
                
                # Skip this tool if it should be filtered out
                if not should_include_tool(server_name, original_name):
                    continue
                
                namespaced_name = f"{server_name}{self.separator}{original_name}"
                # Create a copy of the tool with the namespaced name
                namespaced_tool = tool.model_copy(update={"name": namespaced_name})
                # Add server name to the description for clarity
                namespaced_tool.description = f"[{server_name}] {tool.description or ''}"
                # Store the tool in our map
                self._namespaced_tool_map[namespaced_name] = NamespacedTool(
                    tool=namespaced_tool,
                    server_name=server_name,
                    namespaced_tool_name=namespaced_name,
                    original_name=original_name,
                )

    def _resolve_alias(self, tool_name: str) -> str:
        """
        Resolve an alias to its actual tool name.
        
        Simple one-level alias resolution - no recursive resolution.
        
        Args:
            tool_name: The name to resolve, which might be an alias
            
        Returns:
            str: The resolved tool name (may be the original if not an alias)
        """
        # Just do a simple dictionary lookup - one level of aliases only
        if self.aliases and tool_name in self.aliases:
            return self.aliases[tool_name]
        return tool_name
    
    async def list_tools(self, return_server_mapping: bool = False) -> ListToolsResult | dict[str, list[Tool]]:
        """
        List all available tools from all sub-servers.
        
        This method retrieves all tools from all configured servers, applying
        namespacing to make tool names unique. It can return tools in two formats:
        either as a standard ListToolsResult with namespaced tools, or as a dictionary
        mapping server names to their original (non-namespaced) tools.
        
        Args:
            return_server_mapping: If True, returns a dict mapping server names to their tools without namespacing.
                                  If False, returns a ListToolsResult with all namespaced tools.

        Returns:
            Union[ListToolsResult, dict[str, list[Tool]]]: Either a ListToolsResult with namespaced tools,
            or a dictionary mapping server names to lists of their non-namespaced tools.
            
        Example:
            ```python
            # Get a standard ListToolsResult with namespaced tools
            tools_result = await aggregator.list_tools()
            
            # Get a dictionary mapping server names to their tools
            server_tools = await aggregator.list_tools(return_server_mapping=True)
            memory_tools = server_tools.get("memory", [])
            ```
        """
        # First ensure all tools are loaded
        await self.load_servers()

        if return_server_mapping:
            # Build a map of server name to list of tools
            server_tools: dict[str, list[Tool]] = {}
            for nt in self._namespaced_tool_map.values():
                server_name = nt.server_name
                # Create a copy of the tool with its original name
                original_tool = nt.tool.model_copy(update={"name": nt.original_name})

                if server_name not in server_tools:
                    server_tools[server_name] = []
                server_tools[server_name].append(original_tool)
            return server_tools

        # Default behavior: return ListToolsResult with namespaced tools
        tools = [nt.tool for nt in self._namespaced_tool_map.values()]
        result_dict = {"tools": []}

        for tool in tools:
            if hasattr(tool, "name") and hasattr(tool, "inputSchema"):
                tool_dict = {
                    "name": tool.name,
                    "inputSchema": tool.inputSchema
                }
                if hasattr(tool, "description") and tool.description:
                    tool_dict["description"] = tool.description
                result_dict["tools"].append(tool_dict)

        return ListToolsResult(**result_dict)

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict | None = None,
        server_name: str | None = None,
    ) -> CallToolResult:
        """
        Call a tool by its namespaced name or alias.
        
        Args:
            tool_name: The tool name to call. This can be a namespaced name (server__tool),
                     an alias, or just the tool name if server_name is provided separately.
            arguments: Optional dictionary of arguments to pass to the tool
            server_name: Optional server name if not included in tool_name
            
        Returns:
            CallToolResult with the result of the tool call
        """
        # Resolve any aliases to get the actual tool name
        tool_name = self._resolve_alias(tool_name)
        
        # Determine server and tool names from parameters or the namespaced string
        if server_name:
            actual_server = server_name
            actual_tool = tool_name
        else:
            if self.separator not in tool_name:
                err_msg = (
                    f"Tool name '{tool_name}' must be namespaced as 'server{self.separator}tool' "
                    f"or defined as an alias"
                )
                return CallToolResult(
                    isError=True,
                    message=err_msg,
                    content=[TextContent(type="text", text=err_msg)],
                )
            actual_server, actual_tool = tool_name.split(self.separator, 1)

        # Only load tools from the specific server we need
        # This is more efficient than loading all servers
        await self.load_servers(specific_servers=[actual_server])

        if actual_server not in self.registry.list_servers():
            err_msg = f"Server '{actual_server}' not found in registry"
            return CallToolResult(
                isError=True,
                message=err_msg,
                content=[TextContent(type="text", text=err_msg)],
            )

        # Helper function to create error result
        def error_result(message: str) -> CallToolResult:
            return CallToolResult(
                isError=True,
                message=message,
                content=[TextContent(type="text", text=message)],
            )

        # Check if the tool exists in our namespaced_tool_map
        namespaced_tool_name = f"{actual_server}{self.separator}{actual_tool}"
        if namespaced_tool_name not in self._namespaced_tool_map:
            if actual_server in self.tool_filter and self.tool_filter[actual_server] is not None:
                # The tool might be filtered out
                if actual_tool not in self.tool_filter[actual_server]:
                    return error_result(f"Tool '{actual_tool}' not found or filtered out from server '{actual_server}'")
        
        # Process the result from either connection type
        def process_result(result) -> CallToolResult:
            # If the call returns an error result, propagate it.
            if getattr(result, "isError", False):
                err_msg = f"Server '{actual_server}' returned error: {getattr(result, 'message', '')}"
                return error_result(err_msg)

            # Process returned content into a proper list of content objects.
            content = []
            extracted = None
            if hasattr(result, "content"):
                extracted = result.content
            elif isinstance(result, dict) and "content" in result:
                extracted = result["content"]
            elif hasattr(result, "result"):
                extracted = [result.result]
            elif isinstance(result, dict) and "result" in result:
                extracted = [result["result"]]

            if extracted:
                for item in extracted:
                    if isinstance(item, (TextContent, ImageContent, EmbeddedResource)):
                        content.append(item)
                    elif isinstance(item, dict) and "text" in item and "type" in item:
                        content.append(TextContent(**item))
                    elif isinstance(item, str):
                        content.append(TextContent(type="text", text=item))
                    else:
                        content.append(TextContent(type="text", text=str(item)))
            if not content:
                content = [TextContent(type="text", text="Tool execution completed.")]
            return CallToolResult(isError=False, message="", content=content)

        try:
            result = None

            # Try using persistent connection if available
            if self._in_context_manager and self._connection_manager:
                try:
                    # Get server connection from the connection manager
                    server_conn = await self._connection_manager.get_server(actual_server)
                    if server_conn and server_conn.is_ready and server_conn.session:
                        # Use persistent connection
                        async with asyncio.timeout(30):
                            result = await server_conn.session.call_tool(actual_tool, arguments)
                            logger.debug(f"Called tool using persistent connection to {actual_server}")
                            return process_result(result)
                except asyncio.TimeoutError:
                    return error_result(
                        f"Timeout calling tool '{actual_tool}' on server '{actual_server}'"
                    )
                except Exception as e:
                    logger.warning(f"Failed to use persistent connection, falling back to temporary: {e}")

            # Use temporary connection as fallback or default
            async with self.registry.get_client(actual_server) as client:
                async with asyncio.timeout(30):
                    result = await client.call_tool(actual_tool, arguments)
                    return process_result(result)

        except asyncio.TimeoutError:
            return error_result(
                f"Timeout calling tool '{actual_tool}' on server '{actual_server}'"
            )
        except Exception as e:
            err_msg = f"Error in call_tool for '{tool_name}': {e}"
            logger.error(err_msg)
            return error_result(err_msg)


async def run_registry_server(registry_or_aggregator: ServerRegistry | MCPAggregator):
    """
    Create and run an MCP compound server that aggregates tools from the registry.
    
    Args:
        registry_or_aggregator: Registry or pre-configured MCPAggregator
    """
    # Create server
    server = Server("MCP Registry Server")

    # Create aggregator or use the provided one
    if isinstance(registry_or_aggregator, ServerRegistry):
        aggregator = MCPAggregator(registry_or_aggregator)
    else:
        aggregator = registry_or_aggregator

    # List available tools
    try:
        await aggregator.load_servers()
    except Exception as e:
        logger.error(f"Error loading servers: {e}")
        return

    # Implement list_tools method
    @server.list_tools()
    async def list_tools():
        """List available tools."""
        result = await aggregator.list_tools()
        # Return the list of tools directly as expected by the MCP protocol
        return [t.model_dump() for t in result.tools]

    # Implement call_tool method
    @server.call_tool()
    async def call_tool(name: str, arguments: dict | None = None):
        """Call a specific tool by name."""
        result = await aggregator.call_tool(tool_name=name, arguments=arguments)
        return result.content if hasattr(result, 'content') else [TextContent(type="text", text="No content")]

    # Create initialization options
    init_options = server.create_initialization_options(
        notification_options=NotificationOptions(),
        experimental_capabilities={}
    )

    # Run the server
    async with stdio_server() as (read_stream, write_stream):
        # First set up the server
        await server.run(
            read_stream,
            write_stream,
            init_options
        )

        # Then load servers
        await aggregator.load_servers()
        logger.info("MCP Registry Server ready!")

        # Wait forever or until interrupted
        try:
            while True:
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            logger.info("Registry server shutting down due to cancellation")
            # Clean up by explicitly disconnecting from all servers
            if hasattr(aggregator, "_connection_manager") and aggregator._connection_manager:
                await aggregator._connection_manager.disconnect_all()
            raise