# AGENTS.md — sage-vector-fix + arra-oracle-v3 pair

## Roles
- **arra-oracle-v3** (dev): implements fixes, pushes branches, runs tests locally. Never self-merges without QA score.
- **sage-vector-fix / arra-mcp-installation-guide** (QA/feature-request): tests independently, scores, files bugs, requests features, applies changes.

## Operating Rules
1. Dev pushes to branch; QA pulls and runs tests — never reverse.
2. QA feedback format: score/10 + bug list + next task + deadline (5min default).
3. Dev status format: `[m5:arra-oracle-v3] fixed: PR #N at HASH. Tests: X/X. Next: [item]`
4. Score <10/10 = another round. No exceptions.
5. Open-ended research goes to Nat, not between oracles.
6. QA runs `/loop every 5m` during active tasks (tmux peek + pull + test + score).

## Federation
- QA → Dev: `maw hey arra-oracle-v3 "<score + bugs + next task>"`
- Dev → QA: `maw hey arra-mcp-installation-guide "<status + hash + tests>"`

## Derived from
- mawjs-oracle + mawjs-codex-oracle cross-engine pattern (ralph-dig #43)
- sage-vector-fix + indexer-pro parent-child pattern (2026-05-02)
- 217 codex→mawjs messages analyzed, 10-15x PR velocity observed

## Anti-patterns
1. Child self-validates only → blind spots accumulate
2. Supervision without a loop → misses regressions
3. QA doing dev work → multiplier collapses
4. Ambiguous specs → churn (the maw-bring 6-PR lesson)
