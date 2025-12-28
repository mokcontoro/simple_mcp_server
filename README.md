# Simple MCP Server

A Model Context Protocol (MCP) server with OAuth 2.1 authentication, Supabase user management, and Cloudflare tunnel support. Works with ChatGPT and Claude.ai.

## Quick Start

```bash
# Install via pipx
pipx install git+https://github.com/mokcontoro/simple_mcp_server.git

# Run (opens browser for first-time setup)
simple-mcp-server
```

See [docs/install.md](docs/install.md) for manual installation and troubleshooting.

## Features

- **Streamable HTTP Transport**: Modern MCP transport at `/mcp`
- **OAuth 2.1**: Full flow with PKCE and dynamic client registration
- **Cloudflare Tunnel**: Secure access via `{name}.robotmcp.ai`
- **Creator-Only Access**: Only the server creator can connect
- **Optional OAuth**: Disable with `ENABLE_OAUTH=false`
- **Secure CLI Login**: POST-based credential transfer (not URL params)
- **WSL Support**: Reliable browser opening with PowerShell fallback

## Project Structure

```
simple_mcp_server/
├── main.py              # FastAPI app entry point
├── tools.py             # MCP tools (echo, ping) - replace for custom tools
├── cli.py               # CLI daemon management
├── config.py            # Config management (~/.simple-mcp-server/)
├── setup.py             # Browser-based login flow
├── sse.py               # Legacy SSE endpoints
└── oauth/               # OAuth module (optional)
    ├── endpoints.py     # OAuth routes
    ├── middleware.py    # Token validation
    ├── stores.py        # In-memory token stores
    └── templates.py     # HTML templates
```

**Cloud Service:** CLI login and tunnel creation are handled by [robotmcp-cloud](https://github.com/robotmcp/robotmcp_cloud) at `https://app.robotmcp.ai`.

See [docs/project_plan.md](docs/project_plan.md) for architecture details.

## CLI Commands

| Command | Description |
|---------|-------------|
| `simple-mcp-server` | Start server in background |
| `simple-mcp-server stop` | Stop server and tunnel |
| `simple-mcp-server status` | Show current status |
| `simple-mcp-server logout` | Clear credentials and stop |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anonymous key |
| `SUPABASE_JWT_SECRET` | JWT secret for token validation |
| `ENABLE_OAUTH` | Set `false` to disable OAuth (default: `true`) |
| `ROBOTMCP_CLOUD_URL` | Cloud service URL (default: `https://app.robotmcp.ai`) |

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Server info |
| `POST /mcp` | Streamable HTTP transport (recommended) |
| `GET /sse` | Legacy SSE (backward compat) |
| `/.well-known/oauth-authorization-server` | OAuth metadata |

## Connecting MCP Clients

Use `https://{your-name}.robotmcp.ai/mcp` as the MCP server URL in ChatGPT or Claude.ai.

See [docs/workflow.md](docs/workflow.md) for connection flow diagrams.

## Customization

To add custom MCP tools, replace `tools.py`:

```python
from fastmcp import FastMCP
mcp = FastMCP("my-server")

@mcp.tool()
def my_tool(param: str) -> str:
    return f"Result: {param}"
```

For ros-mcp-server merge: replace `tools.py` and set `ENABLE_OAUTH=false`.

## Documentation

- [Installation Guide](docs/install.md) - Setup, troubleshooting, CLI reference
- [Project Plan](docs/project_plan.md) - Architecture, version history
- [Workflow](docs/workflow.md) - Flow diagrams, components

## Version History

- **v1.12.0**: Supabase centralized logging (replaces CloudWatch for security)
- **v1.11.0**: AWS CloudWatch logging integration with JSON structured logs
- **v1.10.0**: Comprehensive INFO-level logging for all MCP server activities
- **v1.9.0**: Secure POST-based CLI login, WSL browser fix, Claude theme for OAuth pages
- **v1.8.0**: OAuth templates, CLI improvements
- **v1.7.0**: Cloudflare tunnel integration
- **v1.0.0**: Initial release with OAuth 2.1 and Streamable HTTP

## License

Copyright (c) 2025 Contoro. All rights reserved.

This software is proprietary and confidential. Unauthorized copying, modification, distribution, or use of this software is strictly prohibited without express written permission.
