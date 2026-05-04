---
pattern: rerankCandidates() helper for arra-oracle-v3 — graceful-fallback client for the bge-reranker-v2-m3 sidecar
date: 2026-05-04
source: arra-oracle-v3 PR #1100 (feat/reranker-helper, base: alpha)
project: github.com/Soul-Brews-Studio/arra-oracle-v3
---

# Reranker Helper — PR #1100

## Why a separate helper

Three concerns that can be cleanly separated:
1. **The sidecar process** (PR #1098) — Python, FastAPI, `BAAI/bge-reranker-v2-m3`
2. **The client to the sidecar** (this PR #1100) — TS helper with graceful fallback
3. **The integration into search** (next PR) — calls (2) at the right point in `combineResults()`

By landing each separately we get smaller diffs, independent review, and the helper can be unit-tested without standing up the sidecar.

## Graceful-fallback contract

`rerankCandidates({ query, candidates, getText, topK?, url?, timeoutMs? })` returns:

```ts
{ results: T[], reranked: boolean, fallbackReason?: string }
```

Search must **never** block on the reranker. Every error path returns the *input order* unchanged so the caller can be unconditionally:

```ts
const ranked = await rerankCandidates({ query, candidates, getText: c => c.text });
return ranked.results;  // reranked or original — both are valid
```

Fallback paths (each tested):

| Condition | Reason |
|-----------|--------|
| `ORACLE_RERANKER_URL` unset | `disabled` |
| Empty candidate list | (no fallback — empty in, empty out) |
| Single candidate | (no fallback — pass-through) |
| Non-OK HTTP | `http <status>` |
| Empty `results` array | `empty response` |
| Out-of-range indices | `no valid indices` |
| Network error / abort | `error` |
| Timeout (default 2000 ms) | `timeout 2000ms` |

## Test surface

`bun test src/server/__tests__/reranker.test.ts` → **9 pass / 0 fail**

Tests focus on the fallback paths since they're the contractual ones — the success path is empirically validated against the real sidecar (4000× score margin on a Thai blockchain query, documented separately at `2026-05-04_reranker-sidecar-empirical.md`).

## Targeted at `alpha`, not `main`

Per the fleet-wide convention surfaced in the previous iteration. PR #1100 is the first arra-oracle-v3 PR from this oracle to correctly target `alpha` from the start (PR #1098 was retargeted post-creation; #1097 already merged direct-to-main).

`alpha` is currently behind `main` on some tsc errors in `server-legacy.ts` and `handlers.ts` — `/release-alpha` will catch up. Noted in the PR body so reviewers know the noise isn't from this change.

## Three-PR landing sequence

```
#1097  fix+feat(vector): qwen3 dim + instruction-prefix + extended bench   [MERGED → main]
                         │
#1098  feat(services): bge-reranker-v2-m3 Python sidecar                   [OPEN → alpha]
                         │
#1100  feat(server): rerankCandidates() helper                             [OPEN → alpha]
                         │
[next] feat(search): wire rerankCandidates into combineResults             [PENDING]
```

The "next" wiring PR is the smallest of the four — ~10 lines. Waiting for #1098 + #1100 to land first so the wiring PR can `import { rerankCandidates }` from a real shipped path.
