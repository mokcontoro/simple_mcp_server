# Simple MCP Server

A Model Context Protocol (MCP) server with OAuth 2.1 authentication, Supabase user management, and Cloudflare tunnel support. Works with ChatGPT and Claude.ai.

## Features

- **MCP Tools**: Echo and Ping tools for testing connectivity
- **Streamable HTTP Transport**: Modern MCP transport (spec 2025-03-26) at `/mcp`
- **Legacy SSE Support**: Backward compatible SSE transport at `/sse`
- **OAuth 2.1**: Full OAuth flow with PKCE support and dynamic client registration
- **Optional OAuth**: Disable with `ENABLE_OAUTH=false` for simpler deployments
- **Supabase Auth**: User authentication via Supabase
- **Cloudflare Tunnel**: Secure access to your local server via `{name}.robotmcp.ai`
- **Creator-Only Access**: Only the server creator can connect (authorization check)
- **Multi-Platform**: Works with ChatGPT and Claude.ai
- **Modular Architecture**: Separated concerns for easy customization and extension
- **FastMCP Framework**: Aligned with ros-mcp-server for future merge compatibility

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   MCP Client    │────▶│ Cloudflare Tunnel│────▶│  Local Server   │
│ (ChatGPT/Claude)│     │  {name}.robotmcp │     │  (your machine) │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                         │
                                                         ▼
                                                 ┌─────────────────┐
                                                 │    Supabase     │
                                                 │ (user auth DB)  │
                                                 └─────────────────┘
```

## Project Structure

```
simple_mcp_server/
├── main.py              # FastAPI app entry point (~165 lines)
├── tools.py             # MCP tools (echo, ping) - easily replaceable
├── sse.py               # Legacy SSE endpoints (/sse, /message)
├── cli_endpoints.py     # CLI login endpoints (/cli-login, /cli-signup)
├── cli.py               # CLI daemon management
├── config.py            # Configuration management
├── oauth/               # OAuth module (optional)
│   ├── __init__.py
│   ├── endpoints.py     # OAuth routes (/authorize, /login, /token, etc.)
│   ├── middleware.py    # MCPOAuthMiddleware for /mcp endpoint
│   ├── stores.py        # In-memory token stores
│   └── templates.py     # HTML login/signup pages
└── pyproject.toml
```

## Module Architecture

### Request Flow

```
MCP Client Request
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│                         main.py                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│  │ FastAPI App │──│ CORS        │──│ Route to endpoint   │   │
│  └─────────────┘  │ Middleware  │  └─────────────────────┘   │
│                   └─────────────┘            │                │
└──────────────────────────────────────────────┼────────────────┘
                                               │
        ┌──────────────────┬───────────────────┼───────────────────┐
        │                  │                   │                   │
        ▼                  ▼                   ▼                   ▼
   /mcp endpoint    OAuth endpoints     SSE endpoints      CLI endpoints
   (FastMCP app)    (oauth/endpoints)   (sse.py)          (cli_endpoints)
        │                  │                   │
        ▼                  │                   │
┌───────────────┐          │                   │
│ OAuth         │          │                   │
│ Middleware    │◀─────────┴───────────────────┘
│ (if enabled)  │     (shared token validation)
└───────┬───────┘
        │
        ▼
┌───────────────┐
│   tools.py    │
│  MCP Tools    │
│ (echo, ping)  │
└───────────────┘
```

### Module Descriptions

#### Core Modules

| Module | Lines | Role |
|--------|-------|------|
| **main.py** | 165 | Application entry point. Creates FastAPI app, configures middleware, mounts MCP app at `/mcp`, includes routers conditionally based on `ENABLE_OAUTH` flag. |
| **tools.py** | 33 | Defines MCP tools using FastMCP's `@mcp.tool()` decorator. Contains `echo` and `ping` tools. **Replace this file** to customize MCP functionality. |
| **config.py** | 106 | Manages local configuration (user credentials, tunnel URL, robot name). Persists to `~/.simple-mcp-server/config.json`. |

#### OAuth Module (`oauth/`)

| Module | Lines | Role |
|--------|-------|------|
| **endpoints.py** | 380 | OAuth 2.1 flow endpoints: discovery metadata (`/.well-known/*`), client registration (`/register`), authorization (`/authorize`, `/login`, `/signup`, `/consent`), and token exchange (`/token`). |
| **middleware.py** | 67 | `MCPOAuthMiddleware` - Validates Bearer tokens on `/mcp` requests. Checks token expiration and creator-only access. Returns 401/403 with RFC 9728 compliant headers. |
| **stores.py** | 20 | In-memory dictionaries for OAuth state: `registered_clients`, `authorization_codes`, `access_tokens`, `pending_authorizations`, `authenticated_sessions`. |
| **templates.py** | 318 | HTML templates for login, signup, and consent pages. Shared across OAuth flow and CLI login. |

#### Endpoint Modules

| Module | Lines | Role |
|--------|-------|------|
| **sse.py** | 120 | Legacy SSE transport endpoints (`/sse`, `/message`) for backward compatibility with older MCP clients. Includes token validation and creator-only access check. |
| **cli_endpoints.py** | 165 | Browser-based CLI login endpoints (`/cli-login`, `/cli-signup`). Used by the installer to authenticate users via Supabase and redirect credentials back to local CLI. |

#### CLI Module

| Module | Lines | Role |
|--------|-------|------|
| **cli.py** | 862 | Command-line interface for server management. Handles daemon start/stop, Cloudflare tunnel creation, browser-based login flow, and status display. |

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        oauth/stores.py                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐ │
│  │ registered_      │  │ authorization_   │  │ access_       │ │
│  │ clients          │  │ codes            │  │ tokens        │ │
│  │ {client_id: ...} │  │ {code: ...}      │  │ {token: ...}  │ │
│  └────────┬─────────┘  └────────┬─────────┘  └───────┬───────┘ │
│           │                     │                    │         │
└───────────┼─────────────────────┼────────────────────┼─────────┘
            │                     │                    │
            ▼                     ▼                    ▼
     /register             /token (exchange)    middleware.py
     (create client)       (create token)       (validate token)
                                                       │
                                                       ▼
                                               /mcp, /sse, /message
                                               (protected endpoints)
```

### Initialization Sequence

1. **main.py loads** → Environment variables, Supabase client, local config
2. **tools.py imported** → FastMCP instance created with tool definitions
3. **MCP HTTP app created** → With OAuth middleware (if `ENABLE_OAUTH=true`)
4. **FastAPI app created** → With MCP app's lifespan for proper task group init
5. **Routers initialized** → `init_*_routes()` called with dependencies
6. **Routers included** → OAuth (conditional), SSE, CLI endpoints added
7. **Server starts** → Uvicorn runs on configured host/port

### Dependency Injection Pattern

Each router module uses an `init_*_routes()` function to receive dependencies:

```python
# oauth/endpoints.py
def init_oauth_routes(server_url: str, supabase_client):
    global _server_url, _supabase
    _server_url = server_url
    _supabase = supabase_client

# sse.py
def init_sse_routes(server_url: str, local_config, mcp_instance):
    global _server_url, _local_config, _mcp
    ...

# cli_endpoints.py
def init_cli_routes(supabase_client):
    global _supabase
    ...
```

This pattern allows:
- Modules to be imported without side effects
- Dependencies to be injected from main.py
- Easy testing with mock dependencies

### For ros-mcp-server Merge

To adapt for ros-mcp-server:
1. Replace `tools.py` with ROS-specific MCP tools
2. Set `ENABLE_OAUTH=false` to disable authentication
3. Keep or remove CLI/tunnel components as needed

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/mokcontoro/simple_mcp_server.git
cd simple_mcp_server

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your Supabase credentials
```

### First Run

```bash
python cli.py
```

This will:
1. Open browser for login/signup via Supabase
2. Prompt for a robot name (e.g., `myrobot` → `myrobot.robotmcp.ai`)
3. Create a Cloudflare tunnel
4. Start the local MCP server

### CLI Commands

| Command | Description |
|---------|-------------|
| `python cli.py` | Start the MCP server |
| `python cli.py --stop` | Stop server (keep credentials) |
| `python cli.py --logout` | Stop server and clear credentials |
| `python cli.py --status` | Show current status and configuration |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anonymous key |
| `SUPABASE_JWT_SECRET` | JWT secret for token validation |
| `ENABLE_OAUTH` | Set to `false` to disable OAuth (default: `true`) |

## Access Control

**Creator-Only Access**: Only the user who set up the server can connect via MCP clients.

- When you run `python cli.py` and log in, your user ID is stored locally
- When an MCP client (ChatGPT/Claude) connects, they must authenticate
- The server checks if the authenticated user matches the creator
- Unauthorized users receive a `403 Forbidden` error

This prevents others from using your MCP server even if they have a Supabase account.

## API Endpoints

### Server Info
| Endpoint | Description |
|----------|-------------|
| `GET /` | Server info and available tools |
| `GET /health` | Health check |

### MCP Endpoints
| Endpoint | Description |
|----------|-------------|
| `POST /mcp` | Streamable HTTP transport (new, recommended) |
| `GET /mcp` | Streamable HTTP SSE stream |
| `GET /sse` | Legacy SSE connection (backward compat) |
| `POST /message` | Legacy SSE message handler (backward compat) |

### OAuth 2.1 Endpoints
| Endpoint | Description |
|----------|-------------|
| `GET /.well-known/oauth-authorization-server` | OAuth metadata (RFC 8414) |
| `GET /.well-known/oauth-protected-resource` | Resource metadata (RFC 9728) |
| `POST /register` | Dynamic client registration (RFC 7591) |
| `GET /authorize` | Authorization endpoint |
| `POST /token` | Token endpoint |

## MCP Tools

### echo
Echoes back the input message.
```
Input: "Hello, world!"
Output: "Echo: Hello, world!"
```

### ping
Simple connectivity test.
```
Output: "pong from {owner}'s MCP server"
```

## Client Configuration

### ChatGPT
1. Go to **Settings → Connectors → Add**
2. Set MCP Server URL to `https://{your-name}.robotmcp.ai/mcp`
3. Select OAuth authentication
4. Log in with your Supabase account (must be the server creator)

### Claude.ai
1. Add as an MCP integration
2. Use endpoint: `https://{your-name}.robotmcp.ai/mcp`
3. OAuth flow will redirect to login page
4. Log in with your Supabase account (must be the server creator)

> **Note**: Legacy SSE endpoint (`/sse`) is still available for backward compatibility.

## Troubleshooting

### Cloudflared Windows Service Conflict

If you see issues with the tunnel, check if cloudflared is running as a Windows service:

```powershell
# Check status
python cli.py --status

# If service is running, stop it (Admin Command Prompt):
net stop cloudflared

# Or permanently uninstall:
cloudflared service uninstall
```

### Port 8000 Already in Use

The CLI automatically cleans up old processes on startup. If issues persist:

```powershell
# Stop server
python cli.py --stop

# Or manually kill processes
netstat -ano | findstr :8000
taskkill /F /PID <pid>
```

## Development

### Railway Deployment (Auth Server)

The auth server component is deployed on Railway for browser-based login:

1. Push code to GitHub
2. Create new project at [railway.app](https://railway.app)
3. Deploy from GitHub repo
4. Add environment variables
5. Set `AUTH_SERVER_URL` in your local `.env`

## License

Copyright (c) 2025 Contoro. All rights reserved.

This software is proprietary and confidential. Unauthorized copying, modification, distribution, or use of this software, via any medium, is strictly prohibited without the express written permission of Contoro.
