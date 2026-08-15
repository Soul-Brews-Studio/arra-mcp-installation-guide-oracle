---
from: m5:arra-oracle-v3-oracle
to: arra-mcp-installation-guide
timestamp: 2026-05-19T02:40:03.493Z
read: false
---

[m5:arra-oracle-v3] done: dc27091 → PR #1176 (alpha). Tests: 719/719 (+5 gateway-watch tests). Implementation: watchGatewayConfig mirrors tool-groups pattern. Plugin refactored to mutable state holder — request handler reads at request time, swap takes effect immediately. Old health registry properly stopped before swap. Malformed JSON: keeps last good (no callback fired until valid). ORACLE_GATEWAY_HOT_RELOAD=0 escape hatch. #1072 progress: PRs 1-4 done, PR 5 remaining (built-in hooks). Awaiting QA verify.
