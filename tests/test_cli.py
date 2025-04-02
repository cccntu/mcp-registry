"""Tests for the CLI interface."""

import json
import os

import pytest
from click.testing import CliRunner

from mcp_registry.cli import cli


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def temp_config_path(tmp_path, monkeypatch):
    """Create a temporary config file path."""
    config_path = tmp_path / "config.json"
    # Patch the CONFIG_FILE path to use our temporary path
    monkeypatch.setattr("mcp_registry.cli.CONFIG_FILE", config_path)
    return config_path


def test_init_creates_config(runner, temp_config_path):
    """Test that init creates a config file."""
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0
    assert "Initialized configuration" in result.output
    assert temp_config_path.exists()

    with open(temp_config_path) as f:
        config = json.load(f)
    assert "mcpServers" in config


def test_add_stdio_server(runner, temp_config_path):
    """Test adding a stdio server."""
    # First initialize the config
    runner.invoke(cli, ["init"])

    # Then add a server
    result = runner.invoke(
        cli, ["add", "test-server", "python", "-m", "mcp.contrib.file", "--description", "Test file server"]
    )

    assert result.exit_code == 0
    assert "Added server 'test-server'" in result.output

    # Verify the config was updated
    with open(temp_config_path) as f:
        config = json.load(f)

    assert "test-server" in config["mcpServers"]
    assert config["mcpServers"]["test-server"]["type"] == "stdio"
    shell = os.environ.get("SHELL", "/bin/sh")
    assert config["mcpServers"]["test-server"]["command"] == shell
    assert "python -m mcp.contrib.file" in " ".join(config["mcpServers"]["test-server"]["args"])
    assert config["mcpServers"]["test-server"]["description"] == "Test file server"


def test_add_sse_server(runner, temp_config_path):
    """Test adding an SSE server."""
    # First initialize the config
    runner.invoke(cli, ["init"])

    # Then add a server
    result = runner.invoke(
        cli, ["add", "remote-server", "dummy", "--url", "http://localhost:8000/sse", "--description", "Remote server"]
    )

    assert result.exit_code == 0
    assert "Added server 'remote-server'" in result.output

    # Verify the config was updated
    with open(temp_config_path) as f:
        config = json.load(f)

    assert "remote-server" in config["mcpServers"]
    assert config["mcpServers"]["remote-server"]["type"] == "sse"
    assert config["mcpServers"]["remote-server"]["url"] == "http://localhost:8000/sse"
    assert config["mcpServers"]["remote-server"]["description"] == "Remote server"


def test_remove_server(runner, temp_config_path):
    """Test removing a server."""
    # First initialize the config
    runner.invoke(cli, ["init"])

    # Add a server
    runner.invoke(cli, ["add", "test-server", "python", "-m", "mcp.contrib.file"])

    # Then remove it
    result = runner.invoke(cli, ["remove", "test-server"])

    assert result.exit_code == 0
    assert "Removed server 'test-server'" in result.output

    # Verify the server was removed
    with open(temp_config_path) as f:
        config = json.load(f)

    assert "test-server" not in config["mcpServers"]


def test_list_servers(runner, temp_config_path):
    """Test listing servers."""
    # First initialize the config
    runner.invoke(cli, ["init"])

    # Add a server
    runner.invoke(cli, ["add", "test-server", "python", "-m", "mcp.contrib.file"])

    # List servers
    result = runner.invoke(cli, ["list"])

    assert result.exit_code == 0
    assert "test-server" in result.output
    assert "stdio" in result.output
    assert "python -m mcp.contrib.file" in result.output


def test_list_empty(runner, temp_config_path):
    """Test listing servers when none are registered."""
    # First initialize the config
    runner.invoke(cli, ["init"])

    # List servers
    result = runner.invoke(cli, ["list"])

    assert result.exit_code == 0
    assert "No servers registered" in result.output


def test_list_tools_no_config(runner, temp_config_path):
    """Test list-tools when no config exists."""
    # Don't initialize the config
    result = runner.invoke(cli, ["list-tools"])
    
    assert result.exit_code == 0
    assert "Global configuration file not found" in result.output


def test_list_tools_no_servers(runner, temp_config_path):
    """Test list-tools when no servers are registered."""
    # First initialize the config
    runner.invoke(cli, ["init"])
    
    # List tools
    result = runner.invoke(cli, ["list-tools"])
    
    assert result.exit_code == 0
    assert "No servers registered" in result.output


@pytest.mark.asyncio
async def test_list_tools_with_mock_server(runner, temp_config_path, monkeypatch):
    """Test list-tools with a mocked server returning tools."""
    from unittest.mock import AsyncMock, MagicMock
    
    # First initialize the config
    runner.invoke(cli, ["init"])
    
    # Add a mock server
    runner.invoke(cli, ["add", "mock-server", "echo", "dummy"])
    
    # Create mock tool data
    mock_tool1 = MagicMock()
    mock_tool1.name = "tool1"
    mock_tool1.description = "Tool 1 description that is long enough to be truncated in the default output mode"
    mock_tool1.inputSchema = {
        "properties": {
            "param1": {"type": "string", "description": "Parameter 1 description"},
            "param2": {"type": "number", "description": "Parameter 2 description"}
        },
        "required": ["param1"]
    }
    
    mock_tool2 = MagicMock()
    mock_tool2.name = "tool2"
    mock_tool2.description = "Tool 2 description"
    mock_tool2.inputSchema = {
        "properties": {
            "option": {"type": "boolean", "description": "Option description"}
        },
        "required": []
    }
    
    # Create mock for aggregator.list_tools
    mock_list_tools = AsyncMock()
    mock_list_tools.return_value = {"mock-server": [mock_tool1, mock_tool2]}
    
    # Mock the MCPAggregator class
    mock_aggregator = MagicMock()
    mock_aggregator.return_value.list_tools = mock_list_tools
    monkeypatch.setattr("mcp_registry.compound.MCPAggregator", mock_aggregator)
    
    # Test default output (standard verbosity)
    result = runner.invoke(cli, ["list-tools"])
    assert result.exit_code == 0
    assert "Server: mock-server" in result.output
    assert "tool1: Tool 1 description" in result.output
    assert "tool2: Tool 2 description" in result.output
    assert "Parameter 1 description" not in result.output  # Parameters not shown in default mode
    
    # Test -v output (medium verbosity)
    result = runner.invoke(cli, ["list-tools", "-v"])
    assert result.exit_code == 0
    assert "Server: mock-server" in result.output
    assert "Tool: tool1" in result.output
    assert "Description: Tool 1 description" in result.output
    assert "Parameters:" in result.output
    assert "param1 (string, required)" in result.output
    assert "param2 (number, optional)" in result.output
    
    # Test -vv output (high verbosity)
    result = runner.invoke(cli, ["list-tools", "-vv"])
    assert result.exit_code == 0
    assert "Server: mock-server" in result.output
    assert "Tool: tool1" in result.output
    assert "Description: Tool 1 description that is long enough to be truncated" in result.output
    assert "Parameters:" in result.output
    assert "param1 (string, required): Parameter 1 description" in result.output
    
    # Test filtering by server name
    result = runner.invoke(cli, ["list-tools", "mock-server"])
    assert result.exit_code == 0
    assert "Server: mock-server" in result.output
    
    # Test filtering by non-existent server
    result = runner.invoke(cli, ["list-tools", "non-existent-server"])
    assert result.exit_code == 0
    assert "No matching servers found" in result.output


@pytest.mark.asyncio
async def test_test_tool_command(runner, temp_config_path, monkeypatch):
    """Test test-tool command with a mocked server."""
    from unittest.mock import AsyncMock, MagicMock
    from dataclasses import dataclass
    
    # First initialize the config
    runner.invoke(cli, ["init"])
    
    # Add a mock server
    runner.invoke(cli, ["add", "mock-server", "echo", "dummy"])
    
    # Create mock tool result
    @dataclass
    class MockContent:
        type: str = "text"
        text: str = "Test result content"
    
    @dataclass
    class MockResult:
        isError: bool = False
        message: str = ""
        content: list = None
        
        def __post_init__(self):
            if self.content is None:
                self.content = [MockContent()]
    
    # Create mock for aggregator.call_tool
    mock_call_tool = AsyncMock()
    mock_call_tool.return_value = MockResult()
    
    # Create mock for tool schema
    @dataclass
    class MockTool:
        name: str = "tool1"
        description: str = "Test tool"
        inputSchema: dict = None
        
        def __post_init__(self):
            if self.inputSchema is None:
                self.inputSchema = {
                    "properties": {
                        "param1": {"type": "string", "description": "Test parameter"},
                        "param2": {"type": "number", "description": "Another parameter"}
                    },
                    "required": ["param1"]
                }
    
    # Mock the MCPAggregator class
    mock_aggregator = MagicMock()
    mock_aggregator.return_value.call_tool = mock_call_tool
    mock_aggregator.return_value.list_tools = AsyncMock(return_value={"mock-server": [MockTool()]})
    monkeypatch.setattr("mcp_registry.compound.MCPAggregator", mock_aggregator)
    
    # Test basic tool call
    result = runner.invoke(cli, ["test-tool", "mock-server__tool1", "--input", '{"param1": "test"}'])
    assert result.exit_code == 0
    assert "Test result content" in result.output
    
    # Test call with input file
    with open(temp_config_path.parent / "input.json", "w") as f:
        f.write('{"param1": "test", "param2": 123}')
    
    result = runner.invoke(cli, ["test-tool", "mock-server__tool1", "--input-file", 
                                str(temp_config_path.parent / "input.json")])
    assert result.exit_code == 0
    assert "Test result content" in result.output
    
    # Test raw output
    result = runner.invoke(cli, ["test-tool", "mock-server__tool1", "--input", '{"param1": "test"}', "--raw"])
    assert result.exit_code == 0
    assert "isError" in result.output
    assert "content" in result.output
    
    # Test error result
    mock_call_tool.return_value = MockResult(isError=True, message="Test error message")
    result = runner.invoke(cli, ["test-tool", "mock-server__tool1", "--input", '{"param1": "test"}'])
    assert result.exit_code == 1
    assert "Error" in result.output
    assert "Test error message" in result.output
    
    # Test invalid server format
    result = runner.invoke(cli, ["test-tool", "invalid-format", "--input", '{"param1": "test"}'])
    assert result.exit_code == 0
    assert "Error: Tool path must be in format" in result.output
    
    # Test non-existent server
    result = runner.invoke(cli, ["test-tool", "nonexistent__tool", "--input", '{"param1": "test"}'])
    assert result.exit_code == 0
    assert "Error: Server 'nonexistent' not found" in result.output
    
    # Test interactive mode (mocked)
    # Note: We're using non-interactive with stdin to avoid actual prompts in tests
    # In a real interactive session, the user would be prompted for input
    mock_call_tool.return_value = MockResult()
    result = runner.invoke(cli, ["test-tool", "mock-server__tool1", "--non-interactive"], 
                           input='{"param1": "interactive test"}')
    assert result.exit_code == 0  # Should still work with --non-interactive
    
    # For full interactive testing we would need to mock click.prompt,
    # which is more complex in a test environment


def test_show_config(runner, temp_config_path):
    """Test show command."""
    # First initialize the config
    runner.invoke(cli, ["init"])
    
    # Add a server to have something in the config
    runner.invoke(cli, ["add", "test-server", "python", "-m", "test"])
    
    # Show config
    result = runner.invoke(cli, ["show"])
    assert result.exit_code == 0
    assert "mcpServers" in result.output
    assert "test-server" in result.output
