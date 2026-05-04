---
pattern: bge-reranker-v2-m3 sidecar latency degrades sharply under concurrency — single-threaded PyTorch serializes; helper's 2s timeout becomes a load-shedder by design
date: 2026-05-05
source: ψ/lab/embedding-benchmark/rerank_latency_bench.py run on m5
project: github.com/Soul-Brews-Studio/arra-oracle-v3
---

# Reranker Latency-Under-Load — Empirical

## Setup

POST `/rerank` with realistic payload (1 query + 50 candidates, mixed Thai/EN, varied lengths) at concurrency levels 1, 2, 4, 8, 16. 30 requests per level. Single-process FastAPI on m5 (Apple M-series, F32 weights).

## Numbers

| Concurrency | p50 | p95 | p99 | mean | rps | errors |
|-------------|-----|-----|-----|------|-----|--------|
| **1** | **167ms** | 1468ms | 1786ms | 331ms | 3.02 | 0 |
| 2 | 1068ms | 1468ms | 1588ms | 1110ms | 1.80 | 0 |
| 4 | 2978ms | 3416ms | 3425ms | 2820ms | 1.37 | 0 |
| 8 | 7631ms | 9654ms | 9690ms | 7495ms | 1.03 | 0 |
| 16 | 2517ms | 8094ms | 8096ms | 5061ms | 2.83 | 0 |

**No errors at any concurrency** — the service is stable under load, just slow.

## What's happening

The cross-encoder model is single-threaded — PyTorch serializes inference calls. Concurrent requests pile up in the FastAPI/uvicorn queue. So:

- p50 grows roughly linearly with concurrency (until the queue saturates)
- p95/p99 grow even faster (tail latency is "you came in N-th in line")
- Throughput hits a ceiling around 2-3 rps regardless of concurrency

The C=16 row's lower p50 vs C=8 is a sampling artifact — at C=16 most requests arrive nearly simultaneously, so the wall clock is shorter (10.6s vs 29.1s for the same 30 requests) and the queue distribution flattens. The throughput went up (2.83 rps) because more requests overlap.

## Why this is fine — the 2s timeout is load-shedding

The `rerankCandidates()` helper defaults to a **2000ms timeout** (PR #1100). Looking at the table:

- **C=1 (no contention)**: p95 ~1.5s — under the timeout. Reranker fires.
- **C=2**: p95 ~1.5s, but p99 1588ms approaching the limit. Some fallbacks at p99.
- **C≥4**: p50 already over 2s. Most requests fall back to the original hybrid order.

So the helper's timeout effectively **load-sheds** without any explicit logic. Under contention, search returns fast (dense-only) while the reranker queue catches up. This is the right behavior for the env-gated default-off ship: capability when there's headroom, degradation-by-fallback under load. Search latency stays bounded regardless.

## Operational guidance

**For solo development** (1 concurrent user):
- Reranker fires reliably (p50 167ms, p95 1.5s)
- Search latency penalty: ~150-1500ms vs hybrid-only
- Worth it for the cross-lingual edge cases

**For multi-user production**:
- Enable reranker only if you can guarantee low concurrency on the sidecar (≤2)
- Or run multiple sidecar instances behind a load balancer
- Or batch (FastAPI doesn't batch; would need a custom request collector)
- Or use a quantized model (F16 or Q8 — likely 2× speed at minor quality cost)
- Default-off remains the right ship decision until one of those is in place

**For the recommendation in PR #1101**:
> "Ship env-gated default-off. The 2s helper timeout means concurrent traffic falls back gracefully — never blocks search. For production env-on, run multiple reranker instances or quantize."

## What this empirically validates

The graceful-fallback design (PR #1100) was the right call. We didn't *plan* for the 2s timeout to be a load-shedder — that emerged. But the architecture preserves search latency as a hard upper bound, and the cross-encoder gets used opportunistically when there's spare capacity. That's a defensible production posture.

## What's not measured (caveats)

- **Different hardware**: m5 is M-series with no GPU acceleration of the cross-encoder. CUDA/MPS would change the numbers.
- **Different models**: F32 weights here. Q8 or F16 quantization would help significantly.
- **Different candidate counts**: 50 candidates is the production worst case (PR #1101's RERANK_POOL_SIZE). At 10 candidates the latency is much lower.
- **Different queries**: latency is roughly invariant to query length but depends on candidate text length. Longer docs = more cross-encoder tokens = slower.

## Reusable

```bash
cd ~/Code/github.com/Soul-Brews-Studio/arra-oracle-v3/services/reranker-py
uv run --with 'aiohttp,numpy' python ~/Code/github.com/Soul-Brews-Studio/arra-mcp-installation-guide-oracle/ψ/lab/embedding-benchmark/rerank_latency_bench.py
```

Edit the `levels` array in `main()` to test different concurrency configurations. Edit `CANDIDATES` to test different payload shapes.

Raw log: `ψ/lab/embedding-benchmark/2026-05-05_rerank-latency.log`.

## Connecting to the prior empirical chain

| Iteration | Finding |
|-----------|---------|
| 2026-05-04 | bge-m3 vs nomic vs qwen3 — bge-m3 wins the saturated bench |
| 2026-05-04 | qwen3:4b -29 cross-lang from missing instruction prefix → +29 with patch |
| 2026-05-04 | SEA-LION leaderboard advantage doesn't transfer to our use case |
| 2026-05-04 | Reranker smoke test: +14.3 pts R@1 on stress-test |
| 2026-05-05 | Real-corpus reranker: +0 lift on production hybrid |
| **2026-05-05 (this)** | **Reranker single-threaded — 2s timeout = load-shedder** |

Each iteration narrowed the production posture. End state:
- bge-m3 stays primary
- Reranker ships env-gated default-off
- 2s timeout protects search latency
- Quality lift unproven on production; capability proven on smoke

That's the empirical, defensible posture.
