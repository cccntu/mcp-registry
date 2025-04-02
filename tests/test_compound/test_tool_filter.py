"""Tests for the tool filtering functionality in MCPAggregator."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager

from mcp.types import ListToolsResult, Tool
from mcp_registry.compound import ServerRegistry, MCPAggregator, MCPServerSettings


@pytest.fixture
def mock_registry():
    """Create a mock registry with two servers."""
    # Mock server settings
    settings1 = MCPServerSettings(type="stdio", command="cmd1", args=["arg1"])
    settings2 = MCPServerSettings(type="stdio", command="cmd2", args=["arg2"])
    
    # Create registry with mock settings
    registry = ServerRegistry({
        "server1": settings1,
        "server2": settings2
    })
    
    # Create a mock get_client method for the registry
    @asynccontextmanager
    async def mock_get_client(server_name):
        # Create a mock client session
        client = AsyncMock()
        
        # Configure mock tools for each server
        if server_name == "server1":
            tools = [
                Tool(name="tool1", description="Tool 1", inputSchema={}),
                Tool(name="tool2", description="Tool 2", inputSchema={}),
                Tool(name="tool3", description="Tool 3", inputSchema={})
            ]
        else:  # server2
            tools = [
                Tool(name="toolA", description="Tool A", inputSchema={}),
                Tool(name="toolB", description="Tool B", inputSchema={}),
            ]
        
        # Configure the client's list_tools method
        client.list_tools.return_value = ListToolsResult(tools=tools)
        
        try:
            yield client
        finally:
            pass
    
    # Add the mock get_client method to the registry
    registry.get_client = mock_get_client
    
    return registry


@pytest.mark.asyncio
async def test_tool_filter_init():
    """Test that tool_filter is properly initialized."""
    registry = MagicMock()
    tool_filter = {"server1": ["tool1", "tool2"]}
    
    aggregator = MCPAggregator(registry, tool_filter=tool_filter)
    
    assert aggregator.tool_filter == tool_filter


@pytest.mark.asyncio
async def test_tool_filter_empty():
    """Test that an empty tool_filter defaults to include all tools."""
    registry = MagicMock()
    
    aggregator = MCPAggregator(registry, tool_filter={})
    
    assert aggregator.tool_filter == {}


@pytest.mark.asyncio
async def test_tool_filter_none():
    """Test that a None tool_filter defaults to include all tools."""
    registry = MagicMock()
    
    aggregator = MCPAggregator(registry, tool_filter=None)
    
    assert aggregator.tool_filter == {}


def test_tool_filter_validation():
    """Test that invalid tool_filter values raise appropriate errors."""
    registry = MagicMock()
    
    # Test with an invalid type (string instead of list)
    invalid_filter = {"server1": "tool1"}  # Should be a list or None
    
    with pytest.raises(ValueError) as excinfo:
        MCPAggregator(registry, tool_filter=invalid_filter)
    
    assert "Invalid tool_filter" in str(excinfo.value)
    assert "must be a list or None" in str(excinfo.value)
    
    # Test with another invalid type (int instead of list)
    invalid_filter = {"server1": 123}
    
    with pytest.raises(ValueError) as excinfo:
        MCPAggregator(registry, tool_filter=invalid_filter)
    
    assert "Invalid tool_filter" in str(excinfo.value)
    assert "must be a list or None" in str(excinfo.value)


@pytest.mark.asyncio
async def test_load_servers_with_tool_filter(mock_registry):
    """Test that tools are filtered when loading servers."""
    # Create aggregator with tool filter - only include tool1 from server1 and all tools from server2
    tool_filter = {
        "server1": ["tool1"],  # Only include tool1 from server1
        "server2": None,  # Include all tools from server2
    }
    aggregator = MCPAggregator(mock_registry, tool_filter=tool_filter)
    
    # Load the servers
    await aggregator.load_servers()
    
    # Check which tools were loaded
    namespaced_tools = list(aggregator._namespaced_tool_map.keys())
    assert "server1__tool1" in namespaced_tools
    assert "server1__tool2" not in namespaced_tools
    assert "server1__tool3" not in namespaced_tools
    assert "server2__toolA" in namespaced_tools
    assert "server2__toolB" in namespaced_tools


@pytest.mark.asyncio
async def test_load_servers_with_empty_tool_list(mock_registry):
    """Test that an empty tool list filters out all tools from that server."""
    # Create aggregator with tool filter - empty list for server1 means include no tools
    tool_filter = {
        "server1": [],  # Include no tools from server1
        "server2": ["toolA"],  # Only include toolA from server2
    }
    aggregator = MCPAggregator(mock_registry, tool_filter=tool_filter)
    
    # Load the servers
    await aggregator.load_servers()
    
    # Check which tools were loaded
    namespaced_tools = list(aggregator._namespaced_tool_map.keys())
    assert "server1__tool1" not in namespaced_tools
    assert "server1__tool2" not in namespaced_tools
    assert "server1__tool3" not in namespaced_tools
    assert "server2__toolA" in namespaced_tools
    assert "server2__toolB" not in namespaced_tools


@pytest.mark.asyncio
async def test_load_servers_no_filter(mock_registry):
    """Test that all tools are loaded when no tool filter is specified."""
    # Create aggregator with no tool filter
    aggregator = MCPAggregator(mock_registry)
    
    # Load the servers
    await aggregator.load_servers()
    
    # Check that all tools were loaded
    namespaced_tools = list(aggregator._namespaced_tool_map.keys())
    assert "server1__tool1" in namespaced_tools
    assert "server1__tool2" in namespaced_tools
    assert "server1__tool3" in namespaced_tools
    assert "server2__toolA" in namespaced_tools
    assert "server2__toolB" in namespaced_tools


@pytest.mark.asyncio
async def test_list_tools_with_filter(mock_registry):
    """Test that list_tools reflects the tool filtering."""
    # Create aggregator with tool filter
    tool_filter = {
        "server1": ["tool1"],
        "server2": ["toolA"],
    }
    aggregator = MCPAggregator(mock_registry, tool_filter=tool_filter)
    
    # Load the servers and list tools
    await aggregator.load_servers()
    tools_result = await aggregator.list_tools()
    
    # Check that only the filtered tools are included
    tool_names = [t.name for t in tools_result.tools]
    assert "server1__tool1" in tool_names
    assert "server1__tool2" not in tool_names
    assert "server1__tool3" not in tool_names
    assert "server2__toolA" in tool_names
    assert "server2__toolB" not in tool_names
    assert len(tool_names) == 2


@pytest.mark.asyncio
async def test_list_tools_with_server_mapping_and_filter(mock_registry):
    """Test that list_tools with server mapping reflects the tool filtering."""
    # Create aggregator with tool filter
    tool_filter = {
        "server1": ["tool1"],
        "server2": None,  # Include all tools from server2
    }
    aggregator = MCPAggregator(mock_registry, tool_filter=tool_filter)
    
    # Load the servers and list tools with server mapping
    await aggregator.load_servers()
    server_tools = await aggregator.list_tools(return_server_mapping=True)
    
    # Check that server mapping contains the right tools
    assert len(server_tools["server1"]) == 1
    assert server_tools["server1"][0].name == "tool1"
    assert len(server_tools["server2"]) == 2
    assert sorted([t.name for t in server_tools["server2"]]) == ["toolA", "toolB"]


@pytest.mark.asyncio
async def test_call_filtered_out_tool(mock_registry):
    """Test that calling a filtered-out tool fails appropriately."""
    # Mock the call_tool method to verify it's not called
    with patch.object(ServerRegistry, 'get_client') as mock_get_client:
        # Create aggregator with tool filter - only include tool1 from server1
        tool_filter = {
            "server1": ["tool1"],  # Only include tool1 from server1
        }
        aggregator = MCPAggregator(mock_registry, tool_filter=tool_filter)
        
        # Load the servers
        await aggregator.load_servers()
        
        # Attempt to call a filtered-out tool
        result = await aggregator.call_tool("server1__tool2")
        
        # Should return an error without trying to call the server
        assert result.isError is True
        assert "not found" in result.message
        
        # Verify get_client was not called
        mock_get_client.assert_not_called()