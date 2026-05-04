# Indexer-CLI / Daemon — Design

> "the indexer app should open wait and recv like a message to send lets index and do their job then finish can receive another job or queue something" — user, 2026-05-04

## Goals (in priority order)

1. **FTS-first / vector-later** — `arra_learn` returns the moment the FTS row is durable. Vector embedding is enqueued, not awaited.
2. **Plug-and-play** — adding/removing/swapping a model never blocks ingest, never destroys other collections (per `2026-05-04_plug-play-embedding-architecture.md`).
3. **Daemon-shaped** — long-running process that opens, waits, receives jobs, processes them, returns to wait. Survives crashes (jobs durable on disk).
4. **Builds on what exists** — reuses `oracle_documents` (FTS5), `indexing_status`, `/api/indexer/start`. No greenfield.
5. **CLI ergonomics** — `arra-indexer index --model bge-m3` for one-shot; `arra-indexer daemon` for long-running.

## Non-goals (explicitly out of scope)

- Replacing `arra-oracle-v3`'s search path (the indexer feeds it; doesn't subsume it)
- Reranker logic (separate sidecar, separate concern)
- Distributed indexing across machines (single-host first)
- Cross-language workers (TS only — match the rest of arra-oracle-v3)

## What exists today (reuse, don't rebuild)

| Component | Path | Current behavior |
|-----------|------|------------------|
| `oracle_documents` + `oracle_fts` | SQLite, `oracle.db` | Source of truth. Text + FTS5 already populated by `arra_learn`. |
| `indexing_status` table | schema.ts:36-45 | Single row: `is_indexing`, `progress_current`, `progress_total`, `started_at`, `completed_at`, `error`. Already wired for SSE progress. |
| `/api/indexer/start` POST | `src/routes/indexer/start.ts` | Fire-and-forget background task. Takes `model, sourcePath, batchSize`. Returns `jobId` immediately. Aborts on global `abortFlag`. |
| `/api/indexer/progress` SSE | `src/routes/indexer/progress.ts` | Streams `indexing_status` updates every 500ms. |
| `getEmbeddingModels()` | `src/vector/factory.ts` | Returns the registry (bge-m3, nomic, qwen3 → collections). |
| LanceDB collections | `~/.arra-oracle-v2/lancedb/oracle_knowledge_<key>.lance` | One per model. |
| Reranker sidecar | `services/reranker-py/:8765` | After indexing, search uses this. Out of scope for the indexer. |

## Architecture

```
                ┌─────────────────────────────┐
                │     arra-oracle-v3 :47778     │
                │    HTTP + MCP server (Bun)    │
                │                                │
   arra_learn   │  1. Append to oracle_documents │
       ───────> │  2. Insert oracle_fts row      │
                │  3. enqueue(jobId)  ───────────┼──┐
                │  4. Return success ✓ FAST       │  │
                └────────────────────────────────┘  │
                                                    │
                            indexing_jobs table     │
                              (SQLite, durable)     │
                              ◄─────────────────────┘
                                       │
                                       │ poll
                                       ▼
                ┌────────────────────────────────────┐
                │       arra-indexer :47780            │
                │     Daemon (Bun + Elysia)            │
                │                                      │
                │   - HTTP API (POST /index, /events)  │
                │   - Polls indexing_jobs every 1s     │
                │   - Pulls 1+ pending jobs            │
                │   - Embeds via Ollama (bge-m3)       │
                │   - Writes to LanceDB collection     │
                │   - Marks job done                   │
                │                                      │
                │   Concurrency: 1 worker per model    │
                │   (parallel across models, serial    │
                │   within a single model's queue)     │
                └──────────────────────────────────────┘
```

### Why a separate process

Three reasons.

1. **Crash isolation.** Embedding (Ollama) hangs / OOMs / takes seconds — should never affect HTTP ingest latency.
2. **Restart safety.** Daemon restart loses no work — `indexing_jobs` is on disk.
3. **Plug-play tier.** Adding a new model = adding a row to the registry → daemon picks up the new queue. No `arra-oracle-v3` redeploy.

It's a separate **process**, but lives in the same repo (`services/indexer/` alongside `services/reranker-py/`) and shares the same SQLite file via WAL mode.

## Job table

```sql
-- Migration: src/db/migrations/2026-05-05_add_indexing_jobs.sql

CREATE TABLE IF NOT EXISTS indexing_jobs (
  id TEXT PRIMARY KEY,                       -- e.g. "idx-1715000000-bgem3"
  doc_id TEXT NOT NULL,                       -- FK to oracle_documents.id
  model_key TEXT NOT NULL,                    -- "bge-m3", "qwen3", ...
  collection TEXT NOT NULL,                   -- "oracle_knowledge_bge_m3"
  status TEXT NOT NULL DEFAULT 'pending',     -- pending | claimed | done | error
  attempts INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')*1000),
  claimed_at INTEGER,
  finished_at INTEGER,
  error TEXT
);

CREATE INDEX IF NOT EXISTS ix_indexing_jobs_pending
  ON indexing_jobs(status, model_key, created_at)
  WHERE status IN ('pending','claimed');
```

`(status, model_key, created_at)` partial index gives fast `claim next pending for model X` queries without scanning done rows.

## Daemon API

`arra-indexer` listens on `:47780`:

| Endpoint | Method | Behavior |
|----------|--------|----------|
| `/health` | GET | `{status, workers, queue_depth_per_model}` |
| `/index` | POST | Enqueue a job. Body: `{doc_id, model_key?}`. If `model_key` omitted, enqueues for all enabled models. Returns `{job_ids: [...]}`. |
| `/jobs` | GET | List recent jobs with status. Query params: `status, model, limit`. |
| `/jobs/:id` | GET | One job. |
| `/events` | GET (SSE) | Stream of `{type: "claimed"|"done"|"error", job_id, model, doc_id}`. |
| `/cancel/:id` | POST | Cancel a pending job. Cannot cancel claimed (mid-embedding). |
| `/drain` | POST | Stop accepting new jobs, finish in-flight, exit. |

## Worker loop

```ts
// services/indexer/src/worker.ts (sketch)

async function workerLoop(model_key: string, collection: string) {
  while (!shuttingDown) {
    const job = await claimNext(model_key);    // SELECT ... FOR UPDATE SKIP LOCKED equiv
    if (!job) {
      await sleep(1000);                        // queue empty — back off
      continue;
    }
    try {
      const doc = await getDocument(job.doc_id);
      const embedding = await embed(doc.text, model_key);
      await lance(collection).insert([{ id: doc.id, vector: embedding, ...doc.metadata }]);
      await markDone(job.id);
      emitEvent({ type: "done", job_id: job.id, model: model_key, doc_id: doc.id });
    } catch (err) {
      await markError(job.id, err);
      emitEvent({ type: "error", job_id: job.id, error: String(err) });
    }
  }
}
```

One worker per registered model — they don't compete for the same queue (different `model_key`), so no contention. Each worker is single-threaded against its Ollama model (Ollama serializes anyway).

## CLI

```bash
# One-shot ingest from a directory (sync, exits when done)
arra-indexer scan ~/Code/some-repo --model bge-m3

# Enqueue ALL existing oracle_documents into a model's collection (backfill)
arra-indexer backfill --model qwen3-embedding:0.6b

# Daemon mode — listens on :47780
arra-indexer daemon

# Status of recent jobs
arra-indexer status
arra-indexer status --model bge-m3 --limit 20

# Cancel
arra-indexer cancel idx-1715000000-bgem3
```

Implemented with `commander` or just a small `parseArgs` wrapper.

## arra-oracle-v3 changes

Minimal. The `arra_learn` tool currently does FTS + embedding inline (`src/tools/learn.ts:196-219`). Change:

```diff
   // Insert FTS row (existing)
   db.run(`INSERT INTO oracle_fts ...`);

-  // Inline vector embedding — keep DB + lancedb in step
-  try { await vectorStore.addDocuments([{ id, document: content, metadata }]); } catch (e) { /* log */ }
+  // Enqueue vector embedding for the daemon (no await)
+  await enqueueIndexJob({ doc_id: id });    // returns immediately, just inserts a row
```

The new helper `enqueueIndexJob()` is a 5-line SQL insert into `indexing_jobs` for each enabled model. ~10 LOC change.

`/api/indexer/start` stays — it becomes a manual *re-index* trigger that bulk-enqueues many jobs. The fire-and-forget pattern is preserved; the daemon is just the long-running worker.

## Migration story (no destruction)

| Step | Action | Effect |
|------|--------|--------|
| 1 | Ship `services/indexer/` daemon | Independent — doesn't change arra-oracle-v3 behavior |
| 2 | Add `indexing_jobs` table migration | Backwards compatible — old code doesn't see the table |
| 3 | Switch `arra_learn` to enqueue (the diff above) | New writes go through the daemon. Old un-embedded docs unchanged. |
| 4 | Run `arra-indexer backfill --model bge-m3` | Catches up legacy docs (no-op if already embedded) |
| 5 | Optional: drop the inline `vectorStore.addDocuments()` codepath | Cleanup. Daemon is now the only path. |

Each step ships independently. Rollback at any step is `git revert` — no data destruction.

## Failure modes + handling

| Failure | Behavior |
|---------|----------|
| Daemon down | Jobs accumulate in `indexing_jobs`. arra-oracle-v3 still serves search (against the *previously* indexed vectors). Search staleness measurable as "queue depth". |
| Ollama down | Worker logs error, marks job `error`, increments `attempts`. Next attempt after a delay (exponential backoff). After max attempts (e.g. 5), job stays `error` for human review. |
| LanceDB write fails | Same as Ollama — `error` + retry. |
| Daemon crashes mid-embedding | Job stays `claimed` with `claimed_at` set. On daemon restart, sweep `claimed` jobs older than N minutes back to `pending`. |
| Doc deleted between enqueue and claim | Worker checks doc still exists; if not, marks job `done` (no-op). |
| Concurrent daemons (mistake) | `claim` uses an UPDATE with WHERE clause that's atomic in SQLite WAL — only one daemon wins. Second sees no claim. Belt-and-suspenders idempotency. |

## Observability

- Every state change emits an SSE event on `/events`
- Prometheus-style metrics on `/metrics` (queue depth per model, job throughput, error rate, p50/p95/p99 embed latency)
- `arra-indexer status` reads the table directly (works even when daemon down)
- `indexing_status` table preserved for backwards-compat with the studio progress UI

## Why this beats the existing `/api/indexer/start`

| | Current (`/api/indexer/start`) | Indexer daemon |
|---|--------------------------------|---------------|
| Concurrent jobs | No — global `abortFlag` | Yes, one per model |
| Crash recovery | Lost on process restart | All jobs durable in SQLite |
| FTS-first writes | No — `arra_learn` blocks on embedding | Yes — embedding deferred |
| Per-doc resolution | No — only "scan a directory" | Yes — single doc enqueue |
| Backfill new model | Manual API call | One CLI command |
| Cancel a job | Global abort only | Per-job cancel |

Current path stays as a fallback / for one-shot scans. Daemon is additive.

## Not in this design (deferred)

- **Distributed indexing** — single-host is enough for 20K docs; revisit at 200K+
- **Priority queues** — not needed for our workload (every doc equal)
- **Streaming embedding** — Ollama doesn't support; not worth the complexity
- **Reranker integration** — separate concern (PR #1098/#1100), separate sidecar
- **Auth on :47780** — bind to `127.0.0.1` only, same trust model as Ollama

## Implementation milestones

1. **M1**: Job table migration + `enqueueIndexJob()` helper. ~30 LOC. Lands as a first PR (against alpha) — purely additive, doesn't change `arra_learn` yet.
2. **M2**: `services/indexer/` daemon with worker loop, no daemon API. Just polls and processes. ~150 LOC. Run manually for testing.
3. **M3**: Daemon API (`/index`, `/jobs`, `/events`, `/health`, `/drain`). ~100 LOC.
4. **M4**: CLI (`arra-indexer scan/backfill/daemon/status/cancel`). ~80 LOC.
5. **M5**: Switch `arra_learn` to enqueue (the 10-LOC diff). FTS-first / vector-later goes live.
6. **M6**: Backfill any legacy un-embedded docs.
7. **M7**: (Optional) Drop the inline `vectorStore.addDocuments()` codepath.

Total new code: ~360 LOC + the 10-LOC switch in `arra_learn`. Each milestone is a separate PR.

## Open questions (for next iteration)

1. **Embedded vs sidecar daemon?** Could the daemon run inside arra-oracle-v3's process (a worker thread). Pro: simpler deploy. Con: defeats crash isolation. Recommendation: separate process.
2. **Retry policy?** Exponential 1s/4s/16s/1m/5m, then give up. Configurable via env.
3. **Sharing oracle.db** — is WAL safe with two writers? Yes for SQLite WAL, but worth a stress test.
4. **Should the daemon also handle the reranker sidecar's lifecycle?** No — separate concerns. Each sidecar runs independently under pm2 or similar.

## Companion vault doc references

- `2026-05-04_plug-play-embedding-architecture.md` — the invariants this design must respect
- `2026-05-04_thai-embedding-benchmark-result.md` — why bge-m3 is the primary model that the daemon defaults to
- `2026-05-04_reranker-sidecar-empirical.md` — why reranker is a separate concern from indexing
