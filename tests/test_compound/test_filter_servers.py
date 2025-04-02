"""Tests for the ServerRegistry.filter_servers method."""

import pytest
from unittest.mock import MagicMock

from mcp_registry.compound import ServerRegistry, MCPServerSettings


def test_filter_servers_valid():
    """Test filter_servers with valid server names."""
    # Create some mock server settings
    settings1 = MCPServerSettings(type="stdio", command="cmd1", args=["arg1"])
    settings2 = MCPServerSettings(type="stdio", command="cmd2", args=["arg2"])
    settings3 = MCPServerSettings(type="sse", url="http://localhost:3000")
    
    # Create a registry with all settings
    registry = ServerRegistry({
        "server1": settings1,
        "server2": settings2,
        "server3": settings3,
    })
    
    # Filter to only server1 and server3
    filtered = registry.filter_servers(["server1", "server3"])
    
    # Check filtered registry contains only the requested servers
    assert len(filtered.registry) == 2
    assert "server1" in filtered.registry
    assert "server3" in filtered.registry
    assert "server2" not in filtered.registry
    
    # Verify the settings objects are the same
    assert filtered.registry["server1"] is settings1
    assert filtered.registry["server3"] is settings3


def test_filter_servers_missing():
    """Test filter_servers with server names that don't exist."""
    # Create a registry with some settings
    registry = ServerRegistry({
        "server1": MCPServerSettings(type="stdio", command="cmd1", args=["arg1"]),
        "server2": MCPServerSettings(type="stdio", command="cmd2", args=["arg2"]),
    })
    
    # Attempt to filter with a non-existent server name
    with pytest.raises(ValueError) as excinfo:
        registry.filter_servers(["server1", "nonexistent"])
    
    # Check error message
    assert "Servers not found: nonexistent" in str(excinfo.value)


def test_filter_servers_empty():
    """Test filter_servers with an empty list."""
    # Create a registry with some settings
    registry = ServerRegistry({
        "server1": MCPServerSettings(type="stdio", command="cmd1", args=["arg1"]),
        "server2": MCPServerSettings(type="stdio", command="cmd2", args=["arg2"]),
    })
    
    # Filter with empty list
    filtered = registry.filter_servers([])
    
    # Check that the filtered registry is empty
    assert len(filtered.registry) == 0
    assert isinstance(filtered, ServerRegistry)


def test_filter_servers_all():
    """Test filter_servers with all server names."""
    # Create a registry with some settings
    registry = ServerRegistry({
        "server1": MCPServerSettings(type="stdio", command="cmd1", args=["arg1"]),
        "server2": MCPServerSettings(type="stdio", command="cmd2", args=["arg2"]),
    })
    
    # Filter with all server names
    filtered = registry.filter_servers(["server1", "server2"])
    
    # Check that the filtered registry contains all servers
    assert len(filtered.registry) == 2
    assert "server1" in filtered.registry
    assert "server2" in filtered.registry


def test_filter_servers_original_unchanged():
    """Test that filter_servers doesn't modify the original registry."""
    # Create a registry with some settings
    registry = ServerRegistry({
        "server1": MCPServerSettings(type="stdio", command="cmd1", args=["arg1"]),
        "server2": MCPServerSettings(type="stdio", command="cmd2", args=["arg2"]),
    })
    
    # Store the original state
    original_servers = list(registry.registry.keys())
    
    # Filter to only server1
    filtered = registry.filter_servers(["server1"])
    
    # Check that the original registry is unchanged
    assert list(registry.registry.keys()) == original_servers
    assert len(registry.registry) == 2
    assert "server1" in registry.registry
    assert "server2" in registry.registry