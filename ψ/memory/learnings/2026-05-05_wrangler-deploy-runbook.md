---
pattern: ui-oracle 6 apps deploy as Cloudflare Workers Sites — wrangler deploy is the standard, all live under *.buildwithoracle.com
date: 2026-05-05
source: ui-oracle/apps/*/wrangler.json + verified live HTTP probes
project: github.com/Soul-Brews-Studio/ui-oracle
---

# Wrangler Deploy — The Story

## What's live

All 6 UI apps return HTTP 200 (verified 2026-05-05):

```
studio.buildwithoracle.com         oracle-studio
local.buildwithoracle.com          oracle-studio (alias)
vector.buildwithoracle.com         vector-oracle-studio
vector-playground.buildwithoracle.com  vector-oracle-studio (alias)
canvas.buildwithoracle.com         canvas-oracle-studio
schedule.buildwithoracle.com       schedule-oracle-studio
feed.buildwithoracle.com           feed-oracle-studio
forum.buildwithoracle.com          forum-oracle-studio
```

All under Cloudflare account `a5eabdc2b11aae9bd5af46bd6a88179e`. Compat date `2025-06-01`.

## Architecture — thin Workers Sites, not Functions

Each app is a Workers Site:
- `vite build` → `./dist`
- `wrangler deploy` uploads `./dist` as the worker's static assets
- `worker.ts` is a thin wrapper (likely just `env.ASSETS.fetch(req)` with `run_worker_first: true`)
- `single-page-application` 404 handling so React Router routes work

No KV. No R2. No D1. No Durable Objects. Just static SPA assets behind Cloudflare's edge network. **All data fetching is client-side against the user's local backend** (`?host=localhost:47778` localStorage pattern, documented separately).

## Why deploys are safe to run frequently

- No data migrations (all data is on the user's machine)
- No backend coordination (UI is stateless)
- Atomic per-script (Cloudflare swaps the worker in seconds, no in-flight loss)
- Instant rollback (`wrangler rollback`)
- No traffic interruption

This is the **plug-and-play architecture extended to deploys**. Same invariants as the embedding-model swap: never destroy state to ship a change. The deploy moves bytes, never coordinates state.

## Deploy commands

```bash
cd ~/Code/github.com/Soul-Brews-Studio/ui-oracle
bun run deploy:studio       # one app
bun run deploy:all          # all 6 (studio + vector + canvas + schedule + feed + forum)

# Per-app: bun --cwd apps/<name> run deploy
#       = bun run build && wrangler deploy
```

`deploy:all` does NOT include the indexer app (it's a backend daemon, not a Workers Site).

## Auth requirements

Cloudflare credentials needed. Two ways:

- `wrangler login` (persisted in `~/.wrangler/`)
- `CLOUDFLARE_API_TOKEN` env (CI-friendly, needs `Workers Scripts:Edit` + zone permissions)

Verify with `wrangler whoami` before any deploy.

## What I did NOT do this iteration

Ran `wrangler deploy`. Per the safety rules, deploying public content (publishing to a live domain) needs explicit authorization. The user's recurring `/loop` mention of "wrangler deploy" was about CAPABILITY ("we have npx wrangler"), not standing authorization to deploy on each cron tick.

When the user explicitly authorizes a deploy ("ship the studio change"), the command is in `DEPLOY-UI.md`. Until then, the runbook stays documentation, not action.

## Deliverable

`DEPLOY-UI.md` at the root of arra-mcp-installation-guide-oracle. Sections:

1. What's live (table of 6 apps × domains × current HTTP status)
2. How they're built (the wrangler.json shape, with example)
3. The deploy command (per-app + chain wrapper)
4. Auth requirements
5. The thin-client architecture (why deploys are just static)
6. Operator runbook — first-time deploy of a new app
7. Operator runbook — existing app, code change
8. Cost / resources (Workers free-tier sufficient for typical traffic)
9. Why `worker.ts` exists (`run_worker_first` hook)
10. Explicit non-action: deploys not executed in this iteration

## Why this is the install-guide oracle's job

The `arra-mcp-installation-guide-oracle` exists to document the operator-side story of running the arra ecosystem. Wrangler deploy is the core operator interaction with the UI side. This was a hole in the documentation — recurring user theme that never produced concrete artifacts. Now there's a runbook.

Future operators copy-paste the commands; future ME (or another oracle) reads this when authorizing a real deploy.

## Cross-PR ship status (unchanged from last iteration — 10 PRs)

```
arra-oracle-v3 PRs from this oracle:
  #1097  ✅ MERGED
  #1098 / #1100 / #1101  reranker chain (alpha)
  #1102 / #1103 / #1104 / #1106 / #1107  indexer M-chain (alpha + stacked)
  #1105  VectorDocument.vector (alpha)
```

This iteration didn't add a PR — it added a runbook. The recurring user theme finally gets concrete documentation.

## What's next

Recurring themes still on the deferred list:
- `arra-indexer scan <path>` and `backfill --model X` (M4 follow-up)
- Real-corpus regression baseline (eval)
- Actually running `wrangler deploy` (waiting for explicit authorization)

The cron continues. Each iteration ships ONE artifact — sometimes a PR, sometimes a runbook.
