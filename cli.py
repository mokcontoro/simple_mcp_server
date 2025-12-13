"""CLI entry point for simple-mcp-server.

This runs the LOCAL MCP server on the user's machine.
On first run, it opens a browser for login via Railway.
"""
import argparse
import os
import shutil
import signal
import subprocess
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


def check_cloudflared() -> bool:
    """Check if cloudflared is installed and accessible."""
    return shutil.which("cloudflared") is not None


def run_cloudflared_tunnel(tunnel_token: str) -> subprocess.Popen:
    """Start cloudflared tunnel in background.

    Returns the subprocess.Popen object for the tunnel process.
    """
    return subprocess.Popen(
        ["cloudflared", "tunnel", "run", "--token", tunnel_token],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )


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


def show_status():
    """Show current status of simple-mcp-server."""
    print("\n=== Simple MCP Server Status ===\n")

    # Check config
    config = load_config()

    # Login status
    print("[Login]")
    if config.is_valid():
        print(f"  Status: Logged in")
        print(f"  Email: {config.email}")
        print(f"  User ID: {config.user_id}")

        # Fetch additional user info from Supabase
        if SUPABASE_URL and SUPABASE_ANON_KEY:
            user_info = fetch_user_info(config.access_token)
            if user_info:
                print(f"  Name: {user_info.get('name') or '(not set)'}")
                print(f"  Organization: {user_info.get('organization') or '(not set)'}")
    else:
        print(f"  Status: Not logged in")
        print(f"  Run 'simple-mcp-server' to log in")

    print()

    # Tunnel status
    print("[Tunnel]")
    if config.has_tunnel():
        print(f"  Status: Configured")
        print(f"  Robot Name: {config.robot_name}")
        print(f"  URL: {config.tunnel_url}")
    else:
        print(f"  Status: Not configured")
        if config.is_valid():
            print(f"  Run 'simple-mcp-server' to set up tunnel")

    print()

    # cloudflared status
    print("[cloudflared]")
    if check_cloudflared():
        cloudflared_path = shutil.which("cloudflared")
        print(f"  Status: Installed")
        print(f"  Path: {cloudflared_path}")
    else:
        print(f"  Status: Not installed")
        print(f"  Install: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/")

    print()

    # Config file location
    print("[Config]")
    from config import CONFIG_FILE
    print(f"  Location: {CONFIG_FILE}")
    print(f"  Exists: {CONFIG_FILE.exists()}")

    print()


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
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current status and configuration"
    )
    args = parser.parse_args()

    # Handle status
    if args.status:
        show_status()
        sys.exit(0)

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

    # Check if tunnel is configured
    if not config.has_tunnel():
        print("[X] Tunnel not configured.")
        print("  Please run setup again: python cli.py --logout && python cli.py")
        sys.exit(1)

    # Check if cloudflared is installed
    if not check_cloudflared():
        print("[X] cloudflared not found.")
        print("  Please install cloudflared:")
        print("  https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/")
        sys.exit(1)

    # Track tunnel process for cleanup
    tunnel_process = None

    def signal_handler(sig, frame):
        """Handle shutdown signals gracefully."""
        print("\nShutting down...")
        if tunnel_process:
            tunnel_process.terminate()
            tunnel_process.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start cloudflared tunnel
    print(f"Starting tunnel: {config.tunnel_url}")
    tunnel_process = run_cloudflared_tunnel(config.tunnel_token)

    print(f"Starting local MCP server as: {config.email}")
    print(f"Server accessible at: {config.tunnel_url}")
    print("Press Ctrl+C to stop.\n")

    try:
        # Run the LOCAL MCP server
        uvicorn.run("main:app", host="0.0.0.0", port=8000)
    finally:
        # Clean up tunnel process
        if tunnel_process:
            tunnel_process.terminate()
            tunnel_process.wait()


if __name__ == "__main__":
    main()
