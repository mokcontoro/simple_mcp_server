# Project Plan: simple-mcp-server

## Architecture

```
┌──────────────────┐     ┌──────────────────┐
│    Supabase      │     │     Railway      │
│                  │     │                  │
│  • Auth backend  │◄───►│  • Dashboard UI  │
│  • User database │     │  • Robot sharing │  ← User A shares with User B
│  • Access lists  │     │                  │
└──────────────────┘     └──────────────────┘

           DIRECT CONNECTION (Railway not in data path)
┌──────────────────┐     ┌──────────────────┐
│  ChatGPT/Claude  │────►│  Local/Robot     │
│  (MCP Client)    │◄────│  • MCP Server    │
│                  │     │  • Cloudflare    │
└──────────────────┘     └──────────────────┘
```

- **Supabase**: Auth backend, user database, access permission lists
- **Railway**: Dashboard UI only (robot registry, sharing access between users)
- **Local/Robot**: MCP server runs here, direct connection via Cloudflare tunnel
- **MCP traffic**: Direct from client → Cloudflare → Local (Railway not involved)

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
| ChatGPT/Claude.ai testing | ⬚ TODO |
| Documentation | ⬚ TODO |
| PyPI publication | ⬚ TODO |

**Milestone**: End-to-end flow works (client → tunnel → local)

---

## Current Focus

**Phase 2**: Complete Docker testing to validate pipx installation works correctly.

Next: `docker build -f Dockerfile.test -t mcp-test .`
