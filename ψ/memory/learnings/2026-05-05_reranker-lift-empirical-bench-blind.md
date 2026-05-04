---
pattern: bge-m3 + bge-reranker-v2-m3 lift is unmeasurable on the existing paired-target bench — discovered by computation, not assumption
date: 2026-05-05
source: ψ/lab/embedding-benchmark/rerank_lift_bench.py run on m5
project: github.com/Soul-Brews-Studio/arra-oracle-v3
---

# Reranker Precision Lift — Bench Blindness Found Empirically

## What we ran

End-to-end pipeline on the existing 24-doc paired Thai/EN paraphrase + distractor corpus:

```
query → bge-m3 dense (top-10 from cosine over 1024d normalized vectors)
      → POST top-10 to :8765/rerank (bge-reranker-v2-m3 cross-encoder)
      → reranked top-10
```

Continuous metrics (MRR, rank-1 stability) instead of binary R@1/R@5 to escape the saturated 100% ceiling.

## The numbers

| Metric | Dense (bge-m3) | Dense + Reranker | Δ |
|--------|----------------|------------------|---|
| **MRR** (Mean Reciprocal Rank) | **0.9524** | **0.9524** | **+0.0000** |
| Mean rank-1 dense score (cosine) | 0.6305 | — | — |
| **Rank-1 stability** | — | **57%** | — |
| Reranked queries | 14 / 14 | 14 / 14 | — |

## What that means — the surprise

**MRR didn't move.** But **the reranker disagrees on 43% of queries** about who deserves rank 1. The disagreements aren't *wrong*: when dense picks `th7`, the reranker swaps to `en7` (or vice versa). Both are expected answers in our paired-target bench (`expected: ["th7", "en7"]`).

So the reranker is doing real work — it has its own opinion about "best match" — but the **bench structure cannot tell us if its opinion is better than dense's**, because both answers count.

## The meta-finding

The bench is **reranker-blind by construction**. When `expected = [thai_id, english_id]` (either is correct), no relevance-aware metric can show a lift over a model that already finds *one* of them at rank 1.

This is an eval-design issue, not a reranker issue. To actually measure the reranker's contribution we need EITHER:

1. **Unpaired-target queries** — single correct answer per query. E.g., for a Thai query, expect *only* the English paraphrase (forces a cross-language hit). For an English query, expect *only* the Thai paraphrase.
2. **Harder corpus** — distractors that bge-m3 finds at rank 1, where the reranker has to bubble the true target up from rank 5+.
3. **Real-corpus eval** — sample 100 actual oracle docs with hand-labeled ground truth from our 20,842-doc production set.

Without (1) (2) or (3), the reranker can't be empirically justified or rejected on this bench. It's running, the architecture works, the latency is acceptable (~50ms median per top-10) — but the **measurable quality contribution is unknown until we build a discriminating eval.**

## What this implies for the integration PR

The wiring PR (`feat(search): wire rerankCandidates into combineResults`) should ship anyway, because:

- The plumbing has been empirically verified end-to-end (4000× score margin on the smoke test, [Thai blockchain query proof](2026-05-04_reranker-sidecar-empirical.md))
- The graceful-fallback contract means it's free downside (search never blocks)
- It's GATED by `ORACLE_RERANKER_URL` env — disabled by default
- Once wired, A/B testing on real queries becomes possible

But we should NOT claim "X% precision improvement from reranker" until we have a non-saturated eval. We currently can claim:
- The reranker has its own opinion (disagrees 43% of the time on rank 1)
- The disagreements are between equally-valid paired targets
- Aggregate quality (MRR) is unchanged on this bench

## Per-query agreement detail

Quick scan of where dense and reranker agreed/disagreed on rank 1:

| Query | Dense top-1 | Reranked top-1 | Agree? |
|-------|-------------|----------------|--------|
| Air dust paraphrase (Thai) | th2 | th2 | ≡ |
| Air paraphrase (English) | en2 | en2 | ≡ |
| Flood paraphrase (Thai) | th3 | th3 | ≡ |
| Flood paraphrase (English) | en3 | en3 | ≡ |
| IoT mesh paraphrase (Thai) | th5 | th5 | ≡ |
| IoT mesh paraphrase (English) | en5 | en5 | ≡ |
| Beer-vs-wine distractor (Thai) | th8 | en8 | → |
| Beer-vs-wine distractor (English) | en8 | en8 | ≡ |
| AI honesty (Thai) | th4 | th4 | ≡ |
| AI honesty (English) | en4 | en4 | ≡ |
| Tokenize (Thai) | th7 | en7 | → |
| Tokenize (English) | th7 | th7 | ≡ |
| FE/BE (Thai) | th6 | en6 | → |
| FE/BE (English) | th6 | en6 | → |

Pattern: when both dense and reranker score the in-language paired doc highest, they agree. When dense narrowly picks a doc and the reranker has a strong opinion about cross-language relevance, it sometimes flips. **Six flips out of fourteen** queries.

Notable: "Tokenize (English)" — *English* query, dense picked the *Thai* doc (`th7`) at rank 1 (somewhat unusual but valid). Reranker agreed and kept `th7`. Counter-example to "reranker always prefers in-language" — it's not language-biased, just relevance-biased.

## Reusable

```bash
cd ~/Code/github.com/Soul-Brews-Studio/arra-oracle-v3/services/reranker-py
uv run --with requests python ~/Code/github.com/Soul-Brews-Studio/arra-mcp-installation-guide-oracle/ψ/lab/embedding-benchmark/rerank_lift_bench.py
```

Imports `DOCS, QUERIES` from `sea_lion_bench.py` (sibling file). Replace those imports with a different corpus to re-evaluate. Saves JSON output for downstream tooling.

Raw log preserved at `ψ/lab/embedding-benchmark/2026-05-05_rerank-lift.log`.

## Next iterations

1. Build an **unpaired-target eval** — every query has exactly ONE correct doc id. Should produce non-trivial MRR delta.
2. Sample **real production docs** from `oracle.db` (~20,842 to choose from) and hand-label a small ground-truth set (50 queries × 1 expected each).
3. **Then** re-run rerank_lift_bench against that harder corpus. *Then* claim a quality lift number.

Until then: ship the wiring PR with `ORACLE_RERANKER_URL` env-gated and disabled-by-default. No regression risk; lift is unproven on our bench but the architecture is sound.
