---
query: "can we merge the 9 stacked PRs"
target: "Soul-Brews-Studio/arra-oracle-v3"
mode: deep --team-agents
timestamp: 2026-05-05 05:21
friction_score: 0.9
coverage: [oracle, files, git, github]
confidence: high
---

# Trace: Can we merge?

**Target**: Soul-Brews-Studio/arra-oracle-v3 (alpha)
**Mode**: deep + 3 parallel agents | **Friction**: 0.9 | **Confidence**: high
**Time**: 2026-05-05 05:21

## Verdict — YES (with one retarget step)

All 9 PRs are `MERGEABLE` (no conflicts, no `CHANGES_REQUESTED`). CI shows `UNSTABLE` on most, but only because non-blocking notifier (`add-to-inbox`) is QUEUED and unit-test workflow didn't trigger on later stacked PRs — no hard failures. Two PRs ran the full suite: **#1098 and #1102 — both PASSED**.

## PR Mergeability Table

| #    | Mergeable | CI       | Reviews    | Base                          | Note                          |
|------|-----------|----------|------------|-------------------------------|-------------------------------|
| 1098 | MERGEABLE | UNSTABLE | 0          | alpha                         | Tests PASS · 171 commits      |
| 1100 | MERGEABLE | UNSTABLE | COMMENTED  | alpha                         | No test workflow ran          |
| 1101 | MERGEABLE | UNSTABLE | 0          | alpha                         | depends #1100                 |
| 1102 | MERGEABLE | CLEAN    | COMMENTED  | alpha                         | **Tests PASS** — base of stack |
| 1103 | MERGEABLE | UNSTABLE | COMMENTED  | feat/indexer-jobs-table-m1    | **needs retarget to alpha**   |
| 1104 | MERGEABLE | UNSTABLE | COMMENTED  | feat/indexer-worker-m2        | needs retarget after #1103    |
| 1105 | MERGEABLE | UNSTABLE | 0          | alpha                         | independent                   |
| 1106 | MERGEABLE | UNSTABLE | COMMENTED  | feat/indexer-daemon-m3        | needs retarget after #1104    |
| 1107 | MERGEABLE | UNSTABLE | COMMENTED  | feat/indexer-jobs-table-m1    | **sibling of #1103**, not child of #1106 |

## Dependency Graph (verified via `git merge-base --is-ancestor`)

```
alpha (eaddbb9)
├── #1098 reranker-sidecar              (independent · 171 commits, Python only)
├── #1100 reranker-helper               (independent · +1)
│   └── #1101 reranker-search-integration (depends on #1100 · +1)
├── #1102 indexer-jobs-table-m1         (independent · +2)
│   ├── #1103 indexer-worker-m2         (depends on #1102 · +1)
│   │   └── #1104 indexer-daemon-m3     (depends on #1103 · +1)
│   │       └── #1106 indexer-cli-m4    (depends on #1104 · +1)
│   └── #1107 arra-learn-enqueue-m5     (depends on #1102 only · +1)  ← sibling, not descendant
└── #1105 vector-precomputed-vectors    (independent · +1)
```

## Recommended Merge Order

**Wave 1 — independents (any order, fully parallel):**
- #1098 reranker-sidecar
- #1100 reranker-helper
- #1102 indexer-jobs-table-m1
- #1105 vector-precomputed-vectors

**Wave 2 — depends on Wave 1:**
- #1101 (after #1100)
- #1107 (after #1102 — parallel to indexer chain)

**Wave 3 — sequential indexer chain (after #1102):**
- Retarget #1103 to alpha → merge
- Retarget #1104 to alpha → merge
- Retarget #1106 to alpha → merge

## Risks (🟠 watch list)

1. **Retarget required** — #1103, #1104, #1106 currently base on their predecessors. After #1102 lands, GitHub may auto-close them on M1 merge if not retargeted to alpha first. **Use `gh pr edit <#> --base alpha` BEFORE merging the parent.**

2. **Migration `0016_indexing_jobs.sql`** — Renumbered to dodge alpha (0006) vs main (0015) collision. Lands cleanly on alpha. **Future risk**: when alpha catches up to main, the catchup author must NOT renumber 0016 back, and must not collide with new migrations between 0015 and catchup time. Flag for the catchup PR.

3. **#1107 functional dependency** — Env gate is safe to merge, but flipping `ORACLE_INDEXER_ENQUEUE=1` requires #1102 + #1103 + #1104 (daemon running) to drain the queue. Without daemon, jobs accumulate as `pending` forever (silent backlog, no data loss).

4. **Hono vs Elysia drift** — #1104 uses Hono (matches alpha). The eventual catchup to main (Elysia) will need router translation in `api.ts`. Maintainer judgment.

5. **Test coverage** — Only #1098 and #1102 ran the full unit/integration suite. Others may not have triggered the workflow due to GitHub Actions filters. **Recommend re-running CI on #1100, #1101, #1103-1107 before each merge** as a safety net (their hermetic tests pass locally).

## Friction Analysis

**Score**: 0.9 (Near-perfect — Oracle/handoff context + medium-high confidence)
**Coverage**: oracle (handoff), files (PR view), git (ancestry), github (PR API) — 4 of 5 dimensions
**Goal check**: Question fully answered. Order is concrete. Retarget step is the one operational gotcha.

## Summary

| Question | Answer |
|---|---|
| Can we merge? | **Yes** — all 9 are MERGEABLE |
| All at once? | **No** — 3 PRs need retargeting after #1102 |
| Right now? | **Yes** for #1098 / #1100 / #1102 / #1105 (Wave 1 independents) |
| Blockers? | None hard. Soft: re-run CI on stacked PRs to be sure |
| Author of M1-M5? | jeera-p / arra-mcp-installation-guide (this oracle's marathon work) |

**Next**: pick a wave to start with, or kick CI re-runs on the UNSTABLE PRs first.
