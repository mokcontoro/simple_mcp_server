# Workflow: simple-mcp-server

**Copyright (c) 2025 Contoro. All rights reserved.**

---

## Components

| Component | Role |
|-----------|------|
| **Local Computer** | Runs MCP server, handles OAuth, hosts tools |
| **Supabase** | User accounts, authentication |
| **Railway** | CLI login pages, tunnel creation |
| **Cloudflare Tunnel** | Routes `{name}.robotmcp.ai` to local server |
| **MCP Client** | ChatGPT, Claude - connects via tunnel |

---

## First-Run Flow

```
User                CLI                 Railway             Supabase
 │                   │                    │                    │
 │ simple-mcp-server │                    │                    │
 │──────────────────>│                    │                    │
 │                   │ Open browser       │                    │
 │                   │───────────────────>│                    │
 │                   │                    │ Authenticate       │
 │                   │                    │───────────────────>│
 │                   │                    │<───────────────────│
 │                   │<── callback ───────│                    │
 │                   │                    │                    │
 │ Enter robot name  │                    │                    │
 │<──────────────────│                    │                    │
 │──────────────────>│                    │                    │
 │                   │ Create tunnel      │                    │
 │                   │───────────────────>│                    │
 │                   │<───────────────────│                    │
 │                   │                    │                    │
 │ Server running    │                    │                    │
 │<──────────────────│                    │                    │
```

---

## MCP Client Connection Flow

```
MCP Client          Cloudflare          Local Server        Supabase
 │                    │                    │                   │
 │ GET /mcp           │                    │                   │
 │───────────────────>│───────────────────>│                   │
 │                    │                    │ Validate token    │
 │                    │                    │──────────────────>│
 │                    │                    │<──────────────────│
 │<───────────────────│<───────────────────│                   │
 │                    │                    │                   │
 │ Call MCP tool      │                    │                   │
 │───────────────────>│───────────────────>│                   │
 │<───────────────────│<───────────────────│                   │
```

---

## CLI Commands

```bash
simple-mcp-server           # Start (auto-setup on first run)
simple-mcp-server stop      # Stop server
simple-mcp-server status    # Show status
simple-mcp-server logout    # Clear credentials
```

---

## Access Control

- Creator's `user_id` stored in config during setup
- OAuth flow validates connecting user
- Non-creator users receive `403 Forbidden`

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ENABLE_OAUTH` | Set `false` to disable auth (default: `true`) |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anonymous key |

---

## WSL Support

CLI auto-detects WSL and uses the correct IP for browser callback:
- Gets WSL IP via `hostname -I`
- Passes to Railway for callback redirect
- Works with Windows browser + WSL CLI
