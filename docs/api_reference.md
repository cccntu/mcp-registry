# MCP Registry API Reference

This document provides a comprehensive reference for the public API of the MCP Registry package.

## Core Components

MCP Registry consists of several core components that work together to provide server configuration management and aggregation:

- **ServerRegistry**: Manages server configurations
- **MCPAggregator**: Aggregates multiple servers into a single interface
- **MCPConnectionManager**: Manages persistent connections to servers
- **CLI Utilities**: Helper functions for configuration management

## Installation

```bash
pip install mcp-registry
```

## Import

```python
from mcp_registry import (
    ServerRegistry, 
    MCPAggregator, 
    MCPServerSettings,
    get_config_path
)
```

## API Reference

### `ServerRegistry`

A registry for managing server configurations.

```python
class ServerRegistry:
    def __init__(self, servers: dict[str, MCPServerSettings]):
        """
        Initialize a ServerRegistry with a dictionary of server configurations.
        
        Args:
            servers: Dictionary mapping server names to their configuration settings
        """
        
    @classmethod
    def from_dict(cls, config: dict) -> "ServerRegistry":
        """
        Create a ServerRegistry from a dictionary of server configurations.
        
        Args:
            config: Dictionary where keys are server names and values are server configuration dictionaries
            
        Returns:
            ServerRegistry: A new registry instance with the configured servers
            
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
        
    @classmethod
    def from_config(cls, path: Path | str) -> "ServerRegistry":
        """
        Load a ServerRegistry from a configuration file.
        
        Args:
            path: Path to the configuration file (JSON format)
            
        Returns:
            ServerRegistry: A new registry instance with the configured servers
            
        Raises:
            FileNotFoundError: If the configuration file does not exist
            KeyError: If the configuration file does not have a 'mcpServers' section
        """
        
    def save_config(self, path: Path | str) -> None:
        """
        Save the registry configuration to a file.
        
        Args:
            path: Path where the configuration file should be saved
        """
        
    @asynccontextmanager
    async def get_client(self, server_name: str) -> AsyncGenerator[ClientSession, None]:
        """
        Get a client session for a specific server.
        
        Args:
            server_name: Name of the server to connect to
            
        Yields:
            ClientSession: A session connected to the specified server
            
        Raises:
            ValueError: If the server is not found or has invalid configuration
        """
        
    def list_servers(self) -> list[str]:
        """
        Get a list of all server names in the registry.
        
        Returns:
            list[str]: List of server names
        """
        
    def get_server_info(self, server_name: str) -> str:
        """
        Get information about a specific server.
        
        Args:
            server_name: Name of the server to get information about
            
        Returns:
            str: Human-readable information about the server
        """
```

### `MCPServerSettings`

Configuration settings for an MCP server.

```python
class MCPServerSettings(BaseModel):
    """
    Basic server configuration settings.
    
    Attributes:
        type: Transport type ("stdio" or "sse")
        command: Command to run for stdio servers
        args: Command arguments for stdio servers
        url: URL for sse servers
        env: Environment variables to set
        description: Optional description of the server
    """
    type: str
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
            str: Transport type
        """
        
    @transport.setter
    def transport(self, value: str) -> None:
        """
        Set the transport type.
        
        Args:
            value: New transport type
        """
```

### `MCPAggregator`

Aggregates multiple MCP servers into a single interface.

```python
class MCPAggregator:
    """
    Aggregates multiple MCP servers.
    
    This class can be used in two ways:
    1. As a regular object (default) - creates temporary connections for each tool call
    2. As an async context manager - maintains persistent connections during the context
    
    Examples:
        # Method 1: Temporary connections (default behavior)
        aggregator = MCPAggregator(registry)
        result = await aggregator.call_tool("memory__get", {"key": "test"})
        
        # Method 2: Persistent connections with context manager
        async with MCPAggregator(registry) as aggregator:
            # All tool calls in this block will use persistent connections
            result1 = await aggregator.call_tool("memory__get", {"key": "test"})
            result2 = await aggregator.call_tool("memory__set", {"key": "test", "value": "hello"})
    """
    
    def __init__(self, registry: ServerRegistry, tool_filter: dict[str, list[str] | None] | None = None, separator: str = "__"):
        """
        Initialize the aggregator.
        
        Args:
            registry: ServerRegistry containing server configurations
            tool_filter: Optional dict mapping server names to lists of tool names to include.
                       If a server is mapped to None, all tools from that server are included.
                       If a server is not in the dict, all tools from that server are included.
            separator: Separator character between server name and tool name
        """
        
    async def __aenter__(self):
        """
        Enter the context manager - initialize persistent connections.
        
        Returns:
            MCPAggregator: This instance with initialized connections
        """
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the context manager - close all persistent connections.
        """
        
    async def load_servers(self, specific_servers: list[str] | None = None):
        """
        Discover and namespace tools from sub-servers.
        
        Args:
            specific_servers: Optional list of specific server names to load.
                          If None, loads all servers in self.server_names.
        """
        
    async def list_tools(self, return_server_mapping: bool = False) -> ListToolsResult | dict[str, list[Tool]]:
        """
        List all available tools from all sub-servers.
        
        Args:
            return_server_mapping: If True, returns a dict mapping server names to their tools without namespacing.
                               If False, returns a ListToolsResult with all namespaced tools.
                               
        Returns:
            Union[ListToolsResult, dict[str, list[Tool]]]: Either a ListToolsResult with namespaced tools,
            or a dictionary mapping server names to lists of their non-namespaced tools.
        """
        
    async def call_tool(
        self,
        tool_name: str,
        arguments: dict | None = None,
        server_name: str | None = None,
    ) -> CallToolResult:
        """
        Call a tool by its namespaced name.
        
        Args:
            tool_name: Name of the tool to call (format: "server_name__tool_name")
            arguments: Arguments to pass to the tool
            server_name: Optional server name (if provided, tool_name should be just the tool name without namespace)
            
        Returns:
            CallToolResult: Result of the tool call
            
        Examples:
            # Method 1: Using namespaced tool name
            result = await aggregator.call_tool("memory__get", {"key": "test"})
            
            # Method 2: Using separate server and tool names
            result = await aggregator.call_tool("get", server_name="memory", arguments={"key": "test"})
        """
```

### `MCPConnectionManager`

Manages persistent connections to MCP servers.

```python
class MCPConnectionManager:
    """
    Manages persistent connections to MCP servers.
    
    This class is used internally by MCPAggregator, but can also be used directly
    for more advanced connection management scenarios.
    """
    
    def __init__(self, registry: ServerRegistry):
        """
        Initialize the connection manager.
        
        Args:
            registry: ServerRegistry containing server configurations (can be filtered with registry.filter_servers())
        """
        
    async def __aenter__(self):
        """
        Enter the context manager - initialize the task group and connections.
        
        Returns:
            MCPConnectionManager: This instance
        """
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the context manager - shut down all connections and the task group.
        """
        
    async def get_server(self, server_name: str) -> ServerConnection | None:
        """
        Get a connection to a specific server.
        
        Args:
            server_name: Name of the server to connect to
            
        Returns:
            ServerConnection: Server connection object, or None if not found
        """
        
    async def connect_server(self, server_name: str) -> ServerConnection:
        """
        Connect to a specific server.
        
        Args:
            server_name: Name of the server to connect to
            
        Returns:
            ServerConnection: Server connection object
            
        Raises:
            ValueError: If the server is not found in the registry
        """
        
    async def disconnect_all(self):
        """
        Disconnect from all servers.
        """
```

### `ServerConnection`

Represents a connection to a single MCP server.

```python
class ServerConnection:
    """
    Represents a persistent connection to a single MCP server.
    
    This class is used internally by MCPConnectionManager, but can also be used directly
    for more granular control over server connections.
    """
    
    def __init__(self, name: str, settings: MCPServerSettings, registry: ServerRegistry):
        """
        Initialize a server connection.
        
        Args:
            name: Server name
            settings: Server configuration settings
            registry: ServerRegistry containing the server configuration
        """
        
    @property
    def is_ready(self) -> bool:
        """
        Check if the connection is ready for use.
        
        Returns:
            bool: True if the connection is initialized and ready for use
        """
        
    async def connect(self):
        """
        Connect to the server and initialize the session.
        
        This is called automatically by MCPConnectionManager.
        """
        
    async def disconnect(self):
        """
        Disconnect from the server and clean up resources.
        """
        
    async def wait_for_initialized(self, timeout: float = 30.0) -> bool:
        """
        Wait for the connection to be fully initialized.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            bool: True if the connection was successfully initialized
        """
        
    def request_shutdown(self):
        """
        Request the connection to shut down.
        
        This signals the lifecycle task to start the shutdown process.
        """
```

### `ConnectionState`

Enum representing the possible states of a server connection.

```python
class ConnectionState(Enum):
    """
    Enum representing the state of a server connection.
    """
    INITIALIZING = "initializing"  # Connection is being established
    READY = "ready"  # Connection is ready for use
    ERROR = "error"  # Connection encountered an error
    SHUTDOWN = "shutdown"  # Connection is being shut down
    TERMINATED = "terminated"  # Connection has been terminated
```

### Configuration Utilities

```python
def get_default_config_path() -> Path:
    """
    Get the default configuration file path.
    
    Returns:
        Path: Default configuration file path
    """
    
def get_config_path() -> Path:
    """
    Get the configuration file path, respecting environment variables.
    
    Environment variable MCP_REGISTRY_CONFIG can be used to override the default path.
    
    Returns:
        Path: Configuration file path to use
    """
```

### Server Running

```python
async def run_registry_server(registry: ServerRegistry):
    """
    Create and run an MCP compound server that aggregates tools from the registry.
    
    Args:
        registry: ServerRegistry containing server configurations
               (can be filtered using registry.filter_servers() before passing)
    """
```

## Usage Examples

### Basic Usage

```python
from mcp_registry import ServerRegistry, MCPAggregator, get_config_path
import asyncio

async def main():
    # Load servers from config
    registry = ServerRegistry.from_config(get_config_path())
    
    # Create an aggregator with temporary connections
    aggregator = MCPAggregator(registry)
    
    # List available tools
    tools_result = await aggregator.list_tools()
    print(f"Available tools: {[t.name for t in tools_result.tools]}")
    
    # Call a tool
    result = await aggregator.call_tool("memory__set", {"key": "test", "value": "Hello World"})
    print(f"Result: {result.content[0].text if result.content else 'No content'}")
    
    # Get the value back
    result = await aggregator.call_tool("memory__get", {"key": "test"})
    print(f"Value: {result.content[0].text if result.content else 'No content'}")

asyncio.run(main())
```

### Using Persistent Connections

```python
from mcp_registry import ServerRegistry, MCPAggregator, get_config_path
import asyncio
import time

async def main():
    # Load servers from config
    registry = ServerRegistry.from_config(get_config_path())
    
    # Using context manager for persistent connections
    async with MCPAggregator(registry) as aggregator:
        # Connections are established when entering the context
        
        # Make multiple tool calls using the same persistent connections
        start_time = time.time()
        
        for i in range(5):
            result = await aggregator.call_tool("memory__set", {"key": f"key_{i}", "value": f"value_{i}"})
            print(f"Set key_{i}: {result.content[0].text if result.content else 'No content'}")
            
            result = await aggregator.call_tool("memory__get", {"key": f"key_{i}"})
            print(f"Get key_{i}: {result.content[0].text if result.content else 'No content'}")
            
        elapsed = time.time() - start_time
        print(f"5 set/get pairs took {elapsed:.2f} seconds with persistent connections")
        
        # Connections are automatically closed when exiting the context

asyncio.run(main())
```

### Creating Custom Registry

```python
from mcp_registry import ServerRegistry, MCPServerSettings, MCPAggregator
import asyncio

async def main():
    # Create server settings manually
    memory_server = MCPServerSettings(
        type="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-memory"],
        description="Memory storage server"
    )
    
    filesystem_server = MCPServerSettings(
        type="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem"],
        description="Filesystem server"
    )
    
    # Create a registry with these servers
    registry = ServerRegistry({
        "memory": memory_server,
        "filesystem": filesystem_server
    })
    
    # Use the registry with an aggregator
    aggregator = MCPAggregator(registry)
    
    # List available tools
    tools_result = await aggregator.list_tools()
    print(f"Available tools: {[t.name for t in tools_result.tools]}")
    
    # Save the configuration for later use
    registry.save_config("./my_servers_config.json")

asyncio.run(main())
```

## Error Handling

MCP Registry provides detailed error information when tool calls fail:

```python
from mcp_registry import ServerRegistry, MCPAggregator, get_config_path
import asyncio

async def main():
    registry = ServerRegistry.from_config(get_config_path())
    aggregator = MCPAggregator(registry)
    
    # Call a tool that doesn't exist
    result = await aggregator.call_tool("nonexistent__tool", {"key": "test"})
    
    if result.isError:
        print(f"Error: {result.message}")
        # Will print error about the server not being found
    
    # Call a tool with incorrect arguments
    result = await aggregator.call_tool("memory__get", {"incorrect": "argument"})
    
    if result.isError:
        print(f"Error: {result.message}")
        # Will print error about incorrect arguments

asyncio.run(main())
```

## Advanced Use Cases

### Selective Server Loading

```python
from mcp_registry import ServerRegistry, MCPAggregator, get_config_path
import asyncio

async def main():
    # Load all servers from config
    full_registry = ServerRegistry.from_config(get_config_path())
    
    # Create a filtered registry with only specified servers
    specific_servers = ["memory", "filesystem"]
    filtered_registry = full_registry.filter_servers(specific_servers)
    
    # Create an aggregator with the filtered registry
    aggregator = MCPAggregator(filtered_registry)
    
    # Only tools from the specified servers will be available
    tools_result = await aggregator.list_tools()
    print(f"Available tools: {[t.name for t in tools_result.tools]}")

asyncio.run(main())
```

### Custom Namespacing

```python
from mcp_registry import ServerRegistry, MCPAggregator, get_config_path
import asyncio

async def main():
    registry = ServerRegistry.from_config(get_config_path())
    
    # Use a different separator character for namespacing
    aggregator = MCPAggregator(registry, separator=":")
    
    # Tools will be available as "server:tool" instead of "server__tool"
    tools_result = await aggregator.list_tools()
    print(f"Available tools: {[t.name for t in tools_result.tools]}")
    
    # Call a tool using the custom separator
    result = await aggregator.call_tool("memory:get", {"key": "test"})
    print(f"Result: {result.content[0].text if result.content else 'No content'}")

asyncio.run(main())
```