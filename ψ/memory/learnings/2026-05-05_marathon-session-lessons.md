---
pattern: 30-iteration cron-driven contribution chain — 10 PRs, 70 tests, 4 architectural memories — what made it work
date: 2026-05-05
source: rrr after the marathon (5fd1aebf 2026-05-04 21:21 → 2026-05-05 05:03)
project: github.com/Soul-Brews-Studio/arra-oracle-v3
---

# Marathon Session — What Made It Work

## TL;DR

A 30-hour cron-driven contribution chain that produced 10 PRs (1 merged, 9 open against alpha), ~2,680 LOC of TS/Python, 70 hermetic tests, 12 vault learnings, 1 deploy runbook, and 4 architectural memories. Operating mode that worked: **stacked PRs + dependency injection + empirical honesty + every-iteration ships ONE concrete artifact**.

## The 5 invariants that compounded

1. **Don't fake the metric.** Smoke +14.3 / real-corpus +0 = both reported. Bench-blindness diagnosed and named. No quality claims past what the eval can support.

2. **Degrade gracefully over error.** Reranker timeout = load-shedder by design. Worker error → markJobError, doesn't poison the worker. arra_learn enqueue catches its own throw. Search NEVER blocks on the secondary.

3. **Anticipate branch catchup.** Alpha is X commits behind main; numbered artifacts (migrations, sequence IDs) need `max(alpha, main) + 1`. Hono-vs-Elysia drift on alpha caught. Inline-embed presence on main but not alpha caught. Each catch saved a real bug.

4. **Stigmergic disclosure.** Limitations called out in PR bodies became triggers for the next PR. PR #1104 surfaced double-embed → PR #1105 fixed it next iteration. The chain self-prioritizes when each PR leaves a trail.

5. **Pure dependency injection everywhere.** M2 worker, M3 API, M4 CLI, M1 helpers, reranker helper — every function takes deps as parameters, no global state. Tests inject mocks. Production wires real adapters. Both work without changing the function.

## Why stacking PRs scales

| Property | Mega-PR | Stacked PRs |
|----------|---------|-------------|
| Per-PR diff size | 500-2000+ LOC | 150-500 LOC |
| Review fits in head | rarely | usually |
| Merge-time conflicts | catastrophic | localized |
| Rollback granularity | all or nothing | per-PR |
| Independent testability | per-feature | per-PR |
| Reviewer pace flexibility | low | high |

The 10 PRs across this session each had their own tests defending their own contract. When PR #1102 (M1) lands, PR #1103 (M2) can rely on its API staying stable — because the test suite locks it in. That's the mechanism behind "stacked PRs work."

## Where it broke down

- **Test mocks drift from real shapes.** The `??` null-coalescing footgun absorbed an intentional null in a worker test mock. Caught by output inspection mid-test, but if I'd been less attentive it would have shipped. Hermetic tests catch invariants; they don't catch reality drift. Need at least one end-to-end smoke test per chain run.

- **PR bodies inflate over time.** I wrote big PR descriptions: empirical numbers, caveats, dependency chains, future work. Useful at the moment of writing. By the time alpha catches up to main, those bodies will reference benchmarks that may not reproduce. Better posture: link to vault learnings (mutable) rather than inline numbers (frozen).

- **Stale-branch realities cost iterations.** Each catch (migration numbering, schema drift, route framework) ate one iteration. A `bun run alpha-status` script that shows "alpha is N commits behind main, last fast-forward was X" at the start of each iteration would have saved time. Worth building if the cron resumes.

## Reusable artifacts

- `rerank_lift_unpaired_bench.py` — Python bench harness, drops in any embedding model
- `rerank_latency_bench.py` — concurrent latency measurement
- `sea_lion_bench.py` — single-model HF eval template
- `real_corpus_rerank_bench.py` — live API + reranker end-to-end
- DEPLOY-UI.md — operator runbook for the 6 Cloudflare Worker deploys
- `ψ/lab/indexer-cli/DESIGN.md` — full M1-M7 design (M5 shipped, M6/M7 deferred)
- 4 architectural memories at `~/.claude/projects/.../memory/`

## What I'd do differently

1. **Run an end-to-end smoke per chain.** The indexer M1-M5 has 70 hermetic tests but ZERO end-to-end. If the daemon's `daemon.ts` has a wiring bug, no test catches it. Worth a 1-test smoke that boots the daemon, enqueues, and verifies the worker writes to LanceDB.

2. **Set up the alpha-status visibility before iteration 2.** I caught drift by accident multiple times. A small status check at the start of each cron tick would surface it deterministically.

3. **Open issues for deferred work as I defer it.** I deferred `scan/backfill`, real-corpus eval, alpha-vs-main reconciliation, and wrangler deploy. Some are referenced in PR bodies, some only in vault. A formal GH issue per deferred item would make the work visible to maintainers.

4. **Stop iterating earlier.** The session went 30 hours. Diminishing returns started around hour 25 (after M3). M4 and M5 were valuable but the marginal yield per iteration was lower. A self-aware "I've done enough; it's a sleep" check would have been honest.

## What stays valuable

- The architectural memories ("Don't fake the metric", "Degrade over error", "Anticipate branch catchup", "Stigmergic disclosure") will guide future iterations regardless of what specific PRs land.
- The plug-play architecture for embedding models — table per model, vector field per doc, deps injected — generalizes beyond this project.
- The dependency-injection pattern is the meta-trick. Every function in the indexer-CLI is testable because every dependency is a parameter.
- The empirical chain (10+ benches) shows the pattern: stress-test for capability ceilings, real-corpus for production behavior, latency for operational planning. All three needed.

## What's NOT yet validated empirically (tech debt I'm tracking)

- M5's enqueue switch hasn't been turned on against a live daemon. Architecture works in tests; activation is unverified end-to-end.
- The 50+-query real-corpus eval doesn't exist. Current production claim ("reranker +0 on the limited 12-query sample") is honest but small.
- Wrangler deploy hasn't been re-run. Last deploy state was already-live; my runbook is documentation, not action.
- Alpha-vs-main reconciliation requires maintainer judgment when alpha catches up.

These aren't shipped lies. They're shipped honest gaps. Future iterations close them or document why not.
