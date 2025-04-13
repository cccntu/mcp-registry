"""Formatting utilities for MCP Registry output."""

import json


def truncate_text(text: str, max_length: int = 60) -> str:
    """Truncate text to a specified maximum length with a smart break point.
    
    Args:
        text: The text to truncate
        max_length: Maximum length of the result
        
    Returns:
        Truncated text with ellipsis if needed
    """
    if not text or len(text) <= max_length:
        return text
        
    # Try to find a sentence break
    break_point = text[:max_length].rfind('. ')
    if break_point > 30:  # Ensure we don't cut too short
        return text[:break_point+1]
    else:
        # Otherwise break at max_length
        return text[:max_length-3] + "..."


def format_tool_result(result, raw: bool = False) -> str:
    """Format a tool call result for display.
    
    Args:
        result: The result object from the tool call
        raw: Whether to output the raw JSON result
        
    Returns:
        Formatted string representation of the result
    """
    if raw:
        return json.dumps(result.model_dump() if hasattr(result, 'model_dump') else result, indent=2)
    
    # Process different result types
    if not result:
        return "No result returned"
    
    if hasattr(result, 'isError') and result.isError:
        return f"Error: {result.message}"
    
    if hasattr(result, 'content') and result.content:
        output_parts = []
        for item in result.content:
            if hasattr(item, 'type') and item.type == 'text' and hasattr(item, 'text'):
                output_parts.append(item.text)
            elif hasattr(item, 'type') and item.type == 'image':
                output_parts.append("[IMAGE CONTENT]")
            elif hasattr(item, 'type') and item.type == 'embedded_resource':
                output_parts.append(f"[RESOURCE: {getattr(item, 'resourceId', 'unknown')}]")
            else:
                output_parts.append(str(item))
        return "\n".join(output_parts)
    
    # Fallback for unknown result formats
    return str(result)


def extract_parameters(schema: dict) -> list[dict]:
    """Extract parameter information from a JSON schema.
    
    Args:
        schema: JSON schema object to extract parameters from
        
    Returns:
        List of parameter dictionaries with name, type, required, description
    """
    parameters = []
    if not schema or not isinstance(schema, dict):
        return parameters
        
    props = schema.get("properties", {})
    required = schema.get("required", [])
    
    for name, prop in props.items():
        param_type = prop.get("type", "any")
        is_required = name in required
        description = prop.get("description", "")
        
        parameters.append({
            "name": name,
            "type": param_type,
            "required": is_required,
            "description": description
        })
    
    return parameters


def format_tools_as_json(server_tools: dict) -> dict:
    """Convert server tools mapping to a JSON-friendly format.
    
    Args:
        server_tools: Dictionary mapping server names to tools
        
    Returns:
        Dictionary suitable for JSON serialization
    """
    json_result = {}
    
    for server_name, tools in server_tools.items():
        json_result[server_name] = []
        
        for tool in tools:
            # Extract basic info
            tool_info = {
                "name": tool.name,
                "description": getattr(tool, "description", "")
            }
            
            # Extract parameter information if available
            if hasattr(tool, 'inputSchema') and tool.inputSchema:
                parameters = extract_parameters(tool.inputSchema)
                if parameters:
                    tool_info["parameters"] = parameters
                    
            json_result[server_name].append(tool_info)
            
    return json_result