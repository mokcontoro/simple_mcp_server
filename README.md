# Simple MCP Server

A Model Context Protocol (MCP) server with OAuth 2.1 authentication, Supabase user management, and Cloudflare tunnel support. Works with ChatGPT and Claude.ai.

## Features

- **MCP Tools**: Echo and Ping tools for testing connectivity
- **OAuth 2.1**: Full OAuth flow with PKCE support and dynamic client registration
- **Supabase Auth**: User authentication via Supabase
- **Cloudflare Tunnel**: Secure access to your local server via `{name}.robotmcp.ai`
- **Creator-Only Access**: Only the server creator can connect (authorization check)
- **Multi-Platform**: Works with ChatGPT and Claude.ai

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
| `GET /sse` | MCP SSE connection (requires auth) |
| `POST /message` | MCP message handler (requires auth) |

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
2. Set MCP Server URL to `https://{your-name}.robotmcp.ai/sse`
3. Select OAuth authentication
4. Log in with your Supabase account (must be the server creator)

### Claude.ai
1. Add as an MCP integration
2. Use SSE endpoint: `https://{your-name}.robotmcp.ai/sse`
3. OAuth flow will redirect to login page
4. Log in with your Supabase account (must be the server creator)

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

Copyright (c) 2024 Contoro. All rights reserved.

This software is proprietary and confidential. Unauthorized copying, modification, distribution, or use of this software, via any medium, is strictly prohibited without the express written permission of Contoro.
