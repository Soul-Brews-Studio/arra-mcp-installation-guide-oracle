---
pattern: Thai-language RAG — bge-m3 is mid-pack on SEA-BED, our benchmark is saturated, architecture wins more than model swap
date: 2026-05-04
source: deep web research (MTEB, SEA-BED, HF, Ollama library, Thai NLP papers)
project: github.com/Soul-Brews-Studio/arra-oracle-v3
---

# Thai-Language RAG — Deep Research

## The meta-finding

**Our existing 16-doc paired benchmark is saturated.** bge-m3 hits 100% cross-language but that's not because it's the world's best Thai embedder — it's because the eval can't discriminate further on short paired docs. On the public **SEA-BED Thai** leaderboard (most credible Thai-aware bench), bge-m3 sits mid-pack at **77.59**, behind several open and paid models.

**Implication**: before claiming bge-m3 is the right primary forever, we need a *harder* Thai eval — 50+ docs, paraphrased queries, distractor-heavy negatives, long-form retros, mixed-script borrowed-word cases.

## SEA-BED Thai leaderboard (Aug 2025, all-tasks avg)

1. **Qwen3-Embedding-8B — 81.49** (#1 retrieval sub-score)
2. multilingual-e5-large-instruct — 81.11 (#1 clustering/STS)
3. Cohere embed-multilingual-v3.0 — 80.99 (paid)
4. bge-multilingual-gemma2 — 80.58 (9B, slow on M-series)
5. multilingual-e5-large — 79.89
6. jina-embeddings-v3 — 78.64 (CC-BY-NC, paid for commercial)
7. **bge-m3 — 77.59** ← we are here
8. snowflake-arctic-embed2 — XLM-R base, multilingual but Thai not specifically tuned

bge-m3 is competitive but **not the top**. The gap to the top open model is ~4 points on Thai.

## Practical shortlist (M-series + Ollama-pullable)

```bash
# A. Strongest plausible upgrade — Qwen family (mid)
ollama pull qwen3-embedding:4b           # 2.5 GB, 40k ctx, dim≤2560

# B. Same family, tiny — already pulled but blocked by code dim bug
ollama pull qwen3-embedding:0.6b         # 639 MB, 32k ctx, dim≤1024
                                         # (fix arra-oracle-v3 fallback dim first)

# C. Best <1B on SEA-BED Thai — community Modelfile
ollama pull qllama/multilingual-e5-large-instruct
                                         # 1024d, 512 ctx (caveat: chunk to <512 tok)

# D. Apache, multilingual, 8k ctx — bge-m3-class size
ollama pull snowflake-arctic-embed2      # 1.2 GB, 8192 ctx, 1024d
```

**Don't pull yet without a harder eval set.** On the existing 16-doc benchmark all four will likely score ≥90% and we'll learn nothing.

## RAG architecture wins (probably bigger lift than swapping embedder)

bge-m3 already gives THREE retrieval modes for free. The cheap order-of-magnitude wins:

1. **Hybrid retrieval** — bge-m3 outputs dense + sparse + ColBERT. Wire sparse into FTS5 alongside dense. BAAI's own paper recommends this; production reference: [Qdrant + bge-m3 hybrid sample](https://github.com/yuniko-software/bge-m3-qdrant-sample).

2. **Reranking with `bge-reranker-v2-m3`** — same model family, late-stage cross-encoder. Near-zero integration cost. **Biggest single quality lift on Thai mixed-script** per BAAI evals.

3. **ColBERT / multi-vector mode of m3** — late interaction. Already in the model. Check whether arra-oracle-v3 passes `colbert_vecs=True` — if not, free precision lift.

4. **HyDE** (hypothetical document embeddings) — generate a Thai answer with the LLM, embed *that*, retrieve. Particularly strong for short Thai keyword queries against long English/Thai retros.

5. **Query decomposition for Thai** — Thai has no word boundaries. A small LLM rewrite step (split compounds, transliterate borrowed terms both directions) often beats picking a new embedder.

## Ranked next actions

| Priority | Action | Why |
|----------|--------|-----|
| 1 | Build a harder Thai eval set (50+ docs, paraphrased queries, distractors) | Can't measure improvement on a saturated bench |
| 2 | Audit arra-oracle-v3 for bge-m3 multi-mode usage | If we're only using dense, we're leaving free quality on the table |
| 3 | Wire `bge-reranker-v2-m3` as a re-ranking pass after dense recall | Biggest single Thai-quality lift per BAAI |
| 4 | Fix qwen3-embedding dim-fallback bug (issue draft staged) | Unblocks future eval |
| 5 | Pull qwen3-embedding:4b + multilingual-e5-large-instruct + arctic-embed2 — re-bench on the harder set | Fair comparison only after #1 |
| 6 | HyDE prototype on short Thai queries | Compounding win |

## Key model facts (per-row spec)

| Model | Dim | Ctx | License | Ollama |
|-------|-----|-----|---------|--------|
| **bge-m3** (baseline) | 1024 | 8192 | MIT | `bge-m3` |
| Qwen3-Embedding-0.6B | ≤1024 | 32k | Apache-2.0 | `qwen3-embedding:0.6b` |
| Qwen3-Embedding-4B | ≤2560 | 40k | Apache-2.0 | `qwen3-embedding:4b` |
| Qwen3-Embedding-8B | ≤4096 | 40k | Apache-2.0 | `qwen3-embedding:8b` (4.7 GB) |
| multilingual-e5-large-instruct | 1024 | 512 | MIT | `qllama/multilingual-e5-large-instruct` |
| jina-embeddings-v3 | 32–1024 (MRL) | 8192 | **CC-BY-NC** | none official (issue #6922) |
| gte-multilingual-base | 128–768 (elastic) | 8192 | Apache-2.0 | community |
| snowflake-arctic-embed2 | 1024 | 8192 | Apache-2.0 | `snowflake-arctic-embed2` |
| bge-multilingual-gemma2 | 3584 | 8k | Gemma | – |
| Cohere embed-multilingual-v3.0 | 1024 | 512 | Paid API | – |
| Voyage multilingual-2 | 1024 | 32k | Paid API | – |
| gemini-embedding-001 | 768/1536/3072 (MRL) | 2048 | Paid API | – |
| paraphrase-multilingual-mpnet-base-v2 | 768 | 128 | Apache-2.0 | `paraphrase-multilingual` |

## Thai-specialist models (parked — not retrieval-tuned)

WangchanBERTa, PhayaThaiBERT and SimCSE-WangchanBERTa variants are Thai-specialist BERT bases but **not retrieval-tuned out of the box**. ConGen-distilled variants exist (e.g. `kornwtp/ConGen-BGE_M3-phayathaibert` reports 85.80 R@1 on XQuAD-Thai — strong but still below bge-m3 on the same eval). Probably overkill given bge-m3 already handles Thai cleanly; revisit only if a specific Thai-only retrieval workload doesn't perform.

## Sources (for citation in PRs / issues)

- SEA-BED paper: https://arxiv.org/html/2508.12243v1
- Thai-Sentence-Vector-Benchmark: https://github.com/mrpeerat/Thai-Sentence-Vector-Benchmark
- BAAI/bge-m3 + reranker: https://huggingface.co/BAAI/bge-m3 · https://huggingface.co/BAAI/bge-reranker-v2-m3
- Qwen3-Embedding: https://qwenlm.github.io/blog/qwen3-embedding/ · https://arxiv.org/abs/2506.05176
- Qdrant hybrid bge-m3 sample: https://github.com/yuniko-software/bge-m3-qdrant-sample
- MMTEB / MTEB leaderboard: https://huggingface.co/spaces/mteb/leaderboard
- multilingual-e5-large-instruct: https://huggingface.co/intfloat/multilingual-e5-large-instruct
- jina-embeddings-v3: https://jina.ai/news/jina-embeddings-v3-a-frontier-multilingual-embedding-model/
- Snowflake Arctic Embed 2: https://www.snowflake.com/en/engineering-blog/snowflake-arctic-embed-2-multilingual/

## Conclusion

The honest answer: **don't migrate from bge-m3 yet**. It's mid-pack but adequate, and the migration cost is non-zero. Spend that energy on (a) a harder Thai eval set, (b) wiring bge-m3's already-paid-for multi-mode + reranker, and (c) HyDE for query expansion. Once the harder eval exists and we can measurably prove a candidate beats bge-m3, *then* migrate — and with the plug-play architecture (one collection per model), that swap costs ~30 minutes of compute and zero risk to indexed data.

Plug and unplug, never destroy. 🌱
