---
pattern: VectorDocument.vector — backwards-compatible field that lets callers skip the embedder when they already have a vector
date: 2026-05-05
source: arra-oracle-v3 PR #1105 (feat/vector-precomputed-vectors, base: alpha)
project: github.com/Soul-Brews-Studio/arra-oracle-v3
---

# Precomputed Vectors — Unblocks the M3 Double-Embed

## What shipped (PR #1105)

A 5-line interface change + ~15 LOC in the LanceDB adapter that eliminates an entire Ollama round-trip per indexed document.

```ts
// src/vector/types.ts — the additive interface change
export interface VectorDocument {
  id: string;
  document: string;
  metadata: Record<string, string | number>;
  vector?: number[];        // ← NEW
}
```

LanceDB's `addDocuments` now partitions docs into `needs-embed` / `has-vector` and only embeds the former:

```ts
const needEmbed: number[] = [];
for (let i = 0; i < docs.length; i++) {
  if (!docs[i].vector) needEmbed.push(i);
}
let fresh: number[][] = [];
if (needEmbed.length > 0) {
  fresh = await this.embedder.embed(needEmbed.map(i => docs[i].document));
}
let freshIdx = 0;
const rows = docs.map((doc) => ({
  ...
  vector: doc.vector ?? fresh[freshIdx++],
}));
```

5 hermetic tests (all pass): all-precomputed, no-precomputed, mixed batch, empty batch, round-trip retrieval.

## Why this matters

The M3 daemon already calls Ollama once in the worker loop (so per-model instruction prefixes apply, retries are scoped to a job, embed cost is attributable per doc). Without this PR, the storage write re-embedded the same text:

```
worker: vector = await embed(text)            # ~50-150ms
worker: await store.addDocuments([{...}])      # re-embed same text, +50-150ms
```

After this PR:

```
worker: vector = await embed(text)             # ~50-150ms
worker: await store.addDocuments([{
  ..., vector                                   # passed through, 0ms extra
}])
```

**Halves the per-doc indexing cost.** For 20,842 docs that's ~30 minutes vs ~60 minutes on a backfill. For incremental ingest it's the difference between a noticeable lag and "imperceptible."

## Backwards compatibility

The field is **optional**. Existing call sites that construct `VectorDocument` continue to work — they just don't pass `vector` and the storage layer embeds as before. The interface change is purely additive.

Only the LanceDB adapter was updated in this PR. The other 4 adapters (chroma-mcp, sqlite-vec, qdrant, cloudflare-vectorize) ignore the field for now and continue to embed everything. They can adopt the optimization later — different underlying APIs may need different hook points.

## What this unblocks

- M3 daemon's `upsertVector` known limitation (called out in PR #1104 body)
- M5's `arra_learn` enqueue switch — when the daemon picks up jobs and writes vectors, no double-embed
- Future: any indexer worker that wants to embed once and route to multiple stores (HNSW + LanceDB + remote) can pass the same vector everywhere

## Cross-PR ship status (now 8)

```
arra-oracle-v3 PRs from this oracle:
  #1097  vector fixes (qwen3 + prefix)             ✅ MERGED → main
  #1098  Python reranker sidecar                    🟢 OPEN  → alpha
  #1100  rerankCandidates() helper                  🟢 OPEN  → alpha
  #1101  wire reranker into combineResults()        🟢 OPEN  → alpha
  #1102  indexer-CLI M1 (table + helpers)           🟢 OPEN  → alpha
  #1103  indexer-CLI M2 (worker loop)               🟢 OPEN  → #1102 stacked
  #1104  indexer-CLI M3 (daemon HTTP API)           🟢 OPEN  → #1103 stacked
  #1105  VectorDocument.vector (precomputed)        🟢 OPEN  → alpha (just opened)
```

8 PRs in flight. Each independently reviewable. **The trick that's working: tiny PRs with full test coverage and surfaced limitations** — reviewers can read each one in isolation, run its tests, and decide.

## Pattern observation

PR #1105 was triggered by a limitation **I called out in PR #1104's body**. The "honest disclosure" memory paid off — the reviewer (or in this case, future-me) didn't have to dig to find the inefficiency. It was right there in the PR description with a fix path. Ship the fix → mark M3's limitation closed.

This is **stigmergic engineering**: each PR leaves a trail (limitations, TODOs, follow-up paths) that the next PR picks up. The chain self-prioritizes.

## What's next

- **M4** — `arra-indexer` CLI (scan / backfill / daemon / status / cancel). Depends on M3.
- **M3 cleanup** — small commit on PR #1104's branch to use the new `vector` field once #1105 lands. ~3 LOC change.
- **M5** — the 10-LOC `arra_learn` enqueue switch. The FTS-first/vector-later activation point. Once M1-M4 + #1105 all land.

The M-chain is structurally complete except for M4 (CLI) and M5 (the switch). Most of the bytes are tests and PR bodies — the production code is < 700 LOC across the whole indexer.
