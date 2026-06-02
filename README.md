# Claude Status Bar

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Lightweight Claude Code status-line monitor. Shows your 5h / 7d rate-limit usage, reset timers, current model, context window, prompt-cache countdown, and optional session cost — in a single compact line driven by Claude Code's `statusLine` hook.

```
5h[   27%    ]⏰1h28m | 7d[   79%    ]⏰11h28m | Opus 4.7(350.0k/1.0M) | cache 4m23s
```

> **This is a hardened local fork.** Auto-update is disabled, all external URLs are removed, and no network calls are made at runtime. Install from this repo only — never from PyPI.

---

## Contents

- [Quick setup](#quick-setup)
- [Requirements](#requirements)
- [What it shows](#what-it-shows)
- [Styles & themes](#styles--themes)
- [Configuration](#configuration)
- [Fast mode (daemon)](#fast-mode-daemon)
- [Slash commands](#slash-commands)
- [Usage cheatsheet](#usage-cheatsheet)
- [Environment variables](#environment-variables)
- [How the cache countdown works](#how-the-cache-countdown-works)
- [Troubleshooting](#troubleshooting)
- [Security notes](#security-notes)

---

## Quick setup

```bash
# 1. Copy this repo to your machine (or server)
git clone <your-repo-url> claude-code-usage-bar
cd claude-code-usage-bar

# 2. Install from local source — never touches PyPI
pip install -e .
# or with uv (recommended)
uv tool install .
# or with pipx
pipx install .

# 3. Wire the statusLine hook and install slash commands
cs --setup

# 4. Restart Claude Code
```

That's it. The status bar appears at the bottom of Claude Code on next launch.

### Verify it works

```bash
cs doctor          # self-diagnostic — check all wiring
cs preview         # render every style × theme using your real data
```

---

## Requirements

- Python 3.9+
- Claude Code v2.1.80+
- macOS or Linux

---

## What it shows

```
5h[   27%    ]⏰1h28m | 7d[   79%    ]⏰11h28m | Opus 4.7(350.0k/1.0M) | cache 4m23s | $ 1.42
⤷ my-project ⎇ main●
```

| Segment | Meaning |
|---------|---------|
| `5h[27%]` | 5-hour rate-limit usage (from Anthropic API headers) |
| `⏰1h28m` | Time until the 5-hour window resets |
| `7d[79%]` | 7-day rate-limit usage |
| `⏰11h28m` | Time until the 7-day window resets |
| `Opus 4.7(350.0k/1.0M)` | Model name + context window used / total |
| `cache 4m23s` / `cache COLD` | Countdown to prompt-cache expiry. TTL (5min vs 1h) is auto-detected from the transcript. Green → comfortable, yellow → under 1 min, red → expired. Cache hits consume ~10× less rate-limit quota. |
| `$ 1.42` | Session cost. For Pro/Max subscribers this is the API-equivalent value, not money owed. Opt-in: `cs config set show_cost true` |
| `⤷ <project> ⎇ <branch>●` | Second-line identity. Project from `workspace.repo.name`, branch from `.git/HEAD`. `●` = dirty working tree. |

Colors default to green / yellow / red at 30% and 70% — both configurable.

---

## Styles & themes

3 styles × 9 themes = 27 combinations. Try them all with `cs preview`.

### Styles

| Style | Look |
|-------|------|
| `classic` | `[bar] \| pipe` engineering layout. Default. |
| `capsule` | Colored pill per metric with type badge. |
| `hairline` | One-character mini-bar (`▁▃▆█`) per metric. Minimal. |

```bash
cs --style capsule --theme graphite    # try without saving
cs config set style capsule            # save permanently
```

### Themes

| Theme | Vibe |
|-------|------|
| `graphite` | Cool dark graphite. Default. |
| `twilight` | Soft purples/roses. |
| `linen` | Cream/beige — for light terminals. |
| `nord` | Arctic blue. |
| `dracula` | High-contrast purple/black. |
| `sakura` | Soft pink/cream. |
| `mono` | Pure grayscale. |
| `catppuccin-mocha` | Pastel, easy on long sessions. |
| `tokyo-night` | Deep neon-blue. |

```bash
cs themes                              # list all themes
cs styles                              # list all styles
cs preview                             # render every combination
cs preview --theme nord                # filter to one theme
cs preview --style hairline --theme dracula
```

---

## Configuration

Persisted to `~/.claude/claude-statusbar.json`. Edit via `cs config set <key> <value>`.

```json
{
  "style": "capsule",
  "theme": "twilight",
  "density": "regular",
  "auto_compact_width": 100,
  "show_weekly": true,
  "show_cost": false,
  "show_cache_age": true,
  "show_project_branch": true
}
```

| Key | Values | Default | What it does |
|-----|--------|---------|--------------|
| `style` | `classic` / `capsule` / `hairline` | `classic` | Layout |
| `theme` | any theme name | `graphite` | Colors |
| `density` | `compact` / `regular` / `cozy` | `regular` | Padding (capsule + hairline only) |
| `auto_compact_width` | integer | `0` (off) | Force `hairline` when terminal narrower than this |
| `show_weekly` | bool | `true` | Show 7-day window |
| `show_cost` | bool | `false` | Show session cost `$ X.XX` |
| `show_cache_age` | bool | `true` | Show prompt-cache countdown |
| `show_project_branch` | bool | `true` | Show second-line project + branch |
| `warning_threshold` | float | `30.0` | % where green → yellow |
| `critical_threshold` | float | `70.0` | % where yellow → red |
| `color_ok` | `#rrggbb` | theme default | Override green color |
| `color_warn` | `#rrggbb` | theme default | Override yellow color |
| `color_hot` | `#rrggbb` | theme default | Override red color |

```bash
cs config show                         # print all current values
cs config set style hairline
cs config set theme linen
cs config set show_cost true
cs config set color_ok "#4ec85b"
cs config reset                        # wipe everything back to defaults
```

---

## Fast mode (daemon)

`cs --setup` defaults to daemon mode: a long-lived background process pre-renders the bar into `~/.cache/claude-statusbar/rendered.ansi`. The Claude Code hook calls `cs render`, which just reads and prints that file (~3–5ms/tick, <1% CPU at 1Hz refresh).

The legacy inline path (~30ms/tick, ~3% CPU) is available via `cs --setup --inline`.

```bash
cs --setup                  # default: daemon mode
cs --setup --inline         # opt out, inline rendering
cs daemon status            # pid + rendered.ansi freshness
cs daemon start             # start daemon
cs daemon stop              # stop daemon
```

**Crash safety**: if the daemon dies, `cs render` falls back to inline and lazily re-spawns the daemon. The status bar never freezes.

### Optional: auto-start on login

```bash
cs daemon install           # installs LaunchAgent (macOS) or systemd unit (Linux)
cs daemon uninstall         # remove it
cs daemon service           # show OS-level service status
```

On macOS this writes a `KeepAlive=true` plist to `~/Library/LaunchAgents/`. On Linux it creates a `systemd --user` unit with `Restart=always`.

---

## Slash commands

After `cs --setup` (or `cs install-commands`), these slash commands are available inside Claude Code:

| Command | What it does |
|---------|--------------|
| `/statusbar` | Show current config + list styles/themes |
| `/statusbar-preview` | Render every style × theme combo with your real data |
| `/statusbar-style <name>` | Switch style |
| `/statusbar-theme <name>` | Switch theme |
| `/statusbar-doctor` | Self-diagnostic |
| `/statusbar-reset` | Wipe config to defaults |

Reinstall at any time: `cs install-commands --force`

---

## Usage cheatsheet

```bash
# Render
cs                                      # render status line
cs --style capsule                      # one-off style override
cs --theme twilight                     # one-off theme override
cs --json-output                        # machine-readable JSON
cs --no-color                           # strip ANSI colors
cs --detail                             # verbose usage breakdown

# Config
cs config show
cs config set <key> <value>
cs config get <key>
cs config reset

# Discovery
cs styles
cs themes
cs preview
cs preview --theme nord
cs preview --style hairline --theme dracula

# Daemon
cs --setup                              # wire hook + start daemon
cs --setup --inline                     # wire hook, inline mode
cs --setup --project [PATH]             # write project-level override
cs daemon start
cs daemon stop
cs daemon status
cs daemon install                       # OS-level service (macOS/Linux)
cs daemon uninstall

# Diagnostics
cs doctor
cs --version
```

---

## Environment variables

| Variable | Effect |
|----------|--------|
| `CLAUDE_STATUSBAR_STYLE=capsule` | Override style (beats config file) |
| `CLAUDE_STATUSBAR_THEME=twilight` | Override theme (beats config file) |
| `CLAUDE_STATUSBAR_NO_UPDATE=1` | No-op in this fork (auto-update already disabled) |
| `CLAUDE_STATUSBAR_WARNING_THRESHOLD=40` | Green → yellow at 40% |
| `CLAUDE_STATUSBAR_CRITICAL_THRESHOLD=85` | Yellow → red at 85% |
| `NO_COLOR` | Disable all ANSI colors (any value) |
| `CLAUDE_CONFIG_DIR` | Override Claude config directory |

---

## How the cache countdown works

The `cache 4m23s` segment tail-reads the active session transcript (`.claude/projects/.../*.jsonl`) to find the most recent `assistant` entry. The TTL is auto-detected from the per-turn `usage.cache_creation` field:

- `ephemeral_1h_input_tokens > 0` → TTL = 3600s (subscription users)
- `ephemeral_5m_input_tokens > 0` → TTL = 300s (API key users)
- Neither present → fallback 300s (conservative)

`remaining = TTL − (now − last_assistant_timestamp)`

The segment shows `COLD` when remaining ≤ 0. Reads at most 320KB from the file tail — never the whole transcript.

---

## Troubleshooting

**Status bar doesn't appear**
Restart Claude Code. Settings are read at session start. Then run `cs doctor` and check the `statusLine entry` row.

**Numbers stuck / not updating**
`refreshInterval` is unset. Add `"refreshInterval": 1` to `~/.claude/settings.json`, or re-run `cs --setup` (it writes this automatically).

**`cs: command not found`**
The `cs` binary isn't on your PATH. Check where pip/uv installed it:
```bash
pip show claude-statusbar        # shows install location
uv tool list                     # if installed with uv
~/.local/bin/cs --version        # common pip --user location
```
Add the install dir to `PATH` in your shell rc file.

**Daemon mode shows stale data**
```bash
cs daemon stop
cs daemon start
cs doctor                        # check daemon row
```

**Project/branch segment missing**
Run inside a git repo. The segment is read from `.git/HEAD` — it doesn't call `git` directly on the hot path, so it works even if git isn't on PATH.

**`cs doctor` output** is the fastest way to diagnose anything — it prints version, paths, settings.json state, daemon status, and cache freshness in one paste.

---

## Security notes

This fork has the following changes from upstream relative to the original `leeguooooo/claude-code-usage-bar`:

| Change | Why |
|--------|-----|
| `updater.py` neutered to no-ops | Prevents silent `pip install --upgrade` from PyPI |
| `check_for_updates()` removed from `core.py` | Removes the call site that triggered the updater on every render |
| `_maybe_ensure_statusline()` removed from `core.py` | Removes the daily auto-write to `~/.claude/settings.json` |
| `install.sh` / `web-install.sh` deleted | Removed curl-pipe-bash install scripts |
| Git remote `origin` removed | Prevents accidental `git pull` from upstream |
| All upstream URLs stripped from metadata | `pyproject.toml`, `plugin.json`, `FUNDING.yml` |

**Runtime network surface: zero.** The only outbound calls at runtime are to `pypi.org` — and those are now removed. The binary runs fully offline after install.

**Install only from this local copy.** Never run `pip install claude-statusbar` — that fetches the upstream package which has auto-update enabled.

---

## License

MIT — see [LICENSE](LICENSE). Original work by leeguooooo.
