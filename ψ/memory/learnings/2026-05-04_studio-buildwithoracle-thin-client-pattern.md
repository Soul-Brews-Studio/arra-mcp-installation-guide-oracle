---
pattern: studio.buildwithoracle.com is a thin client that connects to user's localhost MCP
date: 2026-05-04
source: dev-browser investigation
project: github.com/Soul-Brews-Studio/ui-oracle
---

# studio.buildwithoracle.com — Thin Client / Local MCP Pattern

## The Discovery

The Oracle Studio (https://studio.buildwithoracle.com/) is **not a hosted SaaS** — it's a static React app deployed to a CDN that **always talks to localhost** (or any user-specified host) for its API.

This is the `local.drizzle.studio` pattern: the UI is shipped via the web, the backend runs on the user's machine.

## How it works

1. **Default host resolution** (`packages/shared-ui/src/host.ts`):
   - `?host=...` URL param → saves to `localStorage['oracle-studio-host']`, then redirects clean
   - `localStorage` value → used as backend host
   - Otherwise → `http://${window.location.hostname}:47778`

2. **Backend probe** (`apps/studio/src/components/BackendGate.tsx`):
   - Calls `${API_BASE}/health` with 3s timeout
   - On failure → shows landing page "ARRA 🔮Racle needs a local MCP" with install instructions

3. **Connect prod → localhost** (the magic URL):
   ```
   https://studio.buildwithoracle.com/?host=localhost:47778
   ```
   Modern browsers allow http://localhost from https origins (treated as secure context).

## Verified working — 2026-05-04

- arra-oracle-v3 server on `:47778`: 20,842 docs, 20,677 embeddings (BGE-M3)
- prod studio fetched: `/api/health` 200, `/api/stats` 200, `/api/auth/status` 200, `/api/reflect` 200
- Renders: full app with menu, doc counts, vault, search, planets

## Implication for the installation guide

The "installation" of arra MCP is really just:
1. Run the server (`bunx --bun arra-oracle-v3@github:Soul-Brews-Studio/arra-oracle-v3 --port 47778`)
2. Open `https://studio.buildwithoracle.com/?host=localhost:47778`

That's it. No clone, no build, no auth flow. Two commands.
