"""MCP Server - Runs on Local Computer.

This server runs on the user's machine (local computer or robot).
It handles:
- MCP tools (echo, ping)
- MCP protocol endpoints via Streamable HTTP (/mcp)
- OAuth flow for MCP clients (/authorize, /login, /token)
- Legacy SSE endpoints for backward compatibility (/sse, /message)

MCP clients (ChatGPT, Claude, etc.) connect directly to this server
via Cloudflare tunnel. Railway is NOT involved in MCP traffic.
"""
import os
import secrets
import hashlib
import base64
import time
import logging
import sys
from pathlib import Path
from urllib.parse import urlencode

# Configure logging to stderr with immediate flush
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware import Middleware
from supabase import create_client, Client

from config import load_config

# Load environment: .env (local override) or .env.public (bundled defaults)
_env_file = Path(".env")
if _env_file.exists():
    load_dotenv(_env_file)
else:
    # Load bundled .env.public from package directory
    _package_dir = Path(__file__).parent
    _public_env = _package_dir / ".env.public"
    if _public_env.exists():
        load_dotenv(_public_env)

# Environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

# Transport configuration (aligned with ros-mcp-server)
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "streamable-http")
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8000"))

# Initialize Supabase client
supabase: Client = None
if SUPABASE_URL and SUPABASE_ANON_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# Load local config (server creator info from CLI login)
local_config = load_config()
logger.info(f"[STARTUP] Config loaded - valid: {local_config.is_valid()}, email: {local_config.email}")

# SERVER_URL: Use tunnel URL if available (for local MCP server), otherwise fallback to env/default
# This is critical for OAuth - MCP clients need to authenticate on THIS server, not Railway
SERVER_URL = local_config.tunnel_url or os.getenv("SERVER_URL", "https://simplemcpserver-production-e610.up.railway.app")
logger.info(f"[STARTUP] SERVER_URL: {SERVER_URL}")

# In-memory stores (use Redis/DB in production)
registered_clients: dict[str, dict] = {}
authorization_codes: dict[str, dict] = {}
access_tokens: dict[str, dict] = {}
pending_authorizations: dict[str, dict] = {}  # session_id -> oauth params
authenticated_sessions: dict[str, dict] = {}  # session_id -> user info

# ============== FastMCP Server (aligned with ros-mcp-server) ==============
# MCP tools imported from tools.py - easily replaceable for ros-mcp-server merge
from tools import mcp


# ============== OAuth Authentication Middleware for MCP ==============

class MCPOAuthMiddleware(BaseHTTPMiddleware):
    """Middleware to validate OAuth Bearer tokens for Streamable HTTP MCP endpoint."""

    async def dispatch(self, request: Request, call_next):
        # Check Bearer token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            logger.debug(f"[MCP] No Bearer token in request")
            return JSONResponse(
                {"error": "unauthorized", "error_description": "Missing or invalid Authorization header"},
                status_code=401,
                headers={"WWW-Authenticate": f'Bearer resource_metadata="{SERVER_URL}/.well-known/oauth-protected-resource"'}
            )

        token = auth_header[7:]
        token_data = access_tokens.get(token)

        if not token_data or time.time() >= token_data.get("expires_at", 0):
            logger.debug(f"[MCP] Invalid or expired token")
            return JSONResponse(
                {"error": "unauthorized", "error_description": "Invalid or expired token"},
                status_code=401,
                headers={"WWW-Authenticate": f'Bearer resource_metadata="{SERVER_URL}/.well-known/oauth-protected-resource"'}
            )

        # Check authorization (creator-only access)
        creator_user_id = local_config.user_id
        connecting_user_id = token_data.get("user_id")

        if creator_user_id and connecting_user_id != creator_user_id:
            logger.warning(f"[MCP] Access denied: user {connecting_user_id} is not the server creator")
            return JSONResponse(
                {"error": "forbidden", "error_description": "Access denied: not authorized for this server"},
                status_code=403
            )

        logger.debug(f"[MCP] Authorized: {token_data.get('user_email')}")
        return await call_next(request)


# ============== Streamable HTTP MCP App ==============
# Create FastMCP app with OAuth middleware BEFORE FastAPI app
# (We need the lifespan from mcp_http_app for FastAPI)
mcp_http_app = mcp.http_app(
    path="/",  # Route at root of mounted app
    transport="streamable-http",
    middleware=[Middleware(MCPOAuthMiddleware)]
)

# ============== FastAPI App with OAuth ==============
# Pass MCP app's lifespan to FastAPI for proper initialization
app = FastAPI(
    title="Simple MCP Server",
    description="A minimal MCP server with echo functionality and OAuth 2.1",
    version="2.0.0",
    lifespan=mcp_http_app.lifespan,  # Required for FastMCP task group initialization
)

# Add CORS middleware for browser-based MCP client access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount MCP app at /mcp
app.mount("/mcp", mcp_http_app)


# ============== HTML Templates ==============
# Imported from oauth/templates.py to reduce duplication
from oauth.templates import LOGIN_PAGE, SIGNUP_PAGE, CONSENT_PAGE


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
    """OAuth 2.0 Authorization Endpoint - redirects to login."""
    if response_type != "code":
        return JSONResponse({"error": "unsupported_response_type"}, status_code=400)

    # Generate session ID and store OAuth params
    session_id = secrets.token_urlsafe(32)
    pending_authorizations[session_id] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "created_at": int(time.time()),
        "expires_at": int(time.time()) + 600  # 10 minutes
    }

    # Redirect to login page
    return RedirectResponse(url=f"/login?session={session_id}", status_code=302)


@app.get("/login")
async def login_page(session: str = "", registered: str = ""):
    """Show login form."""
    if not session or session not in pending_authorizations:
        return HTMLResponse("<h1>Invalid or expired session</h1>", status_code=400)

    # Check if session expired
    auth_data = pending_authorizations[session]
    if time.time() > auth_data["expires_at"]:
        del pending_authorizations[session]
        return HTMLResponse("<h1>Session expired. Please try again.</h1>", status_code=400)

    # Show success message if user just registered
    success_msg = ""
    if registered == "1":
        success_msg = '<div class="success">Account created successfully! Please sign in.</div>'

    return HTMLResponse(LOGIN_PAGE.format(session=session, error="", success=success_msg))


@app.post("/login")
async def login_submit(
    session: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    """Handle login form submission."""
    if not session or session not in pending_authorizations:
        return HTMLResponse("<h1>Invalid or expired session</h1>", status_code=400)

    auth_data = pending_authorizations[session]
    if time.time() > auth_data["expires_at"]:
        del pending_authorizations[session]
        return HTMLResponse("<h1>Session expired. Please try again.</h1>", status_code=400)

    # Authenticate with Supabase
    if not supabase:
        # Fallback: accept any login if Supabase not configured
        authenticated_sessions[session] = {"email": email, "user_id": "demo-user"}
        return RedirectResponse(url=f"/consent?session={session}", status_code=302)

    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if response.user:
            logger.info(f"[LOGIN] User authenticated: {response.user.email}")
            authenticated_sessions[session] = {
                "email": response.user.email,
                "user_id": response.user.id
            }
            return RedirectResponse(url=f"/consent?session={session}", status_code=302)
        else:
            error_html = '<div class="error">Invalid email or password</div>'
            return HTMLResponse(LOGIN_PAGE.format(session=session, error=error_html, success=""))
    except Exception as e:
        error_html = f'<div class="error">Authentication failed: {str(e)}</div>'
        return HTMLResponse(LOGIN_PAGE.format(session=session, error=error_html, success=""))


@app.get("/signup")
async def signup_page(session: str = ""):
    """Show signup form."""
    if not session or session not in pending_authorizations:
        return HTMLResponse("<h1>Invalid or expired session</h1>", status_code=400)

    # Check if session expired
    auth_data = pending_authorizations[session]
    if time.time() > auth_data["expires_at"]:
        del pending_authorizations[session]
        return HTMLResponse("<h1>Session expired. Please try again.</h1>", status_code=400)

    return HTMLResponse(SIGNUP_PAGE.format(session=session, error=""))


@app.post("/signup")
async def signup_submit(
    session: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...)
):
    """Handle signup form submission."""
    if not session or session not in pending_authorizations:
        return HTMLResponse("<h1>Invalid or expired session</h1>", status_code=400)

    auth_data = pending_authorizations[session]
    if time.time() > auth_data["expires_at"]:
        del pending_authorizations[session]
        return HTMLResponse("<h1>Session expired. Please try again.</h1>", status_code=400)

    # Validate passwords match
    if password != confirm_password:
        error_html = '<div class="error">Passwords do not match</div>'
        return HTMLResponse(SIGNUP_PAGE.format(session=session, error=error_html))

    # Validate password length
    if len(password) < 6:
        error_html = '<div class="error">Password must be at least 6 characters</div>'
        return HTMLResponse(SIGNUP_PAGE.format(session=session, error=error_html))

    # Create account with Supabase
    if not supabase:
        # Fallback: just redirect to login if Supabase not configured
        return RedirectResponse(url=f"/login?session={session}&registered=1", status_code=302)

    try:
        response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })

        if response.user:
            return RedirectResponse(url=f"/login?session={session}&registered=1", status_code=302)
        else:
            error_html = '<div class="error">Failed to create account</div>'
            return HTMLResponse(SIGNUP_PAGE.format(session=session, error=error_html))
    except Exception as e:
        error_msg = str(e)
        if "already registered" in error_msg.lower():
            error_html = '<div class="error">An account with this email already exists</div>'
        else:
            error_html = f'<div class="error">Signup failed: {error_msg}</div>'
        return HTMLResponse(SIGNUP_PAGE.format(session=session, error=error_html))


@app.get("/consent")
async def consent_page(session: str = ""):
    """Show consent/authorization page."""
    if not session or session not in pending_authorizations:
        return HTMLResponse("<h1>Invalid or expired session</h1>", status_code=400)

    if session not in authenticated_sessions:
        return RedirectResponse(url=f"/login?session={session}", status_code=302)

    user_info = authenticated_sessions[session]
    return HTMLResponse(CONSENT_PAGE.format(
        session=session,
        user_email=user_info.get("email", "Unknown")
    ))


@app.post("/consent")
async def consent_submit(
    session: str = Form(...),
    action: str = Form(...)
):
    """Handle consent form submission."""
    if not session or session not in pending_authorizations:
        return HTMLResponse("<h1>Invalid or expired session</h1>", status_code=400)

    auth_data = pending_authorizations[session]
    redirect_uri = auth_data["redirect_uri"]
    state = auth_data.get("state", "")

    if action == "deny":
        # User denied access
        del pending_authorizations[session]
        if session in authenticated_sessions:
            del authenticated_sessions[session]

        params = {"error": "access_denied", "error_description": "User denied access"}
        if state:
            params["state"] = state
        return RedirectResponse(url=f"{redirect_uri}?{urlencode(params)}", status_code=302)

    # User approved - generate authorization code
    auth_code = secrets.token_urlsafe(32)
    user_info = authenticated_sessions.get(session, {})

    authorization_codes[auth_code] = {
        "client_id": auth_data["client_id"],
        "redirect_uri": auth_data["redirect_uri"],
        "scope": auth_data["scope"],
        "code_challenge": auth_data["code_challenge"],
        "code_challenge_method": auth_data["code_challenge_method"],
        "user_id": user_info.get("user_id"),
        "user_email": user_info.get("email"),
        "created_at": int(time.time()),
        "expires_at": int(time.time()) + 600  # 10 minutes
    }

    # Clean up session data
    del pending_authorizations[session]
    if session in authenticated_sessions:
        del authenticated_sessions[session]

    # Redirect back with code
    params = {"code": auth_code}
    if state:
        params["state"] = state
    return RedirectResponse(url=f"{redirect_uri}?{urlencode(params)}", status_code=302)


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

    logger.debug(f"[TOKEN] grant_type: {grant_type}, client_id: {client_id}")

    if grant_type == "authorization_code":
        if not code or code not in authorization_codes:
            logger.debug(f"[TOKEN] Invalid authorization code")
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
            "user_id": auth_data.get("user_id"),
            "user_email": auth_data.get("user_email"),
            "created_at": int(time.time()),
            "expires_at": int(time.time()) + expires_in
        }
        logger.info(f"[TOKEN] Access token created for user: {auth_data.get('user_email')}")

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


# ============== Server Info Endpoints ==============

@app.get("/health")
async def health_check():
    """Health check endpoint for Railway."""
    return {"status": "healthy", "service": "mcp-server", "transport": MCP_TRANSPORT}


@app.get("/")
async def root():
    """Root endpoint with server info."""
    return {
        "name": "Simple MCP Server",
        "version": "2.0.0",
        "transport": MCP_TRANSPORT,
        "mcp_endpoint": "/mcp",
        "legacy_sse_endpoint": "/sse",
        "tools": ["echo", "ping"],
        "oauth": {
            "protected_resource": f"{SERVER_URL}/.well-known/oauth-protected-resource",
            "authorization_server": f"{SERVER_URL}/.well-known/oauth-authorization-server"
        }
    }


# ============== Legacy SSE Endpoints (backward compatibility) ==============
# These endpoints maintain compatibility with older MCP clients that use SSE transport

from mcp.server.sse import SseServerTransport

sse_transport = SseServerTransport("/message")


def unauthorized_response(error_description: str) -> JSONResponse:
    """Return 401 with WWW-Authenticate header pointing to resource metadata (RFC 9728)."""
    return JSONResponse(
        {"error": "unauthorized", "error_description": error_description},
        status_code=401,
        headers={
            "WWW-Authenticate": f'Bearer resource_metadata="{SERVER_URL}/.well-known/oauth-protected-resource"'
        }
    )


def forbidden_response(error_description: str) -> JSONResponse:
    """Return 403 Forbidden response for unauthorized access."""
    return JSONResponse(
        {"error": "forbidden", "error_description": error_description},
        status_code=403
    )


def check_authorization(token_data: dict) -> bool:
    """Check if the token belongs to an authorized user (creator-only access)."""
    creator_user_id = local_config.user_id
    connecting_user_id = token_data.get("user_id")

    if not creator_user_id:
        logger.debug("[SSE] No creator configured, allowing access")
        return True

    if connecting_user_id != creator_user_id:
        logger.warning(f"[SSE] Access denied: user {connecting_user_id} is not the server creator")
        raise HTTPException(
            status_code=403,
            detail="Access denied: not authorized for this server"
        )

    return True


@app.get("/sse")
async def sse_endpoint(request: Request) -> Response:
    """Legacy SSE endpoint for MCP client connections (backward compatibility)."""
    logger.debug("[SSE] Legacy SSE endpoint hit")
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return unauthorized_response("Missing or invalid Authorization header")

    token = auth_header[7:]
    token_data = access_tokens.get(token)

    if not token_data or time.time() >= token_data.get("expires_at", 0):
        return unauthorized_response("Invalid or expired token")

    try:
        check_authorization(token_data)
    except HTTPException as e:
        return forbidden_response(e.detail)

    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await mcp._mcp_server.run(
            streams[0], streams[1], mcp._mcp_server.create_initialization_options()
        )

    return Response()


@app.post("/message")
async def message_endpoint(request: Request) -> Response:
    """Legacy message endpoint for SSE transport (backward compatibility)."""
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return unauthorized_response("Missing or invalid Authorization header")

    token = auth_header[7:]
    token_data = access_tokens.get(token)

    if not token_data or time.time() >= token_data.get("expires_at", 0):
        return unauthorized_response("Invalid or expired token")

    try:
        check_authorization(token_data)
    except HTTPException as e:
        return forbidden_response(e.detail)

    await sse_transport.handle_post_message(
        request.scope, request.receive, request._send
    )
    return Response()


# ============== CLI Login Endpoints (for Railway) ==============
# CLI login templates imported from oauth/templates.py
from oauth.templates import CLI_LOGIN_PAGE, CLI_SIGNUP_PAGE

cli_sessions: dict[str, dict] = {}


@app.get("/cli-login")
async def cli_login_page(session: str = "", port: str = ""):
    """Show CLI login form (used by installer)."""
    if not session or not port:
        return HTMLResponse("<h1>Invalid request. Missing session or port.</h1>", status_code=400)

    cli_sessions[session] = {
        "port": port,
        "created_at": int(time.time()),
        "expires_at": int(time.time()) + 600
    }

    return HTMLResponse(CLI_LOGIN_PAGE.format(session=session, port=port, error=""))


@app.post("/cli-login")
async def cli_login_submit(
    session: str = Form(...),
    port: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    """Handle CLI login form submission."""
    if not session or session not in cli_sessions:
        return HTMLResponse("<h1>Invalid or expired session</h1>", status_code=400)

    cli_data = cli_sessions[session]
    if time.time() > cli_data["expires_at"]:
        del cli_sessions[session]
        return HTMLResponse("<h1>Session expired. Please try again.</h1>", status_code=400)

    user_id = None
    access_token = None
    refresh_token = None

    if not supabase:
        user_id = "demo-user"
        access_token = "demo-token"
    else:
        try:
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            if response.user and response.session:
                user_id = response.user.id
                access_token = response.session.access_token
                refresh_token = response.session.refresh_token
            else:
                error_html = '<div class="error">Invalid email or password</div>'
                return HTMLResponse(CLI_LOGIN_PAGE.format(session=session, port=port, error=error_html))
        except Exception as e:
            error_html = f'<div class="error">Authentication failed: {str(e)}</div>'
            return HTMLResponse(CLI_LOGIN_PAGE.format(session=session, port=port, error=error_html))

    del cli_sessions[session]

    callback_params = urlencode({
        "user_id": user_id,
        "email": email,
        "access_token": access_token,
        "refresh_token": refresh_token or "",
    })
    callback_url = f"http://127.0.0.1:{port}/callback?{callback_params}"

    return RedirectResponse(url=callback_url, status_code=302)


@app.get("/cli-signup")
async def cli_signup_page(session: str = "", port: str = ""):
    """Show CLI signup form (used by installer)."""
    if not session or not port:
        return HTMLResponse("<h1>Invalid request. Missing session or port.</h1>", status_code=400)

    cli_sessions[session] = {
        "port": port,
        "created_at": int(time.time()),
        "expires_at": int(time.time()) + 600
    }

    return HTMLResponse(CLI_SIGNUP_PAGE.format(session=session, port=port, error=""))


@app.post("/cli-signup")
async def cli_signup_submit(
    session: str = Form(...),
    port: str = Form(...),
    name: str = Form(...),
    organization: str = Form(""),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...)
):
    """Handle CLI signup form submission."""
    if not session or session not in cli_sessions:
        return HTMLResponse("<h1>Invalid or expired session</h1>", status_code=400)

    cli_data = cli_sessions[session]
    if time.time() > cli_data["expires_at"]:
        del cli_sessions[session]
        return HTMLResponse("<h1>Session expired. Please try again.</h1>", status_code=400)

    if not name.strip():
        error_html = '<div class="error">Name is required</div>'
        return HTMLResponse(CLI_SIGNUP_PAGE.format(session=session, port=port, error=error_html))

    if password != confirm_password:
        error_html = '<div class="error">Passwords do not match</div>'
        return HTMLResponse(CLI_SIGNUP_PAGE.format(session=session, port=port, error=error_html))

    if len(password) < 6:
        error_html = '<div class="error">Password must be at least 6 characters</div>'
        return HTMLResponse(CLI_SIGNUP_PAGE.format(session=session, port=port, error=error_html))

    if not supabase:
        return RedirectResponse(url=f"/cli-login?session={session}&port={port}", status_code=302)

    try:
        user_metadata = {"name": name.strip()}
        if organization.strip():
            user_metadata["organization"] = organization.strip()

        response = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": user_metadata
            }
        })

        if response.user:
            return RedirectResponse(url=f"/cli-login?session={session}&port={port}", status_code=302)
        else:
            error_html = '<div class="error">Failed to create account</div>'
            return HTMLResponse(CLI_SIGNUP_PAGE.format(session=session, port=port, error=error_html))
    except Exception as e:
        error_msg = str(e)
        if "already registered" in error_msg.lower():
            error_html = '<div class="error">An account with this email already exists</div>'
        else:
            error_html = f'<div class="error">Signup failed: {error_msg}</div>'
        return HTMLResponse(CLI_SIGNUP_PAGE.format(session=session, port=port, error=error_html))


# ============== Main Entry Point ==============

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting MCP server with transport: {MCP_TRANSPORT}")
    logger.info(f"Streamable HTTP endpoint: /mcp")
    logger.info(f"Legacy SSE endpoint: /sse")
    uvicorn.run(app, host=MCP_HOST, port=MCP_PORT)
