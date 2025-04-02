"""Test the compound server functionality."""

import json
from pathlib import Path

import pytest

from mcp_registry import (
    MCPAggregator,
    MCPServerSettings,
    ServerRegistry,
    run_registry_server,
)


# Test server configurations
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
def config_file(tmp_path, test_servers):
    """Create a temporary config file with test servers."""
    config_path = tmp_path / "config.json"
    config = {"mcpServers": {name: settings.model_dump() for name, settings in test_servers.items()}}

    with open(config_path, "w") as f:
        json.dump(config, f)

    return config_path


def test_server_registry_from_config(config_file, test_servers):
    """Test creating ServerRegistry from config file."""
    registry = ServerRegistry.from_config(config_file)

    # Check that all servers were loaded
    assert len(registry.registry) == len(test_servers)
    for name, settings in test_servers.items():
        assert name in registry.registry
        loaded = registry.registry[name]
        assert loaded.type == settings.type
        assert loaded.command == settings.command
        assert loaded.args == settings.args
        assert loaded.description == settings.description


def test_server_registry_from_config_not_found():
    """Test error when config file doesn't exist."""
    with pytest.raises(FileNotFoundError):
        ServerRegistry.from_config("nonexistent.json")


def test_server_registry_from_config_invalid():
    """Test error when config file is invalid."""
    tmp_path = Path("test_config.json")
    try:
        # Create invalid config
        with open(tmp_path, "w") as f:
            f.write("invalid json")

        with pytest.raises(json.JSONDecodeError):
            ServerRegistry.from_config(tmp_path)
    finally:
        # Clean up
        if tmp_path.exists():
            tmp_path.unlink()


def test_server_registry_from_config_missing_servers(tmp_path):
    """Test error when config file doesn't have mcpServers section."""
    config_path = tmp_path / "config.json"
    with open(config_path, "w") as f:
        json.dump({"not_servers": {}}, f)

    with pytest.raises(KeyError, match="must have a 'mcpServers' section"):
        ServerRegistry.from_config(config_path)


def test_server_registry_from_config_missing_type(tmp_path):
    """Test loading a config file with servers that don't specify type."""
    config_path = tmp_path / "config.json"
    
    # Create a config with servers missing type field
    config = {
        "mcpServers": {
            "no_type_server": {
                "command": "test",
                "args": ["arg1", "arg2"]
            }
        }
    }
    
    with open(config_path, "w") as f:
        json.dump(config, f)
    
    # Load the config and verify type defaults to stdio
    registry = ServerRegistry.from_config(config_path)
    
    assert "no_type_server" in registry.registry
    server_settings = registry.registry["no_type_server"]
    assert server_settings.type == "stdio"
    assert server_settings.command == "test"
    assert server_settings.args == ["arg1", "arg2"]


def test_server_registry_save_config(tmp_path, test_servers):
    """Test saving ServerRegistry configuration to a file."""
    # Create a registry
    registry = ServerRegistry(test_servers)

    # Save the config
    config_path = tmp_path / "saved_config.json"
    registry.save_config(config_path)

    # Load it back and verify
    loaded_registry = ServerRegistry.from_config(config_path)

    # Check that all servers were preserved
    assert len(loaded_registry.registry) == len(test_servers)
    for name, settings in test_servers.items():
        assert name in loaded_registry.registry
        loaded = loaded_registry.registry[name]
        assert loaded.type == settings.type
        assert loaded.command == settings.command
        assert loaded.args == settings.args
        assert loaded.description == settings.description


def test_server_registry_save_config_creates_dirs(tmp_path, test_servers):
    """Test that save_config creates intermediate directories."""
    registry = ServerRegistry(test_servers)

    # Try to save to a nested path
    config_path = tmp_path / "nested" / "dirs" / "config.json"
    registry.save_config(config_path)

    # Verify the file was created
    assert config_path.exists()

    # Load it back and verify
    loaded_registry = ServerRegistry.from_config(config_path)
    assert len(loaded_registry.registry) == len(test_servers)


def test_server_registry_save_config_excludes_none(tmp_path):
    """Test that save_config excludes None values from output."""
    # Create a minimal server config
    servers = {
        "minimal": MCPServerSettings(
            type="stdio",
            command="test",
            args=["arg"],
            # description and other fields are None
        )
    }
    registry = ServerRegistry(servers)

    # Save the config
    config_path = tmp_path / "minimal_config.json"
    registry.save_config(config_path)

    # Read the raw JSON and verify None values were excluded
    with open(config_path) as f:
        config = json.load(f)

    server_config = config["mcpServers"]["minimal"]
    assert "description" not in server_config
    assert "url" not in server_config
    assert "env" not in server_config


def test_mcp_server_settings_default_type():
    """Test that MCPServerSettings defaults to stdio type when not specified."""
    # Create a settings object without specifying type
    settings = MCPServerSettings(
        command="test",
        args=["arg"],
    )
    
    # Verify the type defaulted to stdio
    assert settings.type == "stdio"
    
    # Verify the transport property reflects the type
    assert settings.transport == "stdio"
    
    # Create a settings object explicitly specifying type
    settings_sse = MCPServerSettings(
        type="sse",
        url="http://localhost:8000",
    )
    
    # Verify the explicit type was used
    assert settings_sse.type == "sse"
    assert settings_sse.transport == "sse"


@pytest.fixture
def registry(test_servers):
    """Create a server registry with test servers."""
    return ServerRegistry(test_servers)


@pytest.fixture
def aggregator(registry):
    """Create an aggregator with all test servers."""
    return MCPAggregator(registry)


async def test_aggregator_list_tools(aggregator):
    """Test that aggregator can list tools from all servers."""
    result = await aggregator.list_tools()
    assert result.tools is not None
    assert len(result.tools) > 0

    # Check that tool names are properly namespaced
    for tool in result.tools:
        assert "__" in tool.name
        server_name = tool.name.split("__")[0]
        assert server_name in ["test_server1", "test_server2"]


async def test_aggregator_call_tool(aggregator):
    """Test that aggregator can call tools on servers."""
    # Skip actual server communication for now
    pytest.skip("Skipping actual server communication test")


async def test_registry_server(registry):
    """Test that registry server initializes and runs correctly."""
    # Skip actual server communication for now
    pytest.skip("Skipping actual server communication test")


async def test_registry_server_with_subset(registry):
    """Test that registry server works with a subset of servers."""
    # Skip actual server communication for now
    pytest.skip("Skipping actual server communication test")


async def test_invalid_server_name(aggregator):
    """Test handling of invalid server names."""
    result = await aggregator.call_tool("invalid_server__test")
    assert result.isError
    assert "not found" in result.message
