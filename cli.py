"""CLI entry point for simple-mcp-server.

This runs the LOCAL MCP server on the user's machine.
On first run, it opens a browser for login via Railway.
"""
import argparse
import os
import sys
import uvicorn

from dotenv import load_dotenv
from supabase import create_client

from config import load_config, clear_config
from setup import run_login_flow

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")


def fetch_user_info(access_token: str) -> dict:
    """Fetch user info from Supabase using access token."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return {}

    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        # Set the session with the access token
        response = supabase.auth.get_user(access_token)
        if response and response.user:
            user = response.user
            return {
                "user_id": user.id,
                "email": user.email,
                "name": user.user_metadata.get("name", "") if user.user_metadata else "",
                "organization": user.user_metadata.get("organization", "") if user.user_metadata else "",
            }
    except Exception as e:
        print(f"  [DEBUG] Failed to fetch user info: {e}")

    return {}


def print_user_debug(user_info: dict, access_token: str, refresh_token: str = ""):
    """Print user info for debugging."""
    print("  [DEBUG] User Info:")
    print(f"    user_id: {user_info.get('user_id', '(unknown)')}")
    print(f"    email: {user_info.get('email', '(unknown)')}")
    print(f"    name: {user_info.get('name') or '(not set)'}")
    print(f"    organization: {user_info.get('organization') or '(not set)'}")
    print(f"    access_token: {access_token[:20]}...")
    print(f"    refresh_token: {refresh_token[:20] + '...' if refresh_token else '(none)'}")
    print()


def logout():
    """Log out by clearing stored credentials."""
    config = load_config()
    if not config.is_valid():
        print("Not logged in.")
        return

    email = config.email
    clear_config()
    print(f"Logged out: {email}")
    print("Config removed from ~/.simple-mcp-server/config.json")


def main():
    """Start the local MCP server with first-run setup."""
    parser = argparse.ArgumentParser(
        description="Simple MCP Server - Local MCP server with OAuth"
    )
    parser.add_argument(
        "--logout",
        action="store_true",
        help="Log out and clear stored credentials"
    )
    args = parser.parse_args()

    # Handle logout
    if args.logout:
        logout()
        sys.exit(0)

    # Check for existing config
    config = load_config()

    if not config.is_valid():
        # Run login flow (opens browser to Railway)
        success = run_login_flow()
        if not success:
            print("Setup failed. Please try again.")
            sys.exit(1)

        # Reload config after login
        config = load_config()
    else:
        # Already logged in - fetch user info from Supabase
        print(f"Already logged in as: {config.email}")
        user_info = fetch_user_info(config.access_token)
        if user_info:
            print_user_debug(user_info, config.access_token, config.refresh_token or "")

    print(f"Starting local MCP server as: {config.email}")
    print("Server running at: http://localhost:8000")
    print("Expose via Cloudflare tunnel for remote access.\n")

    # Run the LOCAL MCP server
    uvicorn.run("main:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
