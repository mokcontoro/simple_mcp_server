"""Local MCP server - runs on user's machine, NOT on Railway.

This server:
- Exposes MCP tools (echo, ping)
- Validates tokens using Supabase
- Is accessed via Cloudflare tunnel
- Does NOT include auth pages (those are on Railway)
"""
import os
import time
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from starlette.responses import Response
from supabase import create_client, Client

from config import load_config

load_dotenv()

# Environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

# Initialize Supabase client for token validation
supabase: Client = None
if SUPABASE_URL and SUPABASE_ANON_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# Load local config (from CLI login)
local_config = load_config()

# Create MCP server
mcp = FastMCP("Simple MCP Server")


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
        A pong response with owner info
    """
    owner = local_config.email or "unknown"
    return f"pong from {owner}'s MCP server"


# Create FastAPI app
app = FastAPI(
    title="Simple MCP Server (Local)",
    description="Local MCP server with OAuth 2.1 support",
    version="1.1.0",
)

# Add CORS middleware for browser-based MCP clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SSE transport for MCP
sse_transport = SseServerTransport("/message")


def get_server_url() -> str:
    """Get the server URL (Cloudflare tunnel or local)."""
    # Try environment variable first
    url = os.getenv("SERVER_URL", "")
    if url:
        return url
    # Fallback to local
    return "http://localhost:8000"


def verify_token(token: str) -> dict[str, Any]:
    """Verify an access token and check authorization.

    For local server, we validate tokens directly with Supabase,
    then verify the user is authorized to access this server.
    """
    # Get server creator's user_id for authorization check
    creator_user_id = local_config.user_id
    print(f"[AUTH] Creator user_id from config: {creator_user_id}", flush=True)

    if not supabase:
        # If Supabase not configured, accept local user's token only
        print("[AUTH] Supabase not configured, checking local token", flush=True)
        if local_config.is_valid() and token == local_config.access_token:
            return {
                "user_id": local_config.user_id,
                "email": local_config.email,
                "scope": "mcp:tools"
            }
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        # Validate JWT with Supabase
        user = supabase.auth.get_user(token)
        if user and user.user:
            print(f"[AUTH] Connecting user_id: {user.user.id}", flush=True)
            print(f"[AUTH] Connecting email: {user.user.email}", flush=True)
            # Authorization check: is this user allowed to access this server?
            if creator_user_id and user.user.id != creator_user_id:
                print(f"[AUTH] DENIED: {user.user.id} != {creator_user_id}", flush=True)
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied: not authorized for this server (your id: {user.user.id[:8]}...)"
                )
            print(f"[AUTH] ALLOWED: user authorized", flush=True)
            return {
                "user_id": user.user.id,
                "email": user.user.email,
                "scope": "mcp:tools"
            }
    except HTTPException:
        raise  # Re-raise 403 errors
    except Exception as e:
        print(f"[AUTH] Exception: {e}", flush=True)
        pass

    raise HTTPException(status_code=401, detail="Invalid or expired token")


def unauthorized_response(error_description: str) -> JSONResponse:
    """Return 401 with WWW-Authenticate header (RFC 9728)."""
    server_url = get_server_url()
    return JSONResponse(
        {"error": "unauthorized", "error_description": error_description},
        status_code=401,
        headers={
            "WWW-Authenticate": f'Bearer resource_metadata="{server_url}/.well-known/oauth-protected-resource"'
        }
    )


def forbidden_response(error_description: str) -> JSONResponse:
    """Return 403 Forbidden response for unauthorized access."""
    return JSONResponse(
        {"error": "forbidden", "error_description": error_description},
        status_code=403
    )


# ============== OAuth 2.0 Discovery Endpoints ==============

@app.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource():
    """OAuth 2.0 Protected Resource Metadata (RFC 9728).

    Points to Railway for authorization (Supabase auth).
    """
    server_url = get_server_url()
    # Authorization happens via Railway/Supabase
    auth_server = os.getenv("AUTH_SERVER_URL", "https://simplemcpserver-production-e610.up.railway.app")

    return {
        "resource": server_url,
        "authorization_servers": [auth_server],
        "scopes_supported": ["mcp:tools", "mcp:read"],
        "bearer_methods_supported": ["header"],
        "resource_documentation": f"{server_url}/docs"
    }


# ============== MCP Endpoints ==============

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "simple-mcp-server",
        "user": local_config.email or "not configured"
    }


@app.get("/")
async def root():
    """Root endpoint with server info."""
    server_url = get_server_url()
    auth_server = os.getenv("AUTH_SERVER_URL", "https://simplemcpserver-production-e610.up.railway.app")

    return {
        "name": "Simple MCP Server",
        "version": "1.0.0",
        "user": local_config.email,
        "mcp_endpoint": "/sse",
        "tools": ["echo", "ping"],
        "oauth": {
            "protected_resource": f"{server_url}/.well-known/oauth-protected-resource",
            "authorization_server": f"{auth_server}/.well-known/oauth-authorization-server"
        }
    }


@app.get("/sse")
async def sse_endpoint(request: Request) -> Response:
    """SSE endpoint for MCP client connections."""
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return unauthorized_response("Missing or invalid Authorization header")

    token = auth_header[7:]

    try:
        verify_token(token)
    except HTTPException as e:
        if e.status_code == 403:
            return forbidden_response(e.detail)
        return unauthorized_response("Invalid or expired token")

    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await mcp._mcp_server.run(
            streams[0], streams[1], mcp._mcp_server.create_initialization_options()
        )

    return Response()


@app.post("/message")
async def message_endpoint(request: Request) -> Response:
    """Handle MCP messages via POST."""
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return unauthorized_response("Missing or invalid Authorization header")

    token = auth_header[7:]

    try:
        verify_token(token)
    except HTTPException as e:
        if e.status_code == 403:
            return forbidden_response(e.detail)
        return unauthorized_response("Invalid or expired token")

    return await sse_transport.handle_post_message(
        request.scope, request.receive, request._send
    )


# Alternative paths for compatibility
@app.get("/mcp/sse")
async def mcp_sse_endpoint(request: Request) -> Response:
    """SSE endpoint (alternative path)."""
    return await sse_endpoint(request)


@app.post("/mcp/message")
async def mcp_message_endpoint(request: Request) -> Response:
    """MCP message endpoint (alternative path)."""
    return await message_endpoint(request)
