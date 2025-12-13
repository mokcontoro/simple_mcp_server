"""Railway Service - CLI Login for Installation.

This service is deployed to Railway and handles ONLY:
- CLI login pages (/cli-login, /cli-signup)
- First-run authentication during installation

This is NOT involved in MCP traffic. MCP clients connect
directly to the Local Computer's MCP server.
"""
import logging
import os
import time
from urllib.parse import urlencode

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("=== RAILWAY.PY v1.2.0 LOADED ===", flush=True)

from dotenv import load_dotenv
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from supabase import create_client, Client

load_dotenv()

# Environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

# Initialize Supabase client
supabase: Client = None
if SUPABASE_URL and SUPABASE_ANON_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# In-memory session store (for tracking CLI login sessions)
cli_sessions: dict[str, dict] = {}

# Create FastAPI app
app = FastAPI(
    title="Simple MCP Server - CLI Login",
    description="Railway service for CLI installation login",
    version="1.2.0",
)

@app.on_event("startup")
async def startup_event():
    logger.warning("=== Railway CLI Login Service v1.2.0 starting ===")
    logger.warning(f"Supabase configured: {bool(supabase)}")


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
        "version": "1.0.0",
        "description": "Railway service for CLI installation login",
        "endpoints": ["/cli-login", "/cli-signup", "/health"]
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
