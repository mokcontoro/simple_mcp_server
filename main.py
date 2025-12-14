"""MCP Server - Runs on Local Computer.

This server runs on the user's machine (local computer or robot).
It handles:
- MCP tools (echo, ping)
- MCP protocol endpoints (/sse, /message)
- OAuth flow for MCP clients (/authorize, /login, /token)

MCP clients (ChatGPT, Claude, etc.) connect directly to this server
via Cloudflare tunnel. Railway is NOT involved in MCP traffic.
"""
import os
import secrets
import hashlib
import base64
import time
from typing import Any
from urllib.parse import urlencode

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from starlette.responses import Response
from supabase import create_client, Client

from config import load_config

load_dotenv()

# Environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
SERVER_URL = os.getenv("SERVER_URL", "https://simplemcpserver-production-e610.up.railway.app")
JWT_SECRET = os.getenv("JWT_SECRET", SUPABASE_JWT_SECRET or secrets.token_hex(32))

# Initialize Supabase client
supabase: Client = None
if SUPABASE_URL and SUPABASE_ANON_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# Load local config (server creator info from CLI login)
local_config = load_config()
print(f"[STARTUP] Config loaded - valid: {local_config.is_valid()}, email: {local_config.email}, user_id: {local_config.user_id}", flush=True)

# In-memory stores (use Redis/DB in production)
registered_clients: dict[str, dict] = {}
authorization_codes: dict[str, dict] = {}
access_tokens: dict[str, dict] = {}
pending_authorizations: dict[str, dict] = {}  # session_id -> oauth params
authenticated_sessions: dict[str, dict] = {}  # session_id -> user info

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
    return "pong from Mok's computer"


# Create FastAPI app
app = FastAPI(
    title="Simple MCP Server",
    description="A minimal MCP server with echo functionality and OAuth 2.1",
    version="1.1.0",
)

# Add CORS middleware for browser-based MCP client access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SSE transport for MCP
sse_transport = SseServerTransport("/message")


# ============== HTML Templates ==============

LOGIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Login - MCP Server</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
               min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0; }}
        .container {{ background: white; padding: 40px; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                     width: 100%; max-width: 400px; }}
        h1 {{ margin: 0 0 10px; color: #333; font-size: 24px; }}
        p {{ color: #666; margin: 0 0 30px; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; margin-bottom: 8px; color: #333; font-weight: 500; }}
        input[type="email"], input[type="password"] {{
            width: 100%; padding: 12px; border: 2px solid #e1e1e1; border-radius: 8px;
            font-size: 16px; box-sizing: border-box; transition: border-color 0.2s; }}
        input:focus {{ outline: none; border-color: #667eea; }}
        button {{ width: 100%; padding: 14px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                 color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600;
                 cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; }}
        button:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4); }}
        .error {{ background: #fee; color: #c00; padding: 12px; border-radius: 8px; margin-bottom: 20px; }}
        .success {{ background: #e6ffed; color: #22863a; padding: 12px; border-radius: 8px; margin-bottom: 20px; }}
        .info {{ background: #f0f4ff; color: #4a5568; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; }}
        .signup-link {{ text-align: center; margin-top: 20px; color: #666; }}
        .signup-link a {{ color: #667eea; text-decoration: none; font-weight: 500; }}
        .signup-link a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Sign In</h1>
        <p>Sign in to authorize MCP client access</p>
        {error}
        {success}
        <div class="info">MCP client is requesting access to server tools.</div>
        <form method="POST" action="/login">
            <input type="hidden" name="session" value="{session}">
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" required placeholder="your@email.com">
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required placeholder="Your password">
            </div>
            <button type="submit">Sign In</button>
        </form>
        <div class="signup-link">
            Don't have an account? <a href="/signup?session={session}">Sign up</a>
        </div>
    </div>
</body>
</html>
"""

SIGNUP_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Sign Up - MCP Server</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
               min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0; }}
        .container {{ background: white; padding: 40px; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                     width: 100%; max-width: 400px; }}
        h1 {{ margin: 0 0 10px; color: #333; font-size: 24px; }}
        p {{ color: #666; margin: 0 0 30px; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; margin-bottom: 8px; color: #333; font-weight: 500; }}
        input[type="email"], input[type="password"] {{
            width: 100%; padding: 12px; border: 2px solid #e1e1e1; border-radius: 8px;
            font-size: 16px; box-sizing: border-box; transition: border-color 0.2s; }}
        input:focus {{ outline: none; border-color: #667eea; }}
        button {{ width: 100%; padding: 14px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                 color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600;
                 cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; }}
        button:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4); }}
        .error {{ background: #fee; color: #c00; padding: 12px; border-radius: 8px; margin-bottom: 20px; }}
        .info {{ background: #f0f4ff; color: #4a5568; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; }}
        .login-link {{ text-align: center; margin-top: 20px; color: #666; }}
        .login-link a {{ color: #667eea; text-decoration: none; font-weight: 500; }}
        .login-link a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Create Account</h1>
        <p>Sign up to use MCP server</p>
        {error}
        <div class="info">Create an account to authorize MCP client access.</div>
        <form method="POST" action="/signup">
            <input type="hidden" name="session" value="{session}">
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" required placeholder="your@email.com">
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required placeholder="Create a password" minlength="6">
            </div>
            <div class="form-group">
                <label for="confirm_password">Confirm Password</label>
                <input type="password" id="confirm_password" name="confirm_password" required placeholder="Confirm your password" minlength="6">
            </div>
            <button type="submit">Create Account</button>
        </form>
        <div class="login-link">
            Already have an account? <a href="/login?session={session}">Sign in</a>
        </div>
    </div>
</body>
</html>
"""

CONSENT_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Authorize - MCP Server</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
               min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0; }}
        .container {{ background: white; padding: 40px; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                     width: 100%; max-width: 450px; }}
        h1 {{ margin: 0 0 10px; color: #333; font-size: 24px; }}
        .app-info {{ display: flex; align-items: center; gap: 15px; padding: 20px; background: #f8f9fa;
                    border-radius: 8px; margin: 20px 0; }}
        .app-icon {{ width: 50px; height: 50px; background: #10a37f; border-radius: 10px;
                    display: flex; align-items: center; justify-content: center; color: white; font-size: 24px; }}
        .app-name {{ font-weight: 600; color: #333; }}
        .scopes {{ margin: 20px 0; }}
        .scope {{ display: flex; align-items: center; gap: 10px; padding: 12px; background: #f0f4ff;
                 border-radius: 8px; margin-bottom: 10px; }}
        .scope-icon {{ color: #667eea; }}
        .user-info {{ color: #666; font-size: 14px; margin-bottom: 20px; }}
        .buttons {{ display: flex; gap: 12px; }}
        button {{ flex: 1; padding: 14px; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; }}
        .allow {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; }}
        .deny {{ background: white; color: #666; border: 2px solid #e1e1e1; }}
        .allow:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4); }}
        .deny:hover {{ background: #f5f5f5; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Authorize Access</h1>
        <div class="user-info">Logged in as: {user_email}</div>
        <div class="app-info">
            <div class="app-icon">M</div>
            <div>
                <div class="app-name">MCP Client</div>
                <div style="color: #666; font-size: 14px;">wants to access your account</div>
            </div>
        </div>
        <div class="scopes">
            <div class="scope">
                <span class="scope-icon">✓</span>
                <span>Access Echo and Ping tools</span>
            </div>
            <div class="scope">
                <span class="scope-icon">✓</span>
                <span>Read basic profile information</span>
            </div>
        </div>
        <form method="POST" action="/consent">
            <input type="hidden" name="session" value="{session}">
            <div class="buttons">
                <button type="submit" name="action" value="deny" class="deny">Deny</button>
                <button type="submit" name="action" value="allow" class="allow">Allow</button>
            </div>
        </form>
    </div>
</body>
</html>
"""


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
            "user_id": auth_data.get("user_id"),
            "user_email": auth_data.get("user_email"),
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
    """Check if the token belongs to an authorized user.

    Returns True if authorized, raises HTTPException if not.
    """
    creator_user_id = local_config.user_id
    connecting_user_id = token_data.get("user_id")

    print(f"[AUTH] ========== AUTHORIZATION CHECK ==========", flush=True)
    print(f"[AUTH] local_config.is_valid(): {local_config.is_valid()}", flush=True)
    print(f"[AUTH] local_config.email: {local_config.email}", flush=True)
    print(f"[AUTH] Creator user_id: {creator_user_id}", flush=True)
    print(f"[AUTH] Connecting user_id: {connecting_user_id}", flush=True)
    print(f"[AUTH] token_data keys: {list(token_data.keys())}", flush=True)
    print(f"[AUTH] token_data user_email: {token_data.get('user_email')}", flush=True)

    # If no creator configured, allow all authenticated users
    if not creator_user_id:
        print("[AUTH] WARNING: No creator configured, allowing access", flush=True)
        return True

    # Check if connecting user matches creator
    if connecting_user_id != creator_user_id:
        print(f"[AUTH] DENIED: {connecting_user_id} != {creator_user_id}", flush=True)
        raise HTTPException(
            status_code=403,
            detail="Access denied: not authorized for this server"
        )

    print("[AUTH] ALLOWED: user is server creator", flush=True)
    return True


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
    print(f"[SSE] ========== SSE ENDPOINT HIT ==========", flush=True)
    # Verify auth token - MCP clients need proper 401 with WWW-Authenticate header
    auth_header = request.headers.get("Authorization", "")
    print(f"[SSE] Auth header present: {bool(auth_header)}", flush=True)

    if not auth_header.startswith("Bearer "):
        print(f"[SSE] No Bearer token, returning 401", flush=True)
        return unauthorized_response("Missing or invalid Authorization header")

    token = auth_header[7:]
    print(f"[SSE] Token (first 20 chars): {token[:20]}...", flush=True)
    print(f"[SSE] Number of access_tokens in memory: {len(access_tokens)}", flush=True)

    token_data = None
    if token in access_tokens:
        token_data = access_tokens[token]
        print(f"[SSE] Token found in access_tokens", flush=True)
        if time.time() >= token_data["expires_at"]:
            print(f"[SSE] Token expired", flush=True)
            token_data = None

    if not token_data:
        print(f"[SSE] No valid token_data, returning 401", flush=True)
        return unauthorized_response("Invalid or expired token")

    print(f"[SSE] Token valid, checking authorization...", flush=True)

    # Check if user is authorized to access this server
    try:
        check_authorization(token_data)
    except HTTPException as e:
        print(f"[SSE] Authorization failed: {e.detail}", flush=True)
        return forbidden_response(e.detail)

    print(f"[SSE] Authorization passed, starting MCP session", flush=True)

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
    # Verify auth token - MCP clients need proper 401 with WWW-Authenticate header
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return unauthorized_response("Missing or invalid Authorization header")

    token = auth_header[7:]
    token_data = None
    if token in access_tokens:
        token_data = access_tokens[token]
        if time.time() >= token_data["expires_at"]:
            token_data = None

    if not token_data:
        return unauthorized_response("Invalid or expired token")

    # Check if user is authorized to access this server
    try:
        check_authorization(token_data)
    except HTTPException as e:
        return forbidden_response(e.detail)

    return await sse_transport.handle_post_message(
        request.scope, request.receive, request._send
    )


# Dual routes for /mcp/* paths (MCP client compatibility)
@app.get("/mcp/sse")
async def mcp_sse_endpoint(request: Request) -> Response:
    """SSE endpoint for MCP client connections (alternative path)."""
    return await sse_endpoint(request)


@app.post("/mcp/message")
async def mcp_message_endpoint(request: Request) -> Response:
    """Handle MCP messages via POST (alternative path)."""
    return await message_endpoint(request)


# ============== CLI Login Endpoints (for Railway) ==============
# These endpoints are used by the CLI installer during first-run setup.
# The CLI opens a browser to Railway, user logs in, then gets redirected
# back to the local CLI with tokens.

cli_sessions: dict[str, dict] = {}  # session_id -> {port, created_at, expires_at}

CLI_LOGIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>CLI Login - Simple MCP Server</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
               min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0; }}
        .container {{ background: white; padding: 40px; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                     width: 100%; max-width: 400px; }}
        h1 {{ margin: 0 0 10px; color: #333; font-size: 24px; }}
        p {{ color: #666; margin: 0 0 30px; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; margin-bottom: 8px; color: #333; font-weight: 500; }}
        input[type="email"], input[type="password"] {{
            width: 100%; padding: 12px; border: 2px solid #e1e1e1; border-radius: 8px;
            font-size: 16px; box-sizing: border-box; transition: border-color 0.2s; }}
        input:focus {{ outline: none; border-color: #667eea; }}
        button {{ width: 100%; padding: 14px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                 color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600;
                 cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; }}
        button:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4); }}
        .error {{ background: #fee; color: #c00; padding: 12px; border-radius: 8px; margin-bottom: 20px; }}
        .info {{ background: #f0f4ff; color: #4a5568; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; }}
        .signup-link {{ text-align: center; margin-top: 20px; color: #666; }}
        .signup-link a {{ color: #667eea; text-decoration: none; font-weight: 500; }}
        .signup-link a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>CLI Login</h1>
        <p>Sign in to configure simple-mcp-server</p>
        {error}
        <div class="info">This will authenticate your local MCP server installation.</div>
        <form method="POST" action="/cli-login">
            <input type="hidden" name="session" value="{session}">
            <input type="hidden" name="port" value="{port}">
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" required placeholder="your@email.com">
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required placeholder="Your password">
            </div>
            <button type="submit">Sign In</button>
        </form>
        <div class="signup-link">
            Don't have an account? <a href="/cli-signup?session={session}&port={port}">Sign up</a>
        </div>
    </div>
</body>
</html>
"""

CLI_SIGNUP_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>CLI Sign Up - Simple MCP Server</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
               min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0; }}
        .container {{ background: white; padding: 40px; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                     width: 100%; max-width: 400px; }}
        h1 {{ margin: 0 0 10px; color: #333; font-size: 24px; }}
        p {{ color: #666; margin: 0 0 30px; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; margin-bottom: 8px; color: #333; font-weight: 500; }}
        .optional {{ color: #999; font-weight: 400; font-size: 14px; }}
        input[type="email"], input[type="password"], input[type="text"] {{
            width: 100%; padding: 12px; border: 2px solid #e1e1e1; border-radius: 8px;
            font-size: 16px; box-sizing: border-box; transition: border-color 0.2s; }}
        input:focus {{ outline: none; border-color: #667eea; }}
        button {{ width: 100%; padding: 14px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                 color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600;
                 cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; }}
        button:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4); }}
        .error {{ background: #fee; color: #c00; padding: 12px; border-radius: 8px; margin-bottom: 20px; }}
        .info {{ background: #f0f4ff; color: #4a5568; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; }}
        .login-link {{ text-align: center; margin-top: 20px; color: #666; }}
        .login-link a {{ color: #667eea; text-decoration: none; font-weight: 500; }}
        .login-link a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Create Account</h1>
        <p>Sign up to use simple-mcp-server</p>
        {error}
        <div class="info">Create an account to configure your MCP server.</div>
        <form method="POST" action="/cli-signup">
            <input type="hidden" name="session" value="{session}">
            <input type="hidden" name="port" value="{port}">
            <div class="form-group">
                <label for="name">Name</label>
                <input type="text" id="name" name="name" required placeholder="Your name">
            </div>
            <div class="form-group">
                <label for="organization">Organization <span class="optional">(optional)</span></label>
                <input type="text" id="organization" name="organization" placeholder="Your organization">
            </div>
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" required placeholder="your@email.com">
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required placeholder="Create a password" minlength="6">
            </div>
            <div class="form-group">
                <label for="confirm_password">Confirm Password</label>
                <input type="password" id="confirm_password" name="confirm_password" required placeholder="Confirm your password" minlength="6">
            </div>
            <button type="submit">Create Account</button>
        </form>
        <div class="login-link">
            Already have an account? <a href="/cli-login?session={session}&port={port}">Sign in</a>
        </div>
    </div>
</body>
</html>
"""


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
        # Build user metadata
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
