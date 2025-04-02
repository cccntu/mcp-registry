#!/usr/bin/env python3
"""
Example showing how to use persistent connections with MCPAggregator.

This demonstrates two approaches:
1. Using MCPAggregator with temporary connections (default behavior)
2. Using MCPAggregator as a context manager with persistent connections
"""

import asyncio
import time
from mcp_registry import ServerRegistry, MCPAggregator, get_config_path

async def with_temporary_connections():
    """Example using MCPAggregator with temporary connections (default behavior)."""
    print("\n--- Using temporary connections ---")
    
    # Load servers from config
    registry = ServerRegistry.from_config(get_config_path())
    
    # Create an aggregator with temporary connections
    aggregator = MCPAggregator(registry)
    
    # Time multiple tool calls with temporary connections
    start_time = time.time()
    
    for i in range(3):
        print(f"Call {i+1}: Making tool call with temporary connection...")
        # Each call creates and destroys a new connection
        result = await aggregator.call_tool(
            tool_name="echo__ping",  # Replace with a tool from your registry
            arguments={"message": f"Hello {i+1}"}
        )
        print(f"Call {i+1} result: {result.content[0].text if result.content else 'No content'}")
    
    elapsed = time.time() - start_time
    print(f"Temporary connections - 3 calls took {elapsed:.2f} seconds\n")

async def with_persistent_connections():
    """Example using MCPAggregator with persistent connections via context manager."""
    print("\n--- Using persistent connections ---")
    
    # Load servers from config
    registry = ServerRegistry.from_config(get_config_path())
    
    # Use MCPAggregator as a context manager to maintain persistent connections
    start_time = time.time()
    
    async with MCPAggregator(registry) as aggregator:
        # Connection is established when entering the context
        print("Persistent connection established")
        
        # Make multiple tool calls using the same connection
        for i in range(3):
            print(f"Call {i+1}: Making tool call with persistent connection...")
            result = await aggregator.call_tool(
                tool_name="echo__ping",  # Replace with a tool from your registry
                arguments={"message": f"Hello {i+1}"}
            )
            print(f"Call {i+1} result: {result.content[0].text if result.content else 'No content'}")
        
        # Connections are closed automatically when exiting the context
    
    elapsed = time.time() - start_time
    print(f"Persistent connections - 3 calls took {elapsed:.2f} seconds\n")
    print("Persistent connections automatically closed")

async def main():
    """Run both examples for comparison."""
    # First run with temporary connections
    await with_temporary_connections()
    
    # Then run with persistent connections
    await with_persistent_connections()
    
    # You should notice that persistent connections are significantly faster
    # after the first call, since they don't need to re-establish connections
    print("\nNote: Replace 'echo__ping' with a tool that exists in your registry.")
    print("The time difference will be more noticeable with tools requiring")
    print("more initialization time (like LLM servers).")

if __name__ == "__main__":
    asyncio.run(main())