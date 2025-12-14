"""Setup flow for simple-mcp-server (browser-based login)."""
import re
import secrets
import socket
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import requests

from config import save_config, update_config_tunnel


# Server URL (Railway deployment)
SERVER_URL = "https://simplemcpserver-production-e610.up.railway.app"


class CallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback from browser."""

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def do_GET(self):
        """Handle callback GET request."""
        parsed = urlparse(self.path)

        if parsed.path == "/callback":
            params = parse_qs(parsed.query)

            # Extract tokens and user info from callback
            user_id = params.get("user_id", [None])[0]
            email = params.get("email", [None])[0]
            access_token = params.get("access_token", [None])[0]
            refresh_token = params.get("refresh_token", [None])[0]
            name = params.get("name", [None])[0]
            organization = params.get("organization", [None])[0]
            error = params.get("error", [None])[0]

            if error:
                self.server.login_error = error
                self._send_response("Login failed. You can close this window.")
            elif user_id and email and access_token:
                self.server.login_result = {
                    "user_id": user_id,
                    "email": email,
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "name": name,
                    "organization": organization,
                }
                self._send_response("Login successful! You can close this window.")
            else:
                self.server.login_error = "Missing credentials"
                self._send_response("Login failed. Missing credentials.")

            # Signal to stop server
            self.server.should_stop = True
        else:
            self.send_error(404)

    def _send_response(self, message: str):
        """Send HTML response."""
        html = f"""<!DOCTYPE html>
<html>
<head><title>Login</title>
<style>
body {{ font-family: sans-serif; display: flex; justify-content: center;
       align-items: center; height: 100vh; margin: 0; background: #f5f5f5; }}
.box {{ background: white; padding: 40px; border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; }}
</style>
</head>
<body><div class="box"><h2>{message}</h2></div></body>
</html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())


def find_free_port() -> int:
    """Find an available port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def validate_robot_name(name: str) -> tuple[bool, str]:
    """Validate robot name format locally.

    Returns (is_valid, error_message).
    """
    if not name:
        return False, "Robot name is required"
    if len(name) < 3:
        return False, "Robot name must be at least 3 characters"
    if len(name) > 32:
        return False, "Robot name must be at most 32 characters"
    if not re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', name):
        return False, "Use only lowercase letters, numbers, and hyphens"
    return True, ""


def prompt_robot_name() -> str:
    """Prompt user for robot name with validation."""
    print("\n--- Robot Setup ---")
    print("Enter a unique name for your robot/device.")
    print("This will create: {name}.robotmcp.ai")
    print("Rules: lowercase letters, numbers, hyphens (3-32 chars)\n")

    while True:
        name = input("Robot name: ").strip().lower()
        is_valid, error = validate_robot_name(name)
        if is_valid:
            return name
        print(f"  [X] {error}")
        print()


def create_tunnel(robot_name: str, user_id: str, access_token: str, force: bool = False) -> dict:
    """Call Railway API to create Cloudflare tunnel.

    Args:
        robot_name: Unique name for the robot
        user_id: User's Supabase ID
        access_token: User's access token
        force: If True and tunnel exists for same user, return existing tunnel

    Returns dict with:
        - success: bool
        - tunnel_token, tunnel_url: on success
        - error: error message on failure
        - owned_by_user: True if tunnel exists and is owned by this user
    """
    try:
        response = requests.post(
            f"{SERVER_URL}/create-tunnel",
            data={
                "robot_name": robot_name,
                "user_id": user_id,
                "access_token": access_token,
                "force": "true" if force else "false"
            },
            timeout=60
        )
        return response.json()
    except requests.RequestException as e:
        return {"success": False, "error": f"Network error: {e}"}
    except Exception as e:
        return {"success": False, "error": f"Error: {e}"}


def run_login_flow() -> bool:
    """Run browser-based login flow.

    Returns True if login successful, False otherwise.
    """
    print("\nNo configuration found. Starting setup...\n")

    # Generate session ID and find free port
    session_id = secrets.token_urlsafe(32)
    port = find_free_port()

    # Build login URL
    login_url = f"{SERVER_URL}/cli-login?session={session_id}&port={port}"

    print("Opening browser for login...")
    print(f"If browser doesn't open, visit:\n  {login_url}\n")

    # Open browser
    webbrowser.open(login_url)

    # Start local callback server
    server = HTTPServer(("127.0.0.1", port), CallbackHandler)
    server.login_result = None
    server.login_error = None
    server.should_stop = False
    server.timeout = 1  # Check every second

    print("Waiting for login...", end="", flush=True)

    # Wait for callback (timeout after 5 minutes)
    max_wait = 300
    waited = 0
    while not server.should_stop and waited < max_wait:
        server.handle_request()
        waited += 1

    print()

    if server.login_error:
        print(f"\n[X] Login failed: {server.login_error}")
        return False

    if server.login_result:
        result = server.login_result
        save_config(
            user_id=result["user_id"],
            email=result["email"],
            access_token=result["access_token"],
            refresh_token=result.get("refresh_token"),
        )
        print(f"\n[OK] Logged in as: {result['email']}")
        print(f"  Config saved to: ~/.simple-mcp-server/config.json\n")

        # Debug: Display user info
        print("  [DEBUG] User Info:")
        print(f"    user_id: {result['user_id']}")
        print(f"    email: {result['email']}")
        print(f"    name: {result.get('name') or '(not set)'}")
        print(f"    organization: {result.get('organization') or '(not set)'}")
        print(f"    access_token: {result['access_token'][:20]}...")
        refresh = result.get('refresh_token') or ''
        print(f"    refresh_token: {refresh[:20] + '...' if refresh else '(none)'}")
        print()

        # Prompt for robot name and create tunnel (retry on name conflict)
        while True:
            robot_name = prompt_robot_name()
            print(f"\nCreating tunnel for {robot_name}.robotmcp.ai...")

            tunnel_result = create_tunnel(
                robot_name=robot_name,
                user_id=result["user_id"],
                access_token=result["access_token"]
            )

            if tunnel_result.get("success"):
                update_config_tunnel(
                    robot_name=robot_name,
                    tunnel_token=tunnel_result["tunnel_token"],
                    tunnel_url=tunnel_result["tunnel_url"]
                )
                print(f"[OK] Tunnel created: {tunnel_result['tunnel_url']}")
                print(f"  Tunnel token saved to config.\n")
                return True
            else:
                error = tunnel_result.get("error", "Unknown error")
                print(f"[X] Tunnel creation failed: {error}")

                # Check if name is taken
                if "already taken" in error.lower() or "already exists" in error.lower():
                    # Check if owned by same user - offer to reuse
                    if tunnel_result.get("owned_by_user"):
                        print(f"\n  You already own the tunnel '{robot_name}.robotmcp.ai'.")
                        reuse = input("  Reuse this tunnel? (y/n): ").strip().lower()
                        if reuse == 'y':
                            print(f"\nReusing tunnel {robot_name}.robotmcp.ai...")
                            # Retry with force=True to get existing tunnel
                            tunnel_result = create_tunnel(
                                robot_name=robot_name,
                                user_id=result["user_id"],
                                access_token=result["access_token"],
                                force=True
                            )
                            if tunnel_result.get("success"):
                                update_config_tunnel(
                                    robot_name=robot_name,
                                    tunnel_token=tunnel_result["tunnel_token"],
                                    tunnel_url=tunnel_result["tunnel_url"]
                                )
                                print(f"[OK] Tunnel reused: {tunnel_result['tunnel_url']}")
                                print(f"  Tunnel token saved to config.\n")
                                return True
                            else:
                                print(f"[X] Failed to reuse tunnel: {tunnel_result.get('error')}")
                                print("  Please try a different name.\n")
                                continue
                        else:
                            print("  Please choose a different name.\n")
                            continue
                    else:
                        # Taken by another user
                        print("  Please choose a different name.\n")
                        continue
                else:
                    # Other error - don't retry
                    print("  You can retry by running: simple-mcp-server")
                    return False

    print("\n[X] Login timed out. Please try again.")
    return False
