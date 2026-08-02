# Security Patches Ledger

This file documents every change made to harden this fork from the upstream
`leeguooooo/claude-code-usage-bar`. Keep it up to date when adding new patches.

Run `./scripts/verify-security.sh` to assert all patches are still in place.
Run `./scripts/sync-upstream.sh` to safely evaluate new upstream features.

---

## Patch 1 — Neuter auto-updater

**File**: `src/claude_statusbar/updater.py`
**Type**: Full replacement

**What upstream does**: `auto_upgrade()` calls `uv tool install --upgrade claude-statusbar`
or `pip install --upgrade claude-statusbar` once per day, silently, on every inline render.
`get_latest_version()` makes a network call to `https://pypi.org/pypi/claude-statusbar/json`.

**What we do**: Replace the entire file with no-op stubs. `auto_upgrade()` returns `False`.
`get_latest_version()` returns `None`. No subprocess, no urllib, no network.

**How to verify**: `grep -E 'urllib|subprocess|pip install|uv tool' src/claude_statusbar/updater.py`
should return nothing.

**How to reapply if broken**:
```python
# auto_upgrade() must be:
def auto_upgrade() -> bool:
    return False

# get_latest_version() must be:
def get_latest_version() -> Optional[str]:
    return None

# check_and_upgrade() must be:
def check_and_upgrade() -> Tuple[bool, str]:
    return False, "Auto-update disabled (local fork)"
```

---

## Patch 2 — Remove auto-update call site from core.py

**File**: `src/claude_statusbar/core.py`
**Type**: Deletion of functions and call site

**What upstream does**: `main()` calls `check_for_updates()` and `_maybe_ensure_statusline()`
on every non-JSON render (throttled to once/day). `check_for_updates()` invokes the updater.
`_maybe_ensure_statusline()` silently rewrites `~/.claude/settings.json`.

**What we do**: Delete both functions entirely from `core.py`, and remove the call block
from `main()`:
```python
# REMOVED — do not restore:
if not json_output and not _suppress_side_effects:
    check_for_updates(stdin_data.get('session_id', ''))
    _maybe_ensure_statusline()
```
Also deleted: `_UPDATE_CHECK_INTERVAL_S`, `_ENSURE_STATUSLINE_INTERVAL_S`, `_time_now()`.

**How to verify**:
```bash
grep -n 'check_for_updates\|_maybe_ensure_statusline\|urlopen' src/claude_statusbar/core.py
# must return nothing
```

**How to reapply if broken**: Delete the call block above from `main()` and delete the
two function bodies. The `_suppress_side_effects` parameter is kept in `main()`'s signature
for API compatibility with `daemon.py` callers but does nothing.

---

## Patch 3 — Delete curl-pipe-bash install scripts

**Files**: `install.sh`, `web-install.sh` (both deleted)

**What upstream does**: `web-install.sh` is designed to be piped to bash via:
`curl -fsSL https://raw.githubusercontent.com/.../main/web-install.sh | bash`
It installs from PyPI and modifies `~/.claude/settings.json` and shell rc files.

**What we do**: Delete both files. Install exclusively from local source.

**How to reapply if broken**: `rm install.sh web-install.sh`

---

## Patch 4 — Strip upstream URLs from metadata

**Files**: `pyproject.toml`, `.claude-plugin/plugin.json`, `.github/FUNDING.yml`

**What upstream does**: Metadata points to `github.com/leeguooooo/claude-code-usage-bar`
and the author's funding page.

**What we do**:
- `pyproject.toml`: Remove Homepage, Repository, Issues from `[project.urls]`
- `.claude-plugin/plugin.json`: Remove `homepage` and `repository` fields; replace
  author with `{"name": "local"}`
- `.github/FUNDING.yml`: Delete the file entirely

**How to reapply if broken**:
```bash
# pyproject.toml — ensure [project.urls] has no leeguooooo entries
# plugin.json — ensure no "homepage" or "repository" keys pointing to upstream
rm -f .github/FUNDING.yml
```

---

## Patch 5 — Remove git push remote to upstream

**What**: After cloning, `git remote remove origin` was run. The repo now has no
push remote pointing at the upstream.

**How to verify**: `git remote -v` should show no remote with `leeguooooo` in a `(push)` line.

**How to reapply if broken**: `git remote remove origin` (then re-add your own fork as origin)

---

## Patch 6 — Fix demo script curl reference

**File**: `demo/record_demo.sh:37`

**What upstream does**: Echoes `curl -fsSL .../main/web-install.sh | bash` as a demo step.

**What we do**: Replace with `pip install -e /path/to/claude-code-usage-bar`.

**How to reapply if broken**:
```bash
# In demo/record_demo.sh, the install step must NOT contain:
# curl ... leeguooooo ... | bash
```

---

## Patch 7 — Neuter egress-IP risk prober

**Files**: `src/claude_statusbar/_ip_risk_refresh.py` (deleted),
`src/claude_statusbar/ip_risk.py`, `src/claude_statusbar/daemon.py`

**What upstream does**: The `show_ip_risk` feature (default off) spawns a detached
prober that calls two third-party services at runtime — `https://api.ipify.org`
(egress IP) and `https://api.ipapi.is/` (datacenter/VPN/proxy/Tor/China-cloud
scoring) — to warn about Claude account ban risk. Unlike the PyPI updater, this
network code was intact even before this patch, just gated behind a config flag:
flipping `show_ip_risk` to `true` (deliberately, by mistake, or via a shared/
tampered config file) was enough to start making outbound calls. The daemon also
ran a 20s heartbeat that called the prober whenever the flag was on.

**What we do**:
- Delete `_ip_risk_refresh.py` entirely — the only file making the actual
  `urllib` calls.
- `ip_risk.ensure_fresh()` → no-op (`return None`), never spawns a subprocess.
- `ip_risk.ip_risk_line()` → always returns `("", "ok")`, regardless of
  `show_ip_risk` or any cached reading left over from a prior install.
- Removed the daemon's IP heartbeat block entirely (dead code once
  `ensure_fresh()` is a no-op).
- `ip_score.py` (pure local risk-scoring math, no network) is left intact —
  harmless, and `test_ip_score.py` still exercises it.

**How to verify**:
```bash
test -f src/claude_statusbar/_ip_risk_refresh.py && echo "BROKEN: prober module exists"
grep -n 'urllib' src/claude_statusbar/ip_risk.py   # must return nothing
grep -n 'ip_risk\|ensure_fresh' src/claude_statusbar/daemon.py   # must return nothing
```

**How to reapply if broken**:
```bash
rm -f src/claude_statusbar/_ip_risk_refresh.py
# ip_risk.py: ensure_fresh() must be `return None`;
#             ip_risk_line() must be `return "", "ok"` unconditionally.
# daemon.py: remove any call to ip_risk.ensure_fresh() from run_forever().
```

---

## Adding a new patch

When you apply a new security fix, document it here:

1. Give it the next patch number
2. State: file, type (deletion/replacement/edit), what upstream does, what you do
3. Add a `verify` one-liner that can be copy-pasted
4. Add the check to `scripts/verify-security.sh`
