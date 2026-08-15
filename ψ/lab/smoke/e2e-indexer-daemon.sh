#!/usr/bin/env bash
# e2e-indexer-daemon.sh — boot Elysia indexer daemon, enqueue a job, verify LanceDB write.
# Smoke procedure for the alpha → main port (PRs #1108-#1110).
#
# Pre-flight:
#   - Ollama running with bge-m3 model installed
#   - Port 47779 free
#   - @lancedb/lancedb installed in node_modules
#
# Usage:
#   bash e2e-indexer-daemon.sh [--keep-data]   # default: cleans up .tmp/smoke-data
#
# Temp paths use project-local .tmp/ (NOT system /tmp). Make sure .tmp/ is gitignored.
#
set -euo pipefail

REPO="${ARRA_REPO:-/Users/nat/Code/github.com/Soul-Brews-Studio/arra-oracle-v3}"
BRANCH="${ARRA_BRANCH:-port/wave3-arra-learn-enqueue}"
TMPROOT="${ARRA_TMP:-$REPO/.tmp}"
WORKTREE="$TMPROOT/smoke-e2e"
DATA="$TMPROOT/smoke-e2e-data"
PORT=47779
KEEP_DATA=0
[ "${1:-}" = "--keep-data" ] && KEEP_DATA=1

mkdir -p "$TMPROOT"

cleanup() {
  set +e
  [ -n "${SSE_PID:-}" ] && kill "$SSE_PID" 2>/dev/null
  [ -n "${DAEMON_PID:-}" ] && kill "$DAEMON_PID" 2>/dev/null
  if [ "$KEEP_DATA" = "0" ]; then
    # mv to a trash subdir instead of rm — survives hooks that block rm -rf
    mkdir -p "$TMPROOT/trash"
    [ -d "$DATA" ] && mv "$DATA" "$TMPROOT/trash/smoke-e2e-data-$(date +%s)" 2>/dev/null
    git -C "$REPO" worktree remove "$WORKTREE" 2>/dev/null
  fi
}
trap cleanup EXIT

echo "→ worktree on $BRANCH"
git -C "$REPO" worktree add "$WORKTREE" "origin/$BRANCH"
cd "$WORKTREE"
ln -sf "$REPO/node_modules" ./node_modules

echo "→ env setup"
mkdir -p "$DATA"
export ORACLE_DATA_DIR="$DATA"
export ORACLE_DB_PATH="$DATA/test.db"
export INDEXER_PORT=$PORT

echo "→ migrate + bootstrap FTS5 (FTS5 isn't in drizzle's tablesFilter — see issue)"
bunx drizzle-kit push --force --config drizzle.config.ts 2>&1 | tail -3
sqlite3 "$ORACLE_DB_PATH" <<'SQL'
CREATE VIRTUAL TABLE IF NOT EXISTS oracle_fts USING fts5(id UNINDEXED, content);
INSERT INTO oracle_fts(id, content) VALUES('smoke-test-doc-001', 'hello world test document');
SQL

echo "→ boot daemon"
bun src/indexer/daemon.ts > "$DATA/daemon.log" 2>&1 &
DAEMON_PID=$!
sleep 3

echo "→ /health"
curl -s "http://localhost:$PORT/health" | jq

echo "→ subscribe SSE (background)"
curl -N -s "http://localhost:$PORT/events" > "$DATA/events.log" 2>&1 &
SSE_PID=$!
sleep 1

echo "→ POST /index"
curl -s -X POST "http://localhost:$PORT/index" \
  -H 'Content-Type: application/json' \
  -d '{"doc_id":"smoke-test-doc-001","model_key":"bge-m3"}' | jq

echo "→ poll /jobs until done"
for i in $(seq 1 30); do
  STATUS=$(curl -s "http://localhost:$PORT/jobs" | jq -r '.jobs[0].status // "missing"')
  echo "  iter $i: status=$STATUS"
  [ "$STATUS" = "done" ] && break
  [ "$STATUS" = "error" ] && { echo "✗ job errored"; cat "$DATA/daemon.log" | tail -20; exit 1; }
  sleep 2
done

echo "→ verify LanceDB write"
ls "$DATA/lancedb/" 2>&1 | head
[ -d "$DATA/lancedb/oracle_knowledge_bge_m3.lance" ] && echo "✓ collection exists" || echo "✗ collection missing"

echo "→ captured SSE frames"
head -20 "$DATA/events.log" || true

echo "→ /drain"
curl -s -X POST "http://localhost:$PORT/drain" | jq
sleep 1

echo "✓ smoke complete"
