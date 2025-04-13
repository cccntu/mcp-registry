"""Tests for the utility functions in the config module."""

import pytest
import tempfile
import json
import os
from pathlib import Path

from mcp_registry.utils.config import (
    parse_tool_filter,
    get_aliases,
    add_alias,
    remove_alias,
    validate_alias
)


def test_parse_tool_filter_empty():
    """Test that empty filter strings return an empty dict."""
    assert parse_tool_filter("") == {}
    assert parse_tool_filter(None) == {}


def test_parse_tool_filter_simple():
    """Test parsing a simple filter with one server and no tools."""
    assert parse_tool_filter("server1") == {"server1": None}


def test_parse_tool_filter_with_tools():
    """Test parsing a filter with tools listed."""
    result = parse_tool_filter("server1:tool1,tool2")
    assert result == {"server1": ["tool1", "tool2"]}


def test_parse_tool_filter_complex():
    """Test parsing a complex filter with multiple servers and tools."""
    # Use the semicolon format for cleaner server separation
    result = parse_tool_filter("server1:tool1,tool2;server2;server3:toolA,toolB")
    assert result == {
        "server1": ["tool1", "tool2"], 
        "server2": None,
        "server3": ["toolA", "toolB"]
    }


def test_parse_tool_filter_negative():
    """Test parsing a filter with negative tool filters."""
    # Use the semicolon format for cleaner server separation
    result = parse_tool_filter("server1:-tool1,-tool2;server2:-dangerous")
    
    # Validate that each server has the expected tools with negative filters
    assert "server1" in result and isinstance(result["server1"], list)
    assert "-tool1" in result["server1"]
    assert "server2" in result and isinstance(result["server2"], list)
    assert "-dangerous" in result["server2"]


def test_parse_tool_filter_mixed():
    """Test parsing a complex filter with a mix of server types."""
    # Use the semicolon format for cleaner server separation
    result = parse_tool_filter("server1;server2:tool1,tool2;server3:-toolX,-toolY")
    
    # Validate the structure matches expectations
    assert "server1" in result and result["server1"] is None  # No tools
    assert "server2" in result and isinstance(result["server2"], list)
    assert "tool1" in result["server2"]  # Has tools
    assert "server3" in result  # Exists
    assert "-toolX" in result["server3"]  # Has negative tools


class MockConfig:
    """Helper to mock the config functions for testing."""
    
    def __init__(self):
        self.config = {
            "mcpServers": {
                "memory": {
                    "type": "stdio",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-memory"]
                }
            },
            "aliases": {
                "get": "memory__get",
                "set": "memory__set"
            }
        }
        
    def get_config(self):
        return self.config
        
    def save_config(self, config):
        self.config = config


@pytest.fixture
def mock_config(monkeypatch):
    """Create a mocked configuration system for testing."""
    mock = MockConfig()
    
    # Mock the load_config function
    def mock_load_config():
        return mock.get_config()
        
    # Mock the save_config function
    def mock_save_config(config):
        mock.save_config(config)
        
    # Apply the patches
    monkeypatch.setattr('mcp_registry.utils.config.load_config', mock_load_config)
    monkeypatch.setattr('mcp_registry.utils.config.save_config', mock_save_config)
    
    return mock


def test_get_aliases(mock_config):
    """Test that get_aliases returns the aliases from the config."""
    aliases = get_aliases()
    assert aliases == {"get": "memory__get", "set": "memory__set"}


def test_add_alias(mock_config):
    """Test adding a new alias."""
    # Add a new alias
    add_alias("search", "github__search")
    
    # Check that it was added
    aliases = get_aliases()
    assert aliases["search"] == "github__search"
    
    # Check that existing aliases are still there
    assert aliases["get"] == "memory__get"
    assert aliases["set"] == "memory__set"
    
    # Verify the config was updated correctly
    config = mock_config.get_config()
    assert config["aliases"]["search"] == "github__search"


def test_remove_alias(mock_config):
    """Test removing an alias."""
    # First check it exists
    aliases = get_aliases()
    assert "get" in aliases
    
    # Remove it
    result = remove_alias("get")
    assert result is True
    
    # Check that it's gone
    aliases = get_aliases()
    assert "get" not in aliases
    assert "set" in aliases  # Other aliases should remain
    
    # Try removing one that doesn't exist
    result = remove_alias("nonexistent")
    assert result is False


def test_validate_alias():
    """Test the alias validation function."""
    # Valid alias
    is_valid, _ = validate_alias("get", "memory__get")
    assert is_valid is True
    
    # Empty alias name
    is_valid, error = validate_alias("", "memory__get")
    assert is_valid is False
    assert "cannot be empty" in error
    
    # Empty tool name
    is_valid, error = validate_alias("get", "")
    assert is_valid is False
    assert "cannot be empty" in error
    
    # Invalid tool name format
    is_valid, error = validate_alias("get", "memory_get")  # Missing double underscore
    assert is_valid is False
    assert "format" in error