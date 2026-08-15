# Handoff: morning port + qwen3 activation + click bug fix

📡 Session: `dded2330` | arra-mcp-installation-guide-oracle | 2026-05-05 05:14 → 08:53 GMT+7 (~3h 39m)

**Date**: 2026-05-05 08:53 +07
**Identity**: arra-mcp-installation-guide-oracle
**Federation tag**: `[mba:arra-mcp-installation-guide]` (host TBD)

## Context

Morning session that closed the marathon's open threads: ported alpha → main on arra-oracle-v3, populated qwen3 LanceDB collection, found + fixed a production cache bug in ui-oracle. Three new global skills shipped, two permanent feedback memories saved.

## What We Did

### arra-oracle-v3 — alpha → main port (3 PRs merged)
- ✅ #1108 Wave 1 foundations (schema + indexer logic + reranker + precomputed vectors)
- ✅ #1112 Wave 2 Elysia daemon (Hono → Elysia translation)
- ✅ #1110 Wave 3 arra_learn env-gated enqueue
- alpha synced to main (`f27ed43b`) via `gh api -X PATCH ... -F force=true`
- 7 `port/*` branches deleted via gh API
- E2E smoke proved daemon → queue → bge-m3 → LanceDB write in ~1s
- SSE smoke captured live `idle/claimed/error` events

### qwen3 activation
- /trace --deep + /dig --deep with 5 parallel agents proved: qwen3 collection was schema-only stub (36KB, 0 rows). Only synthetic 24-doc benches had run; production indexer never invoked
- D-before-A pattern: 4 parallel verification agents (script audit + Ollama dim verify + embedder code + corpus inventory) before launching
- Ran `bun src/scripts/index-model.ts qwen3` in background — **20,844 docs in 16:18, zero errors**
- Backend `/api/vector/stats` confirms: nomic 20761, bge-m3 20677, **qwen3 20844**

### ui-oracle — qwen3 + ADD click bug
- /click-test verified silent noop (button visible/enabled, click fires, zero network)
- 3 parallel agents traced root cause: `getMap3d()` cached `{documents: []}` from when collection was empty, with 24h TTL, no shape validation
- Issue #87 + PR #88 (`fix/87-map3d-no-cache-empty`) — 1-line fix in `apps/studio/src/api/oracle.ts:231-235`
- Verified locally on `:3000` after vite hot-reload — globe count 1 → 2

### 3 new global skills (`~/.claude/skills/`)
- `/check-stack` — PM2-managed oracle stack health
- `/click-test` — empirical UI click verification with full network/console capture
- `/aria-map` — enumerate all clickables on a page (641 captured for studio map)

### 2 new permanent feedback memories
- Never `/tmp` — always project-local `.tmp/`, gitignored
- No private skills — always global `~/.claude/skills/`

### Vault deliverables
- 1 retrospective: `ψ/memory/retrospectives/2026-05/05/08.49_port-and-qwen3-fix.md`
- 1 lesson: `ψ/memory/learnings/2026-05-05_d-before-a-and-cache-poisoning.md`
- 1 technical blog: `ψ/lab/blog/2026-05-05_d-before-a-team-agent-verification.md` (~2400 words)
- 1 smoke script: `ψ/lab/smoke/e2e-indexer-daemon.sh` (executable)
- 1 incubation hub: `ψ/incubate/Soul-Brews-Studio/ui-oracle/ui-oracle.md`
- 3 /learn docs: `ψ/learn/rtk-ai/rtk/2026-05-05/0601_*.md`
- 1 trace: `ψ/memory/traces/2026-05-05/0521_can-we-merge.md`

### arra-oracle-v3 ecosystem
- `ecosystem.oracle-stack.config.js` — PM2 config for the stack (oracle-backend, oracle-indexer, oracle-reranker, oracle-ui)

## Current State

**Stack** — verified at end of session:
- arra-oracle-v3 :47778 ✅ (`v26.5.2-alpha.1704`, oracle: connected)
- ui-oracle vite :3000 ✅
- reranker :8765 ✅
- ollama :11434 ✅ (qwen3-embedding:0.6b/4b, bge-m3, nomic-embed-text installed)
- dev-browser-relay :9222 ✅ (extension connected)
- indexer-daemon :47779 ❌ (not running — optional, only for `ORACLE_INDEXER_ENQUEUE=1`)

**This oracle's git**: clean except untracked vault entries (intentional — vault files don't get `git add`'d). `.gitignore` was modified (added `.tmp/` and `ψ/incubate/**/origin`).

**arra-oracle-v3 git**: on main at `f27ed43b`. Only #1098 (Python reranker sidecar, the 478-file divergent branch) still open from marathon — separate concern.

**ui-oracle git**: PR #88 open on `chore/calver-hmm-indexer` (the active dev branch). Mergeable, build clean.

**Cron**: not running.

## Pending

### Awaiting review (no action from me)
- [ ] PR #88 ui-oracle (cache fix) — awaiting maintainer review
- [ ] PR #1098 arra-oracle-v3 (Python reranker sidecar) — still open, branch was 478-file divergent

### Actionable next session
- [ ] Comment on PR #88 with the un-tested cases (nomic regression check, bge-m3 still works, end-to-end workaround for existing poisoned caches)
- [ ] Once #88 lands → wrangler deploy to studio.buildwithoracle.com so live users get the fix
- [ ] Re-index qwen3 with `qwen3-embedding:4b` for bench-winning quality (~1hr; current 0.6b is fine but 4b won the +29 cross-lang bench)
- [ ] /aria-map other studio pages (`/feed`, `/search`, `/traces`, `/canvas`) for future click-test catalogs
- [ ] Issue #1111 (FTS5 missing from drizzle migrations) — fresh-install correctness

### Awaiting explicit OK
- [ ] PM2 bootstrap of `ecosystem.oracle-stack.config.js` (currently services run via direct `bun &` — works but no auto-restart)

## Next Session

- [ ] /recap to orient
- [ ] Check PR #88 review status — if landed, run wrangler deploy
- [ ] Decide: re-index with 4b, work on a new track, or clean up trailing items

## Key Files

- `ψ/memory/retrospectives/2026-05/05/08.49_port-and-qwen3-fix.md` — full retro (this session)
- `ψ/memory/learnings/2026-05-05_d-before-a-and-cache-poisoning.md` — codified patterns
- `ψ/lab/blog/2026-05-05_d-before-a-team-agent-verification.md` — technical blog
- `ψ/lab/smoke/e2e-indexer-daemon.sh` — reproducible smoke
- `ψ/incubate/Soul-Brews-Studio/ui-oracle/ui-oracle.md` — incubation hub for the click-bug fix work
- `~/.claude/skills/{check-stack,click-test,aria-map}/SKILL.md` — 3 new global skills
- `~/.claude/projects/.../memory/MEMORY.md` — 6 feedback memories now (4 → 6)
- arra-oracle-v3 PRs #1108/#1112/#1110 (merged), #1098 (open, separate concern)
- ui-oracle PR #88 (open, awaiting review)

## Cross-Repo / Federation Notes

- Live studio at `studio.buildwithoracle.com/map` still has the OLD code — wrangler deploy of `chore/calver-hmm-indexer` (after #88 merges) will ship the fix
- Existing users with poisoned `map3d:qwen3` IDB cache need manual eviction (24h TTL otherwise) — workaround in PR #88 body
- arra-oracle-v3 alpha is now == main; cleanly synced
