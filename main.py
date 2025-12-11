import os
import jwt
import secrets
import hashlib
import base64
import time
from typing import Any
from urllib.parse import urlencode

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from starlette.responses import Response

load_dotenv()

# Environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
SERVER_URL = os.getenv("SERVER_URL", "https://simplemcpserver-production-e610.up.railway.app")
JWT_SECRET = os.getenv("JWT_SECRET", SUPABASE_JWT_SECRET or secrets.token_hex(32))

# In-memory stores (use Redis/DB in production)
registered_clients: dict[str, dict] = {}
authorization_codes: dict[str, dict] = {}
access_tokens: dict[str, dict] = {}

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
    description="A minimal MCP server with echo functionality and OAuth 2.1",
    version="1.0.0",
)

# SSE transport for MCP
sse_transport = SseServerTransport("/messages")


# ============== OAuth 2.1 Endpoints ==============

@app.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource():
    """OAuth 2.0 Protected Resource Metadata (RFC 9728)."""
    return {
        "resource": SERVER_URL,
        "authorization_servers": [SERVER_URL],
        "scopes_supported": ["mcp:tools", "mcp:read"],
        "bearer_methods_supported": ["header"],
        "resource_documentation": f"{SERVER_URL}/docs"
    }


@app.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server():
    """OAuth 2.0 Authorization Server Metadata (RFC 8414)."""
    return {
        "issuer": SERVER_URL,
        "authorization_endpoint": f"{SERVER_URL}/authorize",
        "token_endpoint": f"{SERVER_URL}/token",
        "registration_endpoint": f"{SERVER_URL}/register",
        "scopes_supported": ["mcp:tools", "mcp:read"],
        "response_types_supported": ["code"],
        "response_modes_supported": ["query"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["none", "client_secret_post"],
        "code_challenge_methods_supported": ["S256"],
        "service_documentation": f"{SERVER_URL}/docs"
    }


@app.post("/register")
async def register_client(request: Request):
    """OAuth 2.0 Dynamic Client Registration (RFC 7591)."""
    try:
        data = await request.json()
    except:
        data = {}

    client_id = secrets.token_urlsafe(24)
    client_secret = secrets.token_urlsafe(32)

    client_info = {
        "client_id": client_id,
        "client_secret": client_secret,
        "client_name": data.get("client_name", "MCP Client"),
        "redirect_uris": data.get("redirect_uris", ["https://chatgpt.com/connector_platform_oauth_redirect"]),
        "grant_types": data.get("grant_types", ["authorization_code", "refresh_token"]),
        "response_types": data.get("response_types", ["code"]),
        "token_endpoint_auth_method": data.get("token_endpoint_auth_method", "none"),
        "created_at": int(time.time())
    }

    registered_clients[client_id] = client_info

    return JSONResponse({
        "client_id": client_id,
        "client_secret": client_secret,
        "client_name": client_info["client_name"],
        "redirect_uris": client_info["redirect_uris"],
        "grant_types": client_info["grant_types"],
        "response_types": client_info["response_types"],
        "token_endpoint_auth_method": client_info["token_endpoint_auth_method"]
    }, status_code=201)


@app.get("/authorize")
async def authorize(
    request: Request,
    response_type: str = "code",
    client_id: str = "",
    redirect_uri: str = "",
    scope: str = "mcp:tools",
    state: str = "",
    code_challenge: str = "",
    code_challenge_method: str = "S256"
):
    """OAuth 2.0 Authorization Endpoint."""
    # For this simple implementation, auto-approve
    # In production, show a login/consent page

    if response_type != "code":
        return JSONResponse({"error": "unsupported_response_type"}, status_code=400)

    # Generate authorization code
    auth_code = secrets.token_urlsafe(32)

    authorization_codes[auth_code] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "created_at": int(time.time()),
        "expires_at": int(time.time()) + 600  # 10 minutes
    }

    # Redirect back with code
    params = {"code": auth_code}
    if state:
        params["state"] = state

    redirect_url = f"{redirect_uri}?{urlencode(params)}"
    return RedirectResponse(url=redirect_url, status_code=302)


@app.post("/token")
async def token(
    request: Request,
    grant_type: str = Form(None),
    code: str = Form(None),
    redirect_uri: str = Form(None),
    client_id: str = Form(None),
    client_secret: str = Form(None),
    code_verifier: str = Form(None),
    refresh_token: str = Form(None)
):
    """OAuth 2.0 Token Endpoint."""
    # Handle form data or JSON
    if grant_type is None:
        try:
            data = await request.json()
            grant_type = data.get("grant_type")
            code = data.get("code")
            redirect_uri = data.get("redirect_uri")
            client_id = data.get("client_id")
            client_secret = data.get("client_secret")
            code_verifier = data.get("code_verifier")
            refresh_token = data.get("refresh_token")
        except:
            return JSONResponse({"error": "invalid_request"}, status_code=400)

    if grant_type == "authorization_code":
        if not code or code not in authorization_codes:
            return JSONResponse({"error": "invalid_grant"}, status_code=400)

        auth_data = authorization_codes[code]

        # Check expiration
        if time.time() > auth_data["expires_at"]:
            del authorization_codes[code]
            return JSONResponse({"error": "invalid_grant", "error_description": "Code expired"}, status_code=400)

        # Verify PKCE
        if auth_data.get("code_challenge") and code_verifier:
            expected = base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode()).digest()
            ).rstrip(b"=").decode()

            if expected != auth_data["code_challenge"]:
                return JSONResponse({"error": "invalid_grant", "error_description": "PKCE verification failed"}, status_code=400)

        # Generate tokens
        access_token = secrets.token_urlsafe(32)
        new_refresh_token = secrets.token_urlsafe(32)
        expires_in = 3600  # 1 hour

        access_tokens[access_token] = {
            "client_id": client_id,
            "scope": auth_data["scope"],
            "created_at": int(time.time()),
            "expires_at": int(time.time()) + expires_in
        }

        # Clean up used code
        del authorization_codes[code]

        return JSONResponse({
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": expires_in,
            "refresh_token": new_refresh_token,
            "scope": auth_data["scope"]
        })

    elif grant_type == "refresh_token":
        # Simple refresh - generate new tokens
        access_token = secrets.token_urlsafe(32)
        new_refresh_token = secrets.token_urlsafe(32)
        expires_in = 3600

        access_tokens[access_token] = {
            "client_id": client_id,
            "scope": "mcp:tools",
            "created_at": int(time.time()),
            "expires_at": int(time.time()) + expires_in
        }

        return JSONResponse({
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": expires_in,
            "refresh_token": new_refresh_token,
            "scope": "mcp:tools"
        })

    return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)


def verify_access_token(token: str) -> dict[str, Any]:
    """Verify an access token."""
    if token in access_tokens:
        token_data = access_tokens[token]
        if time.time() < token_data["expires_at"]:
            return token_data
    raise HTTPException(status_code=401, detail="Invalid or expired token")


# ============== MCP Endpoints ==============

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
        "oauth": {
            "protected_resource": f"{SERVER_URL}/.well-known/oauth-protected-resource",
            "authorization_server": f"{SERVER_URL}/.well-known/oauth-authorization-server"
        }
    }


@app.get("/sse")
async def sse_endpoint(request: Request) -> Response:
    """SSE endpoint for MCP client connections."""
    # Verify auth token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            verify_access_token(token)
        except HTTPException:
            pass  # Allow unauthenticated for development

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
