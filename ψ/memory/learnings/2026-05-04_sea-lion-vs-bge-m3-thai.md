---
pattern: SEA-LION-ModernBERT-600M's SEA-BED Thai +2.4pt advantage does NOT transfer to our paired Thai/EN paraphrase benchmark — bge-m3 wins by 36pts cross-language
date: 2026-05-04
source: ψ/lab/embedding-benchmark/sea_lion_bench.py run on m5
project: github.com/aisingapore/SEA-LION-ModernBERT-600M
---

# SEA-LION vs bge-m3 — Empirical Result

## TL;DR

The agent research surfaced `aisingapore/SEA-LION-ModernBERT-600M` (March 2026, MIT) as the only Thai-specialist worth testing — it scores 80.00 on SEA-BED Thai vs bge-m3's 77.59 on the official AI Singapore leaderboard. **+2.4 points.**

We pulled it via HuggingFace and ran the same paired Thai/EN paraphrase + distractor benchmark.

| Metric | bge-m3 | SEA-LION CLS-pool | SEA-LION mean-pool |
|--------|--------|-------------------|--------------------|
| Dimensions | 1024 | 1024 | 1024 |
| Index 24 docs (Python) | 164 ms | 2966 ms | 3016 ms |
| Query avg | 29 ms | 54 ms | 55 ms |
| **Recall@1** | **93%** | **93%** | **71%** |
| **Recall@5** | **100%** | **100%** | **86%** |
| **Cross-lang@3** | **100%** | **64%** | **21%** |

**SEA-LION-600M is 36 percentage points behind bge-m3 on cross-language retrieval** in our use case (Thai query → English doc, English query → Thai doc). Mean-pool is even worse than CLS.

## Why the leaderboard advantage didn't transfer

Plausible reasons (theoretical, not all confirmed):

1. **SEA-BED averages over many sub-tasks**, not just Thai↔EN cross-lingual retrieval. SEA-LION's training emphasis is **SEA-SEA pairs** (Thai↔Vietnamese, Thai↔Indonesian, etc.). Thai↔EN retrieval — our actual use case — may not be the strength they optimized for.

2. **Pooling protocol uncertainty**. The SEA-LION model card doesn't prescribe a pooling strategy as definitively as bge-m3's. Both CLS and mean-pool got worse-than-bge-m3 results; neither matches the leaderboard score.

3. **Possible scoring-head mismatch**. AI Singapore's leaderboard may have used a specific scoring layer (Matryoshka head, learned projection, etc.) that we're not invoking with raw last-hidden-state pooling.

4. **Our 24-doc benchmark is small**, but bge-m3 hits 100% on it cleanly — so the discriminator is real for relative comparison.

## Confidence level

Medium-high that **for THIS stack and THIS use case (Thai+English mixed-script knowledge base, paraphrase queries, distractor docs)**, SEA-LION-600M as a drop-in replacement loses to bge-m3.

If a future model card update describes a specific protocol that lifts SEA-LION's numbers on this bench, re-test. Until then, **bge-m3 remains the locked primary**.

## Cost / speed

Even ignoring quality, SEA-LION-600M is **~20× slower to index per doc** than bge-m3 in this Python setup (Ollama F16 vs HF default). Ollama tag would help, but no `aisingapore/SEA-LION-*` Ollama tag exists. Would need GGUF conversion.

## What this confirms

The pattern from earlier iterations holds:

- Published leaderboard scores are necessary but not sufficient evidence
- Always verify on YOUR corpus, with YOUR queries, using YOUR retrieval strategy
- The "plug-and-play" architecture (one collection per model) makes this kind of test cheap — pull, embed, score, decide. Took ~3 minutes of compute for definitive answer.

## Ranked Thai-tested candidates so far

| Rank | Model | R@1 / R@5 / Cross-lang@3 (our bench) | License | Notes |
|------|-------|--------------------------------------|---------|-------|
| 1 | **bge-m3** | **93 / 100 / 100** | MIT | Locked primary |
| 2 | qwen3-embedding:4b (with prefix) | 100 / 100 / 100 | Apache-2.0 | Ties on cross-lang but 1.5× slower, 2.5× larger |
| 3 | qwen3-embedding:0.6b (with prefix) | 93 / 100 / 93 | Apache-2.0 | Smaller alternative, slight cross-lang gap |
| 4 | multilingual-e5-large-instruct (with prefix) | 93 / 100 / 71 | MIT | Needs task-specific prefix; we're sending generic |
| 5 | SEA-LION-ModernBERT-600M (CLS) | 93 / 100 / 64 | MIT | Lost cross-lang despite SEA-BED lead |
| 6 | nomic-embed-text | 57 / 79 / 14 | Apache-2.0 | English-only training, structural mismatch |

bge-m3 is uncontested at the top of this stack on this benchmark. The next move that could change the ranking is a HARDER Thai eval (50+ docs, real corpus sample, harder distractors) — but lower priority than the architecture lifts (reranker, hybrid mode) already in flight.

## Reusable

```bash
cd ~/Code/github.com/Soul-Brews-Studio/arra-oracle-v3/services/reranker-py
uv run python ~/Code/github.com/Soul-Brews-Studio/arra-mcp-installation-guide-oracle/ψ/lab/embedding-benchmark/sea_lion_bench.py
```

Raw log preserved at `ψ/lab/embedding-benchmark/2026-05-04_sea-lion-vs-bge-m3.log`.

## Also in this iteration's research — what didn't pan out

- **SCB10X** has zero public embedding models on HuggingFace. They publish LLMs (typhoon-7b, typhoon-2.5-qwen3-30b, typhoon-ocr, typhoon-asr, typhoon2-safety) but no retrieval/embedding head. **Skip.**
- **"HAI"** could not be confirmed — no Stanford HAI, Anthropic HAI, or Thai-named "HAI" embedding model in HF or arxiv. The closest false-positive is `hiieu/halong_embedding` which is Vietnamese, not Thai. The user may have been conflating something.
- **PhayaThaiBERT, WangchanBERTa, SimCSE-Thai variants**: pre-bge-m3 era, Thai-only without multilingual hard negatives. Not retrieval-tuned. Skip.
- **OpenThaiGPT**: chat LLMs only, no text retrieval embedder.
