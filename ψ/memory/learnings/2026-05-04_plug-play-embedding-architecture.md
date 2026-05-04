---
pattern: Plug-and-play embedding models in arra-oracle-v3 — never destroy indexed data
date: 2026-05-04
source: arra-oracle-v3 src/vector/{factory,config,embeddings}.ts walkthrough
project: github.com/Soul-Brews-Studio/arra-oracle-v3
---

# Plug-and-Play Embedding Models — The Invariants

> "Ground truth: plug in and plug out without destroying our indexed path and repo." — user, 2026-05-04

The arra-oracle-v3 vector layer is **already plug-and-play**. This doc codifies the invariants so future model swaps stay safe.

## The Source of Truth Hierarchy

Three tiers of state. Embedding models live in the highest tier so they can be swapped without touching the lower ones.

```
┌─ tier 0 ─ filesystem markdown files (ψ/, repos)        ←  immortal truth
├─ tier 1 ─ oracle.db  →  oracle_documents + oracle_fts  ←  text + FTS5 index
└─ tier 2 ─ LanceDB collections, ONE PER MODEL           ←  swappable
            ├─ oracle_knowledge.lance         (nomic, 20,761)
            ├─ oracle_knowledge_bge_m3.lance  (bge-m3, 20,677)
            └─ oracle_knowledge_qwen3.lance   (qwen3, 0)
```

**Rule 1 — One collection per model.** `src/vector/config.ts:50-65` declares each registered model gets its own LanceDB collection (`oracle_knowledge_{key}`). Adding a model = adding a collection. Removing one = `rm -rf` the `.lance` directory. Neither touches anything else.

**Rule 2 — Source text is sacred.** `oracle_documents` (FTS5) holds the actual content. Re-indexing into a new model reads from this table — never re-creates it. Re-embedding any model is idempotent and non-destructive.

**Rule 3 — `vector-server.json` is the live registry.** `src/vector/config.ts` exposes `loadVectorConfig() / writeVectorConfig() / configToModels()`. The file is optional; absence falls back to hardcoded defaults. Edit JSON, restart server, model is added. **No code change required.**

**Rule 4 — Benchmarks use isolated tmp collections.** `src/vector/__tests__/benchmark-models.ts` writes to `/var/folders/.../oracle-bench-{model}-{ts}/` then deletes after — production collections are untouchable.

## Adding a new model — the safe recipe

1. Pull the Ollama model:
   ```bash
   ollama pull <provider>/<model>:<tag>
   ollama cp <full-tag> <short-name-the-code-uses>   # alias if needed
   ```

2. Append a collection entry to `vector-server.json`:
   ```json
   "newmodel": {
     "collection": "oracle_knowledge_newmodel",
     "model": "newmodel-embedding",
     "provider": "ollama"
   }
   ```

3. Restart arra-oracle-v3. The new collection is created lazily on first write.

4. (Optional) Backfill against the existing source text:
   ```bash
   curl -XPOST http://localhost:47778/api/vector/index/start \
     -d '{"model":"newmodel"}'
   ```

   This reads from `oracle_documents` and embeds into the new collection. Other collections untouched.

5. Verify before promoting:
   ```bash
   bun run src/vector/__tests__/benchmark-models.ts
   ```

   Compare cross-language % vs the incumbent on the paired Thai/English corpus.

## Removing a model — the safe recipe

1. Remove entry from `vector-server.json`.
2. `rm -rf $ORACLE_DATA_DIR/lancedb/oracle_knowledge_<key>.lance`
3. Restart server. **`oracle_documents` and other collections untouched.**

## Known gotcha — dim auto-detect vs fallback

`src/vector/embeddings.ts:30-46` has a hardcoded `KNOWN_DIMS` table used as fallback before auto-detect. If a tag's actual dim differs from the fallback (e.g. `qwen3-embedding` → 0.6B is 1024d, not 4096d), LanceDB creates the column at the fallback dim and queries fail with *"No vector column found to match with the query vector dimension: N"*.

**Fix paths**:
- Update `KNOWN_DIMS` to the actual model variant in use, **or**
- Skip the fallback and embed a dummy text first to detect dim before `ensureCollection`.

Both are local fixes that don't violate any plug-play invariant.

## Why this architecture matters

Models age. Better embeddings ship every quarter. The **only** way to keep upgrading without dread is to make swap a config edit, not a migration. arra-oracle-v3 already does this — the discipline is: never let embedding choice touch text storage.

## Cross-references

- `src/vector/config.ts` — config plumbing
- `src/vector/factory.ts` — `createVectorStore()` reads config
- `src/vector/embeddings.ts:30-46` — dim registry (the gotcha-prone bit)
- `src/vector/__tests__/benchmark-models.ts` — reusable eval harness
- `ψ/memory/learnings/2026-05-04_thai-embedding-benchmark-result.md` — empirical result

