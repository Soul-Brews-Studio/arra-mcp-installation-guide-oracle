# RTK Quick Reference Guide

## What RTK Does

**RTK (Rust Token Killer)** is a high-performance CLI proxy that intercepts shell commands and compresses their output before it reaches your LLM context. By filtering noise, grouping related items, and deduplicating logs, RTK reduces token consumption by 60-90% on common development operations—without changing your workflow or losing essential information.

A single Rust binary with zero external dependencies, RTK achieves this through four strategies: smart filtering (removes comments and whitespace), grouping (aggregates similar items by directory or type), truncation (keeps relevant context, cuts redundancy), and deduplication (collapses repeated log lines with counts).

## Installation

### Homebrew (Recommended)
```bash
brew install rtk
```

### Quick Install Script (Linux/macOS)
```bash
curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh
# Installs to ~/.local/bin. Add to PATH if needed:
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc  # or ~/.zshrc
```

### Cargo
```bash
cargo install --git https://github.com/rtk-ai/rtk
```

### Pre-built Binaries
Download from [GitHub Releases](https://github.com/rtk-ai/rtk/releases):
- **macOS**: `rtk-x86_64-apple-darwin.tar.gz` or `rtk-aarch64-apple-darwin.tar.gz`
- **Linux**: `rtk-x86_64-unknown-linux-musl.tar.gz` or `rtk-aarch64-unknown-linux-gnu.tar.gz`
- **Windows**: `rtk-x86_64-pc-windows-msvc.zip`

### Verify Installation
```bash
rtk --version    # Should show version number
rtk gain         # Should display token savings stats
```

> **Name Collision Warning**: Another project called "rtk" (Rust Type Kit) exists. If `rtk gain` fails with "command not found," verify correct installation with the commands above.

## Core Commands

| Command | What It Does | Typical Savings | Use Case |
|---------|-------------|-----------------|----------|
| `rtk ls [args]` | Directory listing with tree view | -80% | Browse directory structure |
| `rtk tree [args]` | Directory tree with token optimization | -80% | Show full hierarchy |
| `rtk read <file>` | Smart file reading (supports `-l aggressive` for signatures only) | -70% | View code while keeping context |
| `rtk find <pattern> [path]` | Compact find results | -75% | Search files efficiently |
| `rtk grep <pattern> [path]` | Grouped search results | -80% | Pattern matching without noise |
| `rtk diff <file1> [file2]` | Condensed diff output | -75% | Compare files compactly |
| `rtk git status` | Compact git status | -80% | Check repo state |
| `rtk git log` | One-line commit format | -80% | Browse history |
| `rtk git diff` | Condensed git diff | -75% | View changes |
| `rtk gh pr list` | Compact PR listing | -80% | List pull requests |
| `rtk gh pr view <number>` | PR details + checks | -75% | Inspect PR |
| `rtk cargo test` | Test output (failures only) | -90% | Run Rust tests |
| `rtk cargo build` | Build output (warnings/errors only) | -80% | Compile Rust |
| `rtk pytest` | Python test output (failures only) | -90% | Run pytest |
| `rtk go test` | Go test output (NDJSON format) | -90% | Test Go code |
| `rtk jest` | Jest results (failures only) | -90% | Run Jest tests |
| `rtk vitest` | Vitest results (failures only) | -90% | Run Vitest tests |
| `rtk playwright test` | E2E results (failures only) | -90% | Run Playwright tests |
| `rtk ruff check` | Python linting (grouped by file) | -80% | Check Python code |
| `rtk lint` | ESLint errors grouped by rule | -80% | Check JS/TS code |
| `rtk tsc` | TypeScript errors grouped by file | -80% | Type-check code |
| `rtk prettier --check .` | Files needing formatting | -75% | Find format issues |
| `rtk npm list` | Compact dependency tree | -75% | Browse dependencies |
| `rtk pnpm list` | pnpm dependencies (ultra-compact) | -80% | List monorepo packages |
| `rtk pip list` | Python packages (auto-detects uv) | -80% | Show Python deps |
| `rtk docker ps` | Compact container list | -80% | List containers |
| `rtk docker images` | Compact image list | -80% | List Docker images |
| `rtk docker logs <container>` | Deduplicated logs | -85% | View container logs |
| `rtk kubectl pods` | Compact pod list | -80% | List K8s pods |
| `rtk aws <service> <action>` | Compact AWS CLI output (forces JSON) | -75% | Query AWS resources |
| `rtk json <file>` | JSON structure without values | -80% | View JSON schema |
| `rtk env [-f AWS]` | Environment variables (filtered, masked) | -70% | Show env vars |
| `rtk log <logfile>` | Deduplicated log output | -85% | Analyze logs |
| `rtk err <command>` | Show only errors/warnings | -90% | Extract errors from output |
| `rtk test <command>` | Show only test failures | -90% | Generic test wrapper |
| `rtk gain` | Token savings stats | N/A | See session savings |
| `rtk gain --history` | Recent command history | N/A | Analyze usage patterns |
| `rtk gain --graph` | ASCII graph (last 30 days) | N/A | Visualize savings |
| `rtk discover` | Find missed savings opportunities | N/A | Optimize usage |
| `rtk proxy <command>` | Raw passthrough (for debugging) | 0% | Bypass all filtering |

## Claude Code Integration

RTK integrates transparently with Claude Code via the **PreToolUse hook**, which intercepts bash commands and rewrites them before execution.

### Installation

```bash
# Install hook for Claude Code (default)
rtk init -g

# Install hook for other agents
rtk init -g --agent cursor     # Cursor
rtk init -g --agent windsurf   # Windsurf
rtk init --agent cline          # Cline / Roo Code
rtk init --agent kilocode       # Kilo Code
rtk init --agent antigravity    # Google Antigravity
```

### How It Works

The hook transparently rewrites commands **before** Claude sees them:

```
git status  →  (hook intercepts)  →  rtk git status  →  (filtered output to Claude)
```

Claude never sees the rewrite—it just receives compact output and uses fewer tokens. The hook runs on all Bash tool calls automatically.

### Verification

After installation, restart your AI tool and test:
```bash
git status   # Should run as "rtk git status" internally (you won't see the rewrite)
rtk gain --history  # Verify RTK is logging activity
```

### How to Disable Per-Command

```bash
RTK_DISABLED=1 git status   # Skip RTK, run raw command
```

### Supported Agents

| Agent | Mechanism | Setup |
|-------|-----------|-------|
| Claude Code | Shell hook (`PreToolUse`) | `rtk init -g` |
| Cursor | Shell hook (`preToolUse`) | `rtk init -g --agent cursor` |
| Windsurf | Rules file (`.windsurfrules`) | `rtk init -g --agent windsurf` |
| Cline / Roo Code | Rules file (`.clinerules`) | `rtk init --agent cline` |
| Copilot (VS Code) | Rust binary hook | `rtk init --copilot` |
| Codex | Instructions document | `rtk init --codex` |

## Configuration

RTK stores configuration and usage stats in `~/.rtk/`:

- **`config.toml`**: User configuration (optional, auto-created with `rtk config --create`)
- **`rtk.db`**: SQLite database tracking command usage and token savings

### Creating a Config File

```bash
rtk config --create
```

This creates `~/.rtk/config.toml` with default settings. Tune output verbosity, disable specific commands, or set filtering levels.

### Excluding Commands

In `~/.config/rtk/config.toml`, add:
```toml
[exclude_commands]
commands = [
    "git push",           # Exclude git push
    "^rtk.*",            # Exclude already-RTK commands
    "sensitive_command"   # Exact match
]
```

Commands matching these patterns will skip RTK filtering and run raw.

## Compatibility & Caveats

### Platform Support
- **macOS** (x86_64, Apple Silicon): Full support
- **Linux** (x86_64, ARM64): Full support, MUSL binary for Alpine/busybox
- **Windows**: Supported via pre-built executable and WSL (native hook support)

### Known Issues

1. **Name Collision**: `reachingforthejack/rtk` (Rust Type Kit) is a different project. Use `cargo install --git https://github.com/rtk-ai/rtk` to ensure correct installation.

2. **First-Call Overhead**: RTK has <10ms startup overhead (first command may be slightly slower due to filter compilation). Subsequent commands are cached.

3. **Interactive Commands**: RTK is batch-mode only. Interactive TUIs (vim, htop, less) are not supported.

4. **Windows Differences**: The hook system works fully on WSL but has limited support on native Windows CMD/PowerShell. Use WSL for best experience.

5. **Flag Awareness**: When you explicitly request verbose output (e.g., `cargo test -- --nocapture`), RTK respects that and passes through more content. Default output is aggressively compressed.

## Useful Tips

1. **Check Savings in Real Time**
   ```bash
   rtk gain --history    # See recent commands and token savings
   rtk gain --graph      # Visualize last 30 days of savings
   ```

2. **Find Missed Opportunities**
   ```bash
   rtk discover          # Scan recent commands, find unoptimized ones
   rtk discover --all    # Scan all projects
   ```

3. **Bypass Filtering When Needed**
   ```bash
   rtk proxy git log --stat  # Get full unfiltered output (tracked but not compressed)
   RTK_DISABLED=1 cargo test  # Skip RTK entirely for one command
   ```

4. **Ultra-Compact Mode for Maximum Savings**
   ```bash
   git status --ultra-compact  # ASCII icons, inline format (Level 2 optimization)
   ```

5. **Tune Filtering by Project**
   Create `.rtk/config.toml` in your project root to override global settings for specific repos. The local config takes precedence over `~/.rtk/config.toml`.

---

**Version**: RTK 0.38.0+  
**Docs**: [rtk-ai.app](https://www.rtk-ai.app) | [GitHub](https://github.com/rtk-ai/rtk)  
**Issues**: [github.com/rtk-ai/rtk/issues](https://github.com/rtk-ai/rtk/issues)
