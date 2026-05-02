# Arra Oracle v3 — Installation & CLI Guide

## Quick Install (bunx)

No clone needed. Works from any directory.

```bash
# Start the server
bunx --bun arra-oracle-v3@github:Soul-Brews-Studio/arra-oracle-v3

# Use the CLI
bunx --bun --package arra-oracle-v3@github:Soul-Brews-Studio/arra-oracle-v3 arra-cli --help
```

## Prerequisites

- [Bun](https://bun.sh) >= 1.3.0
- [Ollama](https://ollama.ai) (for vector embeddings)

```bash
bun --version        # >= 1.3.0
ollama list          # should show bge-m3
```

Pull bge-m3 if missing:
```bash
ollama pull bge-m3
```

## Server

### Option A: bunx (zero install)
```bash
bunx --bun arra-oracle-v3@github:Soul-Brews-Studio/arra-oracle-v3 --port 47778
```

### Option B: pm2 (persistent)
```bash
pm2 start src/server.ts --name arra-oracle --interpreter bun
pm2 save
```

### Option C: local dev
```bash
cd /path/to/arra-oracle-v3
bun install
bun run src/server.ts
```

### Verify
```bash
curl http://localhost:47778/api/health
# {"status":"ok","server":"arra-oracle-v3","version":"...","port":47778,"oracle":"connected"}
```

## CLI Usage

### Alias (recommended)
```bash
alias arra='bunx --bun --package arra-oracle-v3@github:Soul-Brews-Studio/arra-oracle-v3 arra-cli'
```

Then use:
```bash
arra search "query"
arra list
arra learn "pattern"
```

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `search` | Semantic + FTS5 hybrid search | `arra search "oracle principles" --limit 5` |
| `list` | List documents by type | `arra list --type learning --limit 10` |
| `learn` | Add a pattern to knowledge base | `arra learn "pattern" --concepts a,b --source src` |
| `read` | Read a document by ID or path | `arra read <id>` |
| `stats` | Show database stats | `arra stats --json` |
| `trace` | Search trace logs | `arra trace "query" --limit 5` |
| `trace-list` | List all traces | `arra trace-list --status raw --limit 10` |
| `trace-get` | Get a specific trace | `arra trace-get <id>` |
| `trace-chain` | Follow trace chain | `arra trace-chain <id> --direction both` |
| `threads` | List forum threads | `arra threads --limit 10` |
| `thread` | Read a thread | `arra thread <id>` |
| `schedule` | View schedule | `arra schedule --date 2026-05-02` |
| `supersede-list` | List superseded docs | `arra supersede-list --project x` |
| `supersede-chain` | Follow supersede chain | `arra supersede-chain <path>` |
| `reflect` | Self-reflection / meta | `arra reflect --json` |
| `session` | Inspect sessions | `arra session list` |
| `menu` | Studio menu management | `arra menu list` |
| `export-obsidian` | Export to Obsidian vault | `arra export-obsidian --out ~/vault` |
| `import-obsidian` | Import from Obsidian | `arra import-obsidian --in ~/vault` |
| `plugin` | Manage CLI plugins | `arra plugin list` |

### Search examples

```bash
# Full-text search
arra search "federation protocol"

# Filter by type
arra search "oracle" --type learning

# Limit results
arra search "maw" --limit 3
```

### Learn examples

```bash
# Basic
arra learn "Always check Layer 0 (service health) before debugging code"

# With metadata
arra learn "bge-m3 needs cosine distance, not L2" \
  --concepts "vector,lancedb,bge-m3" \
  --source "vector-bug-investigation"
```

## MCP Setup (for Claude)

Add to your Claude MCP config:

```json
{
  "mcpServers": {
    "arra-oracle": {
      "command": "bun",
      "args": ["run", "/path/to/arra-oracle-v3/src/index.ts"],
      "env": {
        "ORACLE_EMBEDDING_MODEL": "bge-m3"
      }
    }
  }
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ORACLE_PORT` | `47778` | HTTP server port |
| `ORACLE_VECTOR_DB` | `lancedb` | Vector backend |
| `ORACLE_EMBEDDING_PROVIDER` | `ollama` | Embedding provider |
| `ORACLE_EMBEDDING_MODEL` | `bge-m3` | Embedding model |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `NEO_ARRA_API` | `http://localhost:47778` | CLI → server URL |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| CLI says "Cannot reach ARRA Oracle" | Start server first: `make run` or `pm2 start` |
| Vector search returns 0 | Check Ollama: `curl localhost:11434/api/tags` |
| Slow first query (~5s) | Normal — bge-m3 model cold load (1.1GB) |
| Search returns wrong results | Known bug: L2 distance used instead of cosine ([#1059](https://github.com/Soul-Brews-Studio/arra-oracle-v3/issues/1059)) |
