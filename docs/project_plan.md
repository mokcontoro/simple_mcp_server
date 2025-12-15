# Project Plan: simple-mcp-server

**Copyright (c) 2025 Contoro. All rights reserved.**

---

## Architecture

```
┌──────────────────┐
│    Supabase      │  User accounts, auth API
└────────┬─────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐  ┌────────┐
│ Local  │  │Railway │  CLI login, tunnel creation
│Computer│  │        │
│        │  └────────┘
│ MCP    │       ▲
│ Server │       │ Browser (first-run)
└───┬────┘       │
    │ Tunnel  ┌──┴───┐
    ▼         │ CLI  │
┌────────┐    └──────┘
│  MCP   │
│ Client │  ChatGPT, Claude
└────────┘
```

## Module Structure

```
simple_mcp_server/
├── main.py              # FastAPI app entry (~165 lines)
├── tools.py             # MCP tools (echo, ping)
├── cli.py               # CLI daemon management
├── config.py            # Config management
├── setup.py             # Browser login flow
├── railway.py           # Railway deployment
├── sse.py               # Legacy SSE endpoints
├── cli_endpoints.py     # CLI login endpoints
└── oauth/               # OAuth module (optional)
    ├── endpoints.py     # OAuth routes
    ├── middleware.py    # Token validation
    ├── stores.py        # In-memory token stores
    └── templates.py     # HTML templates
```

---

## Status

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Core MCP server with OAuth 2.1 | ✅ Complete |
| 2 | CLI package (pipx install) | ✅ Complete |
| 3 | First-run setup (browser login, tunnel) | ✅ Complete |
| 4 | Creator-only access control | ✅ Complete |
| 5 | Modularization for ros-mcp-server | ✅ Complete |
| 6 | Railway dashboard | TODO |
| 7 | Multi-user access | TODO |

---

## Version History

| Version | Changes |
|---------|---------|
| 1.7.0 | Modular architecture, WSL2 support |
| 1.6.0 | ENABLE_OAUTH flag, optional auth |
| 1.5.0 | Background daemon mode |
| 1.4.0 | Auto-download cloudflared |
| 1.3.0 | Creator-only access control |
| 1.2.0 | CLI login, tunnel setup |
| 1.0.0 | Initial release |

---

## For ros-mcp-server Merge

1. Replace `tools.py` with ROS tools
2. Set `ENABLE_OAUTH=false` to disable auth
3. Keep or remove CLI/tunnel as needed
