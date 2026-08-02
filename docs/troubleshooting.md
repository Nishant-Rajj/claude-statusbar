# Troubleshooting, diagnostics & upgrading

## `cs doctor` — self-diagnostic

If the status bar isn't behaving the way you expect, run:

```bash
cs doctor
```

It prints (with red ✗ for anything off):

- Which `cs` binary the OS will resolve, plus its version + Python interpreter
- Whether `~/.claude/settings.json` has *our* statusLine entry (vs missing / vs another tool's)
- How fresh `~/.cache/claude-statusbar/last_stdin.json` is (so you can tell if Claude Code is actually pushing data)
- If the daemon is running (fast mode) — its pid and how stale `rendered.ansi` is
- Terminal size and `TERM`
- Current resolved `style` / `theme` / all `show_*` toggles
- Slash commands installed under `~/.claude/commands/`

Paste the output verbatim in any bug report — it's almost always enough to diagnose remotely.

## Common problems

**Status line doesn't appear after install** — Restart Claude Code (settings.json is read at session start). If still missing, run `cs doctor` and check the `statusLine entry` row.

**`cs doctor` says "missing"** — A Claude Code upgrade can wipe `statusLine` from `~/.claude/settings.json`. Run `cs --setup` (or `cs --setup --fast` if you want daemon mode) to restore it. The package also self-heals once per day automatically.

**Numbers stuck / not updating** — Two possibilities:
1. `refreshInterval` not set — Claude Code only re-renders on activity. Add `"refreshInterval": 30` (or `1` for live cache-age).
2. Daemon mode running stale data — `cs daemon stop && cs daemon start`. Or just `cs doctor` and check `daemon` row freshness.

**Cache-age segment shows `cache 0s` and never moves** — `refreshInterval` is unset; Claude Code only re-invokes the statusLine on each user/assistant turn. Set `"refreshInterval": 1` in settings.json. For 1Hz refresh you'll also want `cs --setup --fast` so the per-second invocation stays cheap.

**`cs --setup --fast` then daemon shows wrong rate-limits** — Fixed in v3.2.1. Upgrade with `cs upgrade`.

**Auto-update is annoying / blocked** — nothing to do; auto-update is already permanently disabled in this fork (see [Security notes](../README.md#security-notes)).

For anything else: run `cs doctor` and check the output — it captures version, paths, settings.json state, daemon state, and recent cache freshness in one paste.

## Upgrading

Auto-update and `cs upgrade` are disabled in this fork. To pick up changes:

```bash
git pull                # or ./scripts/sync-upstream.sh to review new upstream commits
pip install -e .        # or: uv tool install . / pipx install .
```

`./scripts/verify-security.sh` re-checks that the hardening patches are still
intact after any pull.
