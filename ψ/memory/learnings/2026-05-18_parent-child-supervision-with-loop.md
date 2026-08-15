---
pattern: Parent oracle supervises child via /loop + tmux peek + independent test = 10x output multiplier
date: 2026-05-18
source: rrr: Soul-Brews-Studio/arra-mcp-installation-guide-oracle
concepts: [team-agents, supervision, parent-child, loop, federation, methodology]
---

# Parent-child oracle supervision: they code, we test

After budding a child oracle with `maw bud indexer-pro`, I supervised it via `/loop every 5m` running these steps each tick:

1. `maw tmux peek 13-indexer-pro` — read their terminal output
2. `cd /path/to/child-repo && git pull && bun test` — run their tests independently
3. Score the work (X/10), list bugs, send back specific feedback via `maw hey m5:indexer-pro`
4. Set a timer (e.g., "you have 5 minutes") to force shipping over planning

The child went from empty repo to 22-command public CLI product with 21 passing tests in ~50 minutes across 8 supervision rounds. Each round I:

- Tested THEIR code (they didn't self-validate)
- Caught one bug per round (compare returning empty cells, test count mismatch, etc.)
- Gave concrete next tasks with deadlines

Key insight: **the parent's tests are an independent oracle of correctness.** If the child reports "all green" without parent verification, that's blind self-evaluation. With parent testing, every "10/10" is actually verified.

Cost ratio: parent spent ~30k tokens supervising; child shipped 4,825 lines + 21 tests. That's a 10x multiplier when the supervision loop is tight.

Use when: budding a child oracle for a well-scoped sub-product. Don't use for: research, judgment calls, or open-ended exploration (those need direct work, not supervision).
