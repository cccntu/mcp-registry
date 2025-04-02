"""
Test MCP Aggregator functionality.

This script demonstrates how to use the MCPAggregator to start and interact with MCP servers.

To run this test, ensure you have the required dependencies and the python-sdk submodule:
1. After cloning this repository, initialize and update the submodule:
   git submodule update --init --recursive

2. Install the required dependencies:
   pip install -e .
   pip install -e ./python-sdk
"""
import asyncio
import os
from pathlib import Path
import json
import sys
import importlib.util

from mcp_registry.compound import ServerRegistry, MCPServerSettings, MCPAggregator

# Check if the required example server module is available
def check_example_server():
    try:
        # Try to find the simple-tool example server
        example_path = None
        
        # Option 1: Look for it in python-sdk subdirectory if it exists
        sdk_path = Path("python-sdk")
        if sdk_path.exists():
            example_path = sdk_path / "examples" / "servers" / "simple-tool" / "mcp_simple_tool" / "__main__.py"
        
        # Option 2: Look for it in site-packages if the SDK is installed with its examples
        if not example_path or not example_path.exists():
            import mcp
            mcp_path = Path(mcp.__file__).parent.parent
            potential_paths = [
                mcp_path / "examples" / "servers" / "simple-tool" / "mcp_simple_tool" / "__main__.py",
                Path("examples") / "servers" / "simple-tool" / "mcp_simple_tool" / "__main__.py"
            ]
            for path in potential_paths:
                if path.exists():
                    example_path = path
                    break
        
        if not example_path or not example_path.exists():
            print("WARNING: Could not find simple-tool example server.")
            print("Please clone the MCP python-sdk repository and install it:")
            print("  git clone https://github.com/modelcontextprotocol/python-sdk.git")
            print("  cd python-sdk")
            print("  pip install -e .")
            return None
        
        return str(example_path.parent.parent)
    except ImportError:
        print("WARNING: MCP package not found.")
        print("Please install the MCP package: pip install mcp")
        return None

async def main():
    # Find example server path
    example_server_module = check_example_server()
    if not example_server_module:
        print("Exiting: Required modules or example server not found.")
        return
    
    # Create a temporary server settings file
    config_dir = Path("./test_config_dir")
    config_dir.mkdir(exist_ok=True)
    config_path = config_dir / "test_servers.json"
    
    # Configure a simple tool server
    server_config = {
        "mcpServers": {
            "simple_tool": {
                "type": "stdio",
                "command": sys.executable,
                "args": [
                    "-m", 
                    f"{example_server_module}"
                ],
                "description": "Simple tool server for testing"
            }
        }
    }
    
    # Save the configuration
    with open(config_path, "w") as f:
        json.dump(server_config, f, indent=2)
    
    try:
        print("Loading server registry from config...")
        # Load the server registry from the config file
        registry = ServerRegistry.from_config(config_path)
        
        print("Creating MCP Aggregator...")
        # Create an aggregator
        aggregator = MCPAggregator(registry)
        
        print("Listing tools...")
        # List the tools
        tools_result = await aggregator.list_tools()
        print(f"Available tools: {[t.name for t in tools_result.tools]}")
        
        print("Calling tool...")
        # Call the tool
        result = await aggregator.call_tool("simple_tool__fetch", {"url": "https://example.com"})
        
        print("Tool call result:")
        print(f"Is error: {result.isError}")
        if result.isError:
            print(f"Error message: {result.message}")
        else:
            for content in result.content:
                if hasattr(content, 'text') and len(content.text) > 100:
                    # Truncate long text for display
                    print(f"Content (truncated): {content.text[:100]}...")
                else:
                    print(f"Content: {content}")
        
        print("Test completed successfully!")
        
    except Exception as e:
        print(f"Error during test: {e}")
        raise
    finally:
        # Clean up the temporary config file
        if config_path.exists():
            config_path.unlink()
        if config_dir.exists():
            config_dir.rmdir()

if __name__ == "__main__":
    asyncio.run(main())