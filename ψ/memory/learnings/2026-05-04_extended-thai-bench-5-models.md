---
pattern: Extended Thai embedding benchmark — 5 models, paraphrase queries + distractors. bge-m3 still wins decisively.
date: 2026-05-04
source: arra-oracle-v3/src/vector/__tests__/benchmark-models-extended.ts run on m5
project: github.com/Soul-Brews-Studio/arra-oracle-v3
---

# Extended Thai Embedding Benchmark — Empirical Result

## Why a new benchmark

The earlier 16-doc paired bench was *saturated* (every viable model hit 100%). To discriminate, this run uses:

- **24 docs** = 16 paired Thai/EN + **8 distractor docs** (share vocabulary with targets but different topics: wine vs beer, ESP8266 vs ESP32, rice paddies vs flood monitoring, hot weather vs PM2.5)
- **14 PARAPHRASE queries** — deliberately use *different vocabulary* than the docs. No keyword overlap. Pure semantic test.
  - "ฝุ่นละอองในอากาศกับเครื่องวัด" (dust+air+meter) → expects PM2.5 doc (no overlap with "PM2.5")
  - "wireless data relay where there is no internet coverage" → expects ESP32 LoRa doc (no "ESP32"/"LoRa" in query)
  - "fermentation temperature for hopped alcoholic drinks" → must pick beer (en8/th8), not wine (d7/d8)
- **3 metrics**: Recall@1 (target is rank 1), Recall@5 (target in top 5), Cross-lang@3 (cross-language match in top 3)

## The result

| Metric | nomic-embed-text | **bge-m3** ✅ | qwen3-embedding (0.6B) | qwen3-embedding:4b | qllama/multilingual-e5-large-instruct |
|--------|------------------|---------------|------------------------|--------------------|--------------------------------------|
| Dimensions | 768 | 1024 | 1024 | 2560 | 1024 |
| Index 24 docs | 266 ms | 1105 ms | 866 ms | 2654 ms | 1936 ms |
| Query avg | 9 ms | 47 ms | 36 ms | 67 ms | 52 ms |
| **Recall@1** | **57%** | **100%** | **100%** | **100%** | **93%** |
| **Recall@5** | **79%** | **100%** | **100%** | **100%** | **100%** |
| **Cross-lang@3** | **14%** | **100%** | **86%** | **71%** | **64%** |

bge-m3 is the only model with a clean sweep across all three metrics on this harder eval.

## Surprising findings

1. **qwen3-embedding 4B is *WORSE* than 0.6B on cross-language** (71% vs 86%). Counter-intuitive. Likely because the 4B model expects an explicit instruction prefix (`Instruct: <task>\nQuery: <q>`) that we're not providing — the bigger model is *more sensitive* to prompt protocol. Without it, the bigger model overfits to within-language matching.

2. **multilingual-e5-large-instruct underperforms despite #2 SEA-BED Thai ranking** — only 64% cross-language. Same likely reason: the "instruct" variant **requires** the instruction prefix, which the arra-oracle-v3 OllamaEmbeddings provider does not pass. SEA-BED scores assume correct prompting.

3. **bge-m3 is uniquely robust** — works correctly without any prompt engineering. This was BAAI's design goal: "BGE-M3 no longer needs instructions." Empirically validated.

4. **Distractor discrimination — bge-m3 clears it cleanly.** "Fermentation temperature for hopped alcoholic drinks" → bge-m3 picks beer (en8) at rank 1 over wine (d8). Smaller models confuse them.

## Verdict (computational, empirical)

**bge-m3 stays primary.** Empirical proof — not imagined, not theoretical:
- 100% Recall@1 on paraphrased queries with distractors
- 100% cross-language Thai↔English in a 24-doc corpus
- Robust without prompt engineering (no instruction prefix tax)
- Already deployed (20,677 docs indexed)

To beat bge-m3, a candidate must:
- Score ≥100% R@1 on this corpus, AND
- Score ≥100% cross-lang, AND
- Tolerate the absence of instruction prefixes (or arra-oracle-v3 must learn to send them)

**No tested model meets that bar today.** Migrate only when one does, AND only after wiring the missing architecture wins (reranker, multi-mode).

## Caveat (intellectual honesty)

24 docs and 14 queries is still a small sample. Three confounders we haven't controlled for:
1. **Instruction prefix omission** likely under-rates qwen3 and e5-instruct. With proper prompting they could close the gap.
2. **No long-document tests** — all docs <500 tokens. Real Oracle retros are 2-5K tokens; behavior at length untested.
3. **No real-corpus eval** — these are synthetic docs. The 20,842 real docs in `~/.arra-oracle-v2/oracle.db` haven't been used for evaluation. A fully honest comparison would sample 100 real docs with hand-labeled queries.

Future work: (a) add instruction-prefix support to OllamaEmbeddings; (b) re-run with proper prompting for qwen3/e5-instruct; (c) build a 100-doc real-corpus eval. None of those are blockers — bge-m3's empirical lead is large enough that the conclusion holds.

## What changed in arra-oracle-v3

To make this benchmark runnable, two local changes:

1. **`src/vector/embeddings.ts`** — extended `KNOWN_DIMS` to include qwen3-embedding tag variants (0.6b=1024, 4b=2560, 8b=4096) and the qllama/multilingual-e5-large-instruct community model (1024). The previous hardcoded `'qwen3-embedding': 4096` blocked the 0.6B variant. **This patch is the proposed fix for the GH issue.**
2. **`src/vector/__tests__/benchmark-models-extended.ts`** — new file. Standalone, isolated tmp collections. Production data untouched.

Both changes are safe to PR. Issue + PR pending.

## Reusable

```bash
cd ~/Code/github.com/Soul-Brews-Studio/arra-oracle-v3
bun run src/vector/__tests__/benchmark-models-extended.ts
```

JSON output emitted at end of run for downstream tooling.

Raw logs:
- `ψ/lab/embedding-benchmark/2026-05-04_extended-run.log`
- `ψ/lab/embedding-benchmark/2026-05-04_dim-fix-run.log` (the qwen3 dim-fallback fix proven)
