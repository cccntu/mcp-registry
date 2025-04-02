"""Integration tests for MCP Registry."""

import pytest

from mcp_registry import (
    MCPAggregator,
    MCPServerSettings,
    ServerRegistry,
    run_registry_server,
)


@pytest.fixture
def memory_server_config():
    """Create a memory server configuration."""
    return {
        "memory": MCPServerSettings(
            type="stdio",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-memory"],
            description="Memory server",
        )
    }


@pytest.fixture
def registry(memory_server_config):
    """Create a registry with the memory server."""
    return ServerRegistry(memory_server_config)


@pytest.fixture
def aggregator(registry):
    """Create an aggregator with the memory server."""
    return MCPAggregator(registry)


async def test_memory_server_integration(aggregator):
    """Test integration with memory server."""
    # Skip actual server communication for now
    pytest.skip("Skipping actual server communication test")


async def test_registry_server_integration(registry):
    """Test registry server with memory server."""
    # Skip actual server communication for now
    pytest.skip("Skipping actual server communication test")
