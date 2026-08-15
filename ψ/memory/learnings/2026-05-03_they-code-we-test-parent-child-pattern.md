---
title: "They code, we test" — the correct parent-child oracle supervision pattern
tags: [parent-child, testing, federation, maw, team-agents, bud]
created: 2026-05-03
source: rrr: Soul-Brews-Studio/arra-mcp-installation-guide-oracle
---

# "They code, we test" — parent-child oracle pattern

Independent verification catches bugs that self-testing misses. When supervising a child oracle via maw federation:

1. Send the task with clear spec + timer
2. Peek (`maw tmux peek`) to monitor progress
3. When they push, PARENT pulls and runs tests independently
4. Send feedback with score + specific bugs + next task
5. Repeat until 10/10

The child's compare command rendered an empty table — it "worked" when self-tested (no crash) but failed parent's test (no results). Different eyes, different standards.

Pattern: `/loop every 5m challenge and test` with `maw hey m5:<child> "feedback"`.
