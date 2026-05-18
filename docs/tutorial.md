# arra-oracle-v3 Tutorial — Setup, Gotchas, and Battle-Tested Wisdom

> Written by sage-vector-fix-oracle after debugging 3 vector bugs, shipping 8 PRs,
> budding a child oracle, and indexing 20,672 docs. These are the gotchas NOT in the README.

## 1. Setup from Scratch

### Prerequisites

```bash
# Bun (runtime)
curl -fsSL https://bun.sh/install | bash

# Ollama (local embeddings)
brew install ollama
ollama serve              # start the daemon
ollama pull nomic-embed-text   # 137MB, 768d, fastest
ollama pull bge-m3             # 1.2GB, 1024d, best quality
```

### Install arra-oracle-v3

```bash
# Option A: bunx (no install)
bunx arra-oracle-v3

# Option B: global install
bun add -g arra-oracle-v3

# Option C: clone for development
ghq get Soul-Brews-Studio/arra-oracle-v3
cd $(ghq root)/github.com/Soul-Brews-Studio/arra-oracle-v3
bun install
bun src/server.ts
```

### First Run Checklist

```bash
# 1. Server
bun src/server.ts          # starts on :47778

# 2. Health check
curl http://localhost:47778/api/health
# → {"status":"ok","version":"26.5.2-alpha.1704"}

# 3. Stats
bun ~/.bun/bin/arra-cli stats
# → total: 0 (empty on first run)
```

### GOTCHA: Data Directory

arra-oracle-v3 stores everything in `~/.arra-oracle-v2/`:
```
~/.arra-oracle-v2/
├── oracle.db          # SQLite + FTS5 (documents)
├── lancedb/           # LanceDB vector collections
│   ├── oracle_knowledge.lance/        # nomic vectors
│   ├── oracle_knowledge_bge_m3.lance/ # bge-m3 vectors
│   └── oracle_knowledge_qwen3.lance/  # qwen3 vectors
└── ψ/memory/          # local vault (small, ~13 files)
```

The central vault (29,305 .md files across 89+ oracles) lives elsewhere — typically pointed to
by `ORACLE_REPO_ROOT` env var.

## 2. Vector Indexing Gotchas

### The Three-Layer Pipeline

```
.md files → SQLite/FTS5 → LanceDB vectors
  (scan)      (store)        (embed)
```

Each layer is independent. You can have 20,672 docs in SQLite but only 1,000 vectors in LanceDB.
The 3D memory map on studio.buildwithoracle.com shows **vectors**, not documents.

### GOTCHA: L2 vs Cosine Distance (Bug #1059, fixed in PR #1061)

LanceDB defaults to L2 (Euclidean) distance. Embedding models like bge-m3 output
unnormalized vectors (~magnitude 26). With L2, distances range 538-555 instead of 0-1.

**Fix**: `.distanceType('cosine')` in every LanceDB query. Already fixed in main.

**How to detect**: If search scores are > 1.0, you have the L2 bug.

### GOTCHA: bge-m3 Needs Instruction Prefix (Bug #1059, fixed in PR #1061)

bge-m3 requires different prefixes for queries vs documents:
- Search queries: prepend `"query: "` to the text
- Indexing documents: prepend `"passage: "` to the text

Without this, queries and documents cluster together in vector space,
producing weak discrimination (correct topic but wrong ranking).

**How to detect**: Search returns related-but-not-best results. The right document exists
but ranks 3rd or 4th instead of 1st.

### GOTCHA: Zombie Processes Serve Stale Data

**The most expensive debugging mistake**: we spent 30 minutes rebuilding LanceDB files while
a zombie `bun` process (PID 44884) held port 47778 with a corrupt LanceDB connection cached
in memory.

**Diagnostic order**: process → port → data → code

```bash
# ALWAYS check this FIRST
lsof -i :47778
# If you see a PID that shouldn't be there → kill it
kill <pid>
```

### GOTCHA: SQLite DB Lock During Indexing

When the vector indexer is writing (especially `embed-all` with parallel models), SQLite gets
locked. The HTTP API returns "disk I/O error" and the UI shows "Connection Error".

**This is temporary.** Wait for indexing to finish. The lock clears automatically.

**Prevention**: Don't run parallel indexing on the same Ollama instance. Sequential is faster
(avoids GPU context switching) and doesn't lock the DB as aggressively.

### GOTCHA: The 1,000 Limit That Isn't

There is NO hard limit in `index-model.ts`. It indexes every doc in SQLite. If you see only
1,000 vectors, it's because someone ran a test batch and stopped. Run the full index:

```bash
cd /path/to/arra-oracle-v3
bun src/scripts/index-model.ts nomic    # ALL docs, ~6 min at 55 doc/s
bun src/scripts/index-model.ts bge-m3   # ALL docs, ~12 min at 30 doc/s
```

### GOTCHA: ORACLE_FORCE_REINDEX

The filesystem indexer (`bun src/indexer/cli.ts`) has a safety check: refuses to delete >50%
of existing docs. If you're pointing at a different vault, set:

```bash
ORACLE_FORCE_REINDEX=1 bun src/indexer/cli.ts
```

### Model Comparison (Real Data)

| Model | Dims | Speed | Quality | Size |
|-------|------|-------|---------|------|
| nomic-embed-text | 768 | 55 doc/s | Good for general search | 137MB |
| bge-m3 | 1024 | 30 doc/s | Best discrimination, needs prefix | 1.2GB |
| qwen3-embedding | 4096 | ~15 doc/s | Highest dims, slower | 4.9GB |

Use `indexer-pro compare-all "query"` to compare models side-by-side with your actual data.

## 3. UI Connection

### Architecture

```
studio.buildwithoracle.com (Cloudflare Workers)
    ↓ fetch
localhost:47778 (arra-oracle-v3 Elysia server)
    ↓ query
SQLite + LanceDB + Ollama
```

### GOTCHA: The UI Runs on Cloudflare but Queries Localhost

The deployed UI at `studio.buildwithoracle.com` makes API calls to whatever host you configure
in the HostPicker (top-right dropdown). Default is `localhost:47778`.

For this to work:
1. Server must be running locally
2. CORS must allow the origin (it does — `*.buildwithoracle.com` is whitelisted)
3. Private Network Access headers must work (Chrome 117+)

### GOTCHA: Cache-Control (Bug #1060, fixed in PR #1062)

Without `Cache-Control: no-cache` headers, the browser caches API responses. You reindex
20,672 docs but the dashboard still shows 1,000 from the cached response.

**Fix**: Already in main. Hard refresh (Cmd+Shift+R) if you see stale data.

### GOTCHA: "demo mode"

The UI shows "demo mode" when it can't connect to the backend. Check:
1. Is the server running? `curl http://localhost:47778/api/health`
2. Is the DB locked? (indexing in progress)
3. Is the host correct in HostPicker?

### Running UI Locally

```bash
# From ui-oracle monorepo
bun run dev:studio      # port 5173 — main dashboard
bun run dev:vector      # port 5173 — vector playground
bun run dev:indexer     # port 5175 — indexer settings
```

## 4. Top 10 CLI Commands

### arra-cli (talks to :47778 API)

```bash
# Run with: bun ~/.bun/bin/arra-cli <command>

# 1. Stats — what's in the DB
arra-cli stats

# 2. Search — FTS5 full-text search
arra-cli search "oracle principles" --limit 10

# 3. List — browse documents
arra-cli list --limit 20

# 4. Learn — add a pattern to the knowledge base
arra-cli learn "Always check lsof before debugging data corruption"
```

### indexer-pro (standalone CLI)

```bash
# 5. Status — full system health
indexer-pro status

# 6. Models — what's installed in Ollama
indexer-pro models

# 7. Doctor — diagnose issues
indexer-pro doctor

# 8. Compare — side-by-side model comparison
indexer-pro compare-all "query" --limit 5

# 9. Search — quick vector search
indexer-pro search "zombie process debugging" --model nomic

# 10. Scan — preview what would be indexed
indexer-pro scan /path/to/vault/ψ/memory
```

## 5. Vault Architecture

### What is ψ/ (psi)?

Every oracle has a `ψ/` directory — the persistent memory vault:

```
ψ/
├── memory/
│   ├── learnings/          # What we learned (8,453 docs)
│   ├── retrospectives/     # Session retros (9,964 docs)
│   ├── resonance/          # Core principles (2,255 docs)
│   └── traces/             # Search logs
├── inbox/
│   └── handoff/            # Session handoffs for continuity
├── outbox/                 # Pending items
├── incubate/               # Active development repos (symlinks)
│   └── .origins            # Manifest for restore
└── contacts.json           # Federation contacts
```

### How Documents Flow

```
Human writes .md in ψ/memory/learnings/
    ↓ indexer scans
SQLite oracle_documents table (20,672 rows)
    ↓ FTS5 indexes text
oracle_fts virtual table (full-text search)
    ↓ vector indexer embeds
LanceDB oracle_knowledge collection (20,672 vectors)
    ↓ API serves
studio.buildwithoracle.com/map shows 3D visualization
```

### GOTCHA: Central Vault vs Local Vault

Each oracle has its own small ψ/ (5-50 files). The central vault at `~/.arra-oracle-v2/`
aggregates ALL oracles (89+ repos, 29,305 .md files → 20,672 parsed docs).

The indexer reads from the central vault's SQLite DB, not from individual oracle repos.

### GOTCHA: ψ/ is a Symlink

In many oracle repos, `ψ/` is a symlink pointing to the real vault location. Always resolve
it before writing:

```bash
PSI=$(readlink -f ψ 2>/dev/null || echo "ψ")
```

Never `git add ψ/` directly — it may accidentally commit the symlink target.

### GOTCHA: Vault Files are Shared State

Files in ψ/ are NOT committed to repos (they're gitignored via `ψ/incubate/**/origin`).
They live on the filesystem and are shared across sessions. Don't delete them — Nothing is Deleted.

---

*Written 2026-05-03 by sage-vector-fix-oracle after a marathon session:
8 PRs merged, 1 oracle budded, 20,672 docs indexed, 3 vector bugs fixed.*
