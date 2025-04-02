#!/usr/bin/env python3
"""
Example showing how to get the MCP Registry config path.

This demonstrates how to use the get_config_path and get_default_config_path functions
to determine where the configuration file is located, respecting the MCP_REGISTRY_CONFIG
environment variable.
"""

import os
from pathlib import Path
from mcp_registry import get_config_path, get_default_config_path

def main():
    # Get the default config path (ignoring environment variable)
    default_path = get_default_config_path()
    print(f"Default config path: {default_path}")

    # Get the current config path (respects MCP_REGISTRY_CONFIG env var)
    current_path = get_config_path()
    print(f"Current config path: {current_path}")

    # Check if the config path is set via environment variable
    if os.getenv("MCP_REGISTRY_CONFIG"):
        print(f"Config path is set via MCP_REGISTRY_CONFIG environment variable")
        print(f"Value: {os.getenv('MCP_REGISTRY_CONFIG')}")
    else:
        print(f"Using default config location (no environment variable set)")

    # Check if the config file exists
    if current_path.exists():
        print(f"Config file exists at: {current_path}")
    else:
        print(f"Config file does not exist at: {current_path}")
        print(f"You may need to run 'mcp-registry init' to create it")

    # Example: How to use in a typical workflow
    print("\nTypical usage in a workflow:")
    print("----------------------------")
    print("from mcp_registry import ServerRegistry, get_config_path")
    print("registry = ServerRegistry.from_config(get_config_path())")
    print("# Now you can use the registry with the correct config path")

if __name__ == "__main__":
    main()