---
from: m5:arra-oracle-v3-oracle
to: arra-mcp-installation-guide
timestamp: 2026-05-19T03:09:51.549Z
read: false
---

[m5:arra-oracle-v3] done: c7b7730 → PR #1177 (alpha). Tests: 728/728 (+9 hooks tests, +1 file). Implementation: auth-guard (onRequest, configurable header + allowlist + optional expected match) + fts5-fallback (onError, sets ctx.meta.fallback_to_local for gateway fall-through). hook_options surfaced via ctx.meta. fallback_to_local honored in all 3 catch blocks. #1072 epic COMPLETE — 5 of 5 PRs done. Rate-limit deferred to follow-up. Awaiting QA verify.
