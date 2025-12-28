"""MCP Tools for simple-mcp-server.

This module defines the MCP tools (echo, ping) that are exposed to clients.
For ros-mcp-server merge, replace these with ROS-specific tools.
"""

import logging
import sys

from fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Debug: Print logger info at import time
print(f"[DEBUG] tools.py imported, logger={logger.name}, effective_level={logger.getEffectiveLevel()}", file=sys.stderr, flush=True)

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
    print(f"[DEBUG] echo tool function called with: {message}", file=sys.stderr, flush=True)
    logger.info(f"[TOOL] echo invoked, message length: {len(message)}")
    return f"Echo: {message}"


@mcp.tool()
def ping() -> str:
    """Simple ping tool to test connectivity.

    Returns:
        A pong response
    """
    print("[DEBUG] ping tool function called", file=sys.stderr, flush=True)
    logger.info("[TOOL] ping invoked")
    return "pong from Mok's computer"
