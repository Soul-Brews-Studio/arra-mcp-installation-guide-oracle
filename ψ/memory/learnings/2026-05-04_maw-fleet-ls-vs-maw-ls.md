---
pattern: maw fleet ls vs maw ls — different sources of truth
date: 2026-05-04
source: mawjs-oracle reply via maw hey federation
project: github.com/ARRA-01/maw-js
---

# maw fleet ls vs maw ls

| Command | What it shows | Source |
|---------|---------------|--------|
| `maw ls` | **Live tmux sessions only** (sessions currently running) | tmux server |
| `maw fleet ls` | **All fleet configs** (registered oracles, running OR stopped) | `~/.config/maw/fleet/*.json` |

`maw fleet ls` output format: `NN-session-name`, window count, running/stopped status. Reads the fleet directory directly — survives session death.

`maw ls` output: only what tmux can see right now. If an oracle was hibernated via `maw fleet hibernate`, it disappears from `maw ls` but stays in `maw fleet ls`.

Use `maw fleet resume <name>` to bring a hibernated oracle back from fleet config.

Source: confirmed by mawjs-oracle (m5:Soul-Brews-Studio/mawjs-oracle) via maw hey federation reply on 2026-05-04.
