"""Setup flow for simple-mcp-server (browser-based login)."""
import secrets
import socket
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

from config import save_config


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
        print(f"\n✗ Login failed: {server.login_error}")
        return False

    if server.login_result:
        result = server.login_result
        save_config(
            user_id=result["user_id"],
            email=result["email"],
            access_token=result["access_token"],
            refresh_token=result.get("refresh_token"),
        )
        print(f"\n✓ Logged in as: {result['email']}")
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

        return True

    print("\n✗ Login timed out. Please try again.")
    return False
