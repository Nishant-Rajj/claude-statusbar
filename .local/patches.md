# Local Feature Patches Ledger

This file documents fork-specific FEATURES — changes that don't exist
upstream (`leeguooooo/claude-code-usage-bar`) and must survive an upstream
sync. It's the additive counterpart to `.security/patches.md`, which
documents changes that *harden* this fork by removing upstream behavior
(telemetry, auto-update, network probes). These patches instead add new
capability layered on top of upstream.

After merging or rebasing onto a new upstream version, re-run the "How to
verify" checks below for each patch. `scripts/` is gitignored (local-only
convenience tooling, not committed to this repo), so there is deliberately no
shared verify script to run automatically — every check here is a
self-contained, copy-pasteable command.

---

## Local Patch 1 — CLAUDE_CONFIG_DIR-aware multi-account isolation

**Files**: `src/claude_statusbar/predict.py`, `src/claude_statusbar/render_thin.py`,
`src/claude_statusbar/core.py`, `tests/conftest.py`, `tests/test_account_switch.py`,
`tests/test_render_thin_stdin.py`

**Background**: Claude Code accounts on a shared machine are commonly
separated by setting a distinct `CLAUDE_CONFIG_DIR` per shell/profile —
Claude Code's own mechanism for this, which relocates `~/.claude.json` (and
`.credentials.json`) to `$CLAUDE_CONFIG_DIR/.claude.json`. `account_id()`
(added upstream to fix a *different* bug — one account's 5h/7d reading
bleeding into another's after `/login`, see the account-suffixing comment in
`predict.py`) only ever read the hardcoded `~/.claude.json`, never
`CLAUDE_CONFIG_DIR`. On a machine using `CLAUDE_CONFIG_DIR` to separate
accounts, every account's 5h/7d cache silently keyed off whichever account's
`~/.claude.json` happened to exist on disk — confirmed live on 2026-08-05:
two real accounts on one root shell, `~/.cache/claude-statusbar/rate_latest.*`
was keyed to the wrong account's uuid, so one account's usage updates
repainted the other account's bar.

**What we do**:
- `predict._claude_json_path(env)`: resolves `$CLAUDE_CONFIG_DIR/.claude.json`
  when set (checked in `env` if given, else `os.environ`), falling back to
  `~/.claude.json`.
- `predict._read_account(env)` / `account_id(env)` / `account_identity(env)` /
  `account_scoped_path(base, env)`: every account/path resolver now takes an
  optional `env` mapping — the per-session env `render_thin` stamps into
  `_cs_env` (see below), so a shared daemon resolves the *session's* account,
  not its own frozen one. `_ACCOUNT_CACHE` is a small dict keyed by resolved
  path (capped at 8 entries), not a single slot, so two accounts alternating
  under one daemon don't invalidate each other's cache entry every tick.
- `render_thin._SESSION_ENV_KEYS` gained `"CLAUDE_CONFIG_DIR"` — stamped into
  `_cs_env` every render tick, the same mechanism already used for
  `CS_API_MODE` (the shared daemon's own `os.environ` is frozen at its start,
  so it can't see a later session's real env).
- `core.parse_stdin_data()` / `core.main()` thread `env=_effective_env` (the
  stamped session env, falling back to `os.environ`) into every relevant
  `predict.*` call: `reconcile_account`, `projection`, `forecast`,
  `quota_cache_status`, `get_cache_age_text`.
- Second leak channel: `core.parse_stdin_data()`'s `debug_file` (a fallback
  source when a session's live stdin has no `rate_limits` yet — e.g. a
  session that just started) and `core.get_cache_age_text()`'s `cache_file`
  are now account-scoped too, via `account_scoped_path`. Both used to be a
  single shared unsuffixed file, so one account's freshly-cached blob could
  get read back as a *different* account's fallback. `render_thin._persist_stdin_bytes`
  additionally writes an account-scoped copy of this file (on top of the
  existing unsuffixed legacy write, kept for `cs doctor` / `cs preview`
  back-compat, which don't go through the shared-daemon frozen-env path).

**How to verify**:
```bash
grep -n 'def _claude_json_path\|"CLAUDE_CONFIG_DIR"' \
  src/claude_statusbar/predict.py src/claude_statusbar/render_thin.py
# must show _claude_json_path() in predict.py, and CLAUDE_CONFIG_DIR present
# in render_thin._SESSION_ENV_KEYS

grep -n 'env=_effective_env' src/claude_statusbar/core.py
# must show at least 6 call sites: get_cache_age_text, reconcile_account,
# projection, forecast, quota_cache_status, and account_scoped_path(...)
# for debug_file/cache_file

grep -n 'def account_scoped_path\|def account_identity\|def _read_account\b' \
  src/claude_statusbar/predict.py
# all three must exist

PYTHONPATH=src uv run pytest tests/test_account_switch.py tests/test_render_thin_stdin.py -q
# must be green
```

**How to reapply if broken**:
- `predict.py`: `account_id` / `account_scoped_path` / `_latest_path` /
  `_projection_path` must each accept an `env=None` parameter and resolve
  `_claude_json_path(env)` (checking `env.get("CLAUDE_CONFIG_DIR")` before
  falling back to `~/.claude.json`) — never a bare `Path.home() / ".claude.json"`.
- `render_thin.py`: `_SESSION_ENV_KEYS` must include `"CLAUDE_CONFIG_DIR"`.
- `core.py`: every `predict.reconcile_account` / `projection` / `forecast` /
  `quota_cache_status` call, plus `get_cache_age_text`, must pass
  `env=_effective_env` (defined near the top of `main()` from
  `stdin_data.get('_session_env')`, falling back to `os.environ`).
- If a future upstream account-uuid change conflicts here, the invariant to
  preserve is: **path resolution must depend on the passed-in per-session
  env, never solely on the resolving process's own `os.environ`** — a shared
  daemon's `os.environ` belongs to a different session than the one actually
  being rendered.

---

## Local Patch 2 — Show logged-in account on the identity line

**Files**: `src/claude_statusbar/config.py`, `src/claude_statusbar/core.py`,
`src/claude_statusbar/styles.py`, `tests/test_show_account.py`

**What we do**: New opt-in config keys `show_account` (bool, default
`false`) and `account_style` (`email` default / `name` / `both` — email is
the field that actually disambiguates accounts, `displayName` can collide
across a team). When on, `core.main()` resolves
`predict.account_identity(env=_effective_env)` and appends the result to the
identity line (`⤷ <project> ⎇ <branch> · <account>`), or gives it its own
`⤷` line when `show_project_branch` is off — the same placement convention
`show_cwd` already uses.

**How to verify**:
```bash
grep -n 'show_account\|account_style' src/claude_statusbar/config.py
# must appear in StatusbarConfig, load_config, VALID_KEYS, _BOOL_KEYS, set_value

grep -n 'account_text' src/claude_statusbar/styles.py
# render_identity_line(...) and render(...) must both accept/thread it

PYTHONPATH=src uv run pytest tests/test_show_account.py -q
# must be green
```

**How to reapply if broken**: re-add `show_account: bool = False` and
`account_style: str = "email"` to `StatusbarConfig`, wire them through
`load_config` / `set_value` / `VALID_KEYS` / `_BOOL_KEYS`; in `core.main()`
build `account_kwargs` from `predict.account_identity(env=_effective_env)`
per `cfg.account_style`, and thread `**account_kwargs` into every
`_render_style(...)` call alongside `**identity_kwargs`.

---

## Upstream-sync notes

When rebasing/merging a new upstream version:

1. `predict.py`, `render_thin.py`, `core.py`, `config.py`, `styles.py` are all
   touched by these two patches — review the diff for conflicts before
   accepting upstream's version of these files wholesale, the same way
   `.security/patches.md`'s patches treat `core.py` / `updater.py`.
2. If upstream ships its own `CLAUDE_CONFIG_DIR` support or its own
   account-identity segment, prefer upstream's — these patches exist only
   because upstream didn't have them. Drop the local-only code once upstream
   covers the same ground, and update or delete the relevant section here.
3. Run the full suite after any upstream sync: `PYTHONPATH=src uv run pytest tests/`.

## Adding a new local patch

1. Give it the next patch number.
2. State: files, background/why, what we do.
3. Add a **How to verify** block of copy-pasteable commands — no dependency
   on anything in the gitignored `scripts/` directory.
4. Add a **How to reapply if broken** block with the concrete invariant to
   restore, not just "revert the commit" (a future edit may need to coexist
   with unrelated upstream changes to the same file).
