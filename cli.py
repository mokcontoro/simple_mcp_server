"""CLI entry point for simple-mcp-server.

Copyright (c) 2024 Contoro. All rights reserved.

This runs the LOCAL MCP server on the user's machine.
On first run, it opens a browser for login via Railway.
"""
import argparse
import os
import platform
import shutil
import signal
import subprocess
import sys
from pathlib import Path

import requests
import uvicorn
from dotenv import load_dotenv
from supabase import create_client

from config import load_config, clear_config, CONFIG_FILE

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

VERSION = "1.3.0"
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

# Cloudflared auto-install settings
CLOUDFLARED_INSTALL_DIR = Path.home() / ".local" / "bin"
CLOUDFLARED_RELEASES_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download"


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
    cloudflared_cmd = get_cloudflared_path()
    return subprocess.Popen(
        [cloudflared_cmd, "tunnel", "run", "--token", tunnel_token],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )


def kill_cloudflared_processes():
    """Kill any running cloudflared processes started by this CLI."""
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


def get_cloudflared_binary_name() -> str | None:
    """Get the correct cloudflared binary name for this platform."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "linux":
        if machine in ("x86_64", "amd64"):
            return "cloudflared-linux-amd64"
        elif machine in ("aarch64", "arm64"):
            return "cloudflared-linux-arm64"
        elif machine.startswith("arm"):
            return "cloudflared-linux-arm"
    elif system == "darwin":
        if machine in ("arm64", "aarch64"):
            return "cloudflared-darwin-arm64"
        else:
            return "cloudflared-darwin-amd64"

    return None  # Windows or unsupported


def install_cloudflared() -> bool:
    """Auto-download cloudflared for Linux/macOS."""
    binary_name = get_cloudflared_binary_name()
    if not binary_name:
        return False

    url = f"{CLOUDFLARED_RELEASES_URL}/{binary_name}"
    dest = CLOUDFLARED_INSTALL_DIR / "cloudflared"

    print("Downloading cloudflared...")
    print(f"  From: {url}")
    print(f"  To:   {dest}")

    try:
        CLOUDFLARED_INSTALL_DIR.mkdir(parents=True, exist_ok=True)

        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()

        with open(dest, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Make executable
        dest.chmod(0o755)

        print("  Done!")

        # Offer to add ~/.local/bin to PATH
        if not is_local_bin_in_path():
            print("\n  ~/.local/bin is not in your PATH.")
            try:
                response = input("  Add to ~/.bashrc? (y/n): ").strip().lower()
                if response == 'y':
                    if add_to_bashrc():
                        print("  Added to ~/.bashrc")
                        print("  Run: source ~/.bashrc  (or restart terminal)")
                    else:
                        print("  Failed to update ~/.bashrc")
            except (EOFError, KeyboardInterrupt):
                pass  # Non-interactive mode, skip

        return True
    except Exception as e:
        print(f"  Failed: {e}")
        return False


def is_local_bin_in_path() -> bool:
    """Check if ~/.local/bin is in PATH."""
    local_bin = str(CLOUDFLARED_INSTALL_DIR)
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    # Check both expanded and unexpanded forms
    return any(local_bin in p or ".local/bin" in p for p in path_dirs)


def add_to_bashrc() -> bool:
    """Add ~/.local/bin to PATH in ~/.bashrc."""
    bashrc = Path.home() / ".bashrc"
    export_line = '\n# Added by simple-mcp-server\nexport PATH="$HOME/.local/bin:$PATH"\n'

    try:
        # Check if already added
        if bashrc.exists():
            content = bashrc.read_text()
            if '.local/bin' in content:
                return True  # Already there

        # Append to bashrc
        with open(bashrc, 'a') as f:
            f.write(export_line)
        return True
    except Exception:
        return False


def get_cloudflared_path() -> str:
    """Get the path to cloudflared binary."""
    # Check system PATH first
    system_path = shutil.which("cloudflared")
    if system_path:
        return system_path

    # Check ~/.local/bin
    local_path = CLOUDFLARED_INSTALL_DIR / "cloudflared"
    if local_path.exists():
        return str(local_path)

    return "cloudflared"  # Fallback


def ensure_cloudflared() -> bool:
    """Ensure cloudflared is available, auto-install if needed."""
    # Check system PATH
    if check_cloudflared():
        return True

    # Check if in ~/.local/bin but not in PATH
    local_bin = CLOUDFLARED_INSTALL_DIR / "cloudflared"
    if local_bin.exists():
        print(f"\n[INFO] cloudflared found at {local_bin}")
        print(f"  Add to PATH: export PATH=\"$HOME/.local/bin:$PATH\"")
        return True

    # Auto-install on Linux/macOS
    if platform.system() in ("Linux", "Darwin"):
        print("\n[INFO] cloudflared not found. Installing automatically...")
        if install_cloudflared():
            print(f"\n[INFO] Add to PATH: export PATH=\"$HOME/.local/bin:$PATH\"")
            print("  Or add to ~/.bashrc for permanent PATH update.\n")
            return True

    return False


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

    # Check cloudflared (auto-install on Linux/macOS if needed)
    if not ensure_cloudflared():
        print("\n[ERROR] cloudflared not found and auto-install failed.")
        print("  Install manually: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/")
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
    sse_url = f"{config.tunnel_url}/sse"
    print("\n" + "=" * 60)
    print("  Simple MCP Server - Running")
    print("=" * 60)
    print(f"  User:    {config.email}")
    print(f"  SSE URL: {sse_url}")
    print("=" * 60)
    print()
    print("  Copy the SSE URL above to your MCP client:")
    print()
    print("  ChatGPT: Settings > Connectors > Add > paste URL")
    print("  Claude:  Add MCP integration > paste URL")
    print()
    print("=" * 60)
    print("  Press Ctrl+C to stop")
    print("=" * 60 + "\n")

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
    local_bin = CLOUDFLARED_INSTALL_DIR / "cloudflared"
    if check_cloudflared():
        print(f"  Status:   Installed (system)")
        print(f"  Path:     {shutil.which('cloudflared')}")
        if check_cloudflared_service():
            print("  Service:  RUNNING (may cause conflicts!)")
        else:
            print("  Service:  Not running")
    elif local_bin.exists():
        print(f"  Status:   Installed (local)")
        print(f"  Path:     {local_bin}")
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
