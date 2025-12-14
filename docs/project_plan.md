# Project Plan: simple-mcp-server

**Copyright (c) 2024 Contoro. All rights reserved.**

This software is proprietary and confidential. Unauthorized copying, modification, distribution, or use of this software is strictly prohibited without the express written permission of Contoro.

---

## Architecture

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

- **Local Computer**: Runs MCP server (`main.py`), handles OAuth + MCP endpoints, creator-only access control
- **Supabase**: Auth backend, user accounts, token validation
- **Railway**: CLI login pages, tunnel creation API, future dashboard (NOT in MCP data path)
- **MCP Client**: Connects directly to Local Computer via Cloudflare tunnel
- **Cloudflare Tunnel**: Secure access via `{name}.robotmcp.ai`

---

## Phase 1: Core MCP Server ✅ COMPLETE

| Task | Status |
|------|--------|
| MCP server with OAuth 2.1 | ✅ Done |
| Echo/ping tools | ✅ Done |
| Supabase auth (login/signup) | ✅ Done |
| Cloudflare tunnel (manual) | ✅ Done |

**Milestone**: MCP server works locally, accessible via Cloudflare tunnel

---

## Phase 2: Package & CLI ✅ COMPLETE

| Task | Status |
|------|--------|
| pyproject.toml for pipx | ✅ Done |
| cli.py entry point | ✅ Done |
| --status command | ✅ Done |
| --stop command | ✅ Done |
| --logout command | ✅ Done |
| Process cleanup on startup | ✅ Done |

**Milestone**: `python cli.py` manages server lifecycle

---

## Phase 3: Installer & First-Run Setup ✅ COMPLETE

| Task | Status |
|------|--------|
| First-run config detection | ✅ Done |
| Browser-based OAuth login flow | ✅ Done |
| Robot naming prompt | ✅ Done |
| Cloudflare tunnel creation | ✅ Done |
| Config saved to ~/.simple-mcp-server/ | ✅ Done |
| Cloudflared service conflict detection | ✅ Done |

**Milestone**: `python cli.py` auto-configures on first run

---

## Phase 4: Access Control ✅ COMPLETE

| Task | Status |
|------|--------|
| Creator-only access (user_id check) | ✅ Done |
| Dynamic SERVER_URL from tunnel config | ✅ Done |
| 403 Forbidden for unauthorized users | ✅ Done |
| OAuth flow on local server | ✅ Done |

**Milestone**: Only server creator can connect via MCP clients

---

## Phase 5: Railway Dashboard ⬚ TODO

| Task | Status |
|------|--------|
| Web UI (Supabase auth) | ⬚ TODO |
| Robot registry | ⬚ TODO |
| Access control (share with users) | ⬚ TODO |
| API endpoints for robot management | ⬚ TODO |

**Milestone**: Users can register robots and share access via dashboard

---

## Phase 6: Multi-User & Production ⬚ TODO

| Task | Status |
|------|--------|
| Multi-user access to single robot | ⬚ TODO |
| Allowed users list in config | ⬚ TODO |
| MCP client testing (ChatGPT, Claude) | ⬚ TODO |
| Documentation | ✅ Done |
| PyPI publication | ⬚ TODO |

**Milestone**: End-to-end flow works with shared access

---

## Current Focus

**Phase 5**: Build Railway dashboard for robot management and access sharing.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024-12 | Initial release with OAuth 2.1 |
| 1.1.0 | 2024-12 | CLI login, tunnel setup |
| 1.2.0 | 2024-12 | Creator-only access control, CLI improvements |
