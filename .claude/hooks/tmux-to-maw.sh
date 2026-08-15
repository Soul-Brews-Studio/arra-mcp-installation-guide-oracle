#!/bin/bash
# Hook: block raw tmux commands, suggest maw equivalents
# Exit 2 = block with feedback message
#
# Why: maw wraps tmux with pane locking, fleet tracking, agent detection,
# and layout management. Raw tmux bypasses all of that and causes state drift.

INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

[ -z "$CMD" ] && exit 0

# Only match commands that directly invoke tmux (not inside strings)
echo "$CMD" | grep -qE '^\s*tmux\s' || exit 0
# Allow if tmux is inside a string (commit message, echo, grep, etc.)
echo "$CMD" | grep -qE '(git commit|echo|cat|grep|printf|sed|awk)' && exit 0

# No read-only exceptions — ALL tmux goes through maw
# Use: maw panes, maw ls, maw peek <target>

# ─── Session management ─────────────────────────────────────────────
if echo "$CMD" | grep -qE 'tmux\s+new-session|tmux\s+new\b'; then
  echo "Use 'maw wake <oracle>' to create sessions (handles fleet config + worktrees)" >&2
  exit 2
fi
if echo "$CMD" | grep -qE 'tmux\s+kill-session'; then
  echo "Use 'maw kill <session> --session' instead of raw tmux kill-session" >&2
  exit 2
fi
if echo "$CMD" | grep -qE 'tmux\s+rename-session'; then
  echo "Use 'maw tmux rename <old> <new>' instead of raw tmux rename-session" >&2
  exit 2
fi
if echo "$CMD" | grep -qE 'tmux\s+attach|tmux\s+a\b'; then
  echo "Use 'maw a <session>' instead of raw tmux attach" >&2
  exit 2
fi
if echo "$CMD" | grep -qE 'tmux\s+switch-client'; then
  echo "Use 'maw a <session>' instead of raw tmux switch-client" >&2
  exit 2
fi

# ─── Window management ──────────────────────────────────────────────
if echo "$CMD" | grep -qE 'tmux\s+new-window'; then
  echo "Use 'maw wake <oracle> --task <name>' to create windows (tracks in fleet)" >&2
  exit 2
fi
if echo "$CMD" | grep -qE 'tmux\s+kill-window'; then
  echo "Use 'maw kill <target>' instead of raw tmux kill-window" >&2
  exit 2
fi
if echo "$CMD" | grep -qE 'tmux\s+rename-window'; then
  echo "Use 'maw tmux rename <target> <name>' instead of raw tmux rename-window" >&2
  exit 2
fi
if echo "$CMD" | grep -qE 'tmux\s+select-window'; then
  echo "Use 'maw a <session>:<window>' instead of raw tmux select-window" >&2
  exit 2
fi

# ─── Pane management ────────────────────────────────────────────────
if echo "$CMD" | grep -qE 'tmux\s+split-window'; then
  echo "Use 'maw split <target>' or 'maw swarm --count N' instead of raw tmux split-window" >&2
  exit 2
fi
if echo "$CMD" | grep -qE 'tmux\s+kill-pane'; then
  echo "Use 'maw kill <pane-id>' instead of raw tmux kill-pane" >&2
  exit 2
fi
if echo "$CMD" | grep -qE 'tmux\s+break-pane'; then
  echo "Use 'maw close <pane>' instead of raw tmux break-pane" >&2
  exit 2
fi
if echo "$CMD" | grep -qE 'tmux\s+join-pane'; then
  echo "Use 'maw open <pane>' instead of raw tmux join-pane" >&2
  exit 2
fi
if echo "$CMD" | grep -qE 'tmux\s+swap-pane'; then
  echo "Use 'maw layout' to manage pane arrangement instead of raw tmux swap-pane" >&2
  exit 2
fi
if echo "$CMD" | grep -qE 'tmux\s+resize-pane'; then
  echo "Use 'maw layout [main-vertical|tiled]' instead of raw tmux resize-pane" >&2
  exit 2
fi
if echo "$CMD" | grep -qE 'tmux\s+select-pane'; then
  echo "Use 'maw zoom <pane>' or 'maw a <target>' instead of raw tmux select-pane" >&2
  exit 2
fi

# ─── Read-only (still blocked — use maw equivalents) ────────────────
if echo "$CMD" | grep -qE 'tmux\s+capture-pane'; then
  echo "Use 'maw peek <target>' instead of raw tmux capture-pane" >&2
  exit 2
fi
if echo "$CMD" | grep -qE 'tmux\s+list-panes'; then
  echo "Use 'maw panes' instead of raw tmux list-panes" >&2
  exit 2
fi
if echo "$CMD" | grep -qE 'tmux\s+list-sessions'; then
  echo "Use 'maw ls' instead of raw tmux list-sessions" >&2
  exit 2
fi
if echo "$CMD" | grep -qE 'tmux\s+list-windows'; then
  echo "Use 'maw ls -v' instead of raw tmux list-windows" >&2
  exit 2
fi
if echo "$CMD" | grep -qE 'tmux\s+display-message'; then
  echo "Use 'maw panes' for pane info instead of raw tmux display-message" >&2
  exit 2
fi

# ─── Input/output ───────────────────────────────────────────────────
if echo "$CMD" | grep -qE 'tmux\s+send-keys'; then
  echo "Use 'maw tmux send <target> <command>' instead of raw tmux send-keys" >&2
  exit 2
fi
if echo "$CMD" | grep -qE 'tmux\s+pipe-pane'; then
  echo "Use 'maw peek <target>' to read pane content instead of raw tmux pipe-pane" >&2
  exit 2
fi

# ─── Layout ─────────────────────────────────────────────────────────
if echo "$CMD" | grep -qE 'tmux\s+select-layout'; then
  echo "Use 'maw layout [main-vertical|tiled]' instead of raw tmux select-layout" >&2
  exit 2
fi

# ─── Styling ────────────────────────────────────────────────────────
if echo "$CMD" | grep -qE 'tmux\s+set-option|tmux\s+set\b'; then
  echo "Pane/window options are managed by maw's layout-manager. Use 'maw layout'" >&2
  exit 2
fi

# ─── Catch-all for any other raw tmux mutation ──────────────────────
echo "Raw tmux command detected. Use maw CLI instead:" >&2
echo "  maw ls              list sessions" >&2
echo "  maw panes           list all panes" >&2
echo "  maw wake <oracle>   create/wake session" >&2
echo "  maw a <session>     attach" >&2
echo "  maw kill <target>   kill pane/window/session" >&2
echo "  maw peek <target>   read pane content" >&2
echo "  maw split <target>  split pane" >&2
echo "  maw zoom <pane>     toggle zoom" >&2
echo "  maw swarm --count N spawn agents" >&2
echo "  maw preflight       health check" >&2
exit 2
