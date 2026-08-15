---
query: "indexer pipeline docs"
target: "arra-oracle-v3 + indexer-pro"
mode: documentation
timestamp: 2026-05-03 00:30
---

# How the Indexer Pipeline Works

## Architecture

```
.md files (vault/ψ/memory/)
    ↓ scan
SQLite + FTS5 (20,672 docs)
    ↓ embed
LanceDB vectors (per model)
    ↓ query
arra-cli search / indexer-pro compare
```

Three layers: **filesystem → SQLite/FTS5 → LanceDB vectors**

## Layer 1: Filesystem → SQLite (Indexer)

The indexer scans `.md` files and stores them in SQLite with FTS5 full-text search.

### Run the indexer

```bash
# Ensure server is running
curl -s http://localhost:47778/api/health

# Run the filesystem indexer (scans ψ/memory/ → SQLite)
cd /path/to/arra-oracle-v3
bun src/indexer/cli.ts
```

### What it does

1. **Collects** — scans `ψ/memory/` for `.md` files (learnings, retros, principles)
2. **Parses** — splits by `##` headers into granular documents
3. **Deduplicates** — content hash to avoid duplicates
4. **Stores** — inserts into `oracle_documents` table + `oracle_fts` (FTS5 virtual table)

### Check results

```bash
bun ~/.bun/bin/arra-cli stats
# → total: 20,672 docs

bun ~/.bun/bin/arra-cli list --limit 5
# → shows recent docs with types
```

### Document types

| Type | Count | Source |
|------|-------|--------|
| learning | 8,453 | ψ/memory/learnings/ |
| retro | 9,964 | ψ/memory/retrospectives/ |
| principle | 2,255 | ψ/memory/resonance/ |

## Layer 2: SQLite → LanceDB Vectors (Vector Indexer)

The vector indexer reads docs from SQLite and embeds them into LanceDB collections using Ollama.

### Available models

```bash
# Check what's installed
indexer-pro models
# OR
curl -s http://localhost:11434/api/tags | jq '.models[].name'
```

| Model | Dims | Speed | Collection |
|-------|------|-------|------------|
| nomic-embed-text | 768 | ~100 doc/s | oracle_knowledge |
| bge-m3 | 1024 | ~50 doc/s | oracle_knowledge_bge_m3 |
| qwen3-embedding | 4096 | ~30 doc/s | oracle_knowledge_qwen3 |

### Run vector indexing (ALL docs, no limit)

```bash
# Index ALL docs with nomic (fastest)
cd /path/to/arra-oracle-v3
bun src/scripts/index-model.ts nomic

# Index ALL docs with bge-m3 (better quality)
bun src/scripts/index-model.ts bge-m3
```

The script:
1. Reads ALL docs from SQLite (FTS5 join)
2. Batches them (nomic: 100/batch, bge-m3: 50/batch)
3. Embeds via Ollama
4. Stores in LanceDB collection

**There is NO limit in the code** — it indexes every doc in SQLite. The 1,000 we saw on studio.buildwithoracle.com was from a test run that only indexed 1,000 learnings.

### Check vector counts

```bash
bun ~/.bun/bin/arra-cli stats
# → vectors: [{ key: "nomic", count: 1000 }, { key: "bge-m3", count: 1 }]

# Or via indexer-pro
indexer-pro collections
indexer-pro status
```

## Layer 3: Querying

### FTS5 search (text matching)

```bash
bun ~/.bun/bin/arra-cli search "oracle principles" --limit 5
# → uses SQLite FTS5, fast, keyword-based
```

### Vector search (semantic)

```bash
# Via API
curl "http://localhost:47778/api/search?q=oracle+principles&mode=vector&model=nomic&limit=5"

# Via indexer-pro
indexer-pro search "oracle principles" --model nomic --limit 5
indexer-pro compare-all "oracle principles" --limit 5
```

### Hybrid search (FTS5 + vector)

```bash
curl "http://localhost:47778/api/search?q=oracle+principles&mode=hybrid&model=nomic&limit=5"
```

## How to Do a Full Reindex

### Step 1: Check current state

```bash
bun ~/.bun/bin/arra-cli stats
indexer-pro status
indexer-pro doctor
```

### Step 2: Ensure Ollama is running with the model

```bash
ollama list | grep embed
# If model missing:
ollama pull nomic-embed-text
ollama pull bge-m3
```

### Step 3: Run full vector index

```bash
cd /path/to/arra-oracle-v3

# Full index with nomic (all 20,672 docs, ~3-4 min at 100 doc/s)
bun src/scripts/index-model.ts nomic

# Full index with bge-m3 (all 20,672 docs, ~7 min at 50 doc/s)
bun src/scripts/index-model.ts bge-m3
```

### Step 4: Verify

```bash
bun ~/.bun/bin/arra-cli stats
# → nomic count should be 20,672
# → bge-m3 count should be 20,672

indexer-pro compare-all "test query" --limit 3
# → both models should return results
```

### Step 5: Check the UI

Open https://studio.buildwithoracle.com/map — should show all 20,672 docs, not 1,000.

## What is indexer-pro?

**indexer-pro** is a standalone interactive CLI tool for managing the indexer pipeline.

Repo: https://github.com/Soul-Brews-Studio/indexer-pro

### Key commands

```bash
indexer-pro                    # Interactive wizard
indexer-pro status             # DB stats, vector counts, Ollama health
indexer-pro models             # Embedding models + install status
indexer-pro scan <path>        # Scan .md files
indexer-pro search <query>     # Quick vector search
indexer-pro compare-all <q>    # Compare ALL models side by side
indexer-pro doctor             # Diagnose issues
indexer-pro collections        # List LanceDB collections
indexer-pro top                # Live dashboard (like htop)
```

### 22 total subcommands, 21 tests, MIT licensed, public

## Why Only 1,000 Vectors?

Yesterday we ran `scripts/index-learnings.ts` which filtered to learnings only AND we stopped at 1,000 as a test batch. The actual `index-model.ts` script has NO limit — it indexes everything in SQLite.

**Fix**: just run `bun src/scripts/index-model.ts nomic` to index all 20,672 docs.
