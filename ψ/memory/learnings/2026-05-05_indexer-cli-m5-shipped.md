---
pattern: M5 of indexer-CLI shipped — env-gated FTS-first/vector-later switch in arra_learn, M-chain complete
date: 2026-05-05
source: arra-oracle-v3 PR #1107 (feat/arra-learn-enqueue-m5, base: feat/indexer-jobs-table-m1)
project: github.com/Soul-Brews-Studio/arra-oracle-v3
---

# Indexer-CLI M5 — The Activation Point Lands

## What shipped (PR #1107)

The 10-LOC switch. After `arra_learn` writes its FTS5 row, an env-gated branch enqueues one job per registered model into `indexing_jobs`. The daemon (M2 worker loop / M3 entrypoint) picks them up asynchronously.

```ts
if (process.env.ORACLE_INDEXER_ENQUEUE === '1') {
  try {
    enqueueIndexJob(ctx.sqlite, { docId: id, models: getEmbeddingModels() });
  } catch (e) {
    console.warn('[arra_learn] enqueue failed:', e instanceof Error ? e.message : String(e));
  }
}
```

That's it. 11 lines of production diff.

## Plot twist mid-iteration

Started building M5 expecting to **switch from inline-embed to enqueue** (per the design doc). When I read alpha's `learn.ts`, **there was no inline embed** — alpha's `arra_learn` writes FTS5 and returns. The vector embedding was missing entirely on the alpha branch.

Then a system reminder surfaced the MAIN version of `learn.ts` — which DOES have inline embedding (with graceful fallback, embedding status tracker, idempotent FTS5 delete-then-insert, the works). Plus a separate logic path that I'd need to handle when alpha catches up.

So the M5 design held but the **base state was different** than expected. Two scenarios:

1. **Now (alpha base)**: M5 = pure addition. Add enqueue gated by env. No inline embed to remove.
2. **After alpha catches up to main**: alpha will inherit the inline embed. Need to decide: (a) remove the inline embed when env=1, (b) skip-enqueue for the model that inline already covered, (c) accept the double-write.

I went with scenario 1 for this PR — simplest, correct against the current alpha. The maintainers (or a future cron tick) reconcile on catchup.

This is the "anticipate branch catchup" memory in action again, applied to a different domain than migration numbering. **Whenever you patch on a stale branch, look at what the catchup will bring** — sometimes it changes the architecture of the patch itself.

## Why env-gated default-off

Same playbook as the reranker ship (PR #1101). Same posture:

- Land without flipping the switch — zero behavior change for anyone who hasn't set the env var
- Existing `learn.test.ts` (12 pure-helper tests) passes UNCHANGED — backwards compat baked in
- No orphan jobs accumulate if daemon isn't running (the env gate protects against that)
- Operators flip the switch per-host **after** the daemon is up and consuming
- Reversible: unset the env var, restart, enqueue stops, FTS5 ingest unchanged

This is the pattern: **architecture validation ≠ feature activation**. PRs land architecture; flags activate features. They're separable concerns.

## Strict equality on '1'

`process.env.ORACLE_INDEXER_ENQUEUE === '1'`, not truthiness. Typo'ing `'true'` or `'yes'` silently keeps the gate closed rather than activating an opt-in feature accidentally. There's a dedicated test for this — try value `'true'`, expect 0 jobs enqueued.

This is small but matters. Truthy env flags lead to confusing prod surprises. Strict equality forces the operator to be precise about what they want.

## Graceful degrade — the third invocation of the same memory

```ts
try { enqueueIndexJob(...); }
catch (e) { console.warn('[arra_learn] enqueue failed:', ...); }
```

The try/catch around the enqueue is the same posture as:
- Reranker fallback (PR #1100)
- Worker error path (PR #1103, M2)
- M3 SSE bus subscriber try-catch (PR #1104)

**Never block the primary path on an optional secondary**. Test verifies: drop the `indexing_jobs` table mid-test → enqueue throws → ingest still succeeds → log surfaces the reason.

## Tests (4 hermetic, plus 12 backwards-compat)

```
src/tools/__tests__/learn-enqueue.test.ts → 4 pass / 0 fail
  - default (env unset) → 0 jobs enqueued, FTS still written
  - ORACLE_INDEXER_ENQUEUE=1 → one job per registered model
  - enqueue throws (DROP TABLE) → ingest still succeeds (graceful)
  - non-'1' value → no enqueue (strict equality)

src/tools/__tests__/learn.test.ts → 12 pass / 0 fail (unchanged)
  - All pure-helper tests work without any modification → backwards compat
```

Combined indexer chain: M1 (16) + M2 (11) + M3 (14) + M4 (25) + M5 (4) = **70 hermetic tests across the chain.**

## The chain is now complete

```
arra-oracle-v3 PRs from this oracle:
  #1097  vector fixes (qwen3 + prefix)              ✅ MERGED → main
  #1098  Python reranker sidecar                     🟢 OPEN  → alpha
  #1100  rerankCandidates() helper                   🟢 OPEN  → alpha
  #1101  wire reranker into combineResults()         🟢 OPEN  → alpha
  #1102  indexer-CLI M1 (table + helpers)            🟢 OPEN  → alpha
  #1103  indexer-CLI M2 (worker loop)                🟢 OPEN  → #1102
  #1104  indexer-CLI M3 (daemon HTTP API)            🟢 OPEN  → #1103
  #1105  VectorDocument.vector (precomputed)         🟢 OPEN  → alpha
  #1106  indexer-CLI M4 (CLI subcommands)            🟢 OPEN  → #1104
  #1107  indexer-CLI M5 (arra_learn enqueue)         🟢 OPEN  → #1102
```

10 PRs total. **9 currently open, 1 merged.** All 5 indexer milestones (M1-M5) shipped. Plus 3 reranker PRs (#1098/#1100/#1101). Plus 1 standalone interface improvement (#1105).

**Production code across the indexer-CLI**: ~900 LOC. Tests: ~1,100 LOC. Designs/docs: 1 long DESIGN.md + 8 vault learnings.

## Operational deployment recipe (post-merge of all 10 PRs)

1. Land #1097 (already merged) → vector fixes baseline
2. Land #1098 / #1100 / #1101 → reranker chain available
3. Land #1102 → indexing_jobs table exists
4. Land #1103 → worker loop is callable
5. Land #1104 → daemon entrypoint is runnable: `bun src/indexer/daemon.ts`
6. Land #1105 → daemon's upsertVector skips re-embed
7. Land #1106 → `arra-indexer status` is callable
8. Land #1107 → `arra_learn` knows how to enqueue
9. Operator: set `ORACLE_INDEXER_ENQUEUE=1` on the arra-oracle-v3 server
10. Operator: start `arra-indexer daemon` (e.g. via pm2)
11. Operator: restart arra-oracle-v3 server to pick up the env var
12. Make a test arra_learn call → check `arra-indexer status` for the new pending job
13. Watch the daemon process the job (SSE: `curl :47780/events`)
14. Verify the vector arrived in LanceDB

The flip is reversible: unset the env var and restart. Enqueue stops; existing FTS5 ingest resumes unchanged.

## What's next

The M-chain is structurally complete. Remaining work:
- `arra-indexer scan <path>` and `arra-indexer backfill --model X` subcommands (deferred from M4)
- Reconcile alpha's behavior with main's inline-embed when alpha catches up
- Real-corpus regression baseline (the deferred 50-100 query labeled eval)
- The 3 reranker PRs reviewing/landing
- Wrangler deploy story (still in the recurring user theme list, not yet touched)

The cron continues. Each iteration has shipped one concrete artifact since 2026-05-04.
