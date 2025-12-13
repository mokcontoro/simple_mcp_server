"""CLI entry point for simple-mcp-server.

This runs the LOCAL MCP server on the user's machine.
On first run, it opens a browser for login via Railway.
"""
import sys
import uvicorn

from config import load_config
from setup import run_login_flow


def main():
    """Start the local MCP server with first-run setup."""
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
