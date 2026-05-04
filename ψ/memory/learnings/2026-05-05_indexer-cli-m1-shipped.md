---
pattern: M1 of indexer-CLI shipped — indexing_jobs table + 6 helpers + 16 tests, purely additive, plug-play invariant tested
date: 2026-05-05
source: arra-oracle-v3 PR #1102 (feat/indexer-jobs-table-m1, base: alpha)
project: github.com/Soul-Brews-Studio/arra-oracle-v3
---

# Indexer-CLI M1 — Foundation Landed

## What shipped (PR #1102)

The first milestone of the indexer-CLI design — purely additive scaffolding. No behavior change. arra_learn still embeds inline.

**Schema**: new `indexing_jobs` table for per-doc per-model embedding jobs. Status tracked through `pending → claimed → done | error`. Partial index on `(status, model_key, created_at) WHERE status IN ('pending','claimed')` keeps queue scans fast as `done` rows accumulate.

**Helpers** (src/indexer/jobs.ts):

| Function | Purpose |
|----------|---------|
| `enqueueIndexJob` | Insert N rows (one per registered model when modelKey omitted) |
| `claimNextJob` | Atomic UPDATE…RETURNING; concurrent claimers can't double-claim |
| `markJobDone` | Terminal state, clears error |
| `markJobError` | Terminal state, preserves row + error message |
| `reclaimStaleJob` | Daemon-crash recovery: claimed → pending; no-op on terminal |
| `jobsByStatus` | Counts per (status, model_key); filterable |

**Tests**: 16 pass / 0 fail / 37 expects. Hermetic — `:memory:` SQLite, no filesystem touch.

## The plug-and-play invariant has a dedicated test

```ts
it('enqueues for newly-added model on next call without touching prior rows', () => {
  // doc-A enqueued with just bge-m3 (1 row)
  // qwen3 added to registry later
  // doc-B enqueued — both models get rows; doc-A's row UNTOUCHED
});
```

This is the load-bearing invariant from yesterday's design doc. Adding a model never disturbs existing queue entries. Removing one (just stop passing it in `models`) similarly leaves prior rows alone.

## Migration numbering — caught a forward-compatibility issue

While branched off `alpha`, the next migration index was `0007`. After pushing, system signals revealed that `main` has migrations `0007`–`0015` (the menu_items / forum series) that haven't reached alpha yet. When `/release-alpha` catches up, my `0007` would collide.

Fix: renumbered to `0016_indexing_jobs` in a small chore commit. Forward-safe — when alpha inherits 7–15, my 16 lands cleanly above.

This is a real consequence of "alpha-behind-main is fine" — alpha-targeted PRs need to anticipate what main will bring. Pattern for future PRs: **if the migration index is anywhere near the current alpha tail, check main's tail too and pick `max(alpha, main) + 1`**.

## Atomic claim — the key correctness primitive

```sql
UPDATE indexing_jobs
SET status = 'claimed', claimed_at = ..., attempts = attempts + 1
WHERE id = (
  SELECT id FROM indexing_jobs
  WHERE status = 'pending' AND model_key = ?
  ORDER BY created_at ASC
  LIMIT 1
)
RETURNING id, doc_id, model_key, collection
```

SQLite's row-level lock during UPDATE serializes concurrent claimers. Each gets a different row OR null. No "lost-update" hazard. The test for "claim doesn't re-claim already-claimed jobs" verifies this directly.

## What this PR does NOT do (deferred milestones, in dependency order)

- **M2** (~150 LOC): daemon worker loop. One worker per registered model. Polls + claims + embeds + writes to LanceDB.
- **M3** (~100 LOC): daemon HTTP API on `:47780` — `/index`, `/jobs`, `/events` (SSE), `/drain`, `/health`.
- **M4** (~80 LOC): `arra-indexer` CLI commands: `scan`, `backfill`, `daemon`, `status`, `cancel`.
- **M5** (~10 LOC): the `arra_learn` switch — replace inline `vectorStore.addDocuments()` with `enqueueIndexJob()`. **This is when FTS-first/vector-later goes live.**
- **M6**: `arra-indexer backfill --model bge-m3` to catch up legacy un-embedded docs.
- **M7**: drop the inline embedding codepath. Optional cleanup.

Each independently shippable. Rollback at any milestone is `git revert` — no data destruction (the table is append-only outside its own writes; existing oracle_documents/LanceDB collections are untouched).

## Connection to the empirical findings of yesterday/today

The reranker work proved **the architecture matters more than the model choice** at this scale. The indexer-CLI is the same insight applied to ingest:

- The model can change (plug-play); the table doesn't.
- The pipeline can change (FTS-first/vector-later); the queue contract doesn't.
- Crashes are isolated; rollback is git revert.

Same pattern: small invariants, sharp metrics, observable degradation.

## Ship status (cross-PR view)

```
arra-oracle-v3 PRs from this oracle, all targeting alpha:
  #1097  qwen3 dim + instruction-prefix + extended bench   ✅ MERGED → main
  #1098  Python reranker sidecar                            🟢 OPEN
  #1100  rerankCandidates() helper                          🟢 OPEN
  #1101  wire reranker into combineResults()                🟢 OPEN
  #1102  indexer-CLI M1 — table + helpers                   🟢 OPEN (just opened)
```

5 PRs in flight. Each is a discrete reviewable artifact. No PR depends on more than one other PR. The story tells itself if read in order.
