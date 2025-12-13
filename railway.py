"""Railway Service - CLI Login for Installation.

This service is deployed to Railway and handles ONLY:
- CLI login pages (/cli-login, /cli-signup)
- First-run authentication during installation
- Cloudflare tunnel creation (/create-tunnel)

This is NOT involved in MCP traffic. MCP clients connect
directly to the Local Computer's MCP server.
"""
import base64
import logging
import os
import re
import secrets
import time
from urllib.parse import urlencode

import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("=== RAILWAY.PY v1.3.0 LOADED ===", flush=True)

from dotenv import load_dotenv
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from supabase import create_client, Client

load_dotenv()

# Environment variables - Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

# Environment variables - Cloudflare
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "")
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
CLOUDFLARE_ZONE_ID = os.getenv("CLOUDFLARE_ZONE_ID", "")
CLOUDFLARE_DOMAIN = "robotmcp.ai"  # Base domain for tunnel URLs

# Initialize Supabase client
supabase: Client = None
if SUPABASE_URL and SUPABASE_ANON_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# In-memory session store (for tracking CLI login sessions)
cli_sessions: dict[str, dict] = {}

# Create FastAPI app
app = FastAPI(
    title="Simple MCP Server - CLI Login",
    description="Railway service for CLI installation login and tunnel creation",
    version="1.3.0",
)

@app.on_event("startup")
async def startup_event():
    logger.warning("=== Railway CLI Login Service v1.3.0 starting ===")
    logger.warning(f"Supabase configured: {bool(supabase)}")
    cloudflare_configured = bool(CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_ZONE_ID)
    logger.warning(f"Cloudflare configured: {cloudflare_configured}")


# ============== HTML Templates ==============

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


# ============== Endpoints ==============

@app.get("/health")
async def health_check():
    """Health check endpoint for Railway."""
    return {"status": "healthy", "service": "cli-login"}


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "name": "Simple MCP Server - CLI Login",
        "version": "1.3.0",
        "description": "Railway service for CLI installation login and tunnel creation",
        "endpoints": ["/cli-login", "/cli-signup", "/create-tunnel", "/health"]
    }


@app.get("/cli-login")
async def cli_login_page(session: str = "", port: str = ""):
    """Show CLI login form."""
    if not session or not port:
        return HTMLResponse("<h1>Invalid request. Missing session or port.</h1>", status_code=400)

    # Store CLI session
    cli_sessions[session] = {
        "port": port,
        "created_at": int(time.time()),
        "expires_at": int(time.time()) + 600  # 10 minutes
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

    # Authenticate with Supabase
    user_id = None
    access_token = None
    refresh_token = None
    name = ""
    organization = ""

    if not supabase:
        # Fallback: accept any login if Supabase not configured (demo mode)
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
                # Extract user metadata
                print(f"[DEBUG] user_metadata: {response.user.user_metadata}", flush=True)
                if response.user.user_metadata:
                    name = response.user.user_metadata.get("name", "")
                    organization = response.user.user_metadata.get("organization", "")
                print(f"[DEBUG] Extracted - name: {name}, org: {organization}", flush=True)
            else:
                error_html = '<div class="error">Invalid email or password</div>'
                return HTMLResponse(CLI_LOGIN_PAGE.format(session=session, port=port, error=error_html))
        except Exception as e:
            error_html = f'<div class="error">Authentication failed: {str(e)}</div>'
            return HTMLResponse(CLI_LOGIN_PAGE.format(session=session, port=port, error=error_html))

    # Clean up session
    del cli_sessions[session]

    # Redirect to local callback with credentials and user info
    callback_params = urlencode({
        "user_id": user_id,
        "email": email,
        "access_token": access_token,
        "refresh_token": refresh_token or "",
        "name": name,
        "organization": organization,
    })
    callback_url = f"http://127.0.0.1:{port}/callback?{callback_params}"

    return RedirectResponse(url=callback_url, status_code=302)


@app.get("/cli-signup")
async def cli_signup_page(session: str = "", port: str = ""):
    """Show CLI signup form."""
    if not session or not port:
        return HTMLResponse("<h1>Invalid request. Missing session or port.</h1>", status_code=400)

    # Store or update CLI session
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

    # Validate name
    if not name.strip():
        error_html = '<div class="error">Name is required</div>'
        return HTMLResponse(CLI_SIGNUP_PAGE.format(session=session, port=port, error=error_html))

    # Validate passwords match
    if password != confirm_password:
        error_html = '<div class="error">Passwords do not match</div>'
        return HTMLResponse(CLI_SIGNUP_PAGE.format(session=session, port=port, error=error_html))

    if len(password) < 6:
        error_html = '<div class="error">Password must be at least 6 characters</div>'
        return HTMLResponse(CLI_SIGNUP_PAGE.format(session=session, port=port, error=error_html))

    # Create account with Supabase
    if not supabase:
        # Fallback: redirect to login (demo mode)
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
            # Redirect to login page after signup
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


# ============== Cloudflare Tunnel API ==============

def validate_robot_name(name: str) -> tuple[bool, str]:
    """Validate robot name format.

    Returns (is_valid, error_message).
    """
    if not name:
        return False, "Robot name is required"
    if len(name) < 3:
        return False, "Robot name must be at least 3 characters"
    if len(name) > 32:
        return False, "Robot name must be at most 32 characters"
    if not re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', name):
        return False, "Robot name must be lowercase alphanumeric with optional hyphens"
    return True, ""


async def check_dns_exists(robot_name: str) -> bool:
    """Check if DNS record already exists for robot name."""
    if not CLOUDFLARE_API_TOKEN or not CLOUDFLARE_ZONE_ID:
        return False

    url = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    params = {"name": f"{robot_name}.{CLOUDFLARE_DOMAIN}"}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            return len(data.get("result", [])) > 0
    return False


async def create_cloudflare_tunnel(robot_name: str) -> dict:
    """Create a Cloudflare tunnel and return tunnel info.

    Returns dict with: tunnel_id, tunnel_token, or error.
    """
    if not all([CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_ZONE_ID]):
        return {"error": "Cloudflare not configured"}

    # Generate tunnel secret (32 bytes, base64 encoded)
    tunnel_secret = base64.b64encode(secrets.token_bytes(32)).decode()

    # Create tunnel
    tunnel_url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/cfd_tunnel"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    tunnel_data = {
        "name": f"{robot_name}-tunnel",
        "tunnel_secret": tunnel_secret
    }

    async with httpx.AsyncClient() as client:
        # Create tunnel
        logger.info(f"Creating tunnel for {robot_name}...")
        response = await client.post(tunnel_url, headers=headers, json=tunnel_data)

        if response.status_code not in [200, 201]:
            error_detail = response.json().get("errors", [{}])[0].get("message", "Unknown error")
            logger.error(f"Tunnel creation failed: {error_detail}")
            return {"error": f"Failed to create tunnel: {error_detail}"}

        tunnel_result = response.json()
        tunnel_id = tunnel_result["result"]["id"]
        tunnel_token = tunnel_result["result"]["token"]

        logger.info(f"Tunnel created: {tunnel_id}")

        # Create DNS CNAME record
        dns_url = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records"
        dns_data = {
            "type": "CNAME",
            "name": robot_name,
            "content": f"{tunnel_id}.cfargotunnel.com",
            "proxied": True
        }

        logger.info(f"Creating DNS record for {robot_name}.{CLOUDFLARE_DOMAIN}...")
        dns_response = await client.post(dns_url, headers=headers, json=dns_data)

        if dns_response.status_code not in [200, 201]:
            error_detail = dns_response.json().get("errors", [{}])[0].get("message", "Unknown error")
            logger.error(f"DNS creation failed: {error_detail}")
            # Try to clean up the tunnel
            await client.delete(f"{tunnel_url}/{tunnel_id}", headers=headers)
            return {"error": f"Failed to create DNS record: {error_detail}"}

        logger.info(f"DNS record created: {robot_name}.{CLOUDFLARE_DOMAIN}")

        # Configure tunnel ingress rules
        config_url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/cfd_tunnel/{tunnel_id}/configurations"
        config_data = {
            "config": {
                "ingress": [
                    {
                        "hostname": f"{robot_name}.{CLOUDFLARE_DOMAIN}",
                        "service": "http://localhost:8000"
                    },
                    {
                        "service": "http_status:404"
                    }
                ]
            }
        }

        logger.info(f"Configuring tunnel ingress rules...")
        config_response = await client.put(config_url, headers=headers, json=config_data)

        if config_response.status_code not in [200, 201]:
            error_detail = config_response.json().get("errors", [{}])[0].get("message", "Unknown error")
            logger.warning(f"Tunnel config failed (non-fatal): {error_detail}")

        return {
            "tunnel_id": tunnel_id,
            "tunnel_token": tunnel_token,
            "tunnel_url": f"https://{robot_name}.{CLOUDFLARE_DOMAIN}"
        }


@app.post("/create-tunnel")
async def create_tunnel_endpoint(
    robot_name: str = Form(...),
    user_id: str = Form(...),
    access_token: str = Form(...)
):
    """Create a Cloudflare tunnel for a robot.

    Requires valid Supabase access token for authentication.
    """
    # Validate robot name
    is_valid, error_msg = validate_robot_name(robot_name)
    if not is_valid:
        return {"success": False, "error": error_msg}

    # Validate access token with Supabase
    if supabase:
        try:
            user_response = supabase.auth.get_user(access_token)
            if not user_response or not user_response.user:
                return {"success": False, "error": "Invalid access token"}
            if user_response.user.id != user_id:
                return {"success": False, "error": "User ID mismatch"}
        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            return {"success": False, "error": "Authentication failed"}

    # Check if robot name is already taken
    if await check_dns_exists(robot_name):
        return {"success": False, "error": f"Robot name '{robot_name}' is already taken"}

    # Create tunnel
    result = await create_cloudflare_tunnel(robot_name)

    if "error" in result:
        return {"success": False, "error": result["error"]}

    return {
        "success": True,
        "tunnel_id": result["tunnel_id"],
        "tunnel_token": result["tunnel_token"],
        "tunnel_url": result["tunnel_url"]
    }
