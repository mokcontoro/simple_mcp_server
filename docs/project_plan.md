# Project Plan: simple-mcp-server

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

- **Local Computer**: Runs MCP server (`server.py`), handles OAuth + MCP endpoints
- **Supabase**: Auth backend, user accounts, token validation
- **Railway**: CLI login pages only, future dashboard (NOT in MCP data path)
- **MCP Client**: Connects directly to Local Computer via Cloudflare tunnel

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

## Phase 2: Package & Local Testing 🔄 IN PROGRESS

| Task | Status |
|------|--------|
| pyproject.toml for pipx | ✅ Done |
| cli.py entry point | ✅ Done |
| Dockerfile.test | ✅ Done |
| docker-compose.test.yml | ✅ Done |
| Test pipx install in Docker | ⬚ TODO |

**Milestone**: `pipx install .` works in Docker container

---

## Phase 3: Installer & First-Run Setup ⬚ TODO

| Task | Status |
|------|--------|
| First-run config detection | ⬚ TODO |
| Browser-based OAuth login flow | ⬚ TODO |
| Robot naming prompt | ⬚ TODO |
| Cloudflare tunnel creation | ⬚ TODO |
| Config saved to ~/.simple-mcp-server/ | ⬚ TODO |

**Milestone**: `simple-mcp-server` auto-configures on first run

---

## Phase 4: Railway Dashboard ⬚ TODO

| Task | Status |
|------|--------|
| Web UI (Supabase auth) | ⬚ TODO |
| Robot registry | ⬚ TODO |
| Access control (share with users) | ⬚ TODO |
| API endpoints for robot management | ⬚ TODO |

**Milestone**: Users can register robots and share access via dashboard

---

## Phase 5: Integration & Production ⬚ TODO

| Task | Status |
|------|--------|
| Local server validates access via Supabase | ⬚ TODO |
| Multi-user access to single robot | ⬚ TODO |
| MCP client testing | ⬚ TODO |
| Documentation | ⬚ TODO |
| PyPI publication | ⬚ TODO |

**Milestone**: End-to-end flow works (client → tunnel → local)

---

## Current Focus

**Phase 2**: Complete Docker testing to validate pipx installation works correctly.

Next: `docker build -f Dockerfile.test -t mcp-test .`
