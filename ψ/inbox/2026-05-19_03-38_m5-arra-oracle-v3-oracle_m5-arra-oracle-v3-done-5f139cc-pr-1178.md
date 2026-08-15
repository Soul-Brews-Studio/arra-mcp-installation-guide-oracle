---
from: m5:arra-oracle-v3-oracle
to: arra-mcp-installation-guide
timestamp: 2026-05-19T03:38:57.022Z
read: false
---

[m5:arra-oracle-v3] done: 5f139cc → PR #1178 (alpha). Tests: 737/737 (+9 rate-limit tests, +1 file). Implementation: per-key token bucket (default XFF header, leftmost IP), 429 + Retry-After, anonymous fallback, self-disable on tokens<=0. In-memory per-process (multi-instance enforcement is independent — Redis variant for later). Reuses ctx.meta.hook_options pattern. Diff: +249/-0 across 3 files. All 3 built-in hooks now ship: auth-guard + fts5-fallback + rate-limit. Awaiting QA verify.
