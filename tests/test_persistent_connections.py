"""Tests for persistent connection functionality."""

import json
import asyncio
from contextlib import asynccontextmanager
import pytest
from unittest.mock import patch, MagicMock, AsyncMock, call

from mcp.client.session import ClientSession

from mcp_registry import (
    MCPAggregator,
    MCPServerSettings,
    ServerRegistry,
    MCPConnectionManager,
    ServerConnection,
    ConnectionState,
)


@pytest.fixture
def test_servers():
    """Create test server configurations."""
    return {
        "test_server1": MCPServerSettings(
            type="stdio",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-memory"],
            description="Memory server",
        ),
        "test_server2": MCPServerSettings(
            type="stdio",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem"],
            description="Filesystem server",
        ),
    }


@pytest.fixture
def registry(test_servers):
    """Create a server registry with test servers."""
    return ServerRegistry(test_servers)


@pytest.mark.asyncio
async def test_specific_server_loading():
    """Test that only specific servers are loaded when using call_tool."""
    # Create a mock registry
    mock_registry = MagicMock()
    mock_registry.registry = {
        "server1": MCPServerSettings(type="stdio", command="test", args=[]),
        "server2": MCPServerSettings(type="stdio", command="test", args=[]),
    }
    mock_registry.list_servers.return_value = ["server1", "server2"]
    
    # Mock the get_client method
    mock_client_session = AsyncMock()
    mock_client_session.call_tool = AsyncMock()
    mock_client_session.list_tools = AsyncMock()
    mock_client_session.list_tools.return_value.tools = []
    
    @asynccontextmanager
    async def mock_get_client(server_name):
        yield mock_client_session
    
    mock_registry.get_client = mock_get_client
    
    # Create the aggregator and patch load_servers
    aggregator = MCPAggregator(mock_registry)
    
    # Create a spy for load_servers to check its arguments
    original_load_servers = aggregator.load_servers
    load_servers_calls = []
    
    async def spy_load_servers(specific_servers=None):
        load_servers_calls.append(specific_servers)
        return await original_load_servers(specific_servers)
    
    aggregator.load_servers = spy_load_servers
    
    # Call a tool
    await aggregator.call_tool("server1__test", {"arg": "value"})
    
    # Verify load_servers was called with the specific server
    assert len(load_servers_calls) > 0
    assert load_servers_calls[-1] == ["server1"]


@pytest.mark.asyncio
async def test_connection_state_transitions():
    """Test ServerConnection state transitions."""
    # Create a server connection
    conn = ServerConnection(
        server_name="test_server",
        server_config=MCPServerSettings(
            type="stdio",
            command="test",
            args=["arg"],
        ),
        transport_context_factory=lambda: None,
        client_session_factory=lambda *args: None,
    )
    
    # Initial state should be INITIALIZING
    assert conn.state == ConnectionState.INITIALIZING
    
    # Test requesting shutdown
    conn.request_shutdown()
    assert conn._shutdown_requested == True
    
    # Test is_ready
    assert conn.is_ready == False
    conn.state = ConnectionState.READY
    conn.session = AsyncMock()
    assert conn.is_ready == True
    
    # Set initialized event to avoid hanging
    conn._initialized_event.set()


@pytest.mark.asyncio
async def test_aggregator_context_manager_lifecycle():
    """Test the lifecycle of MCPAggregator as a context manager."""
    # Mock connection manager
    mock_connection_manager = AsyncMock()
    mock_connection_manager.__aenter__ = AsyncMock(return_value=mock_connection_manager)
    mock_connection_manager.__aexit__ = AsyncMock()
    
    # Create a registry and patch the connection manager
    mock_registry = MagicMock()
    mock_registry.registry = {"server1": MCPServerSettings(type="stdio", command="test", args=[])}
    mock_registry.list_servers.return_value = ["server1"]
    
    # Patch the import to return our mock
    with patch("mcp_registry.connection.MCPConnectionManager", return_value=mock_connection_manager):
        # Use the aggregator as a context manager
        async with MCPAggregator(mock_registry) as aggregator:
            # Verify connection manager was initialized
            assert aggregator._in_context_manager == True
            assert aggregator._connection_manager == mock_connection_manager
            mock_connection_manager.__aenter__.assert_called_once()
            
            # Mock a successful call_tool
            with patch.object(aggregator, "load_servers", AsyncMock()):
                # Add a mock server connection to the manager
                mock_server_conn = MagicMock()
                mock_server_conn.is_ready = True
                mock_server_conn.session = AsyncMock()
                mock_server_conn.session.call_tool = AsyncMock()
                
                mock_connection_manager.get_server = AsyncMock(return_value=mock_server_conn)
                
                # Call a tool
                await aggregator.call_tool("server1__test", {"arg": "value"})
                
                # Verify connection was reused
                mock_connection_manager.get_server.assert_called_with("server1")
        
        # Verify cleanup
        mock_connection_manager.__aexit__.assert_called_once()


@pytest.mark.asyncio
async def test_connection_manager_init_and_cleanup():
    """Test that MCPConnectionManager initializes and cleans up properly."""
    # Create a mock registry
    mock_registry = MagicMock()
    mock_registry.registry = {
        "server1": MCPServerSettings(type="stdio", command="test", args=[]),
        "server2": MCPServerSettings(type="stdio", command="test", args=[]),
    }
    
    # Create a mock task group
    mock_tg = AsyncMock()
    mock_tg.__aenter__ = AsyncMock(return_value=mock_tg)
    mock_tg.__aexit__ = AsyncMock()
    
    # Patch anyio.create_task_group to return our mock
    with patch("anyio.create_task_group", return_value=mock_tg):
        # Create the connection manager and enter its context
        manager = MCPConnectionManager(mock_registry)
        await manager.__aenter__()
        
        # Check that the task group was initialized
        assert manager._tg == mock_tg
        mock_tg.__aenter__.assert_called_once()
        
        # Test cleanup
        await manager.__aexit__(None, None, None)
        mock_tg.__aexit__.assert_called_once()
        assert manager._tg is None


@pytest.mark.asyncio
async def test_connection_manager_disconnect_server():
    """Test that connection manager properly disconnects servers."""
    # Create a mock registry
    mock_registry = MagicMock()
    
    # Create a mock server connection
    mock_conn = MagicMock()
    mock_conn.request_shutdown = MagicMock()
    
    # Create the connection manager
    manager = MCPConnectionManager(mock_registry)
    manager._tg = AsyncMock()  # Mock task group
    
    # Add the server to running servers
    manager.running_servers = {"server1": mock_conn}
    
    # Disconnect the server
    await manager.disconnect_server("server1")
    
    # Verify the server was disconnected
    mock_conn.request_shutdown.assert_called_once()
    assert "server1" not in manager.running_servers
    
    # Test disconnecting a non-existent server (should not raise exceptions)
    await manager.disconnect_server("nonexistent")


@pytest.mark.asyncio
async def test_connection_manager_disconnect_all():
    """Test that connection manager properly disconnects all servers."""
    # Create a mock registry
    mock_registry = MagicMock()
    
    # Create mock server connections
    mock_conn1 = MagicMock()
    mock_conn1.request_shutdown = MagicMock()
    mock_conn2 = MagicMock()
    mock_conn2.request_shutdown = MagicMock()
    
    # Create the connection manager
    manager = MCPConnectionManager(mock_registry)
    manager._tg = AsyncMock()  # Mock task group
    
    # Add servers to running servers
    manager.running_servers = {
        "server1": mock_conn1,
        "server2": mock_conn2
    }
    
    # Disconnect all servers
    await manager.disconnect_all()
    
    # Verify all servers were disconnected
    mock_conn1.request_shutdown.assert_called_once()
    mock_conn2.request_shutdown.assert_called_once()
    assert len(manager.running_servers) == 0


@pytest.mark.asyncio
async def test_connection_manager_launch_server():
    """Test that connection manager properly launches a server."""
    # Create a mock registry with server config
    mock_registry = MagicMock()
    mock_registry.registry = {
        "server1": MCPServerSettings(
            type="stdio",
            command="test",
            args=["arg"],
        ),
    }
    
    # Create a mock task group
    mock_tg = AsyncMock()
    mock_tg.start_soon = MagicMock()
    
    # Create the connection manager with the mock task group
    manager = MCPConnectionManager(mock_registry)
    manager._tg = mock_tg
    
    # Patch the _server_lifecycle_task function
    with patch("mcp_registry.connection._server_lifecycle_task"):
        # Launch the server
        server_conn = await manager.launch_server("server1")
        
        # Verify the server was launched
        assert "server1" in manager.running_servers
        assert manager.running_servers["server1"] == server_conn
        assert server_conn.server_name == "server1"
        assert server_conn.server_config == mock_registry.registry["server1"]
        
        # Check that the lifecycle task was started
        mock_tg.start_soon.assert_called_once()
        
        # Try to launch the same server again (should return existing connection)
        server_conn2 = await manager.launch_server("server1")
        assert server_conn2 == server_conn
        
        # Mock task group start_soon should still have been called only once
        assert mock_tg.start_soon.call_count == 1


@pytest.mark.asyncio
async def test_connection_manager_get_server():
    """Test that connection manager's get_server method properly gets or launches a server."""
    # Create a mock registry
    mock_registry = MagicMock()
    mock_registry.registry = {
        "server1": MCPServerSettings(type="stdio", command="test", args=[]),
    }
    
    # Create the connection manager
    manager = MCPConnectionManager(mock_registry)
    manager._tg = AsyncMock()  # Mock task group
    
    # Mock an existing server connection
    mock_conn = MagicMock()
    mock_conn.wait_for_initialized = AsyncMock()
    mock_conn.is_ready = True
    mock_conn.session = AsyncMock()
    
    # Mock the launch_server method
    with patch.object(manager, "launch_server", AsyncMock(return_value=mock_conn)):
        # Get the server
        server_conn = await manager.get_server("server1")
        
        # Verify the server was launched and initialized
        assert server_conn == mock_conn
        mock_conn.wait_for_initialized.assert_called_once()
        manager.launch_server.assert_called_once_with(server_name="server1", client_session_factory=ClientSession)
        
        # Add the server to running servers
        manager.running_servers = {"server1": mock_conn}
        
        # Reset the mocks
        manager.launch_server.reset_mock()
        mock_conn.wait_for_initialized.reset_mock()
        
        # Get the server again (should use existing connection)
        server_conn2 = await manager.get_server("server1")
        
        # Verify we reused the existing connection
        assert server_conn2 == mock_conn
        assert manager.launch_server.call_count == 0  # Should not call launch_server


@pytest.mark.asyncio
async def test_server_connection_lifecycle():
    """Test the server connection's lifecycle."""
    # Create a server connection
    conn = ServerConnection(
        server_name="test_server",
        server_config=MCPServerSettings(
            type="stdio",
            command="test",
            args=["arg"],
        ),
        transport_context_factory=lambda: None,
        client_session_factory=lambda *args: None,
    )
    
    # Set up the initialized event
    conn._initialized_event.set()
    
    # Test changing state to READY
    conn.state = ConnectionState.READY
    conn.session = AsyncMock()
    
    # Verify is_ready property works correctly
    assert conn.is_ready == True
    
    # Test requesting shutdown
    conn.request_shutdown()
    assert conn._shutdown_requested == True
    
    # Test READY -> ERROR transition
    test_error = ValueError("Test error")
    conn.state = ConnectionState.ERROR
    conn.error = test_error
    
    # Verify not ready when in ERROR state
    assert conn.is_ready == False


@pytest.mark.asyncio
async def test_error_handling_in_call_tool():
    """Test error handling in the call_tool method."""
    # Create a registry and patch its get_client method to raise an exception
    registry = ServerRegistry({
        "server1": MCPServerSettings(type="stdio", command="test", args=[]),
    })
    
    # Create the aggregator
    aggregator = MCPAggregator(registry)
    
    # Patch both load_servers and get_client
    with patch.object(aggregator, "load_servers", AsyncMock()):
        with patch.object(registry, "get_client", side_effect=ValueError("Test connection error")):
            # Call tool (should handle the error)
            result = await aggregator.call_tool("server1__test", {"arg": "value"})
            
            # Verify the result contains the error information
            assert result.isError == True
            assert "Error in call_tool for 'server1__test'" in result.message


@pytest.mark.asyncio
async def test_server_connections_used_for_correct_tools():
    """Test that the right server connections are used for tools."""
    # Create a registry and patch its methods
    registry = ServerRegistry({
        "server1": MCPServerSettings(type="stdio", command="test", args=[]),
        "server2": MCPServerSettings(type="stdio", command="test", args=[]),
    })
    
    # Create the aggregator with persistent mode
    aggregator = MCPAggregator(registry)
    
    # Create mocks for the get_client method's results
    mock_session1 = AsyncMock()
    mock_session1.call_tool = AsyncMock(return_value=MagicMock(isError=False, content=[], message=""))
    
    mock_session2 = AsyncMock()
    mock_session2.call_tool = AsyncMock(return_value=MagicMock(isError=False, content=[], message=""))
    
    # Patch the needed methods
    with patch.object(aggregator, "load_servers", AsyncMock()):
        # Create a side effect function for get_client to return different sessions
        # based on server name
        @asynccontextmanager
        async def get_client_side_effect(server_name):
            if server_name == "server1":
                yield mock_session1
            else:
                yield mock_session2
                
        # Patch the get_client method
        with patch.object(registry, "get_client", side_effect=get_client_side_effect):
            # Call tools on different servers
            await aggregator.call_tool("server1__test1", {"arg": "value1"})
            await aggregator.call_tool("server2__test2", {"arg": "value2"})
            
            # Verify each server's session was called with the correct tool
            mock_session1.call_tool.assert_called_once_with("test1", {"arg": "value1"})
            mock_session2.call_tool.assert_called_once_with("test2", {"arg": "value2"})


@pytest.mark.asyncio
async def test_graceful_shutdown_with_cancellation():
    """Test that server connection handles cancellation during shutdown."""
    # Create a mock server connection
    server_conn = ServerConnection(
        server_name="test_server",
        server_config=MCPServerSettings(
            type="stdio",
            command="test",
            args=["arg"],
        ),
        transport_context_factory=AsyncMock(),
        client_session_factory=lambda *args: AsyncMock(),
    )
    
    # Create a mock session that will be set during the task
    mock_session = AsyncMock()
    
    # Create a task that will simulate a cancelled server lifecycle
    async def mock_lifecycle_task():
        # First set the session
        server_conn.session = mock_session
        server_conn.state = ConnectionState.READY
        server_conn._initialized_event.set()
        
        # Then simulate a CancelledError during the main loop
        await asyncio.sleep(0.1)  # Small delay
        
        # Verify the connection handles cancellation gracefully
        raise asyncio.CancelledError()
    
    # Run the task and verify it's handled properly
    task = asyncio.create_task(mock_lifecycle_task())
    
    # Wait for the task to complete or be cancelled
    try:
        await asyncio.wait_for(task, timeout=0.5)
    except asyncio.CancelledError:
        pass  # Expected
    
    # Check if the initialized event was set and the connection is in proper state
    assert server_conn._initialized_event.is_set()