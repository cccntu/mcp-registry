"""Tests for the negative tool filtering functionality in MCPAggregator."""

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
                Tool(name="tool3", description="Tool 3", inputSchema={}),
                Tool(name="dangerous", description="Dangerous Tool", inputSchema={}),
            ]
        else:  # server2
            tools = [
                Tool(name="toolA", description="Tool A", inputSchema={}),
                Tool(name="toolB", description="Tool B", inputSchema={}),
                Tool(name="risky", description="Risky Tool", inputSchema={}),
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


def test_negative_filter_validation():
    """Test that mixed positive and negative filters raise appropriate errors."""
    registry = MagicMock()
    
    # Test with mixed positive and negative filters
    mixed_filter = {"server1": ["tool1", "-tool2"]}  # Mixed filter types
    
    with pytest.raises(ValueError) as excinfo:
        MCPAggregator(registry, tool_filter=mixed_filter)
    
    assert "Mixed filter types" in str(excinfo.value)
    assert "all positive filters or all negative filters" in str(excinfo.value)


@pytest.mark.asyncio
async def test_load_servers_with_negative_filter(mock_registry):
    """Test that tools are excluded when using negative filtering."""
    # Create aggregator with negative tool filter - exclude dangerous tool
    tool_filter = {
        "server1": ["-dangerous"],  # Exclude dangerous tool from server1
        "server2": ["-risky"],  # Exclude risky tool from server2
    }
    aggregator = MCPAggregator(mock_registry, tool_filter=tool_filter)
    
    # Load the servers
    await aggregator.load_servers()
    
    # Check which tools were loaded (dangerous should be excluded)
    namespaced_tools = list(aggregator._namespaced_tool_map.keys())
    assert "server1__tool1" in namespaced_tools
    assert "server1__tool2" in namespaced_tools
    assert "server1__tool3" in namespaced_tools
    assert "server1__dangerous" not in namespaced_tools
    assert "server2__toolA" in namespaced_tools
    assert "server2__toolB" in namespaced_tools
    assert "server2__risky" not in namespaced_tools


@pytest.mark.asyncio
async def test_load_servers_with_multiple_negative_filters(mock_registry):
    """Test that multiple tools can be excluded with negative filtering."""
    # Create aggregator with negative tool filter - exclude multiple tools
    tool_filter = {
        "server1": ["-tool1", "-tool2"],  # Exclude tool1 and tool2
        "server2": None,  # Include all tools from server2
    }
    aggregator = MCPAggregator(mock_registry, tool_filter=tool_filter)
    
    # Load the servers
    await aggregator.load_servers()
    
    # Check which tools were loaded (tool1 and tool2 should be excluded)
    namespaced_tools = list(aggregator._namespaced_tool_map.keys())
    assert "server1__tool1" not in namespaced_tools
    assert "server1__tool2" not in namespaced_tools
    assert "server1__tool3" in namespaced_tools
    assert "server1__dangerous" in namespaced_tools
    assert "server2__toolA" in namespaced_tools
    assert "server2__toolB" in namespaced_tools
    assert "server2__risky" in namespaced_tools


@pytest.mark.asyncio
async def test_list_tools_with_negative_filter(mock_registry):
    """Test that list_tools reflects the negative tool filtering."""
    # Create aggregator with negative tool filter
    tool_filter = {
        "server1": ["-dangerous"],  # Exclude dangerous tool
        "server2": ["-risky"],  # Exclude risky tool
    }
    aggregator = MCPAggregator(mock_registry, tool_filter=tool_filter)
    
    # Load the servers and list tools
    await aggregator.load_servers()
    tools_result = await aggregator.list_tools()
    
    # Check that filtered tools are excluded
    tool_names = [t.name for t in tools_result.tools]
    assert "server1__tool1" in tool_names
    assert "server1__tool2" in tool_names
    assert "server1__tool3" in tool_names
    assert "server1__dangerous" not in tool_names
    assert "server2__toolA" in tool_names
    assert "server2__toolB" in tool_names
    assert "server2__risky" not in tool_names
    assert len(tool_names) == 5  # 3 from server1 + 2 from server2


@pytest.mark.asyncio
async def test_list_tools_with_server_mapping_and_negative_filter(mock_registry):
    """Test that list_tools with server mapping reflects the negative tool filtering."""
    # Create aggregator with negative tool filter
    tool_filter = {
        "server1": ["-dangerous", "-tool1"],  # Exclude dangerous and tool1
        "server2": None,  # Include all tools from server2
    }
    aggregator = MCPAggregator(mock_registry, tool_filter=tool_filter)
    
    # Load the servers and list tools with server mapping
    await aggregator.load_servers()
    server_tools = await aggregator.list_tools(return_server_mapping=True)
    
    # Check that server mapping contains the right tools
    assert len(server_tools["server1"]) == 2
    tool1_names = [t.name for t in server_tools["server1"]]
    assert "tool2" in tool1_names
    assert "tool3" in tool1_names
    assert "dangerous" not in tool1_names
    assert "tool1" not in tool1_names
    
    assert len(server_tools["server2"]) == 3
    tool2_names = [t.name for t in server_tools["server2"]]
    assert "toolA" in tool2_names
    assert "toolB" in tool2_names
    assert "risky" in tool2_names