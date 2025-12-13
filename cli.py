"""CLI entry point for simple-mcp-server.

This runs the LOCAL MCP server on the user's machine.
On first run, it opens a browser for login via Railway.
"""
import argparse
import sys
import uvicorn

from config import load_config, clear_config
from setup import run_login_flow


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

    print(f"Starting local MCP server as: {config.email}")
    print("Server running at: http://localhost:8000")
    print("Expose via Cloudflare tunnel for remote access.\n")

    # Run the LOCAL MCP server
    uvicorn.run("main:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
