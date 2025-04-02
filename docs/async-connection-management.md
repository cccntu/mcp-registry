# Async Connection Management Patterns

This document explains the industry-standard patterns for connection management in asynchronous code, as implemented in the MCP Registry project.

## Core Async Connection Management Patterns

### 1. Connection Pooling

**What it is**: Maintaining a cache of reusable connections rather than creating/destroying connections for each operation.

**Key components**:
- **Pool Manager**: Central authority that tracks available connections
- **Connection Object**: Represents a single connection with its state
- **Acquisition/Release Mechanism**: How connections are checked out and returned

**Why it matters in async code**: In async environments, connections can be shared efficiently among many tasks without blocking, making pooling even more valuable.

**In our implementation**:
- [`MCPConnectionManager`](../src/mcp_registry/connection.py) serves as the pool manager
- [`ServerConnection`](../src/mcp_registry/connection.py) represents individual connections
- Acquisition happens via `get_server()` method

### 2. Context Managers for Resource Lifecycle

**What it is**: Using async context managers (`async with`) to ensure proper resource cleanup.

**Key patterns**:
- **Two-level context management**: Outer level manages the pool, inner level manages individual connections
- **Resource acquisition deferral**: Resources are only obtained when needed
- **Guaranteed cleanup**: Resources are released even if exceptions occur

**In our implementation**:
- [`MCPAggregator.__aenter__`](../src/mcp_registry/compound.py) and `__aexit__` implement the outer context manager
- Connection resources are automatically cleaned up on exit

Example usage:
```python
async with MCPAggregator(registry) as aggregator:  # Pool-level context
    # Connections automatically managed within this block
    result = await aggregator.call_tool("memory__get", {"key": "test"})
```

### 3. Task Groups for Concurrent Management

**What it is**: Using task groups to manage multiple concurrent background tasks that handle connection lifecycles.

**Key patterns**:
- **TaskGroup/nursery pattern**: Create a task group to manage related tasks
- **Background monitoring**: Tasks run in background to monitor connection health
- **Graceful shutdown**: All tasks are properly cancelled on exit

**In our implementation**:
- [`MCPConnectionManager`](../src/mcp_registry/connection.py) creates a task group in `__aenter__`
- [`_server_lifecycle_task`](../src/mcp_registry/connection.py) runs as a background task for each connection
- All tasks are properly cancelled in `__aexit__`

### 4. Event-Based Coordination

**What it is**: Using events to coordinate between tasks handling the same connection.

**Key patterns**:
- **Initialization events**: Signal when a connection is ready for use
- **Shutdown events**: Signal when a connection should be closed
- **Error propagation**: Communicating errors across tasks

**In our implementation**:
- [`ServerConnection._initialized_event`](../src/mcp_registry/connection.py) signals when initialization is complete
- [`ServerConnection.wait_for_initialized()`](../src/mcp_registry/connection.py) waits for connection readiness
- [`ServerConnection.request_shutdown()`](../src/mcp_registry/connection.py) signals a connection to shut down

### 5. Connection State Management

**What it is**: Explicit tracking of connection states to handle the full lifecycle.

**Common states**:
- **INITIALIZING**: Connection is being established
- **READY**: Connection is established and ready for use
- **ERROR**: Connection failed or encountered an error
- **SHUTDOWN**: Connection is being or has been closed

**In our implementation**:
- [`ConnectionState`](../src/mcp_registry/connection.py) enum defines the possible states
- [`ServerConnection.state`](../src/mcp_registry/connection.py) tracks the current state
- State transitions are managed carefully with proper error handling

## Benefits of These Patterns

1. **Efficiency**: Reuse connections instead of creating new ones for each operation
2. **Reliability**: Proper error handling and recovery mechanisms
3. **Resource Safety**: Ensure connections are always properly closed
4. **Concurrency**: Safe handling of concurrent connection requests
5. **Scalability**: Better performance under high load

## How It's Used in MCP Registry

The MCP Registry implements these patterns to provide two connection modes:

1. **Temporary Connections** (default): Each tool call creates and destroys its own connection
   - Optimized to only load the specific server needed for a tool call
   - Simple to use but less efficient for multiple calls to the same server

2. **Persistent Connections**: Using `MCPAggregator` as a context manager maintains connections for the duration of the context
   - More efficient for multiple tool calls
   - Better performance for servers with costly initialization

Example of persistent connections:

```python
async with MCPAggregator(registry) as aggregator:
    # First tool call - connection is established
    result1 = await aggregator.call_tool("memory__set", {"key": "test", "value": "Hello"})
    
    # Second tool call - reuses the same connection
    result2 = await aggregator.call_tool("memory__get", {"key": "test"})
    
    # Connections automatically closed when exiting the context
```

For more examples, see the [persistent connections example](../examples/persistent_connections_example.py).

## Implementation Details

The key classes in our implementation are:

1. **MCPAggregator**: Main interface that users interact with, supports context manager pattern
2. **MCPConnectionManager**: Manages the lifecycle of persistent connections
3. **ServerConnection**: Represents a single persistent connection to a server
4. **ConnectionState**: Enum to track connection states

Together, these classes provide a robust connection management system that follows industry best practices.