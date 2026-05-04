---
pattern: Thai+English embedding benchmark — bge-m3 wins decisively
date: 2026-05-04
source: arra-oracle-v3/src/vector/__tests__/benchmark-models.ts run on m5
project: github.com/Soul-Brews-Studio/arra-oracle-v3
---

# Thai Embedding Benchmark — Empirical Result

## TL;DR

**Winner: bge-m3.** 100% cross-language retrieval on the paired Thai/English corpus. nomic-embed-text scores 20%. Qwen3-Embedding-0.6B has a code-side dim-mismatch bug blocking it on this stack.

## Setup

- **Corpus**: 16 docs (8 Thai + 8 English), paired ground-truth (`th1`↔`en1`, etc.) on principles, learnings, retros — exactly the Oracle's content profile.
- **Queries**: 10 (5 Thai + 5 English) from `arra-oracle-v3/src/vector/__tests__/benchmark-models.ts`.
- **Cross-language metric**: a Thai query is "correct" if its top-3 includes the English equivalent (and vice versa).
- **Machine**: m5 (M-series, 18 CPUs), Ollama F16 quantization for all models.

## Result

| Metric | nomic-embed-text | bge-m3 | qwen3-embedding (0.6B) |
|--------|------------------|--------|------------------------|
| Dimensions | 768 | 1024 | 1024 (model) — but code expects 4096 |
| Index 16 docs | 192ms | 761ms | 600ms (insert OK) |
| Query avg | 9ms | 47ms | failed |
| **Cross-language %** | **20%** | **100%** | failed |

bge-m3 query latency is ~5× nomic but acceptable (47ms is well within interactive). 5× the recall is worth 5× the latency.

## Per-query cross-language hit detail

| Query | nomic | bge-m3 |
|-------|-------|--------|
| Air quality (Thai → expects en2) | ✗ [th2,th5,th4] | ✓ [th2,**en2**,th3] |
| Air quality (English → expects th2) | ✗ [en2,en3,en8] | ✓ [**th2**,en2,th3] |
| Flood monitoring (Thai → expects en3) | ✗ | ✓ [th3,**en3**,th2] |
| Flood monitoring (English → expects th3) | ✗ | ✓ [**th3**,en3,en2] |
| IoT sensors (Thai → expects en5) | ✗ | ✓ [th5,**en5**,th3] |
| IoT sensors (English → expects th5) | ✗ | ✓ [en5,**th5**,th3] |
| Brewing (Thai → expects en8) | ✗ | ✓ [th8,**en8**,th3] |
| Brewing (English → expects th8) | ✓ [en8,**th8**,th4] | ✓ [en8,**th8**,th2] |
| AI transparency (Thai → expects en4) | ✗ | ✓ [th4,**en4**,th1] |
| AI transparency (English → expects th4) | ✓ [en4,**th5**,th4] | ✓ [en4,**th4**,th6] |

nomic only finds the cross-language match when the **English query** is the source — i.e. it semi-works one direction. Thai queries fail to bridge into English documents 100% of the time. This is the structural English-only training showing up.

bge-m3 finds the cross-language match for every single query, both directions.

## qwen3-embedding (0.6B) — blocked by code bug, not by the model

Two bugs hit, in this order:

1. **Wrong Ollama tag**: `dengcao/Qwen3-Embedding-0.6B:F16` declares `Capabilities: completion`, not `embedding`. Ollama refuses to serve it via `/api/embed` or `/api/embeddings`. **Fix**: use the official `qwen3-embedding:0.6b` (correct capability), then `ollama cp qwen3-embedding:0.6b qwen3-embedding` to alias under the name the codebase uses.

2. **Dim mismatch in arra-oracle-v3**: `src/vector/embeddings.ts:39` registers `'qwen3-embedding': 4096` (the 8B variant size). The 0.6B model outputs 1024d. LanceDB creates the column at 4096 from the fallback, then the actual embeddings come in at 1024 → query fails: *"No vector column found to match with the query vector dimension: 1024"*. **Fix**: change the fallback to 1024, or remove the hardcoded entry and rely on the existing auto-detect path. File a GH issue against arra-oracle-v3.

After fixing those, qwen3-0.6B becomes a viable secondary, but **bge-m3's 100% empirical Thai cross-lang score is the bar — there's no urgency to migrate.**

## Verdict for this Oracle stack

- **Primary: bge-m3.** Already indexed (20,677 docs). 100% empirical Thai cross-lang. MIT license. 1024d. Stay.
- **Drop nomic-embed-text.** 20% cross-lang on Thai is a structural mismatch, not a tuning issue. Wasting compute and 20,761 docs of disk for an English-only fallback we don't need (bge-m3 is multilingual).
- **Park qwen3-embedding-0.6b.** File the code-side dim fix as a GH issue. Re-evaluate when fixed; even then, only worth migrating if Thai cross-lang clears bge-m3's bar in the same benchmark.

## Reusable artifact

This result is a **frozen ground truth**. Re-run any time:

```bash
cd ~/Code/github.com/Soul-Brews-Studio/arra-oracle-v3
bun run src/vector/__tests__/benchmark-models.ts
```

The benchmark uses isolated tmp LanceDB collections (`/var/folders/.../oracle-bench-*`) — **never touches production data**. Plug-and-play eval, no risk to indexed paths or repos.

Raw run log preserved at `ψ/lab/embedding-benchmark/2026-05-04_run.log`.
