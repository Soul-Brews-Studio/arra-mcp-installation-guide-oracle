# Handoff: arra-oracle-v3 bug fixes shipped + indexer app next

**Date**: 2026-05-02 16:17 +07
**Context**: ~55%

📡 Session: ccf5a4e2 | arra-mcp-installation-guide-oracle | ~2h

## What We Did
- Installed arra-oracle-v3 (server via pm2, CLI via bun link, bunx tested)
- Imported oracle-vault (29,305 .md files) → SQLite + FTS5 (20,670 docs)
- Indexed 1,000 learnings into nomic-embed-text vectors (17s on M5 Max)
- Analysed vault: 12,905 learnings, 6,098 retros, 2,255 principles, 75 repos
- Created vault analyser + filtered indexer scripts
- Fixed zombie process bug (PID holding port with stale LanceDB cache)
- Team agents shipped 2 PRs:
  - PR #1061: cosine distance + bge-m3 instruction prefix (6 files)
  - PR #1062: Cache-Control header (1 file)
- Filed issues: #1059, #1060 (arra-oracle-v3), #1088, #1089 (maw-js)
- Created gist: https://gist.github.com/nazt/6969b71ab93ecbc4d7204811eb5a1aef
- Incubated ui-oracle monorepo (apps/studio, apps/vector, apps/canvas)

## Pending
- [ ] Merge PR #1061 (vector bugs)
- [ ] Merge PR #1062 (cache-control)
- [ ] Clean up agent worktree branches after merge
- [ ] Index full 8,451 learnings (or 20k) once PRs merged
- [ ] Write Bug 3 chunking proposal
- [ ] Build interactive indexer app (see plan below)

## Next Session: Indexer App
- [ ] Plan and build interactive indexer settings UI
- [ ] Select vector DB adapter (LanceDB, SQLite-vec, ChromaDB, Qdrant, Cloudflare)
- [ ] Select embedding model (nomic, bge-m3, qwen3, OpenAI)
- [ ] Configure data source (.md directory path)
- [ ] File browser / file list for .md files
- [ ] Run indexing with live progress bar
- [ ] Deploy as new app in ui-oracle monorepo (`apps/indexer`)

## Key Files
- `INSTALL.md` — installation guide
- `scripts/analyse-vault.ts` — vault analyser
- `scripts/index-learnings.ts` — filtered indexer
- `ψ/incubate/Soul-Brews-Studio/ui-oracle/` — UI monorepo
- `ψ/incubate/Soul-Brews-Studio/arra-oracle-v3/` — backend
