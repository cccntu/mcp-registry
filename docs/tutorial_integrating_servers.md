# Tutorial: Integrating MCP Servers with Claude and Other AI Tools

This tutorial will walk you through setting up a consistent MCP server environment that works across multiple AI tools like Claude Desktop, Claude Code, and others. We'll demonstrate how to use MCP Registry to manage your server configurations and selectively expose them to different clients.

## Prerequisites

Before starting, make sure you have:

1. Installed MCP Registry:
   ```bash
   pip install mcp-registry
   ```

2. Installed at least one MCP client (Claude Desktop, Claude Code, etc.)

3. Have access to some MCP servers (either ones you've developed or Node-based servers like `@modelcontextprotocol/server-memory`)

## Step 1: Initialize Your Configuration

First, let's initialize the MCP Registry configuration:

```bash
mcp-registry init
```

This creates a configuration file at `~/.config/mcp_registry/mcp_registry_config.json` by default.

## Step 2: Add Common MCP Servers

Let's add some commonly useful MCP servers to our configuration:

```bash
# Add a memory server for simple key-value storage
mcp-registry add memory npx -y @modelcontextprotocol/server-memory

# Add a filesystem server for file operations
mcp-registry add filesystem npx -y @modelcontextprotocol/server-filesystem

# Add a web fetch server
mcp-registry add web npx -y @modelcontextprotocol/server-web

# Add a screenshot server
mcp-registry add screenshot npx -y @modelcontextprotocol/server-screenshot
```

## Step 3: Verify Your Configuration

Let's check the servers we've configured:

```bash
mcp-registry list
```

You should see all four servers listed with their descriptions and commands.

## Step 4: Test the Compound Server

Now let's test our compound server to make sure everything works:

```bash
# Start the compound server in a separate terminal
mcp-registry serve

# In another terminal, test with the inspector
npx -y @modelcontextprotocol/inspector
```

In the inspector, try some commands:

```
/tools

# Try storing some data
/call memory__set {"key": "greeting", "value": "Hello, World!"}

# Try retrieving the data
/call memory__get {"key": "greeting"}

# Try a filesystem operation 
/call filesystem__list {"path": "."}
```

If everything is working, you should see successful responses from each server.

## Step 5: Integrate with Claude Desktop

Now let's add our servers to Claude Desktop:

```bash
# If you have Claude Desktop installed, add all servers:
claude desktop mcp add servers mcp-registry serve
```

Open Claude Desktop and check that the tools are available:

1. Click on the tools icon in the chat interface
2. You should see tools from all four servers, prefixed with their server names
3. Try using one of the tools, like the memory__get tool, to retrieve the "greeting" value we set earlier

## Step 6: Create Different Server Profiles for Different Clients

One of the key benefits of MCP Registry is the ability to selectively expose only specific servers to different clients. Let's create two different profiles:

### For Claude Code (Development Profile)

Let's create a development profile with all servers for Claude Code:

```bash
# Add all servers to Claude Code
claude mcp add servers mcp-registry serve
```

### For Claude Desktop (Limited Profile)

Let's create a more restricted profile for Claude Desktop, with only memory and web access:

```bash
# Remove the current configuration (if you added all servers earlier)
claude desktop mcp remove servers mcp-registry

# Add only memory and web servers to Claude Desktop
claude desktop mcp add servers mcp-registry serve memory web
```

## Step 7: Verify the Different Profiles

Now let's verify that each client has the correct server profile:

1. Open Claude Desktop and check the available tools:
   - You should only see tools from the memory and web servers
   - The filesystem and screenshot tools should not be available

2. Open a project in Claude Code and check the available tools:
   - You should see tools from all four servers
   - Try using the filesystem tool, which should only be available in Claude Code

## Step 8: Create a Custom Server

Let's create a simple custom MCP server and add it to our registry. For this example, we'll use the simple-tool example from the MCP Python SDK.

First, make sure you have the submodule initialized:

```bash
# If you cloned the MCP Registry repository
cd mcp-registry
git submodule update --init --recursive
pip install -e ./python-sdk
```

Now add the simple-tool server to our registry:

```bash
mcp-registry add simple-tool python -m python-sdk.examples.servers.simple-tool.mcp_simple_tool
```

## Step 9: Integration with Python Code

Finally, let's create a Python script that uses our registry to interact with the servers:

```python
# save as example_integration.py
import asyncio
from mcp_registry import ServerRegistry, MCPAggregator, get_config_path

async def main():
    # Load the same registry used by Claude Desktop and Claude Code
    registry = ServerRegistry.from_config(get_config_path())
    
    # Create an aggregator with all servers
    aggregator = MCPAggregator(registry)
    
    # List all available tools
    tools_result = await aggregator.list_tools()
    print("Available tools:")
    for tool in tools_result.tools:
        print(f"- {tool.name}")
    
    # Store a value using the memory server
    print("\nStoring a value...")
    result = await aggregator.call_tool("memory__set", {"key": "from_script", "value": "Hello from Python script!"})
    print(f"Result: {'Success' if not result.isError else f'Error: {result.message}'}")
    
    # Retrieve the value
    print("\nRetrieving the value...")
    result = await aggregator.call_tool("memory__get", {"key": "from_script"})
    if not result.isError and result.content:
        print(f"Retrieved value: {result.content[0].text}")
    else:
        print(f"Error: {result.message}")
    
    # Try using our simple-tool server to fetch a website
    print("\nFetching a website...")
    result = await aggregator.call_tool("simple-tool__fetch", {"url": "https://example.com"})
    if not result.isError and result.content:
        content = result.content[0].text
        # Print just the first 100 characters
        print(f"Website content (truncated): {content[:100]}...")
    else:
        print(f"Error: {result.message}")

if __name__ == "__main__":
    asyncio.run(main())
```

Run the script:

```bash
python example_integration.py
```

You should see output showing all available tools, and the results of using the memory and simple-tool servers.

## Step 10: Verify Integration Across Tools

Now you can verify that the data persists between different clients:

1. Open Claude Desktop and try:
   ```
   /call memory__get {"key": "from_script"}
   ```

2. Open Claude Code and try the same command:
   ```
   /call memory__get {"key": "from_script"}
   ```

3. Both should return "Hello from Python script!"

## Conclusion

Congratulations! You've now set up a consistent MCP server environment that works across multiple AI tools:

1. **Centralized Configuration**: All your MCP server settings are managed in one place
2. **Selective Exposure**: Different clients have access to different subsets of servers
3. **Programmatic Access**: Your Python code can use the same servers as your AI tools
4. **Synchronized State**: Data stored by one client can be accessed by others

This approach makes it much easier to manage and use MCP servers across your entire workflow, ensuring consistency and reducing configuration overhead.

## Next Steps

- Try adding more specialized servers for your specific needs
- Explore creating your own custom MCP servers
- Consider how persistent connections can optimize performance for server-heavy workflows
- Check out the [API Reference](api_reference.md) for more advanced usage options