import os
import jwt
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from starlette.responses import Response

load_dotenv()

# Environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

# Create MCP server
mcp = FastMCP("Echo Server")


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
    return "pong"


# Create FastAPI app
app = FastAPI(
    title="Simple MCP Server",
    description="A minimal MCP server with echo functionality and Supabase OAuth",
    version="1.0.0",
)

# SSE transport for MCP
sse_transport = SseServerTransport("/messages")


def verify_token(token: str) -> dict[str, Any]:
    """Verify Supabase JWT token."""
    if not SUPABASE_JWT_SECRET:
        # If no secret configured, skip validation (for development)
        return {"sub": "anonymous"}

    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint for Railway."""
    return {"status": "healthy", "service": "mcp-echo-server"}


@app.get("/")
async def root():
    """Root endpoint with server info."""
    return {
        "name": "Simple MCP Server",
        "version": "1.0.0",
        "mcp_endpoint": "/sse",
        "tools": ["echo", "ping"],
    }


@app.get("/sse")
async def sse_endpoint(request: Request) -> Response:
    """SSE endpoint for MCP client connections."""
    # Optional: verify auth token from query param or header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            verify_token(token)
        except HTTPException:
            pass  # Allow unauthenticated for now during development

    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await mcp._mcp_server.run(
            streams[0], streams[1], mcp._mcp_server.create_initialization_options()
        )

    return Response()


@app.post("/messages")
async def messages_endpoint(request: Request) -> Response:
    """Handle MCP messages via POST."""
    return await sse_transport.handle_post_message(
        request.scope, request.receive, request._send
    )
