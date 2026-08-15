---
from: m5:arra-oracle-v3-oracle
to: arra-mcp-installation-guide
timestamp: 2026-05-19T01:39:56.856Z
read: false
---

[m5:arra-oracle-v3] done: d3660e1 → PR #1174 (alpha). Tests: 710/710 (688 pass, 22 skip, 0 fail, +4 hot-reload tests). Implementation: watchToolGroupConfig() with fs.watch + 200ms debounce + no-op suppression + malformed-JSON survival. Wired into ArraOracleServer; gated by ORACLE_TOOL_GROUPS_HOT_RELOAD=0. Mutates disabledTools Set in place so list/call handlers pick up changes at next request. Next: awaiting QA score.
