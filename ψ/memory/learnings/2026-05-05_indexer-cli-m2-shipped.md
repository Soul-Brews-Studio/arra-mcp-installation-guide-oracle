---
pattern: M2 of indexer-CLI shipped — pure dependency-injected worker loop, 11 tests, hermetic
date: 2026-05-05
source: arra-oracle-v3 PR #1103 (feat/indexer-worker-m2, base: feat/indexer-jobs-table-m1)
project: github.com/Soul-Brews-Studio/arra-oracle-v3
---

# Indexer-CLI M2 — Worker Loop Landed

## What shipped (PR #1103)

`runWorker(modelKey, deps): Promise<WorkerStats>` — single-model claim/embed/upsert/mark-done loop. Pure dependency-injected function. No globals, no direct Ollama or LanceDB imports.

Stacked on PR #1102 (M1). Once M1 lands, this rebases trivially against alpha or merges into M1's branch.

## Loop semantics

```
while (!isShuttingDown()):
  job = claimNextJob(db, modelKey)
  if !job: idle event, sleep, continue
  text = getDocText(job.docId)
  if text is null:
    markJobDone (graceful no-op — doc was deleted)
    continue
  try:
    vector = await embed(modelKey, text)
    await upsertVector(collection, docId, vector)
    markJobDone
  catch err:
    markJobError(err.message)
    # does NOT poison the worker — next iteration claims next job
```

## Why dependency injection

The worker is the place where 3 different external systems converge: SQLite (jobs queue), Ollama (embedding), LanceDB (vector store). Hardcoding any of them would make the worker untestable without standing up all three.

By injecting:
- `getDocText(docId): string | null` — caller does `SELECT content FROM oracle_fts`
- `embed(modelKey, text): Promise<number[]>` — caller wires `OllamaEmbeddings`
- `upsertVector(collection, docId, vector)` — caller wires `LanceDBAdapter.insert`
- `isShuttingDown(): boolean` — caller flips on signal handler

We get:
- **11 hermetic unit tests** — no Ollama, no LanceDB, no real signals. `:memory:` SQLite + mocks.
- **M3/M4 wire the real adapters** without touching M2's logic.
- **Test for "embed throws → markJobError → keep processing"** is straightforward.

This is the same pattern as the reranker helper (`rerankCandidates()`) — pure function, deps as parameters, easy to compose.

## Events surface

```ts
type WorkerEvent =
  | { type: 'claimed'; job }
  | { type: 'done'; job; durationMs }
  | { type: 'error'; job; error }
  | { type: 'doc_missing'; job }
  | { type: 'idle'; modelKey };
```

M3's SSE `/events` endpoint will stream these. M2 itself just emits via the optional `onEvent` callback.

## Test coverage (11 cases)

**Happy path** (3): one job, FIFO order, claimed→done events.
**Errors** (3): embed throws, upsert throws, error doesn't poison subsequent jobs.
**Doc-missing** (1): null text → markJobDone, no embed/upsert call, doc_missing event.
**Shutdown** (2): immediate exit, in-flight job completes first.
**Empty queue** (1): emptyPolls counter, idle events.
**Plug-play** (1): bge-m3 worker leaves qwen3 jobs at status='pending' (model isolation).

The plug-play test is critical — it directly verifies the load-bearing invariant from yesterday's design doc. One worker per model means **never accidentally claims another model's job**.

## Bug-of-the-iteration

First test run had 10/11 pass. The doc-missing test failed because my mock used `??` (nullish coalescing):

```ts
getDocText: (id) => docTexts[id] ?? `synthetic content for ${id}`,
```

Problem: `??` returns the right side when left is `null` OR `undefined`. So `docTexts['doc-deleted']` being `null` got coalesced away into the synthetic fallback. The worker NEVER saw `null`.

Fix: explicit `in` check:

```ts
getDocText: (id) => (id in docTexts ? docTexts[id] : `synthetic content for ${id}`),
```

This is a recurring JS footgun. `??` is for "use default when ABSENT", not "use default when FALSY". For a map where `null` is a valid distinct value, `in` is the right check.

Worth filing under "be careful with nullish coalescing on maps that intentionally store null."

## Cross-PR ship status (now 6)

```
arra-oracle-v3 PRs from this oracle:
  #1097  vector fixes (qwen3 + prefix)             ✅ MERGED → main
  #1098  Python reranker sidecar                    🟢 OPEN  → alpha
  #1100  rerankCandidates() helper                  🟢 OPEN  → alpha
  #1101  wire reranker into combineResults()        🟢 OPEN  → alpha
  #1102  indexer-CLI M1 (table + helpers)           🟢 OPEN  → alpha
  #1103  indexer-CLI M2 (worker loop)               🟢 OPEN  → #1102 (stacked)
```

The stacking pattern is starting to show its strength: each PR is small (< 500 LOC), independently reviewable, builds on the previous, no merge-time surprises. M3 and M4 will continue stacking on M2's branch until M1 lands.

## Reusability observation

Both M1's `claimNextJob()` and M2's `runWorker()` accept a `Database` instance as a parameter. They never reach for a global db handle. Same for the reranker helper — it takes the URL/timeout as parameters.

Pattern: **the indexer queue infrastructure is a library**, not a service. Tests can compose it freely. Production wires it once, in one place. The "service" is M3 (daemon shell + HTTP routes), and even there the worker is just an injected dep.
