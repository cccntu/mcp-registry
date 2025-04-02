"""
This module defines persistent connection management for MCP servers.
"""

import logging
import asyncio
from typing import Dict, Callable, Optional, Any
from contextlib import asynccontextmanager
from datetime import timedelta
from enum import Enum, auto
import anyio
from anyio.abc import TaskGroup

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client, get_default_environment
from mcp.client.sse import sse_client
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

from mcp_registry.compound import MCPServerSettings, ServerRegistry

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """State of a server connection"""
    INITIALIZING = auto()
    READY = auto()
    ERROR = auto()
    SHUTDOWN = auto()


class ServerConnection:
    """
    Represents a persistent connection to an MCP server.
    """

    def __init__(
        self,
        server_name: str,
        server_config: MCPServerSettings,
        transport_context_factory: Callable[[], Any],
        client_session_factory: Callable[
            [MemoryObjectReceiveStream, MemoryObjectSendStream, timedelta | None],
            ClientSession,
        ],
    ):
        self.server_name = server_name
        self.server_config = server_config
        self.transport_context_factory = transport_context_factory
        self.client_session_factory = client_session_factory
        
        self.session: Optional[ClientSession] = None
        self.state = ConnectionState.INITIALIZING
        self.error: Optional[Exception] = None
        self._shutdown_requested = False
        self._initialized_event = asyncio.Event()
        self._lock = asyncio.Lock()
        
    async def wait_for_initialized(self) -> None:
        """Wait until the server is initialized or has encountered an error."""
        await self._initialized_event.wait()
        if self.state == ConnectionState.ERROR and self.error:
            raise self.error
            
    def request_shutdown(self) -> None:
        """Request the server connection to shut down."""
        self._shutdown_requested = True
        
    @property
    def is_ready(self) -> bool:
        """Check if the server is ready to accept requests."""
        return self.state == ConnectionState.READY and self.session is not None


async def _server_lifecycle_task(server_conn: ServerConnection) -> None:
    """
    Manages the lifecycle of a server connection.
    
    This runs as a background task and maintains the connection until
    shutdown is requested.
    """
    server_name = server_conn.server_name
    logger.info(f"{server_name}: Starting server lifecycle task")
    
    try:
        # Create the transport context (stdio or sse)
        transport_context = server_conn.transport_context_factory()
        async with transport_context as (read_stream, write_stream):
            # Create client session
            read_timeout_seconds = (
                timedelta(seconds=server_conn.server_config.read_timeout_seconds)
                if hasattr(server_conn.server_config, "read_timeout_seconds") and
                   server_conn.server_config.read_timeout_seconds
                else None
            )
            
            session = server_conn.client_session_factory(
                read_stream, write_stream, read_timeout_seconds
            )
            
            async with session:
                try:
                    # Initialize the session
                    logger.info(f"{server_name}: Initializing session")
                    await session.initialize()
                    
                    # Update server connection state
                    async with server_conn._lock:
                        server_conn.session = session
                        server_conn.state = ConnectionState.READY
                        server_conn._initialized_event.set()
                    
                    logger.info(f"{server_name}: Server initialized and ready")
                    
                    # Keep the connection alive until shutdown is requested
                    try:
                        while not server_conn._shutdown_requested:
                            await asyncio.sleep(1)
                            
                            # Optional: implement ping/keepalive logic here
                            # try:
                            #     await session.send_ping()
                            # except Exception as e:
                            #     logger.warning(f"{server_name}: Ping failed: {e}")
                    except asyncio.CancelledError:
                        # Gracefully handle task cancellation during shutdown
                        logger.debug(f"{server_name}: Server lifecycle task cancelled")
                        server_conn._shutdown_requested = True
                finally:
                    # Cleanup when exiting the session context
                    async with server_conn._lock:
                        server_conn.session = None
                        server_conn.state = ConnectionState.SHUTDOWN
    
    except Exception as e:
        logger.error(f"{server_name}: Error in server lifecycle: {e}")
        async with server_conn._lock:
            server_conn.state = ConnectionState.ERROR
            server_conn.error = e
            server_conn._initialized_event.set()
    
    finally:
        logger.info(f"{server_name}: Server lifecycle task ending")
        async with server_conn._lock:
            server_conn.state = ConnectionState.SHUTDOWN
            if not server_conn._initialized_event.is_set():
                server_conn._initialized_event.set()


class MCPConnectionManager:
    """
    Manages the lifecycle of multiple MCP server connections.
    """

    def __init__(self, server_registry: ServerRegistry):
        self.server_registry = server_registry
        self.running_servers: Dict[str, ServerConnection] = {}
        self._lock = asyncio.Lock()
        self._tg: Optional[TaskGroup] = None

    async def __aenter__(self):
        # We create a task group to manage all server lifecycle tasks
        self._tg = await anyio.create_task_group().__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.debug("MCPConnectionManager: shutting down all server tasks...")
        # First request shutdown for all connections to ensure graceful cleanup
        async with self._lock:
            for conn in self.running_servers.values():
                conn.request_shutdown()
                
        # Small delay to allow shutdown requests to be processed
        await asyncio.sleep(0.5)
                
        # Then exit the task group which will cancel any remaining tasks
        if self._tg:
            await self._tg.__aexit__(exc_type, exc_val, exc_tb)
        self._tg = None

    async def launch_server(
        self,
        server_name: str,
        client_session_factory: Callable[
            [MemoryObjectReceiveStream, MemoryObjectSendStream, timedelta | None],
            ClientSession,
        ] = ClientSession,
    ) -> ServerConnection:
        """
        Connect to a server and return a ServerConnection instance that will persist
        until explicitly disconnected.
        """
        if not self._tg:
            raise RuntimeError(
                "MCPConnectionManager must be used inside an async context (i.e. 'async with' or after __aenter__)."
            )

        config = self.server_registry.registry.get(server_name)
        if not config:
            raise ValueError(f"Server '{server_name}' not found in registry.")

        logger.debug(f"{server_name}: Found server configuration")

        def transport_context_factory():
            if config.type == "stdio":
                if not config.command or not config.args:
                    raise ValueError(f"Command and args required for stdio type: {server_name}")
                server_params = StdioServerParameters(
                    command=config.command,
                    args=config.args,
                    env={**get_default_environment(), **(config.env or {})},
                )
                return stdio_client(server_params)
            elif config.type == "sse":
                if not config.url:
                    raise ValueError(f"URL required for SSE type: {server_name}")
                return sse_client(config.url)
            else:
                raise ValueError(f"Unsupported transport type: {config.type}")

        server_conn = ServerConnection(
            server_name=server_name,
            server_config=config,
            transport_context_factory=transport_context_factory,
            client_session_factory=client_session_factory,
        )

        async with self._lock:
            # Check if already running
            if server_name in self.running_servers:
                return self.running_servers[server_name]

            self.running_servers[server_name] = server_conn
            self._tg.start_soon(_server_lifecycle_task, server_conn)

        logger.info(f"{server_name}: Up and running with a persistent connection!")
        return server_conn

    async def get_server(
        self,
        server_name: str,
        client_session_factory: Callable = ClientSession,
    ) -> ServerConnection:
        """
        Get a running server instance, launching it if needed.
        """
        # Get the server connection if it's already running
        async with self._lock:
            server_conn = self.running_servers.get(server_name)
            if server_conn and server_conn.is_ready:
                return server_conn

        # Launch the connection
        server_conn = await self.launch_server(
            server_name=server_name,
            client_session_factory=client_session_factory,
        )

        # Wait until it's fully initialized, or an error occurs
        await server_conn.wait_for_initialized()

        # If the session is still None, it means the lifecycle task crashed
        if not server_conn or not server_conn.session:
            raise RuntimeError(
                f"{server_name}: Failed to initialize server; check logs for errors."
            )
        return server_conn

    async def disconnect_server(self, server_name: str) -> None:
        """
        Disconnect a specific server if it's running under this connection manager.
        """
        logger.info(f"{server_name}: Disconnecting persistent connection to server...")

        async with self._lock:
            server_conn = self.running_servers.pop(server_name, None)
        if server_conn:
            server_conn.request_shutdown()
            logger.info(
                f"{server_name}: Shutdown signal sent (lifecycle task will exit)."
            )
        else:
            logger.info(
                f"{server_name}: No persistent connection found. Skipping server shutdown"
            )

    async def disconnect_all(self) -> None:
        """
        Disconnect all servers that are running under this connection manager.
        """
        logger.info("Disconnecting all persistent server connections...")
        async with self._lock:
            for conn in self.running_servers.values():
                conn.request_shutdown()
            self.running_servers.clear()
        logger.info("All persistent server connections signaled to disconnect.")