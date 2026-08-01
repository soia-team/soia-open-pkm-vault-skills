# Agent session log setup

## Safety gate

Before editing Claude Code settings or Codex config, show the exact structural change, explain the script path and log destination, back up the existing file, and obtain explicit approval. Merge arrays/tables; never replace an entire config file.

## Claude Code

Add one `SessionEnd` command that calls the installed `session_end_log.sh` with `--agent Claude-Code` and the customer vault. Preserve all existing hooks. Run the script manually with `--dry-run` before enabling it, then end a small test session and inspect the generated Markdown.

## Codex

Codex accepts one notify command. If no notify exists, point it to `codex_notify_wrapper.sh`. If one exists, use the wrapper's `--original-count N -- <existing-command-and-fixed-args>` form so the original command receives Codex event arguments before the log script runs.

Do not copy an existing notify value through shell `eval`; keep each argv item as a structured string.

## Uninstall

Restore the backed-up config or remove only the exact hook/notify entry added by this skill. Keep the customer’s earlier hook/notify entries. Removing generated logs or XDG state is a separate destructive action and needs an explicit list and approval.
