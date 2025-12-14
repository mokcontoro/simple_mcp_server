# Workflow for Simple MCP Server

**Copyright (c) 2024 Contoro. All rights reserved.**

This software is proprietary and confidential. Unauthorized copying, modification, distribution, or use of this software is strictly prohibited without the express written permission of Contoro.

---

This document tracks the development workflow for deploying MCP servers on robot computers. The `simple-mcp-server` serves as a testing ground for individual components before migrating to `ros-mcp-server`.

---

## Entity Roles

### 1. Local Computer (user's PC / robot)
**What it is**: The user's machine that runs the MCP server
**Runs**: `main.py` (MCP server application) via `cli.py`
**Responsibilities**:
- Run the MCP server process
- Host MCP tools (echo, ping, etc.)
- Handle MCP protocol (`/sse`, `/message` endpoints)
- Handle OAuth flow for MCP clients (`/authorize`, `/login`, `/token`)
- Validate access tokens
- **Enforce creator-only access control** (403 for unauthorized users)
- Expose to internet via Cloudflare tunnel (`{name}.robotmcp.ai`)

**Does NOT**:
- Store user credentials (delegates to Supabase)
- Handle CLI installer login (that's Railway)

### 2. Supabase
**What it is**: Cloud authentication service (Backend-as-a-Service)
**Responsibilities**:
- Store user accounts (email, hashed password, name, organization)
- Authenticate login requests (verify credentials)
- Issue JWT access tokens
- Validate JWT tokens

**Does NOT**:
- Host any UI or web pages
- Run MCP server
- Handle MCP traffic

### 3. Railway
**What it is**: Cloud platform hosting auth and tunnel management
**Runs**: Web service for CLI login and tunnel creation
**Responsibilities**:
- Host CLI login pages (`/cli-login`, `/cli-signup`)
- Authenticate users via Supabase during first-run setup
- Create Cloudflare tunnels (`/create-tunnel`)
- Redirect back to CLI with tokens after login
- Future: Dashboard for robot management and access sharing

**Does NOT**:
- Handle MCP traffic (MCP clients never connect here)
- Store user credentials (uses Supabase)
- Run MCP server

### 4. MCP Client (ChatGPT, Claude, etc.)
**What it is**: AI assistant that uses MCP tools
**Responsibilities**:
- Discover MCP server via `/.well-known/*` endpoints
- Authenticate via OAuth flow (login pages served by local computer)
- Call MCP tools via `/sse` + `/message`

**Connects to**: Local Computer's MCP server (via Cloudflare tunnel)
**Does NOT connect to**: Railway (never)

### 5. Cloudflare Tunnel
**What it is**: Secure tunnel service
**Responsibilities**:
- Route traffic from `{name}.robotmcp.ai` to local server
- TLS termination
- DDoS protection

---

## Architecture Diagram
```
                    ┌──────────────────┐
                    │    Supabase      │
                    │                  │
                    │  • User accounts │
                    │  • Auth API      │
                    └────────┬─────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  │
┌──────────────────┐  ┌──────────────────┐      │
│ Local Computer   │  │     Railway      │      │
│  (runs main.py)  │  │  (auth server)   │      │
│                  │  │                  │      │
│  • MCP server    │  │  • /cli-login    │      │
│  • OAuth flow    │  │  • /cli-signup   │      │
│  • MCP endpoints │  │  • /create-tunnel│      │
│  • Tools         │  │  • Dashboard     │      │
│  • Auth check    │  │    (future)      │      │
└────────┬─────────┘  └──────────────────┘      │
         │                     ▲                │
         │ Cloudflare          │ Browser        │
         │ Tunnel              │ (first-run)    │
         ▼                     │                │
┌──────────────────┐    ┌──────────────────┐    │
│   MCP Client     │    │  CLI Installer   │────┘
│ (ChatGPT, Claude)│    │  (cli.py)        │
└──────────────────┘    └──────────────────┘
```

---

## Implementation Status

### 1. User installs simple-mcp-server on a robot computer ✅
- Tool: Git clone + pip install
- Status: **Complete**
- Commands: `git clone`, `pip install -r requirements.txt`

### 2. User runs CLI and logs in via browser ✅
- Tool: `cli.py` + Railway auth pages + Supabase
- Status: **Complete**
- Command: `python cli.py` (opens browser for login/signup)

### 3. User info retrieved from Supabase ✅
- Tool: Supabase client
- Status: **Complete**
- Stored in `~/.simple-mcp-server/config.json`

### 4. User enters a robot name ✅
- Tool: CLI prompt
- Status: **Complete**
- Format: `{name}.robotmcp.ai`

### 5. Cloudflare tunnel created automatically ✅
- Tool: Railway API + Cloudflare
- Status: **Complete**
- Tunnel token saved to config

### 6. User inputs robot URL in MCP client ✅
- Tool: MCP client (ChatGPT, Claude)
- Status: **Complete**
- Example: `https://myrobot.robotmcp.ai/sse`

### 7. OAuth login for MCP connection ✅
- Tool: OAuth 2.1 flow in main.py
- Status: **Complete**
- Creator-only access enforced (403 for others)

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `python cli.py` | Start server (first-run triggers setup) |
| `python cli.py --stop` | Stop server and tunnel |
| `python cli.py --logout` | Stop server and clear credentials |
| `python cli.py --status` | Show current configuration |

---

## Access Control

### Current: Creator-Only Access ✅
- Server creator's `user_id` stored in config during setup
- On MCP client connection, server checks if authenticated user matches creator
- Non-matching users receive `403 Forbidden`

### Future: Multi-User Access (TODO)
```python
# Planned config structure
{
    "user_id": "creator-uuid",
    "email": "creator@example.com",
    "allowed_users": [
        "user-uuid-1",
        "user-uuid-2"
    ]
}

# Authorization check
allowed = [creator_user_id] + config.allowed_users
if connecting_user_id not in allowed:
    raise HTTPException(status_code=403)
```

---

## Installation Strategy (for ros-mcp-server)

**Recommended approach:** `pipx` + first-run auto-setup

### User Experience
```bash
# Install (one command)
pipx install ros-mcp-server

# Run (setup happens automatically on first run)
ros-mcp-server
# → Opens browser for Supabase OAuth login
# → Prompts for robot name
# → Creates Cloudflare tunnel
# → Saves config to ~/.ros-mcp-server/config.json
# → Starts server
```

### Package Structure
```
ros-mcp-server/
├── pyproject.toml          # Entry point: ros-mcp-server = "ros_mcp.cli:main"
├── ros_mcp/
│   ├── cli.py              # Main entry with first-run detection
│   ├── setup.py            # Interactive setup (OAuth, naming, tunnel)
│   ├── config.py           # Config management
│   └── server.py           # MCP server logic
```

### First-Run Detection (Implemented)
```python
def main():
    config = load_config()
    if not config.is_valid():
        run_login_flow()  # Interactive setup

    # Clean up old processes
    kill_cloudflared_processes()
    kill_processes_on_port(8000)

    # Start tunnel and server
    tunnel_process = run_cloudflared_tunnel(config.tunnel_token)
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
```

---

## Troubleshooting

### Cloudflared Windows Service Conflict
If cloudflared is installed as a Windows service, it may intercept tunnel traffic:
```powershell
# Check status
python cli.py --status

# Stop service (Admin Command Prompt)
net stop cloudflared

# Or uninstall permanently
cloudflared service uninstall
```

### Port 8000 Already in Use
```powershell
python cli.py --stop
# or
netstat -ano | findstr :8000
taskkill /F /PID <pid>
```

---

## Open Questions (Resolved)

| Question | Answer |
|----------|--------|
| How do we allow multiple users to access one MCP server? | Phase 6: Add `allowed_users` list to config, check during authorization |
| How to handle cloudflared service conflicts? | Added detection and warning in CLI startup |
| How to clean up zombie processes? | Added `--stop` command and auto-cleanup on startup |
