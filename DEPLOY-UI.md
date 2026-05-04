# Deploying the UI apps — `wrangler deploy` story

The `ui-oracle` monorepo ships 6 thin-client UIs to Cloudflare Workers under `*.buildwithoracle.com`. This is the operator-side runbook for deploying them. The architecture and connection pattern is documented at `ψ/memory/learnings/2026-05-04_studio-buildwithoracle-thin-client-pattern.md`.

## What's live (verified 2026-05-05)

| App | Worker name | Domain(s) | HTTP |
|-----|-------------|-----------|------|
| studio | `oracle-studio` | studio.buildwithoracle.com, local.buildwithoracle.com | 200 |
| vector | `vector-oracle-studio` | vector.buildwithoracle.com, vector-playground.buildwithoracle.com | 200 |
| canvas | `canvas-oracle-studio` | canvas.buildwithoracle.com | 200 |
| schedule | `schedule-oracle-studio` | schedule.buildwithoracle.com | 200 |
| feed | `feed-oracle-studio` | feed.buildwithoracle.com | 200 |
| forum | `forum-oracle-studio` | forum.buildwithoracle.com | 200 |

All six share Cloudflare account `a5eabdc2b11aae9bd5af46bd6a88179e`. Compatibility date: `2025-06-01`.

## How they're built

Each app is a **Workers Site** (assets-served SPA), not a serverless function:

```jsonc
// apps/studio/wrangler.json
{
  "name": "oracle-studio",
  "main": "worker.ts",
  "compatibility_date": "2025-06-01",
  "account_id": "a5eabdc2b11aae9bd5af46bd6a88179e",
  "workers_dev": true,
  "routes": [
    { "pattern": "studio.buildwithoracle.com", "custom_domain": true },
    { "pattern": "local.buildwithoracle.com",  "custom_domain": true }
  ],
  "assets": {
    "directory": "./dist",
    "binding": "ASSETS",
    "not_found_handling": "single-page-application",
    "run_worker_first": true
  }
}
```

`vite build` produces `./dist`; wrangler uploads it as the worker's static assets. The `worker.ts` is a thin wrapper that serves from `ASSETS`.

## The deploy command

Per-app:

```bash
cd ~/Code/github.com/Soul-Brews-Studio/ui-oracle
bun run deploy:studio        # → bun --cwd apps/studio run deploy
                              # → bun run build && wrangler deploy
```

All six at once:

```bash
bun run deploy:all
# = deploy:studio && deploy:vector && deploy:canvas
#   && deploy:schedule && deploy:feed && deploy:forum
```

Each invocation:
1. `bun run build` — `tsc -b && vite build` produces `./dist`
2. `wrangler deploy` — uploads `./dist` to the named worker, binds custom domains

## Authentication for `wrangler deploy`

Cloudflare credentials must be available. Two options:

| Method | Where |
|--------|-------|
| `~/.wrangler/config/default.toml` (interactive auth) | After `wrangler login`, persists across sessions |
| `CLOUDFLARE_API_TOKEN` env var | For CI; needs `Workers Scripts:Edit` + zone permissions on the route domains |

Verify before deploying:

```bash
wrangler whoami
# OR
wrangler deploy --dry-run --outdir /tmp/wrangler-dry  # builds but doesn't upload
```

## The thin-client architecture (why deploy is just static)

These UIs are stateless. They serve a SPA bundle and **all data fetching happens at runtime against the user's local backend** — `localhost:47778` for arra-oracle-v3, `localhost:8765` for the reranker, etc.

The connection is wired via the `?host=` URL parameter (BackendGate.tsx) — the first time you load `studio.buildwithoracle.com/?host=localhost:47778`, the app saves the host to `localStorage['oracle-studio-host']` and uses it for every subsequent fetch. Documented at `ψ/memory/learnings/2026-05-04_studio-buildwithoracle-thin-client-pattern.md`.

This means deploys are **fast and safe**:
- No data migrations
- No backend coordination
- Rollback = redeploy the previous bundle
- Each user's data lives only on their machine

## Operator runbook — first-time deploy of a NEW app

If a future ui-oracle app needs deploying for the first time:

1. **Reserve the domain** in Cloudflare (DNS zone for `buildwithoracle.com`)
2. **Add `wrangler.json`** to the app, mirroring an existing one (change `name`, `routes[].pattern`)
3. **Add deploy script** to root `package.json`: `"deploy:<name>": "bun --cwd apps/<name> run deploy"`
4. **Add per-app deploy script**: `"deploy": "bun run build && wrangler deploy"`
5. First deploy: `bun run deploy:<name>` — wrangler will create the worker on first run
6. Add the new app to `deploy:all` in root `package.json` if it should ship with the group
7. Update this `DEPLOY-UI.md` with the new entry

## Operator runbook — existing app, code change

```bash
cd ~/Code/github.com/Soul-Brews-Studio/ui-oracle
git checkout main && git pull
bun install                  # if dependencies changed
bun run deploy:studio        # or deploy:all
# wrangler tail --format pretty   # live logs from the worker
```

Cloudflare's Workers deploys are atomic per-script — the new bundle goes live in seconds, no in-flight request loss.

## Cost / resources

Cloudflare Workers free tier covers the typical UI traffic. The interesting numbers:

- 100,000 requests/day on the free plan
- $5/mo for 10M requests
- Static assets are bundled with the worker — no separate KV / R2 costs
- Custom domain DNS hosted in the same Cloudflare zone — $0 incremental

## Why `worker.ts` exists at all (it's not just a static site)

`run_worker_first: true` in the assets config means the worker's `fetch` handler runs BEFORE asset routing. The default `worker.ts` is usually a 5-line passthrough to `env.ASSETS.fetch(req)`, but the hook is there for cases where you want to:

- Inject CORS / auth headers per-route
- Rewrite specific URLs (e.g. `/api/*` proxy)
- Add observability (request timing, etc.)

The studio's worker.ts likely does the host parsing for `?host=` redirects. Not deploy-critical to understand the details.

## Status: deploys not executed in this iteration

The cron mission has consistently surfaced "wrangler deploy" as a recurring theme. This iteration documented the existing infrastructure but did NOT run an actual deploy — that's a "publishing public content" action requiring explicit authorization beyond the cron's standing instructions.

When ready to deploy a change:

```bash
# Smoke test first
cd ~/Code/github.com/Soul-Brews-Studio/ui-oracle/apps/studio && bun run build
# (verify ./dist looks right)

# Dry run
cd ~/Code/github.com/Soul-Brews-Studio/ui-oracle && bun run deploy:studio --dry-run

# Real deploy
bun run deploy:studio
```

Or the chain wrapper:

```bash
bun run deploy:all          # all 6 apps
```

The deploy itself is non-destructive (wrangler keeps the prior version available for instant rollback via `wrangler rollback`).
