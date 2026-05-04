---
pattern: M4 of indexer-CLI shipped — subcommand CLI with parseCli + dispatcher, 25 hermetic tests, dynamic-imports daemon for the read paths
date: 2026-05-05
source: arra-oracle-v3 PR #1106 (feat/indexer-cli-m4, base: feat/indexer-daemon-m3)
project: github.com/Soul-Brews-Studio/arra-oracle-v3
---

# Indexer-CLI M4 — CLI Surface Landed

## What shipped (PR #1106)

5 subcommands: `status / enqueue / cancel / daemon / help`. Built on Bun's `util.parseArgs` shape (well, a tiny custom parser since `parseArgs`'s positionals API is awkward) — zero npm deps.

```
arra-indexer status [--model <key>] [--status <state>] [--limit <n>]
arra-indexer enqueue <doc_id> [--model <key>]
arra-indexer cancel <job_id>
arra-indexer daemon                    # M3 entrypoint
arra-indexer help
```

`status / enqueue / cancel` operate directly on the SQLite queue — no daemon needed, useful for inspection and one-off admin. `daemon` dynamic-imports `./daemon.ts` so the CLI doesn't pull LanceDB / Hono / Ollama deps for the read paths.

## Test coverage — 25 hermetic cases

`parseCli` (7), `cmdStatus` (5), `cmdEnqueue` (4), `cmdCancel` (4), `cmdHelp + dispatch` (5).

Combined indexer suite: **66 pass / 0 fail / 171 expects across M1+M2+M3+M4.**

## Cancel safety — pending only

```sql
UPDATE indexing_jobs
SET status = 'error', finished_at = ..., error = 'cancelled by CLI'
WHERE id = ? AND status = 'pending'
```

Claimed jobs are mid-embed; cancelling them would write 'error' on a row the worker is about to overwrite with 'done'. Returns exit 1 + stderr if no pending row matched.

This is the same kind of invariant as M1's `reclaimStaleJob` (no-op on terminal states): each function in the indexer-CLI **knows the invariants it protects**. The "M-chain" isn't a bunch of files; it's a bunch of small, defensible functions.

## Pure dispatch — the architectural through-line

```ts
export const COMMANDS: Record<string, SubcommandFn> = {
  status: cmdStatus, enqueue: cmdEnqueue, cancel: cmdCancel, help: cmdHelp,
  '': cmdHelp, '--help': cmdHelp, '-h': cmdHelp,
};

export async function dispatch(argv: string[], deps: CliDeps) {
  const args = parseCli(argv);
  if (args.subcommand === 'daemon') {
    await import('./daemon.ts');  // heavy deps loaded only here
    return 0;
  }
  return await (COMMANDS[args.subcommand] ?? cmdHelp)(deps, args);
}
```

The same DI pattern from M2/M3 carries through M4: pure functions, deps as parameters, dispatch table for routing. Tests inject mock `out`/`err`. Production wires `process.stdout.write` / `process.stderr.write`.

## Cross-PR ship status (now 9)

```
arra-oracle-v3 PRs from this oracle:
  #1097  vector fixes (qwen3 + prefix)             ✅ MERGED → main
  #1098  Python reranker sidecar                    🟢 OPEN  → alpha
  #1100  rerankCandidates() helper                  🟢 OPEN  → alpha
  #1101  wire reranker into combineResults()        🟢 OPEN  → alpha
  #1102  indexer-CLI M1 (table + helpers)           🟢 OPEN  → alpha
  #1103  indexer-CLI M2 (worker loop)               🟢 OPEN  → #1102 stacked
  #1104  indexer-CLI M3 (daemon HTTP API)           🟢 OPEN  → #1103 stacked
  #1105  VectorDocument.vector (precomputed)        🟢 OPEN  → alpha
  #1106  indexer-CLI M4 (CLI subcommands)           🟢 OPEN  → #1104 stacked
```

9 PRs in flight, 1 merged, 8 open. The indexer M-chain (M1→M2→M3→M4) is structurally complete. M5 — the 10-LOC `arra_learn` switch that flips FTS-first/vector-later live — is the only thing remaining.

## What would unlock M5

M5's diff is tiny: replace `vectorStore.addDocuments([...])` in `arra_learn` with `enqueueIndexJob(db, { docId, models })`. 10-15 LOC.

But it needs:
1. M1 (table + helpers) on alpha
2. The daemon process running (M2+M3)
3. Otherwise enqueued jobs sit forever

So the M5 PR can either:
- Land after M1-M4 all merge to alpha (hard dependency)
- Land with a feature flag (`ORACLE_INDEXER_ENQUEUE_ONLY=1`) that's off by default, on once the operator starts the daemon

The flag approach is more flexible. Adds a small env check in `arra_learn`. Default off → existing inline-embed behavior preserved. Flag on → enqueue. Operators flip the flag when they're ready.

This is the "ship env-gated default-off" pattern from the reranker work (PR #1101). Same playbook applies to ingest.

## Lines so far

| PR | Title | LOC |
|----|-------|-----|
| #1102 | M1 (table + helpers) | 429 |
| #1103 | M2 (worker loop) | 393 |
| #1104 | M3 (daemon HTTP API) | 554 |
| #1106 | M4 (CLI) | 539 |
| **Total** | **indexer-CLI** | **1,915 LOC** |

Production code ~900, tests ~1,000. Tests dominate by design — they enable the stacked-PR shape without merge anxiety.

## What's next

- **M5** with feature flag — small, ships independently of M1-M4 merge order
- `scan` and `backfill` CLI subcommands (the "beefier" deferred ones from M4)
- `arra_learn` integration — once M5 lands and the flag flips on, FTS-first/vector-later goes live empirically
