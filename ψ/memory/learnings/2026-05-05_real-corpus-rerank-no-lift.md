---
pattern: Real-corpus rerank lift = 0 on 12-query smoke against live hybrid index — smoke-test +14.3 pts did NOT transfer to the production pipeline
date: 2026-05-05
source: ψ/lab/embedding-benchmark/real_corpus_rerank_bench.py against arra-oracle-v3:47778
project: github.com/Soul-Brews-Studio/arra-oracle-v3
---

# Real-Corpus Rerank — Empirical Surprise: Zero Lift

## Setup

12 hand-labeled cross-language queries against the **live production hybrid index** (20,842 docs, FTS5 + bge-m3 dense, on `:47778`). Each query had an expected doc-id substring. For each:

1. `GET /api/search?q=<query>&limit=20&mode=hybrid` → 20 ranked hybrid results
2. Find rank of expected doc-id in those 20
3. POST top-20 contents to `:8765/rerank` → reordered
4. Find rank of expected doc-id again

Same query, same candidate pool, only difference is the reranking pass.

## Result

| Metric | Hybrid (FTS+bge-m3) | Hybrid + Reranker | Δ |
|--------|---------------------|-------------------|---|
| Queries succeeded | 11 / 12 | 11 / 12 | — |
| Target not in top-20 | 5 | 5 | — |
| **R@1** | **54.5%** | **54.5%** | **+0.0 pts** |
| **MRR** | **0.5455** | **0.5455** | **+0.0000** |
| Flips toward correct | — | **0** | — |
| Flips away from correct | — | **0** | — |

**The reranker did not change rank 1 on any of the 12 queries.** Where the production hybrid had the target at #1, reranker agreed. Where the hybrid didn't have the target at all (5 queries with target outside top-20), the reranker couldn't recover it.

## Yesterday's smoke test was +14.3 pts. Why not here?

Hypothesis: the smoke test was a STRESS TEST of cross-lingual semantic retrieval — 24 docs, paraphrase queries with no keyword overlap, distractor docs sharing vocabulary. That's where bge-m3-dense alone struggled (43% R@1) and the reranker rescued recall (+14.3 pts).

The production pipeline isn't dense-only. It's **FTS5 + dense hybrid with a 10% boost for hits in both**. The FTS5 keyword leg compensates for cross-lingual semantic mismatches when ANY keyword is shared (technical terms, named entities, code identifiers — common in our corpus). By the time results reach top-20 of the hybrid, they're already mostly correct, and reranking has nothing material to fix.

In other words: **on a corpus where keyword recall is strong, the reranker has no precision lift to add over the existing hybrid pipeline.**

## What's NOT proven by this 12-query sample

- The reranker is useless. Cross-lingual queries with NO shared vocabulary (the smoke-test condition) still benefit. Most production queries do have shared technical vocab — that's why hybrid works — but edge cases exist.
- Production R@1 is fine. 54.5% R@1 is *low*. Half of my hand-labeled queries didn't put the expected doc at rank 1. Either:
  - My labeling is bad (the corpus has multiple equally-valid matches and I picked the wrong canonical one)
  - The hybrid retrieval is actually missing things
  Either way, **rank-1 quality is not "solved" — but the reranker isn't the right knob.**
- The reranker is broken. It's running, scoring, returning results. It just agrees with hybrid on every rank-1 we tested.

## Labeling caveat — important

5/12 of my "expected doc" picks weren't even in the API's top-20 results. Looking at the actual rank-1 returned:

| My target | API rank-1 |
|-----------|------------|
| `maw-sync-best-practices` | `git/2025-12-28_git-c-not-cd_0` (different but on same topic) |
| `incarnation-vs-birth-oracle-identity` | `oracle-philosophy-recursive-reincarnation-session` (different but related) |
| `tong-claude-code-training` | `mobile-oracle-session-pattern` (different mobile session) |
| `maeon-craft-oracle-birth-analysis` | (couldn't find a match) |

The corpus is *denser* than I assumed. For most topics there are multiple chunks across multiple sessions, and any of them could legitimately be rank 1. My eval treats only ONE id as correct, which under-counts cases where the API found a perfectly-good alternative.

A more honest eval would mark cases where rank-1 is "topically correct but not the specific id I picked" as partial-credit. That requires manual review of each result, which is real labor — and would lower our confidence interval rather than raise it.

## Implication for the wiring PR (#1101)

The PR body already includes the smoke-test number with caveats:

> *"R@1 42.9% → 57.1% (+14.3 pts) on a 14-query unpaired-target Thai/EN smoke test. Caveats: 14 queries is a smoke test, not a production regression baseline. Real-corpus eval pending."*

This iteration's result **strengthens the caveat**: real-corpus showed +0. Updating the PR body to reflect both numbers honestly:

- Smoke test (synthetic, stress-test of cross-lingual): **+14.3 pts R@1**
- Real corpus (production hybrid index, 12 queries): **+0.0 pts R@1**
- The truth is in between, depends on query distribution

This doesn't kill the PR — env-gated default-off means zero regression risk. It DOES kill any "ship reranker enabled by default" plan. The reranker stays available to operators who hit cross-lingual edge cases; the production default stays hybrid-only.

## Recommendation

1. **Leave the wiring PR env-gated** (already the design). Operators opt in.
2. **Update PR #1101 body** to cite both numbers (smoke +14.3, real-corpus +0) with the explanation of why.
3. **Don't claim a production lift number.** The 12-query real-corpus eval can't support one.
4. **A real production claim needs**:
   - 100+ queries (statistical significance)
   - Stratified sampling by query type (cross-lingual, monolingual, code, prose)
   - Multi-rater hand labeling (or at least: partial-credit for topical match)
   - Or: A/B telemetry from real users against an opt-in flight
5. **Reranker is NOT useless**: smoke test confirms it works on the hard cross-lingual case. It's just not a universal lift over an already-strong hybrid pipeline.

## What this teaches about evaluation

> "We measured. The result wasn't what the smoke test predicted. We're saying so." — this iteration

The lesson is structural: **stress-test benches show capability ceilings; production benches show production behavior**. The reranker has the cross-lingual capability (smoke test). It rarely needs to exercise that capability in production (real corpus). Both are true. Both go in the PR description.

## Reusable

```bash
cd ~/Code/github.com/Soul-Brews-Studio/arra-oracle-v3/services/reranker-py
uv run --with requests python ~/Code/github.com/Soul-Brews-Studio/arra-mcp-installation-guide-oracle/ψ/lab/embedding-benchmark/real_corpus_rerank_bench.py
```

Hand-labeled `EVAL` array at the top of the file. Edit to add more queries — once you reach 50+ with reviewed labels, this becomes a real regression baseline.

Raw log: `ψ/lab/embedding-benchmark/2026-05-05_real-corpus-rerank.log`.

## Connecting to the "don't fake the metric" memory

This is exactly what the feedback memory was for. The smoke test gave us +14.3 pts. The production eval gave us +0. We could have:

- ❌ Reported only the +14.3 pts number from the smoke test ("up to +14.3 pts!")
- ❌ Buried the +0 result and waited for a friendlier eval
- ✅ Reported both, explained why they differ, recommended the right action

The third option is what shipped.
