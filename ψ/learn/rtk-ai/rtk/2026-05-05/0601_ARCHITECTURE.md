# RTK (Rust Token Killer) Architecture

**RTK v0.38.0** — High-performance CLI proxy that filters and compresses command outputs before they reach LLM context, achieving 60-90% token savings.

---

## Top-Level Directory Structure

```
rtk/
├── src/                    # Rust source code (main binary + libraries)
├── tests/                  # Integration tests
├── hooks/                  # Pre-tool-use hook scripts for AI agents
├── openclaw/              # OpenClaw MCP integration (Claude Code MCP)
├── Formula/               # Homebrew tap configuration
├── .rtk/                  # Internal config (cache, version checks)
├── scripts/               # Build and utility scripts
├── docs/                  # Markdown documentation
├── Cargo.toml            # Package manifest (deps, metadata)
├── build.rs              # Pre-build script
├── CHANGELOG.md          # Release notes
├── INSTALL.md            # Installation guide
├── README.md             # Project overview
└── CLAUDE.md             # RTK's own development guidelines
```

---

## Module Hierarchy (src/)

RTK is organized into **seven core modules** plus entry point:

### 1. **main.rs** — CLI Entry Point & Routing
- **Location**: `/src/main.rs` (~1500 lines)
- **Role**: Clap-based CLI parser and top-level command dispatcher
- **Key Components**:
  - `Cli` struct: Global flags (verbose, ultra_compact, skip_env)
  - `AgentTarget` enum: Target AI agents (Claude Code, Cursor, Windsurf, Cline, etc.)
  - `Commands` enum: All subcommands (ls, tree, read, git, cargo, pytest, etc.)
  - Per-command argument parsing (e.g., git with -C, -c, --git-dir flags)

### 2. **cmds/** — Language/Tool-Specific Filters
Organized by **ecosystem** with command-specific output formatters:

**Subdirectories**:
- **cloud/** (5 filters): aws_cmd, container, curl_cmd, psql_cmd, wget_cmd
- **dotnet/** (4 filters): dotnet_cmd, dotnet_format_report, dotnet_trx, binlog
- **git/** (5 filters): git.rs (main), diff_cmd, gh_cmd, glab_cmd, gt_cmd
- **go/** (2 filters): go_cmd, golangci_cmd
- **js/** (9 filters): npm_cmd, pnpm_cmd, tsc_cmd, vitest_cmd, pytest_cmd, prettier_cmd, prisma_cmd, next_cmd, playwright_cmd, lint_cmd
- **python/** (4 filters): pytest_cmd, pip_cmd, mypy_cmd, ruff_cmd
- **ruby/** (3 filters): rspec_cmd, rake_cmd, rubocop_cmd
- **rust/** (3 filters): cargo_cmd, runner, (mod.rs)
- **system/** (15 filters): ls, tree, grep_cmd, find_cmd, json_cmd, log_cmd, env_cmd, format_cmd, read, summary, pipe_cmd, wc_cmd, local_llm, deps, constants

**Pattern**: Each filter module exports a `run()` function that:
1. Spawns the native command
2. Captures raw stdout/stderr
3. Applies regex-based or heuristic filtering
4. Returns compact output

**Example** (git): `git status` output is summarized to: branch name, tracked/untracked counts, and any conflicts.

---

### 3. **core/** — Shared Filtering Infrastructure
Central logic for command execution, output processing, and telemetry.

**Key files**:
- **runner.rs** (100+ lines): Generic command runner with three modes:
  - `RunMode::Filtered(fn)` — Apply lambda filter to output
  - `RunMode::Streamed(Box<dyn StreamFilter>)` — Line-by-line streaming
  - `RunMode::Passthrough` — No filtering
- **filter.rs** (300+ lines): Code comment stripper with language detection
  - `FilterLevel` enum: None, Minimal, Aggressive
  - `Language` enum: Rust, Python, JS/TS, Go, C/C++, Java, Ruby, Shell, Data
  - Comment pattern matching for each language
- **stream.rs**: Streaming/line-buffered filtering (not block-based)
- **tracking.rs**: SQLite-backed telemetry recorder (see below)
- **telemetry.rs** / **telemetry_cmd.rs**: Command execution logging
- **tee.rs**: "Tee" mode to write raw output to disk while showing filtered
- **toml_filter.rs**: TOML-specific formatting
- **display_helpers.rs**: CLI formatting (colors, progress bars)
- **utils.rs**: Token counting heuristics (char-count approximation)
- **config.rs**: RTK config file parsing (~/.config/rtk/rtk.toml)

---

### 4. **analytics/** — Token Savings Dashboard & Export
Queries historical tracking data and displays metrics.

**Key files**:
- **gain.rs** (400+ lines): Main `rtk gain` command
  - Shows total/daily/weekly/monthly savings
  - Exports JSON/CSV
  - Supports project-scoped stats (added recently)
  - KPI-style formatted output
- **ccusage.rs**: Claude Code API usage integration
- **cc_economics.rs**: Cost modeling (tokens → $ estimates)
- **session_cmd.rs**: Per-session breakdown
- **mod.rs**: Module exports

**Output**: Token savings tracked in `~/.local/share/rtk/tracking.db` (SQLite).

---

### 5. **hooks/** — AI Agent Integration Layer
Pre-tool-use hook implementations for command rewriting.

**Key files**:
- **hook_cmd.rs** (300+ lines): Main hook entry point
  - Detects hook format (VS Code Copilot Chat vs GitHub Copilot CLI)
  - Auto-routes to handler (handle_vscode, handle_copilot_cli)
  - Reads up to 1 MiB stdin (JSON protocol)
  - Outputs rewritten command as JSON with permission decision
- **rewrite_cmd.rs**: Legacy rewrite logic
- **hook_check.rs**: Validates hook installation
- **hook_audit_cmd.rs**: Logs/audits hook calls
- **permissions.rs**: Permission check engine
- **trust.rs**: Allowlist/blocklist management
- **verify_cmd.rs**: Signature verification
- **init.rs**: Hook installation/setup
- **integrity.rs**: Hook health check
- **constants.rs**: Hook config paths

**Protocol** (Claude Code):
1. Hook receives JSON: `{ "tool_name": "Bash", "tool_input": { "command": "git log" } }`
2. Calls `rtk rewrite "git log"` (Rust registry-based)
3. Returns JSON with rewritten command + permissionDecision: "allow" or null (to prompt)

---

### 6. **discover/** — Command Registry & Rewrite Rules
Matches shell commands to RTK equivalents; drives all rewrites.

**Key files**:
- **rules.rs**: Static array `RULES[]` — 100+ rule objects
  - Pattern: regex matching the command
  - Rewrite: replacement command
  - Category: "Git", "Cargo", "Tests", "Files", etc.
  - Estimated savings %: heuristic (e.g., git log = 80%)
  - Status: Stable, Beta, Experimental
- **registry.rs** (400+ lines): Classification engine
  - `classify_command(cmd)` → Classification enum
  - Strips env prefixes (sudo, VAR=val)
  - Strips absolute paths (/usr/bin/grep → grep)
  - Strips git/golangci global options before subcommand
  - Applies regex rules in order (last match wins = most specific)
  - Returns: Supported with savings %, Unsupported, or Ignored
- **lexer.rs**: Tokenizes commands (splits on operators like &&, |, >)
- **provider.rs**: Detects tool providers (npm vs pnpm, pytest vs unittest)
- **report.rs**: Generates discovery reports (`rtk discover`)

**Command Rewrite Example**:
- Input: `git log --oneline -10`
- Rule matches: `git log`
- Rewrite to: `rtk git log --oneline -10`
- Estimated savings: 85% (git log = 200 avg tokens, filtered = ~30)

---

### 7. **learn/** — Auto-Discovery from History
Scans Claude Code history to find missed optimization opportunities.

**Key files**:
- **detector.rs**: Pattern matcher for unused RTK commands in logs
- **mod.rs**: `rtk discover` implementation
- **report.rs**: Human-readable discovery results

**Purpose**: Helps users find commands they ran (unoptimized) that RTK could have filtered.

---

## Entry Points & Execution Flow

### Binary: `rtk` (main executable)

**Cargo manifest** (`Cargo.toml` line 2-68):
```toml
[package]
name = "rtk"
version = "0.38.0"
edition = "2021"

[dependencies]
clap = "4"              # CLI parser
regex = "1"             # Pattern matching
rusqlite = "0.31"       # SQLite tracking DB
serde_json = "1"        # Hook JSON protocol
colored = "2"           # Terminal colors
chrono = "0.4"          # Timestamps
```

**Top-level Commands** (from main.rs):
```
rtk ls [args]           → cmds::system::ls::run()
rtk read [files]        → cmds::system::read::run()
rtk tree [args]         → cmds::system::tree::run()
rtk smart [file]        → cmds::system::summary::run()
rtk git [subcommand]    → cmds::git::git::run()
rtk cargo [subcommand]  → cmds::rust::cargo_cmd::run()
rtk pytest [args]       → cmds::python::pytest_cmd::run()
rtk npm [args]          → cmds::js::npm_cmd::run()
... (50+ more)

rtk gain                → analytics::gain::run()
rtk gain --history      → analytics::gain::run() with history table
rtk discover            → discover::mod::run()
rtk rewrite [cmd]       → discover::registry::classify_command()
rtk hook [subcommand]   → hooks::hook_cmd::run_*()
```

---

## Filtering Pipeline Architecture

### Step 1: Command Execution
```rust
// core::runner::run()
let mut cmd = Command::new("git");
cmd.arg("log").arg("--oneline");
```

### Step 2: Output Capture
```rust
// core::stream::run_streaming()
// Spawns process, captures stdout/stderr, returns FilterResult
let result = stream::run_streaming(&mut cmd, StdinMode::Null, FilterMode::CaptureOnly)?;
let raw_output = result.raw;  // Full output
```

### Step 3: Apply Filter
```rust
// Language-specific filter (e.g., git log)
let filtered = cmds::git::git::format_git_log(&raw_output);
// Reduces 2000 chars → 200 chars
```

### Step 4: Telemetry
```rust
// core::tracking::TimedExecution
let timer = tracking::TimedExecution::start();
timer.track("git log", "rtk git log", &raw_output, &filtered);
// Records: input_tokens, output_tokens, savings_pct, exec_ms
// Stored in SQLite: ~/.local/share/rtk/tracking.db
```

### Step 5: Output to User
```rust
// core::runner::print_with_hint()
println!("{}", filtered);  // Show compressed output
// Optionally: tee raw to ~/.local/share/rtk/tee/[timestamp].log
```

---

## Hook Integration (Claude Code PreToolUse)

**Flow**:
1. User in Claude Code: `git log` (bash command)
2. Claude Code fires PreToolUse hook with JSON input
3. Hook script `/hooks/claude/rtk-rewrite.sh` invoked
4. Script calls `rtk rewrite "git log"`
5. RTK registry matches → returns exit code 0 with rewritten command: `rtk git log`
6. Hook wraps response: `{ "updatedInput": { "command": "rtk git log" }, "permissionDecision": "allow" }`
7. Claude Code auto-allows and runs `rtk git log`
8. Output filtered, 80% tokens saved, tracking recorded

**Exit codes** (rtk rewrite):
- 0: Rewrite found, safe to auto-allow
- 1: No RTK equivalent, pass through unchanged
- 2: Deny rule matched, let Claude Code's native deny handle it
- 3: Ask rule matched, rewrite but prompt user

---

## Analytics & Telemetry

### Storage
- **Database**: `~/.local/share/rtk/tracking.db` (SQLite 3)
- **Schema**: `commands` table
  - timestamp (UTC), rtk_cmd, input_tokens, output_tokens, saved_tokens, savings_pct, exec_ms, project_path
- **Retention**: Auto-cleanup of records >90 days old

### Queries (via gain.rs)
```
rtk gain                    # Summary (total, avg savings %)
rtk gain --daily           # Per-day breakdown
rtk gain --weekly          # Per-week breakdown
rtk gain --monthly         # Per-month breakdown
rtk gain --project         # Project-scoped (current working dir)
rtk gain --history         # Recent command list
rtk gain --format json     # JSON export
rtk gain --format csv      # CSV export
```

### Display
- ASCII tables with colored cells (colored crate)
- KPI-style layout: "Total commands: 1,234" | "Tokens saved: 45,678 (82%)"
- Progress bars for multi-command runs

---

## Dependency Graph

### Direct Rust Crates
| Crate | Purpose |
|-------|---------|
| clap 4 | CLI argument parsing (derive macros) |
| anyhow | Error handling (Result<T>, Context) |
| regex, lazy_static | Pattern matching, compiled regex cache |
| serde, serde_json | JSON serialization (hook protocol) |
| rusqlite (bundled) | SQLite 3 wrapper (tracking DB) |
| chrono | Timestamp handling (UTC) |
| colored | ANSI color output |
| dirs | XDG/platform home dirs |
| ureq, flate2 | HTTP (optional), gzip |
| which | Find commands in PATH |
| automod | Code generation for mod.rs |

### External Binaries (Runtime)
- git, gh, glab, gt (git tools)
- cargo, rustc (Rust)
- python, pytest, pip, ruff, mypy (Python)
- npm, pnpm, node, tsc (JS/Node)
- go, golangci-lint (Go)
- dotnet (C#/.NET)
- grep, find, ls, tree (Unix utils)
- jq (hook script dependency)

---

## Key Design Patterns

### Pattern 1: Regex-Based Filtering
Filters use **compiled regex** (lazy_static) to match patterns in output. Example: Git branch name extraction.

### Pattern 2: Language-Specific Comment Stripping
`core::filter::Language` enum auto-detects file language, strips comments accordingly.

### Pattern 3: Hook Delegation
Hook script (`rtk-rewrite.sh`) is thin; all rewrite logic is in Rust registry (single source of truth). Version guard caches result.

### Pattern 4: Telemetry on Every Run
Every command auto-records to SQLite. No opt-in required; data is anonymized (only token counts + command name).

### Pattern 5: Graceful Degradation
- Command not in RTK rules? Pass through unchanged (exit code 1).
- Hook dependencies missing (jq)? Warn and skip rewrite.
- Old RTK version (<0.23)? Cache version check and skip hook.

---

## Performance Characteristics

### Token Savings by Command Type
| Category | Typical Savings |
|----------|-----------------|
| Git (log/diff/show) | 75-85% |
| Cargo (test/build) | 70-80% |
| Pytest/Vitest | 60-75% |
| NPM/Pnpm install | 50-70% |
| Grep/Find/Ls | 40-60% |
| Source code read (comments stripped) | 20-40% |

### Execution Overhead
- Filtering typically < 50ms (regex compiled once)
- Hook rewrite: ~5-10ms (jq + rtk spawns)
- Telemetry write: ~5ms (SQLite batch insert)

---

## File Locations Reference

| Purpose | Path |
|---------|------|
| Hook script (Claude Code) | `hooks/claude/rtk-rewrite.sh` |
| Rewrite rules registry | `src/discover/rules.rs` |
| Tracking database | `~/.local/share/rtk/tracking.db` |
| Configuration | `~/.config/rtk/rtk.toml` |
| Cache (hook version check) | `~/.cache/rtk-hook-version-ok` |
| Hook logs (tee mode) | `~/.local/share/rtk/tee/[timestamp].log` |
| Cargo package manifest | `Cargo.toml` |
| Build script | `build.rs` |

---

## Summary

RTK is a modular, performant CLI proxy with clear separation of concerns:

- **main.rs + cmds/**: Fast, language-aware filters for 50+ tools
- **core/**: Shared execution, filtering, tracking infrastructure
- **hooks/**: Thin delegation to Rust registry for AI agent integration
- **discover/**: Static registry of 100+ rewrite rules (single source of truth)
- **analytics/**: SQLite-backed telemetry dashboard

The system achieves 60-90% token savings by compressing command output *before* it reaches LLM context, with transparent hook integration into Claude Code and compatible AI editors.
