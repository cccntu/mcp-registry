#!/usr/bin/env python3

"""
Anthropic MCP Agent implementation with persistent connections.
This version uses the context manager pattern to maintain persistent connections
to MCP servers, improving performance for multiple tool calls.
"""

import os
import json
import time
import asyncio
from typing import Dict, Any, List, Optional

from anthropic import AsyncAnthropic
from mcp_registry import ServerRegistry, MCPAggregator, get_config_path


class MCPAgent:
    """
    An agent that uses tools from the MCP registry with Claude.
    This version maintains persistent connections to MCP servers.
    """

    def __init__(self):
        # Initialize Async Anthropic client
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        self.client = AsyncAnthropic(api_key=api_key)

        # Conversation history
        self.conversation = []

        # Tool registry
        self.tools = []

        # Initialize MCP registry 
        self.registry = ServerRegistry.from_config(get_config_path())
        
        # The aggregator will be initialized during context enter
        self.aggregator = None
        
    async def __aenter__(self):
        """Enter context manager - establish persistent connections."""
        # Create aggregator with persistent connections
        self.aggregator = MCPAggregator(self.registry)
        # Enter the aggregator's context to establish persistent connections
        self.aggregator = await self.aggregator.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - clean up connections."""
        if self.aggregator:
            try:
                await self.aggregator.__aexit__(exc_type, exc_val, exc_tb)
            except Exception as e:
                print(f"Warning: Error during MCP aggregator cleanup: {e}")
            finally:
                self.aggregator = None

    async def initialize_tools(self):
        """Initialize tools from MCP registry"""
        if not self.aggregator:
            raise RuntimeError("Agent must be used as a context manager to initialize tools")
            
        # Get all available tools from the MCP registry
        results = await self.aggregator.list_tools()

        # Register each tool with the agent
        for tool in results.tools:
            # Extract tool information and register it
            self.tools.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema,
            })

        print(f"Registered {len(self.tools)} tools from MCP registry")

    async def process_query(self, query: str, max_iterations: int = 20):
        """Process a query using Claude with tools

        Args:
            query: The user's query
            max_iterations: Maximum number of tool-calling iterations to allow

        Returns:
            The final agent response text
        """
        if not self.aggregator:
            raise RuntimeError("Agent must be used as a context manager to process queries")
            
        # Add user message to conversation history
        self.conversation.append({"role": "user", "content": query})

        # Track iteration count to prevent infinite loops
        iterations = 0
        final_response = ""

        # Continue the conversation until no more tool calls or max iterations reached
        while iterations < max_iterations:
            iterations += 1

            try:
                # Call Claude with current conversation
                response = await self.client.messages.create(
                    model="claude-3-5-haiku-20241022",
                    max_tokens=1000,
                    messages=self.conversation,
                    tools=self.tools,
                )

                # Process the response
                has_tool_calls = False
                tool_results = []
                response_text = ""

                # Add Claude's response to conversation
                self.conversation.append({"role": "assistant", "content": response.content})

                # Process text content and tool calls
                for content in response.content:
                    if content.type == "text":
                        response_text = content.text
                        final_response = response_text  # Save the text response
                    elif content.type == "tool_use":
                        has_tool_calls = True
                        tool_name = content.name
                        tool_args = content.input
                        tool_id = content.id

                        # Execute the tool directly through the aggregator
                        print(f"Calling tool {tool_name} with args {tool_args} and tool_id {tool_id}")

                        try:
                            # Call the tool through the aggregator (using persistent connection)
                            result = await self.aggregator.call_tool(tool_name, tool_args)

                            # Extract content and error status from the result object
                            tool_result = {
                                "tool_use_id": tool_id,
                                "content": result.content if hasattr(result, 'content') else result,
                                "is_error": result.isError if hasattr(result, 'isError') else False
                            }
                        except Exception as e:
                            # For errors, create an error result
                            tool_result = {
                                "tool_use_id": tool_id,
                                "content": {"error": f"Error calling MCP tool {tool_name}: {str(e)}"},
                                "is_error": True
                            }

                        # Add to tool results
                        tool_results.append(tool_result)

                # If no tool calls were made, we're done with this query
                if not has_tool_calls:
                    break

                # Add tool results to conversation
                for result in tool_results:
                    self.conversation.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": result["tool_use_id"],
                                    "content": result["content"],
                                    "is_error": result["is_error"]
                                }
                            ],
                        }
                    )

            except Exception as e:
                # Handle API errors
                error_message = f"Error calling Anthropic API: {str(e)}"
                print(f"API Error: {error_message}")
                final_response = f"I encountered an error: {error_message}"
                break

        return final_response


async def run_examples():
    """Run example queries to demonstrate the Anthropic MCP agent's capabilities with persistent connections"""
    
    # Measure total execution time
    start_time = time.time()
    
    # Create and initialize the MCP agent with persistent connections
    async with MCPAgent() as agent:
        # Initialize tools (will reuse the persistent connections)
        await agent.initialize_tools()

        # Print the number of available tools
        print(f"Agent has {len(agent.tools)} tools available")

        # Display a few tool names if available
        if len(agent.tools) > 0:
            print("\nSample of available tools:")
            for i, tool in enumerate(agent.tools[:5]):  # Show first 5 tools
                print(f"  - {tool['name']}: {tool['description'][:60]}...")
                if i >= 4:
                    break

        # Example 1: Ask about available tools
        print("\n=== Example 1: Ask about available tools ===")
        response = await agent.process_query("What tools are available and what can they do?")
        print(response)

        # Example 2: Use a specific tool if available
        print("\n=== Example 2: Try to use a specific tool ===")
        response = await agent.process_query(
            "If there's a search tool available, please use it to search for 'machine learning frameworks'"
        )
        print(response)

        # Example 3: Try to use GitHub tools
        print("\n=== Example 3: Try to use GitHub tools ===")
        response = await agent.process_query(
            "Can you search for popular Python repositories on GitHub? Use the appropriate GitHub tool."
        )
        print(response)

        # Example 4: Try a multi-step task
        print("\n=== Example 4: Try a multi-step task ===")
        response = await agent.process_query(
            "First search for information about 'transformer models', then try to find a popular GitHub repository related to transformers."
        )
        print(response)
    
    # Calculate and print the total time taken
    elapsed_time = time.time() - start_time
    print(f"\nTotal execution time: {elapsed_time:.2f} seconds")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_examples())