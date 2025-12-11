import os
import jwt
from contextlib import asynccontextmanager
from typing import AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from mcp.server.fastmcp import FastMCP
from starlette.routing import Mount

load_dotenv()

# Environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

# Security scheme
security = HTTPBearer(auto_error=False)


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Verify Supabase JWT token."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    token = credentials.credentials

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


# Mount MCP SSE endpoint
# The MCP FastMCP handles SSE transport automatically
app.mount("/mcp", mcp.sse_app())
