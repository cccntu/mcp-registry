"""Interactive parameter collection utilities for MCP tools."""

import json
import sys
import click
import asyncio

from mcp_registry.compound import MCPAggregator


async def collect_parameters_interactively(tool_path: str, server_name: str, 
                                          tool_name: str, aggregator: MCPAggregator):
    """Interactively collect parameters for the tool from the user.
    
    Args:
        tool_path: Full tool path in format server__tool
        server_name: Name of the server
        tool_name: Name of the tool
        aggregator: MCPAggregator instance to use for schema retrieval
    
    Returns:
        Dictionary of collected parameters
    
    Exits:
        On user cancellation or inability to get tool schema
    """
    click.echo(f"Interactive mode for tool: {tool_path}")
    
    # Helper function to get tool schema
    async def get_schema():
        try:
            server_tools = await aggregator.list_tools(return_server_mapping=True)
            if server_name not in server_tools:
                return None
                
            for tool in server_tools[server_name]:
                if tool.name == tool_name:
                    return getattr(tool, 'inputSchema', {})
            
            return None
        except Exception:
            return None
    
    # Get the tool schema
    schema = await get_schema()
    if not schema:
        click.echo(f"Could not retrieve schema for tool '{tool_name}'.", err=True)
        click.echo(f"The tool '{tool_name}' may not exist on server '{server_name}'.", err=True)
        click.echo("\nTo see available tools for this server, use:", err=True)
        click.echo(f"  mcp-registry list-tools {server_name}", err=True)
        if click.confirm("Continue with an empty parameter object?", default=False):
            return {}
        else:
            sys.exit(1)
        
    parameters = {}
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    
    if not properties:
        click.echo("This tool does not require any parameters.")
        return {}
        
    click.echo("Please enter values for the following parameters:")
    
    # Process each parameter in the schema
    for name, prop in properties.items():
        param_type = prop.get("type", "any")
        is_required = name in required
        description = prop.get("description", "")
        default = prop.get("default", None)
        
        # Format the prompt text
        req_text = "required" if is_required else "optional"
        default_text = f" (default: {default})" if default is not None else ""
        desc_text = f"\n  {description}" if description else ""
        prompt_text = f"{name} ({param_type}, {req_text}){default_text}{desc_text}: "
        
        # Handle different parameter types
        value = None
        
        # Boolean parameters
        if param_type == "boolean":
            if default is not None:
                default_val = "y" if default else "n"
                value = click.prompt(prompt_text, default=default_val, show_default=True)
                value = value.lower() in ("y", "yes", "true", "t", "1")
            else:
                if is_required:
                    value = click.prompt(prompt_text, type=click.BOOL)
                else:
                    value_str = click.prompt(prompt_text, default="", show_default=False)
                    if not value_str:
                        continue  # Skip optional parameter
                    value = value_str.lower() in ("y", "yes", "true", "t", "1")
        
        # Number parameters
        elif param_type == "number" or param_type == "integer":
            type_class = int if param_type == "integer" else float
            if default is not None:
                value = click.prompt(prompt_text, default=default, type=type_class, show_default=True)
            else:
                if is_required:
                    value = click.prompt(prompt_text, type=type_class)
                else:
                    value_str = click.prompt(prompt_text, default="", show_default=False)
                    if not value_str:
                        continue  # Skip optional parameter
                    try:
                        value = type_class(value_str)
                    except ValueError:
                        click.echo(f"Invalid {param_type}. Skipping parameter.")
                        continue
        
        # Object parameters
        elif param_type == "object":
            click.echo(f"  Enter a JSON object for '{name}':")
            if is_required:
                json_str = click.prompt("  JSON", default="{}")
            else:
                json_str = click.prompt("  JSON", default="")
                if not json_str:
                    continue
            
            try:
                value = json.loads(json_str)
            except json.JSONDecodeError:
                click.echo("  Invalid JSON. Using empty object.")
                value = {}
        
        # Array parameters
        elif param_type == "array":
            click.echo(f"  Enter a JSON array for '{name}':")
            if is_required:
                json_str = click.prompt("  JSON", default="[]")
            else:
                json_str = click.prompt("  JSON", default="")
                if not json_str:
                    continue
            
            try:
                value = json.loads(json_str)
            except json.JSONDecodeError:
                click.echo("  Invalid JSON. Using empty array.")
                value = []
        
        # String and other types
        else:
            if default is not None:
                value = click.prompt(prompt_text, default=default, show_default=True)
            else:
                if is_required:
                    value = click.prompt(prompt_text)
                else:
                    value = click.prompt(prompt_text, default="", show_default=False)
                    if not value:
                        continue  # Skip optional parameter
        
        # Add the parameter value
        parameters[name] = value
    
    # Show the final parameters and confirm
    click.echo("\nParameters to be sent:")
    click.echo(json.dumps(parameters, indent=2))
    if not click.confirm("Send these parameters?", default=True):
        if click.confirm("Start over?", default=False):
            return await collect_parameters_interactively(tool_path, server_name, tool_name, aggregator)
        else:
            sys.exit(0)
    
    return parameters