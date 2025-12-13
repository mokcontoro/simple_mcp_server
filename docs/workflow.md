# Workflow for Simple MCP Server

This document tracks the development workflow for deploying MCP servers on robot computers. The `simple-mcp-server` serves as a testing ground for individual components before migrating to `ros-mcp-server`.

---

## Entity Roles

### 1. Local Computer (user's PC / robot)
**What it is**: The user's machine that runs the MCP server
**Runs**: `server.py` (MCP server application)
**Responsibilities**:
- Run the MCP server process
- Host MCP tools (echo, ping, etc.)
- Handle MCP protocol (`/sse`, `/message` endpoints)
- Handle OAuth flow for MCP clients (`/authorize`, `/login`, `/token`)
- Validate access tokens via Supabase
- Expose to internet via Cloudflare tunnel

**Does NOT**:
- Store user credentials (delegates to Supabase)
- Handle CLI installer login (that's Railway)

### 2. Supabase
**What it is**: Cloud authentication service (Backend-as-a-Service)
**Responsibilities**:
- Store user accounts (email, hashed password)
- Authenticate login requests (verify credentials)
- Issue JWT access tokens
- Validate JWT tokens

**Does NOT**:
- Host any UI or web pages
- Run MCP server
- Handle MCP traffic

### 3. Railway
**What it is**: Cloud platform hosting a web dashboard service
**Runs**: `railway.py` (web service for CLI login)
**Responsibilities**:
- Host CLI login pages (`/cli-login`, `/cli-signup`)
- Authenticate users via Supabase during first-run setup
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
│ (runs server.py) │  │ (runs railway.py)│      │
│                  │  │                  │      │
│  • MCP server    │  │  • /cli-login    │      │
│  • OAuth flow    │  │  • /cli-signup   │      │
│  • MCP endpoints │  │  • Dashboard     │      │
│  • Tools         │  │    (future)      │      │
└────────┬─────────┘  └──────────────────┘      │
         │                     ▲                │
         │ Cloudflare          │ Browser        │
         │ Tunnel              │ (first-run)    │
         ▼                     │                │
┌──────────────────┐    ┌──────────────────┐    │
│   MCP Client     │    │  CLI Installer   │────┘
│ (ChatGPT, Claude)│    │  (setup.py)      │
└──────────────────┘    └──────────────────┘
```

---

1. **User installs simple-mcp-server on a robot computer**
   - Tool: UV, pip, or shell script (TBD)
   - Status: Manual git clone with setup
   - TODO: Create an automated installation script

2. **Installer prompts user to login at robotmcp.ai (or sign up if no account)**
   - Tool: Supabase authentication
   - Status: **Implemented** - Login/signup pages with Supabase auth exist in main.py
   - Note: Currently using Railway URLs; robotmcp.ai is the planned production domain
   - TODO: Create installer that triggers the auth flow (Claude Code style login)

3. **Installer retrieves user info from Supabase after login**
   - Tool: Supabase client
   - Status: **Implemented** - User info stored in `authenticated_sessions` after OAuth flow
   - TODO: Integrate into installer script

4. **User enters a robot name during installation**
   - Tool: Shell script / installer prompt
   - Status: Not yet implemented
   - TODO: Add robot naming step to installer

5. **Installer creates robot-specific URL (e.g., mok-robot1.robotmcp.ai)**
   - Tool: Cloudflared CLI / Cloudflare API
   - Status: Manual process via Cloudflare CLI and web interface
   - TODO: Automate URL generation using Cloudflare API (must avoid duplicate names)

6. **User inputs robot-specific URL in MCP client**
   - Tool: MCP client (ChatGPT, Claude, etc.)
   - Status: Working prototype
   - TODO: Continue testing with various clients

7. **OAuth login for MCP connection (skipped if already authenticated)**
   - Tool: OAuth 2.1 flow in main.py
   - Status: Working prototype
   - TODO: Continue testing

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
│   ├── setup_flow.py       # Interactive setup (OAuth, naming, tunnel)
│   ├── config.py           # Config management
│   └── server.py           # MCP server logic
```

### First-Run Detection
```python
def main():
    config = load_config()
    if not config.is_valid():
        run_setup_flow()  # Interactive setup
    start_server(config)
```

### Optional Bootstrap (for users without pipx)
```bash
curl -fsSL https://robotmcp.ai/install.sh | bash
# Checks Python → installs pipx → runs pipx install → starts setup
```

### Why pipx?
- Single command install with automatic isolation
- No dependency conflicts
- Easy updates: `pipx upgrade ros-mcp-server`
- Security: no curl|bash required for main install

---

## Open Questions

- How do we allow multiple users to access one MCP server?
