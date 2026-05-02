---
title: Check process ownership before debugging data corruption
tags: [debugging, lancedb, process, port, zombie]
created: 2026-05-02
source: rrr: Soul-Brews-Studio/arra-mcp-installation-guide-oracle
---

# Check process ownership before debugging data corruption

When a server returns stale/corrupt data after restart, check `lsof -i :PORT` FIRST. A zombie process holding the port with cached state will serve old data regardless of how many times you rebuild the underlying files. We spent 30 minutes moving LanceDB directories and rebuilding collections while PID 44884 silently held port 47778 with a corrupt LanceDB connection cached in memory. One `kill` fixed everything.

Diagnostic order: process → port → data → code.
