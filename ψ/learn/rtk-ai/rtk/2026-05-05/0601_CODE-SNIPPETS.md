# RTK Code Patterns & Architecture

## Overview

RTK (Rust Token Killer) is a CLI proxy that filters shell command output before it reaches LLM context, achieving 60-90% token savings. This document extracts key architectural patterns from the codebase.

---

## 1. Main Entry Point: Command Routing

**File**: `/Users/nat/Code/github.com/rtk-ai/rtk/src/main.rs:1367-1420`

The CLI dispatcher uses a match statement to route each command to its handler. Each filter function receives configuration (verbosity, ultra_compact mode) and returns an exit code.

```rust
let code = match cli.command {
    Commands::Ls { args } => ls::run(&args, cli.verbose)?,

    Commands::Tree { args } => tree::run(&args, cli.verbose)?,

    Commands::Read {
        files,
        level,
        max_lines,
        tail_lines,
        line_numbers,
    } => {
        let mut had_error = false;
        let mut stdin_seen = false;
        for file in &files {
            let result = if file == Path::new("-") {
                if stdin_seen {
                    eprintln!("rtk: warning: stdin specified more than once");
                    continue;
                }
                stdin_seen = true;
                read::run_stdin(level, max_lines, tail_lines, line_numbers, cli.verbose)
            } else {
                read::run(
                    file,
                    level,
                    max_lines,
                    tail_lines,
                    line_numbers,
                    cli.verbose,
                )
            };
            if let Err(e) = result {
                eprintln!("cat: {}: {}", file.display(), e.root_cause());
                had_error = true;
            }
        }
        if had_error { 1 } else { 0 }
    }
    // ... 40+ more command arms follow
};
```

**Why it matters**: Each subcommand (git, npm, grep, read) is modeled as a variant in the `Commands` enum. This pattern allows the CLI parser to validate flags upfront, and dispatching happens in one central location. Multiple files can be read like `rtk read file1 file2` — stdin is deduplicated to prevent accidental re-reads.

---

## 2. Grep Filter: Grouping & Truncation

**File**: `/Users/nat/Code/github.com/rtk-ai/rtk/src/cmds/system/grep_cmd.rs:12-147`

RTK rewrites `grep -rn` calls to use `rg` (ripgrep) for speed, groups matches by file, and truncates long lines while centering the pattern match.

```rust
pub fn run(
    pattern: &str,
    path: &str,
    max_line_len: usize,
    max_results: usize,
    context_only: bool,
    file_type: Option<&str>,
    extra_args: &[String],
    verbose: u8,
) -> Result<i32> {
    let timer = tracking::TimedExecution::start();

    // Fix: convert BRE alternation \| → | for rg (which uses PCRE-style regex)
    let rg_pattern = pattern.replace(r"\|", "|");

    let mut rg_cmd = resolved_command("rg");
    // --no-ignore-vcs: match grep -r behavior (don't skip .gitignore'd files).
    rg_cmd.args(["-n", "--no-heading", "--no-ignore-vcs", &rg_pattern, path]);

    // ... execute rg, fall back to grep if rg unavailable ...

    let mut by_file: HashMap<String, Vec<(usize, String)>> = HashMap::new();
    for line in result.stdout.lines() {
        let parts: Vec<&str> = line.splitn(3, ':').collect();

        let (file, line_num, content) = if parts.len() == 3 {
            let ln = parts[1].parse().unwrap_or(0);
            (parts[0].to_string(), ln, parts[2])
        } else if parts.len() == 2 {
            let ln = parts[0].parse().unwrap_or(0);
            (path.to_string(), ln, parts[1])
        } else {
            continue;
        };

        let cleaned = clean_line(content, max_line_len, context_re.as_ref(), pattern);
        by_file.entry(file).or_default().push((line_num, cleaned));
    }

    let mut rtk_output = String::new();
    rtk_output.push_str(&format!(
        "{} matches in {} files:\n\n",
        total_matches,
        by_file.len()
    ));

    let mut shown = 0;
    let mut files: Vec<_> = by_file.iter().collect();
    files.sort_by_key(|(f, _)| *f);

    let per_file = config::limits().grep_max_per_file;
    for (file, matches) in files {
        if shown >= max_results {
            break;
        }

        let file_display = compact_path(file);
        for (line_num, content) in matches.iter().take(per_file) {
            if shown >= max_results {
                break;
            }
            rtk_output.push_str(&format!("{}:{}:{}\n", file_display, line_num, content));
            shown += 1;
        }
    }

    if total_matches > shown {
        rtk_output.push_str(&format!("[+{} more]\n", total_matches - shown));
    }

    timer.track(
        &format!("grep -rn '{}' {}", pattern, path),
        "rtk grep",
        &raw_output,
        &rtk_output,
    );

    Ok(exit_code)
}
```

**Why it matters**: This filter demonstrates **two compression techniques**: (1) grouping matches by file reduces visual noise, and (2) line truncation with context-aware centering keeps pattern matches visible even in 80-character columns. The `clean_line()` helper uses Unicode-aware character indexing (not byte offsets) to handle emoji and Thai text correctly.

---

## 3. Read Filter: Language-Aware Boilerplate Stripping

**File**: `/Users/nat/Code/github.com/rtk-ai/rtk/src/cmds/system/read.rs:9-80`

RTK reads files with optional language-aware filtering. If a filter empties a file, it falls back to raw content.

```rust
pub fn run(
    file: &Path,
    level: FilterLevel,
    max_lines: Option<usize>,
    tail_lines: Option<usize>,
    line_numbers: bool,
    verbose: u8,
) -> Result<()> {
    let timer = tracking::TimedExecution::start();

    // Read file content
    let content = fs::read_to_string(file)
        .with_context(|| format!("Failed to read file: {}", file.display()))?;

    // Detect language from extension
    let lang = file
        .extension()
        .and_then(|e| e.to_str())
        .map(Language::from_extension)
        .unwrap_or(Language::Unknown);

    // Apply filter
    let filter = filter::get_filter(level);
    let mut filtered = filter.filter(&content, &lang);

    // Safety: if filter emptied a non-empty file, fall back to raw content
    if filtered.trim().is_empty() && !content.trim().is_empty() {
        eprintln!(
            "rtk: warning: filter produced empty output for {} ({} bytes), showing raw content",
            file.display(),
            content.len()
        );
        filtered = content.clone();
    }

    if verbose > 0 {
        let original_lines = content.lines().count();
        let filtered_lines = filtered.lines().count();
        let reduction = if original_lines > 0 {
            ((original_lines - filtered_lines) as f64 / original_lines as f64) * 100.0
        } else {
            0.0
        };
        eprintln!(
            "Lines: {} -> {} ({:.1}% reduction)",
            original_lines, filtered_lines, reduction
        );
    }

    filtered = apply_line_window(&filtered, max_lines, tail_lines, &lang);

    let rtk_output = if line_numbers {
        format_with_line_numbers(&filtered)
    } else {
        filtered.clone()
    };
    print!("{}", rtk_output);
    timer.track(
        &format!("cat {}", file.display()),
        "rtk read",
        &content,
        &rtk_output,
    );
    Ok(())
}
```

**Why it matters**: The **safety fallback** is critical — if a filter strips too aggressively, RTK warns the user and shows raw content rather than silently losing information. The timer records input/output sizes for telemetry.

---

## 4. Git Filter: Argument Normalization

**File**: `/Users/nat/Code/github.com/rtk-ai/rtk/src/cmds/git/git.rs:73-120`

When `rtk git diff` receives arguments, it must re-insert `--` before path-like arguments because clap's trailing_var_arg parser drops the separator.

```rust
/// Re-insert `--` before the first path-like argument when clap has consumed it.
///
/// clap's `trailing_var_arg = true` silently drops `--` when it appears as the
/// first positional argument (before any other positional).  This means:
///   `rtk git diff -- file` → args = ["file"]   (clap ate `--`)
///   `rtk git diff HEAD -- file` → args = ["HEAD", "--", "file"]  (preserved)
fn normalize_diff_args(args: &[String]) -> Vec<String> {
    normalize_diff_args_impl(args, |p| std::path::Path::new(p).exists())
}

/// Testable core of `normalize_diff_args` — accepts an injectable filesystem existence checker.
fn normalize_diff_args_impl<F>(args: &[String], path_exists: F) -> Vec<String>
where
    F: Fn(&str) -> bool,
{
    // Already has `--` — nothing to do
    if args.iter().any(|a| a == "--") {
        return args.to_vec();
    }
    let path_start = args.iter().position(|arg| {
        if arg.starts_with('-') {
            return false;
        }
        // Explicit path prefixes — always treat as path regardless of existence
        if arg.starts_with('.') || arg.starts_with('~') {
            return true;
        }
        // Contains path separator — use filesystem check to distinguish
        // branch names (feature/auth) from real paths (src/main.rs)
        if arg.contains('/') || arg.contains('\\') {
            return path_exists(arg);
        }
        // Bare word (no separator, no special prefix) — never inject `--`
        false
    });
    match path_start {
        Some(idx) => {
            let mut out = args[..idx].to_vec();
            out.push("--".to_string());
            out.extend_from_slice(&args[idx..]);
            out
        }
        None => args.to_vec(),
    }
}
```

**Why it matters**: This demonstrates **defensive parsing** — the code handles three disambiguation strategies (prefix rules, path separators, filesystem checks) to avoid ambiguity errors like "fatal: ambiguous argument". The function is testable because path existence is injected, making unit tests feasible without filesystem mocking.

---

## 5. Telemetry: Tracking Token Savings

**File**: `/Users/nat/Code/github.com/rtk-ai/rtk/src/core/tracking.rs:40-62`

Token savings are recorded to SQLite with project-scoped queries for `rtk gain --project`.

```rust
// ── Project path helpers ── // added: project-scoped tracking support

/// Get the canonical project path string for the current working directory.
fn current_project_path_string() -> String {
    std::env::current_dir()
        .ok()
        .and_then(|p| p.canonicalize().ok())
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_default()
}

/// Build SQL filter params for project-scoped queries.
/// Returns (exact_match, glob_prefix) for WHERE clause.
/// Uses GLOB instead of LIKE to avoid `_` and `%` in paths acting as wildcards.
fn project_filter_params(project_path: Option<&str>) -> (Option<String>, Option<String>) {
    match project_path {
        Some(p) => (
            Some(p.to_string()),
            Some(format!("{}{}*", p, std::path::MAIN_SEPARATOR)),
        ),
        None => (None, None),
    }
}
```

**Why it matters**: Each command is recorded with its canonicalized project path, enabling `rtk gain --project` to filter savings by cwd. Using `GLOB` instead of `LIKE` prevents path separators from acting as SQL wildcards. The tracking table is indexed on `(project_path, timestamp)` for fast aggregation.

---

## 6. Gain Command: Token Savings Analytics

**File**: `/Users/nat/Code/github.com/rtk-ai/rtk/src/analytics/gain.rs:14-80`

The gain telemetry path reads from tracking database and displays KPI-style output with efficiency meters.

```rust
pub fn run(
    project: bool,
    graph: bool,
    history: bool,
    quota: bool,
    tier: &str,
    daily: bool,
    weekly: bool,
    monthly: bool,
    all: bool,
    format: &str,
    failures: bool,
    reset: bool,
    yes: bool,
    _verbose: u8,
) -> Result<()> {
    let tracker = Tracker::new().context("Failed to initialize tracking database")?;
    let project_scope = resolve_project_scope(project)?;

    if reset {
        if !yes && !confirm_reset()? {
            println!("Aborted.");
            return Ok(());
        }
        tracker
            .reset_all()
            .context("Failed to reset token savings")?;
        println!("{}", styled("Token savings stats reset to zero.", true));
        return Ok(());
    }

    let summary = tracker
        .get_summary_filtered(project_scope.as_deref())
        .context("Failed to load token savings summary from database")?;

    if summary.total_commands == 0 {
        println!("No tracking data yet.");
        println!("Run some rtk commands to start tracking savings.");
        return Ok(());
    }

    // Default view (summary)
    if !daily && !weekly && !monthly && !all {
        let title = if project_scope.is_some() {
            "RTK Token Savings (Project Scope)"
        } else {
            "RTK Token Savings (Global Scope)"
        };
        println!("{}", styled(title, true));
        println!("{}", "═".repeat(60));
        if let Some(ref scope) = project_scope {
            println!("Scope: {}", shorten_path(scope));
        }
        println!();

        print_kpi("Total commands", summary.total_commands.to_string());
        print_kpi("Input tokens", format_tokens(summary.total_input));
        print_kpi("Output tokens", format_tokens(summary.total_output));
        print_kpi(
            "Tokens saved",
            format!(
                "{} ({:.1}%)",
                format_tokens(summary.total_saved),
                summary.avg_savings_pct
            ),
        );
        print_kpi(
            "Total exec time",
            format!(
                "{} (avg {})",
                format_duration(summary.total_time_ms),
                format_duration(summary.avg_time_ms)
            ),
        );
```

**Why it matters**: The analytics layer translates raw token counts from the database into user-facing KPIs (key performance indicators). Project scoping enables local debugging while global scoping shows overall RTK impact across all commands.

---

## 7. Hook Integration: Command Rewriting

**File**: `/Users/nat/Code/github.com/rtk-ai/rtk/src/hooks/rewrite_cmd.rs:18-50`

The bash hook calls `rtk rewrite "git status"` → prints `rtk git status` and exits with a code that indicates permission verdict.

```rust
pub fn run(cmd: &str) -> anyhow::Result<()> {
    let excluded = crate::core::config::Config::load()
        .map(|c| c.hooks.exclude_commands)
        .unwrap_or_default();

    // SECURITY: check deny/ask BEFORE rewrite so non-RTK commands are also covered.
    let verdict = check_command(cmd);

    if verdict == PermissionVerdict::Deny {
        std::process::exit(2);
    }

    match registry::rewrite_command(cmd, &excluded) {
        Some(rewritten) => match verdict {
            PermissionVerdict::Allow => {
                print!("{}", rewritten);
                let _ = std::io::stdout().flush();
                Ok(())
            }
            PermissionVerdict::Ask | PermissionVerdict::Default => {
                print!("{}", rewritten);
                let _ = std::io::stdout().flush();
                std::process::exit(3);
            }
            PermissionVerdict::Deny => unreachable!(),
        },
        None => {
            // No RTK equivalent. Exit 1 = passthrough.
            // Claude Code independently evaluates its own ask rules on the original cmd.
            std::process::exit(1);
        }
    }
}
```

**Exit code protocol**:
- `0` → rewrite allowed, auto-allow in hook
- `1` → no RTK equivalent, passthrough
- `2` → deny rule matched
- `3` → ask rule or default (must confirm)

**Why it matters**: The exit code protocol separates concerns — the Rust CLI handles rewriting and permissions, while the bash hook interprets the exit code to decide whether to auto-allow or prompt. This keeps permissions logic auditable.

---

## 8. Stream Filter: Block-Based Output Processing

**File**: `/Users/nat/Code/github.com/rtk-ai/rtk/src/core/stream.rs:7-84`

RTK uses trait-based streaming filters to process output line-by-line, grouping related lines into "blocks" (e.g., error messages).

```rust
pub trait StreamFilter {
    fn feed_line(&mut self, line: &str) -> Option<String>;
    fn flush(&mut self) -> String;
    fn on_exit(&mut self, _exit_code: i32, _raw: &str) -> Option<String> {
        None
    }
}

pub trait BlockHandler {
    fn should_skip(&mut self, line: &str) -> bool;
    fn is_block_start(&mut self, line: &str) -> bool;
    fn is_block_continuation(&mut self, line: &str, block: &[String]) -> bool;
    fn format_summary(&self, exit_code: i32, raw: &str) -> Option<String>;
}

pub struct BlockStreamFilter<H: BlockHandler> {
    handler: H,
    in_block: bool,
    current_block: Vec<String>,
    blocks_emitted: usize,
}

impl<H: BlockHandler> StreamFilter for BlockStreamFilter<H> {
    fn feed_line(&mut self, line: &str) -> Option<String> {
        if self.handler.should_skip(line) {
            return None;
        }

        if self.handler.is_block_start(line) {
            let prev = self.emit_block();
            self.current_block.push(line.to_string());
            self.in_block = true;
            prev
        } else if self.in_block {
            if self
                .handler
                .is_block_continuation(line, &self.current_block)
            {
                self.current_block.push(line.to_string());
                None
            } else {
                self.in_block = false;
                self.emit_block()
            }
        } else {
            None
        }
    }

    fn flush(&mut self) -> String {
        self.emit_block().unwrap_or_default()
    }

    fn on_exit(&mut self, exit_code: i32, raw: &str) -> Option<String> {
        self.handler.format_summary(exit_code, raw)
    }
}
```

**Why it matters**: The **trait-based streaming design** allows command-specific handlers (e.g., linters, test runners) to define their own block detection rules. This separates **parsing logic** (identifying blocks) from **filtering logic** (deciding what to output).

---

## 9. Test: Pytest Filter

**File**: `/Users/nat/Code/github.com/rtk-ai/rtk/src/cmds/python/pytest_cmd.rs:255-298`

Tests use realistic pytest output to verify filters extract only failure summaries.

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_filter_pytest_all_pass() {
        let output = r#"=== test session starts ===
platform darwin -- Python 3.11.0
collected 5 items

tests/test_foo.py .....                                            [100%]

=== 5 passed in 0.50s ==="#;

        let result = filter_pytest_output(output);
        assert!(result.contains("Pytest"));
        assert!(result.contains("5 passed"));
    }

    #[test]
    fn test_filter_pytest_with_failures() {
        let output = r#"=== test session starts ===
collected 5 items

tests/test_foo.py ..F..                                            [100%]

=== FAILURES ===
___ test_something ___

    def test_something():
>       assert False
E       assert False

tests/test_foo.py:10: AssertionError

=== short test summary info ===
FAILED tests/test_foo.py::test_something - assert False
=== 4 passed, 1 failed in 0.50s ==="#;

        let result = filter_pytest_output(output);
        assert!(result.contains("4 passed, 1 failed"));
        assert!(result.contains("test_something"));
        assert!(result.contains("assert False"));
    }
}
```

**Why it matters**: These tests use **realistic fixture data** rather than mocks, ensuring the filter works on actual pytest output. The all-pass case tests the "happy path," while the failure case verifies that relevant context (file, line, assertion) is preserved.

---

## Key Patterns Summary

| Pattern | Location | Purpose |
|---------|----------|---------|
| **Command routing** | main.rs | Central dispatcher for 40+ CLI subcommands |
| **Grouping + truncation** | grep_cmd.rs | Compress search results by file, center pattern matches |
| **Safety fallback** | read.rs | Degrade gracefully if filter empties file |
| **Argument normalization** | git.rs | Handle parser quirks (clap's trailing_var_arg) |
| **Project-scoped tracking** | tracking.rs | Filter telemetry by cwd for `rtk gain --project` |
| **Exit code protocol** | rewrite_cmd.rs | Communicate verdicts (allow/deny/ask) to bash hook |
| **Trait-based streaming** | stream.rs | Generic block filter for error aggregation |
| **Realistic test fixtures** | pytest_cmd.rs | Test filters against actual tool output |

---

## Rust Idioms & Quality

- **Defensive fallbacks**: Grep falls back to system `grep` if `rg` missing; read shows raw content if filter fails
- **Unicode-aware**: Line truncation uses char indices, not bytes; handles emoji and Thai correctly
- **Testable design**: Dependency injection (path_exists closure in git.rs) enables unit tests without filesystem mocking
- **Exit code semantics**: Hook protocol uses exit codes as a state machine (Allow=0, Ask=3, Deny=2, Passthrough=1)
- **Trait composition**: StreamFilter and BlockHandler traits decouple parsing from formatting logic

Total codebase: ~60KB across filters, analytics, hooks, and core utilities. Strong emphasis on user feedback (warnings, fallbacks) and observability (token tracking, verbose output).
