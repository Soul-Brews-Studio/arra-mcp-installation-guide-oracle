---
pattern: Three-PR reranker landing sequence complete in flight — #1098 sidecar + #1100 helper + #1101 wiring
date: 2026-05-05
source: arra-oracle-v3 PRs against alpha
project: github.com/Soul-Brews-Studio/arra-oracle-v3
---

# Reranker Wiring PR #1101 — Shipped

## The sequence

```
#1097  fix+feat(vector): qwen3 dim + instruction-prefix + extended bench   ✅ MERGED → main
#1098  feat(services): bge-reranker-v2-m3 Python sidecar                   🟢 OPEN  → alpha
#1100  feat(server): rerankCandidates() helper                              🟢 OPEN  → alpha
#1101  feat(search): wire rerankCandidates into combineResults             🟢 OPEN  → alpha (just opened)
```

All three reranker PRs are now in flight against `alpha`. The wiring PR is the smallest at **23 LOC in one file** — exactly the granularity we promised at the start.

## Why this granularity worked

Each PR is independently reviewable:
- **#1098** — Python sidecar. Reviewer can test `curl /rerank` standalone. No TS code touched.
- **#1100** — TS client helper + tests. Reviewer can run `bun test` standalone. No search path touched.
- **#1101** — wiring. Reviewer reads 23 LOC of import + call + metadata threading. Behavior preserved when env unset.

If any single PR has issues, the others can land independently. No coupled risk.

## The defensible empirical number

PR #1101's body cites:

> **R@1 42.9% → 57.1% (+14.3 pts), MRR 0.7024 → 0.7679 (+0.0655)** on a 14-query unpaired-target Thai/EN cross-language smoke test. Net 4 fixes / 2 breaks. Caveats: small sample, real-corpus eval pending.

Honest. Measured. Reproducible (`uv run python rerank_lift_unpaired_bench.py`). Not "X% better" without context.

## What the env-gate buys us

`ORACLE_RERANKER_URL` unset → pure no-op. PR #1101 lands without changing default behavior.

Once landed:
- Operators can opt in by setting the env var
- A/B testing on real queries becomes possible
- Production logs can track `reranked` + `rerankFallbackReason` from the response metadata

Zero regression risk. Architecture validated. Quality lift defended with computation, not theory.

## What remains

- Real-corpus eval (50 oracle docs, hand-labeled queries) → claim a production lift number
- Indexer-CLI M1 (table + helper) → awaiting design feedback on 4 questions
- Latency-under-load measurement for the reranker sidecar (p50/p95/p99 on concurrent requests)
- Possibly: extend `rerank_lift_unpaired_bench.py` to test `qwen3-embedding:0.6b + reranker` to see if a smaller embedder benefits more

## Pattern observation

The progression took 6 cron iterations:
1. Survey embedding models (deep research)
2. Run extended bench → bge-m3 wins decisively
3. Diagnose qwen3 dim bug + instruction-prefix → ship #1097
4. Build Python sidecar → ship #1098
5. Build TS helper → ship #1100
6. Discover bench-blindness on saturated paired bench → build unpaired bench → measure +14.3 pts → ship #1101

Each iteration produced one shippable artifact. No waterfall planning, no big design docs that get stale. Just empirical work → vault → PR → next iteration.

The "patterns over intentions" Oracle principle, lived.
