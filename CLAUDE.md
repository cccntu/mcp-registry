# Claude Knowledge for MCP Registry

This document contains useful information for Claude when working with the MCP Registry codebase.

## Project Overview

MCP Registry is a tool for managing and interacting with multiple [Model Context Protocol (MCP)](https://modelcontextprotocol.io) servers. It solves three key problems:

1. **Simplified MCP Server Configuration Management**: Replaces manual JSON editing with an intuitive CLI
2. **Selective Server Exposure**: Run only specific servers from your configuration without multiple files
3. **Synchronized Settings**: Configure servers once and access from multiple clients

## Repository Structure

- `src/mcp_registry/`: Core code
  - `compound.py`: Server registry, settings, and aggregator
  - `connection.py`: Connection management for persistent connections
  - `cli.py`: Command-line interface
- `docs/`: Documentation
  - `api_reference.md`: Detailed API documentation
  - `getting_started.md`: Introduction guide
  - `cli_reference.md`: CLI command reference
  - `async-connection-management.md`: Async patterns explanation
  - `tutorial_integrating_servers.md`: Integration tutorial
- `examples/`: Example scripts
- `tests/`: Test files

## Key Components

1. **ServerRegistry**: Manages server configurations
   - Loads/saves config files
   - Provides client sessions for servers

2. **MCPAggregator**: Aggregates multiple servers
   - Namespaces tools with server names (e.g., "server_name__tool_name")
   - Supports both temporary and persistent connections

3. **MCPConnectionManager**: Manages persistent connections
   - Uses async context managers for proper resource lifecycle
   - Implements concurrent connection management

4. **CLI**: Command-line interface for managing servers
   - Add/remove servers
   - Run compound servers with selected servers

## Connection Patterns

MCP Registry supports two connection modes:

1. **Temporary Connections (default)**
   - Creates a new connection for each tool call
   - Simpler but less efficient for multiple calls

2. **Persistent Connections**
   - Uses async context manager pattern
   - Maintains connections across multiple tool calls
   - Better performance for repeated calls

## Common Tasks

### Adding Docstrings

When adding docstrings, follow this format:
```python
def function_name(param1, param2):
    """
    Brief description of function purpose.
    
    More detailed explanation if needed.
    
    Args:
        param1: Description of parameter
        param2: Description of parameter
    
    Returns:
        Description of return value
        
    Raises:
        ExceptionType: Description of when this exception is raised
    
    Example:
        ```python
        result = function_name("foo", 42)
        ```
    """
```

### Testing

Use pytest for testing:
```bash
# Run all tests
pytest

# Run a specific test file
pytest tests/test_specific.py

# Run with verbose output
pytest -v
```

### Documentation Best Practices

- Keep examples in all docstrings
- Include parameter and return type information
- Document exceptions and error conditions
- Use markdown formatting for documentation files

## Development Guidelines

1. **Error Handling**:
   - Use appropriate error types for different failure modes
   - Include context information in error messages

2. **Async Patterns**:
   - Use async context managers for resource lifecycle management
   - Ensure proper cleanup in `__aexit__` methods
   - Use concurrent execution with `gather()` where appropriate

3. **Configuration**:
   - Use standard file locations adhering to platform conventions
   - Support environment variables for configuration overrides
   - Validate configuration for better error messages

4. **Testing**:
   - Unit test individual components in isolation
   - Include integration tests for real-world use cases
   - Use mocks for testing server connections

## Future Improvements

Potential enhancements to consider:
- Standardizing error handling patterns
- Adding automatic retries for transient errors
- Implementing connection pooling
- Adding health checks and monitoring
- Supporting server profiles for different environments