"""MCP Tools for simple-mcp-server.

This module defines the MCP tools (echo, ping) that are exposed to clients.
For ros-mcp-server merge, replace these with ROS-specific tools.
"""

from fastmcp import FastMCP

# Create the FastMCP server instance
mcp = FastMCP("simple-mcp-server")


@mcp.tool()
def echo(message: str) -> str:
    """Echo back the input message.

    Args:
        message: The message to echo back

    Returns:
        The echoed message with a prefix
    """
    return f"Echo: {message}"


@mcp.tool()
def ping() -> str:
    """Simple ping tool to test connectivity.

    Returns:
        A pong response
    """
    return "pong from Mok's computer"
