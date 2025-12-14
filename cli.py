"""CLI entry point for simple-mcp-server.

Copyright (c) 2024 Contoro. All rights reserved.

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

from config import load_config, clear_config, CONFIG_FILE

load_dotenv()

VERSION = "1.2.0"
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")


# ============== Helper Functions ==============

def fetch_user_info(access_token: str) -> dict:
    """Fetch user info from Supabase using access token."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return {}

    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        response = supabase.auth.get_user(access_token)
        if response and response.user:
            user = response.user
            return {
                "user_id": user.id,
                "email": user.email,
                "name": user.user_metadata.get("name", "") if user.user_metadata else "",
                "organization": user.user_metadata.get("organization", "") if user.user_metadata else "",
            }
    except Exception:
        pass
    return {}


def check_cloudflared() -> bool:
    """Check if cloudflared is installed and accessible."""
    return shutil.which("cloudflared") is not None


def check_cloudflared_service() -> bool:
    """Check if cloudflared is running as a Windows service."""
    import platform
    if platform.system() != "Windows":
        return False
    try:
        result = subprocess.run(
            ["sc", "query", "cloudflared"],
            capture_output=True,
            text=True
        )
        return "RUNNING" in result.stdout
    except Exception:
        return False


def is_server_running() -> bool:
    """Check if MCP server is already running on port 8000."""
    import platform
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True
            )
            for line in result.stdout.split('\n'):
                if ":8000" in line and "LISTENING" in line:
                    return True
        except Exception:
            pass
    else:
        try:
            result = subprocess.run(
                ["lsof", "-ti", ":8000"],
                capture_output=True,
                text=True
            )
            return bool(result.stdout.strip())
        except Exception:
            pass
    return False


def run_cloudflared_tunnel(tunnel_token: str) -> subprocess.Popen:
    """Start cloudflared tunnel in background."""
    return subprocess.Popen(
        ["cloudflared", "tunnel", "run", "--token", tunnel_token],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )


def kill_cloudflared_processes():
    """Kill any running cloudflared processes started by this CLI."""
    import platform
    killed = False
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["taskkill", "/F", "/IM", "cloudflared.exe"],
                capture_output=True,
                text=True
            )
            if "SUCCESS" in result.stdout:
                killed = True
        except Exception:
            pass
    else:
        try:
            result = subprocess.run(["pkill", "-f", "cloudflared tunnel run"], capture_output=True)
            killed = result.returncode == 0
        except Exception:
            pass
    return killed


def kill_processes_on_port(port: int) -> bool:
    """Kill any processes listening on the specified port."""
    import platform
    killed = False
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True
            )
            for line in result.stdout.split('\n'):
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        try:
                            subprocess.run(
                                ["taskkill", "/F", "/PID", pid],
                                capture_output=True
                            )
                            killed = True
                        except Exception:
                            pass
        except Exception:
            pass
    else:
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True,
                text=True
            )
            for pid in result.stdout.strip().split('\n'):
                if pid:
                    subprocess.run(["kill", "-9", pid], capture_output=True)
                    killed = True
        except Exception:
            pass
    return killed


# ============== CLI Commands ==============

def cmd_start():
    """Start the MCP server."""
    from setup import run_login_flow

    config = load_config()

    # First-run setup
    if not config.is_valid():
        success = run_login_flow()
        if not success:
            print("\n[ERROR] Setup failed. Please try again.")
            sys.exit(1)
        config = load_config()
    else:
        print(f"Logged in as: {config.email}")

    # Check tunnel config
    if not config.has_tunnel():
        print("\n[ERROR] Tunnel not configured.")
        print("  Run: simple-mcp-server logout")
        print("  Then: simple-mcp-server start")
        sys.exit(1)

    # Check cloudflared
    if not check_cloudflared():
        print("\n[ERROR] cloudflared not found.")
        print("  Install from: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/")
        sys.exit(1)

    # Warn about cloudflared service
    if check_cloudflared_service():
        print("\n[WARNING] cloudflared Windows service is running!")
        print("  This may cause conflicts. Stop it with:")
        print("  > net stop cloudflared  (as Admin)")
        print()

    # Check if already running
    if is_server_running():
        print("\n[WARNING] Server may already be running on port 8000.")
        print("  Use 'simple-mcp-server stop' first, or 'simple-mcp-server restart'")
        print()

    # Track tunnel process
    tunnel_process = None

    def signal_handler(sig, frame):
        print("\n\nShutting down...")
        if tunnel_process:
            tunnel_process.terminate()
            tunnel_process.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Cleanup old processes
    print("\nCleaning up old processes...")
    if kill_cloudflared_processes():
        print("  - Stopped old cloudflared processes")
    if kill_processes_on_port(8000):
        print("  - Stopped old server on port 8000")

    # Start tunnel
    print(f"\nStarting tunnel: {config.tunnel_url}")
    tunnel_process = run_cloudflared_tunnel(config.tunnel_token)

    # Print startup banner
    print("\n" + "=" * 50)
    print("  Simple MCP Server")
    print("=" * 50)
    print(f"  User:   {config.email}")
    print(f"  URL:    {config.tunnel_url}")
    print(f"  SSE:    {config.tunnel_url}/sse")
    print("=" * 50)
    print("  Press Ctrl+C to stop")
    print("=" * 50 + "\n")

    try:
        uvicorn.run("main:app", host="0.0.0.0", port=8000)
    finally:
        if tunnel_process:
            tunnel_process.terminate()
            tunnel_process.wait()


def cmd_stop():
    """Stop the MCP server and tunnel."""
    print("Stopping MCP server...")

    stopped_server = kill_processes_on_port(8000)
    stopped_tunnel = kill_cloudflared_processes()

    if stopped_server or stopped_tunnel:
        if stopped_server:
            print("  - Server stopped")
        if stopped_tunnel:
            print("  - Tunnel stopped")
        print("\nServer stopped successfully.")
    else:
        print("  No running server found.")


def cmd_restart():
    """Restart the MCP server."""
    print("Restarting MCP server...\n")
    cmd_stop()
    print()
    cmd_start()


def cmd_status():
    """Show current status."""
    config = load_config()

    print("\n" + "=" * 50)
    print("  Simple MCP Server Status")
    print("=" * 50)

    # Account
    print("\n[Account]")
    if config.is_valid():
        print(f"  Status:   Logged in")
        print(f"  Email:    {config.email}")
        print(f"  User ID:  {config.user_id[:8]}...")
        if SUPABASE_URL and SUPABASE_ANON_KEY:
            user_info = fetch_user_info(config.access_token)
            if user_info:
                if user_info.get('name'):
                    print(f"  Name:     {user_info['name']}")
                if user_info.get('organization'):
                    print(f"  Org:      {user_info['organization']}")
    else:
        print("  Status:   Not logged in")
        print("  Action:   Run 'simple-mcp-server start' to log in")

    # Tunnel
    print("\n[Tunnel]")
    if config.has_tunnel():
        print(f"  Status:   Configured")
        print(f"  Name:     {config.robot_name}")
        print(f"  URL:      {config.tunnel_url}")
        print(f"  SSE:      {config.tunnel_url}/sse")
    else:
        print("  Status:   Not configured")

    # Server
    print("\n[Server]")
    if is_server_running():
        print("  Status:   Running on port 8000")
    else:
        print("  Status:   Not running")

    # Cloudflared
    print("\n[Cloudflared]")
    if check_cloudflared():
        print(f"  Status:   Installed")
        print(f"  Path:     {shutil.which('cloudflared')}")
        if check_cloudflared_service():
            print("  Service:  RUNNING (may cause conflicts!)")
        else:
            print("  Service:  Not running")
    else:
        print("  Status:   Not installed")
        print("  Install:  https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/")

    # Config
    print("\n[Config]")
    print(f"  File:     {CONFIG_FILE}")
    print(f"  Exists:   {CONFIG_FILE.exists()}")

    print("\n" + "=" * 50 + "\n")


def cmd_logout():
    """Log out and clear credentials."""
    config = load_config()

    if not config.is_valid():
        print("Not logged in.")
        return

    email = config.email

    # Stop server first
    print("Stopping server...")
    kill_processes_on_port(8000)
    kill_cloudflared_processes()

    # Clear config
    clear_config()
    print(f"\nLogged out: {email}")
    print(f"Config removed: {CONFIG_FILE}")


def cmd_version():
    """Show version information."""
    print(f"simple-mcp-server v{VERSION}")
    print("Copyright (c) 2024 Contoro. All rights reserved.")


def cmd_help():
    """Show detailed help."""
    print("""
Simple MCP Server - Local MCP server with OAuth
Copyright (c) 2024 Contoro. All rights reserved.

USAGE:
    simple-mcp-server <command>

COMMANDS:
    start       Start the MCP server (default if no command given)
    stop        Stop the running server and tunnel
    restart     Restart the server
    status      Show current status and configuration
    logout      Log out and clear stored credentials
    version     Show version information
    help        Show this help message

EXAMPLES:
    # First run - will prompt for login and tunnel setup
    simple-mcp-server start

    # Check if server is running
    simple-mcp-server status

    # Stop the server
    simple-mcp-server stop

    # Restart after making changes
    simple-mcp-server restart

    # Log out and reconfigure
    simple-mcp-server logout
    simple-mcp-server start

QUICK START:
    1. Run 'simple-mcp-server start'
    2. Log in via browser (opens automatically)
    3. Enter a robot name (e.g., 'myrobot')
    4. Server starts at https://myrobot.robotmcp.ai
    5. Add to ChatGPT/Claude using the /sse endpoint

For more information, see: https://github.com/mokcontoro/simple_mcp_server
""")


# ============== Main Entry Point ==============

def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        prog="simple-mcp-server",
        description="Simple MCP Server - Local MCP server with OAuth",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  start     Start the MCP server (default)
  stop      Stop the running server
  restart   Restart the server
  status    Show current status
  logout    Log out and clear credentials
  version   Show version
  help      Show detailed help

Examples:
  simple-mcp-server start
  simple-mcp-server status
  simple-mcp-server stop
"""
    )

    parser.add_argument(
        "command",
        nargs="?",
        default="start",
        choices=["start", "stop", "restart", "status", "logout", "version", "help"],
        help="Command to run (default: start)"
    )

    # Legacy flags for backward compatibility
    parser.add_argument("--status", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--stop", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--logout", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--version", "-v", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args()

    # Handle legacy flags
    if args.status:
        cmd_status()
    elif args.stop:
        cmd_stop()
    elif args.logout:
        cmd_logout()
    elif args.version:
        cmd_version()
    # Handle commands
    elif args.command == "start":
        cmd_start()
    elif args.command == "stop":
        cmd_stop()
    elif args.command == "restart":
        cmd_restart()
    elif args.command == "status":
        cmd_status()
    elif args.command == "logout":
        cmd_logout()
    elif args.command == "version":
        cmd_version()
    elif args.command == "help":
        cmd_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
