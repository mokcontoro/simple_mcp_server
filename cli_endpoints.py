"""CLI login endpoints for browser-based authentication.

This module provides endpoints for CLI-based login flow:
- /cli-login: Login form for CLI users
- /cli-signup: Signup form for new CLI users

These endpoints are used by the installer/CLI to authenticate users
via browser redirect.
"""

import time
import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from oauth.templates import CLI_LOGIN_PAGE, CLI_SIGNUP_PAGE

logger = logging.getLogger(__name__)

# Router for CLI endpoints
router = APIRouter(tags=["cli"])

# CLI session storage
cli_sessions: dict[str, dict] = {}

# Supabase client - set by init_cli_routes()
_supabase = None


def init_cli_routes(supabase_client):
    """Initialize CLI routes with Supabase client.

    Args:
        supabase_client: The Supabase client for authentication

    Must be called before including the router in the app.
    """
    global _supabase
    _supabase = supabase_client


@router.get("/cli-login")
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


@router.post("/cli-login")
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

    if not _supabase:
        user_id = "demo-user"
        access_token = "demo-token"
    else:
        try:
            response = _supabase.auth.sign_in_with_password({
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


@router.get("/cli-signup")
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


@router.post("/cli-signup")
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

    if not _supabase:
        return RedirectResponse(url=f"/cli-login?session={session}&port={port}", status_code=302)

    try:
        user_metadata = {"name": name.strip()}
        if organization.strip():
            user_metadata["organization"] = organization.strip()

        response = _supabase.auth.sign_up({
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
