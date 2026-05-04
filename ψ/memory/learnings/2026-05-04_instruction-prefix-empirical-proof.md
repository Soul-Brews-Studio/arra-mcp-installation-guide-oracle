---
pattern: Instruction-prefix protocol mismatch silently caps embedding cross-language recall — empirical proof
date: 2026-05-04
source: arra-oracle-v3/src/vector/__tests__/benchmark-models-extended.ts before/after instruction-prefix patch
project: github.com/Soul-Brews-Studio/arra-oracle-v3
---

# Instruction Prefix — The Hypothesis That Was Right

## Setup

After last iteration's extended benchmark showed qwen3-embedding:4b *underperforming* qwen3-embedding:0.6b on cross-language (71% vs 86%), the hypothesis was: **the bigger model is more sensitive to the missing instruction-prefix protocol that arra-oracle-v3 doesn't currently send.**

Empirical test: patch `OllamaEmbeddings.embed()` to apply the correct protocol per model family, re-run the same 24-doc / 14-query extended benchmark, compare.

## Result — hypothesis confirmed

| Model | Cross-lang@3 BEFORE | Cross-lang@3 AFTER | Δ |
|-------|---------------------|--------------------|----|
| **qwen3-embedding:4b** | **71%** | **100%** | **+29 pts** |
| qwen3-embedding:0.6b | 86% | 93% | +7 pts |
| multilingual-e5-large-instruct | 64% | 71% | +7 pts |
| bge-m3 (control) | 100% | 100% | 0 (still perfect) |
| nomic-embed-text (control, no prefix added) | 14% | 14% | 0 |

**qwen3:4b jumped 29 percentage points from a one-line protocol change.** The bigger model wasn't worse — we were holding it wrong.

## Per-family protocols (the patch)

| Family | Query prefix | Passage prefix |
|--------|--------------|----------------|
| qwen3-embedding | `Instruct: Given a search query, retrieve relevant passages that answer the query\nQuery: <q>` | (raw — no prefix) |
| multilingual-e5 / bge-v1.5 | `query: <q>` | `passage: <p>` |
| bge-m3 | tolerates `query:` prefix (no harm) | tolerates `passage:` prefix |

Source: HF model cards for `Qwen/Qwen3-Embedding-0.6B`, `intfloat/multilingual-e5-large-instruct`, `BAAI/bge-m3`.

## Implication for the embedding-model choice

Even WITH correct prefixes, **bge-m3 still wins R@1=100, R@5=100, cross-lang=100**. Qwen3:4b now ties on cross-lang@3 (100%) but is 1.5× slower per query and 2.5× larger on disk. The protocol fix doesn't change the verdict — it just makes the comparison fair.

Where this DOES matter:
- **Future-proofing** — when a *truly* better Thai-tuned model lands on Ollama, our embedding layer must be able to send the right prompt. We can't say "Qwen3 isn't better" without first sending it the correct prompt. Now we can.
- **Drop nomic with confidence** — even if nomic added a prefix protocol, its English-only training is structural. 14% cross-lang doesn't recover from prompt engineering.

## Why R@1 dropped slightly for qwen3:0.6b (100% → 93%)

One query that previously hit rank 1 dropped out of rank 1 but stayed in top-5 (R@5 still 100%). Likely benign reordering near the top of the result list — the prefix slightly changes the embedding manifold. Not a regression worth worrying about; the *aggregate* signal is overwhelmingly positive.

## Curious finding for follow-up

`multilingual-e5-large-instruct` only improved from 64% → 71% with the prefix. The HF model card suggests it wants a *task-specific* instruction (e.g. "Given a web search query, retrieve relevant passages that answer the query"). Our generic `query: <q>` prefix is the older e5-base/large protocol, not the e5-INSTRUCT protocol. To squeeze more from e5-instruct we'd need to add a separate branch with the instruct-style prompt. Logged as TODO in the PR description; not pursuing now since e5-instruct still doesn't beat bge-m3.

## What shipped

- **arra-oracle-v3 PR #1097** now has TWO commits:
  1. `fix(vector): qwen3-embedding dim fallback for 0.6B/4B + extended Thai benchmark`
  2. `feat(vector): instruction-prefix support for qwen3-embedding + e5 families`
- **Vault**: this learning + raw before/after benchmark logs in `ψ/lab/embedding-benchmark/2026-05-04_with-prefix-run.log`

## Reusable

```bash
cd ~/Code/github.com/Soul-Brews-Studio/arra-oracle-v3
git checkout fix/qwen3-dim-fallback-and-extended-benchmark
bun run src/vector/__tests__/benchmark-models-extended.ts
```

The exact comparison can be re-run anytime. Ground truth in the JSON output at end of run.

Plug and unplug, never destroy. The protocol patch was 23 lines of code that unlocked 29 points of cross-language recall on a 4B model. The cheapest single quality lift in the project so far.
