"""Tests for the tool aliasing functionality in MCPAggregator."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager

from mcp.types import ListToolsResult, Tool, CallToolResult, TextContent
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
        
        # Configure the client's call_tool method
        async def mock_call_tool(tool_name, arguments=None):
            return CallToolResult(
                isError=False,
                message=f"Called {tool_name} with {arguments}",
                content=[TextContent(type="text", text=f"Result from {tool_name}")]
            )
        
        client.call_tool = mock_call_tool
        
        try:
            yield client
        finally:
            pass
    
    # Add the mock get_client method to the registry
    registry.get_client = mock_get_client
    
    return registry


@pytest.mark.asyncio
async def test_alias_init():
    """Test that aliases are properly initialized."""
    registry = MagicMock()
    aliases = {"mytool": "server1__tool1", "anothertool": "server2__toolA"}
    
    aggregator = MCPAggregator(registry, aliases=aliases)
    
    assert aggregator.aliases == aliases


@pytest.mark.asyncio
async def test_alias_empty():
    """Test that empty aliases initialize to an empty dict."""
    registry = MagicMock()
    
    aggregator = MCPAggregator(registry, aliases={})
    
    assert aggregator.aliases == {}


@pytest.mark.asyncio
async def test_alias_none():
    """Test that None aliases initialize to an empty dict."""
    registry = MagicMock()
    
    aggregator = MCPAggregator(registry, aliases=None)
    
    assert aggregator.aliases == {}


@pytest.mark.asyncio
async def test_call_tool_with_alias(mock_registry):
    """Test that calling a tool by its alias works correctly."""
    # Create aggregator with aliases
    aliases = {
        "mytool": "server1__tool1",
        "special": "server2__toolA"
    }
    aggregator = MCPAggregator(mock_registry, aliases=aliases)
    
    # Load servers
    await aggregator.load_servers()
    
    # Call tool using the alias
    result = await aggregator.call_tool("mytool", {"param": "value"})
    
    # Check that it worked correctly
    assert not result.isError
    assert "Result from tool1" in result.content[0].text


@pytest.mark.asyncio
async def test_call_tool_with_chained_alias(mock_registry):
    """Test that calling a tool with an alias that points to another alias does NOT work recursively."""
    # Create aggregator with chained aliases
    aliases = {
        "mytool": "server1__tool1",
        "shortcut": "mytool"  # This points to the first alias
    }
    aggregator = MCPAggregator(mock_registry, aliases=aliases)
    
    # Load servers
    await aggregator.load_servers()
    
    # Call tool using the chained alias
    result = await aggregator.call_tool("shortcut", {"param": "value"})
    
    # Since we don't do recursive resolution, this should fail
    assert result.isError
    assert "must be namespaced" in result.message
    
    # However, the direct alias should still work
    result = await aggregator.call_tool("mytool", {"param": "value"})
    assert not result.isError
    assert "Result from tool1" in result.content[0].text


@pytest.mark.asyncio
async def test_call_tool_with_unknown_alias(mock_registry):
    """Test that calling an unknown alias doesn't break the normal flow."""
    # Create aggregator with some aliases
    aliases = {"mytool": "server1__tool1"}
    aggregator = MCPAggregator(mock_registry, aliases=aliases)
    
    # Load servers
    await aggregator.load_servers()
    
    # Call a tool that isn't an alias but is a valid namespaced tool
    result = await aggregator.call_tool("server1__tool2", {"param": "value"})
    
    # This should work fine
    assert not result.isError
    assert "Result from tool2" in result.content[0].text
    
    # Now try with an invalid name that isn't an alias
    result = await aggregator.call_tool("unknown_tool", {"param": "value"})
    
    # This should fail with an error
    assert result.isError
    assert "must be namespaced" in result.message