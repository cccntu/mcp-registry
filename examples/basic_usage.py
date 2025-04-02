#!/usr/bin/env python3
"""
Basic usage example for MCP Registry.

This demonstrates how to load servers from the config file and interact with them.
"""

import asyncio
import json
from pathlib import Path

from mcp_registry import MCPAggregator, ServerRegistry, get_config_path

async def main():
    # Load servers from config (using the current config path)
    registry = ServerRegistry.from_config(get_config_path())

    # Create an aggregator to interact with servers
    aggregator = MCPAggregator(registry)

    # List all available tools
    tools_result = await aggregator.list_tools()
    tools = [tool.name for tool in tools_result.tools]
    print(f"Available tools: {json.dumps(tools, indent=2)}")

    # Example: Call a tool if the memory server is available
    memory_tools = [t for t in tools if t.startswith("memory__")]
    if memory_tools:
        print("\nMemory server is available. Setting a value...")
        result = await aggregator.call_tool(
            tool_name="set",
            server_name="memory",
            arguments={"key": "test", "value": "Hello from MCP Registry!"}
        )
        print(f"Result: {result}")

        # Get the value back
        result = await aggregator.call_tool(
            tool_name="get",
            server_name="memory",
            arguments={"key": "test"}
        )
        print(f"Retrieved value: {result}")

        # Alternative: Call using combined name
        result = await aggregator.call_tool(
            tool_name="memory__get",  # Format: "server_name__tool_name"
            arguments={"key": "test"}
        )
        print(f"Retrieved value (using combined name): {result}")
    else:
        print("\nMemory server is not available. Add it with:")
        print("mcp-registry add memory npx -y @modelcontextprotocol/server-memory")

if __name__ == "__main__":
    asyncio.run(main())
