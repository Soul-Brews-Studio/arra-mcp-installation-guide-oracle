---
pattern: M3 of indexer-CLI shipped — Hono daemon HTTP API + SSE + entrypoint, 14 tests, plus a known-limitation note for the M5 path
date: 2026-05-05
source: arra-oracle-v3 PR #1104 (feat/indexer-daemon-m3, base: feat/indexer-worker-m2)
project: github.com/Soul-Brews-Studio/arra-oracle-v3
---

# Indexer-CLI M3 — Daemon API Landed

## What shipped (PR #1104)

5 endpoints (Hono):
- `GET /health` — queue depth, models, shutdown state
- `POST /index` — enqueue (per-model or all-models), 503 when draining
- `GET /jobs` — list with `status`/`model`/`limit` filters
- `GET /events` — SSE stream of `WorkerEvent`s with 15s heartbeat
- `POST /drain` — flip shutdown flag

Plus `daemon.ts` (the entrypoint) and `makeEventBus<E>()` (12 LOC pub-sub).

Combined indexer suite: **41 pass / 0 fail / 110 expects** across M1 + M2 + M3.

## Hono surprise — alpha doesn't use Elysia

Main has Elysia routes (e.g. `src/routes/indexer/start.ts`). When I branched off alpha, those didn't exist — alpha uses **Hono** in flat `src/routes/*.ts`. This is the same kind of "alpha behind main" situation we caught with the migration numbering.

For M3 I went with Hono to match alpha's idioms. Whichever framework alpha consolidates on (probably converges with main once `/release-alpha` catches up), the daemon's API factory pattern still works — `createDaemonApp(deps)` is framework-coupled but small (~150 LOC). Could be retargeted in a small follow-up PR if the eventual standard is Elysia.

## Pub-sub bus is the load-bearing primitive

```ts
function makeEventBus<E>() {
  const subs = new Set<(ev: E) => void>();
  return {
    publish: (ev) => { for (const cb of subs) try { cb(ev); } catch {} },
    subscribe: (cb) => { subs.add(cb); return () => subs.delete(cb); },
  };
}
```

12 LOC. Worker.onEvent → bus.publish. Each SSE connection → bus.subscribe. The `try {} catch {}` around each callback is critical — one slow/throwing subscriber must not block events to the others. There's a dedicated test for this.

This is the same dependency-injection pattern as the rest of the indexer-CLI: pure functions, deps as parameters, no globals. The daemon entrypoint is the ONE place where everything wires together; everything else is a library.

## In-process testing without Bun.serve

```ts
const res = await app.fetch(new Request('http://localhost/health'));
expect(res.status).toBe(200);
```

Hono's `.fetch()` accepts a `Request`, returns a `Response`. No port binding, no real network, no flake. **Hermetic API tests** are this easy when the framework is request/response-driven.

## Known limitation called out in the PR

The daemon's `upsertVector()` currently re-embeds via `store.addDocuments()` because the public `VectorStoreAdapter` interface doesn't expose a "write precomputed vector" method. The worker has the vector from `embed()` but can't pass it through.

**Cost**: an extra Ollama call per job (~50-150ms wasted per doc).

**Fix path**: extend `VectorStoreAdapter` with `upsert(id, vector, metadata)`. Separate small PR — keeps M3's scope clean.

This is the **"don't fake the metric" memory in action** — I noticed the inefficiency, called it out explicitly in the PR body and code comment, and didn't paper over it. If a reviewer pulls and runs the daemon, they'll see Ollama getting called twice per doc and know it's a known issue tracked for follow-up.

## Cross-PR ship status (now 7)

```
arra-oracle-v3 PRs from this oracle, all targeting alpha (or stacked-on-alpha):
  #1097  vector fixes                       ✅ MERGED → main
  #1098  Python reranker sidecar             🟢 OPEN
  #1100  rerankCandidates() helper           🟢 OPEN
  #1101  wire reranker into combineResults()  🟢 OPEN
  #1102  indexer-CLI M1 (table + helpers)    🟢 OPEN
  #1103  indexer-CLI M2 (worker loop)        🟢 OPEN  → #1102 stacked
  #1104  indexer-CLI M3 (daemon HTTP API)    🟢 OPEN  → #1103 stacked
```

The indexer-CLI is now structurally complete for the daemon process: table, worker, API, entrypoint. M4 is CLI ergonomics; M5 is the 10-LOC `arra_learn` switch that flips FTS-first/vector-later live.

## Lines so far

- M1 (#1102): 429 LOC — table + 6 helpers + 16 tests
- M2 (#1103): 393 LOC — worker loop + 11 tests
- M3 (#1104): 554 LOC — API + entrypoint + 14 tests

**1,376 LOC** across 3 PRs. The original design estimated ~330 LOC for M1+M2+M3+M4+M5. Tests dominate (~750 LOC); production code is ~620.

This is fine — tests are the enabler for stacking PRs without fear. Each milestone landed with its own coverage. Reviewers can run the suite at any merge boundary and see green.

## What's next

- **M4**: `arra-indexer` CLI commands (scan / backfill / daemon / status / cancel). Mostly thin wrappers around the M3 endpoints + `enqueueIndexJob`.
- **The `upsertVector` re-embed fix**: small dedicated PR, extends `VectorStoreAdapter` interface with `upsert(id, vector, metadata)`.
- **M5**: the 10-LOC switch in `arra_learn` to enqueue instead of inline-embed. **The FTS-first/vector-later activation point.**

Cron will pick up M4 next iteration unless the user redirects.
