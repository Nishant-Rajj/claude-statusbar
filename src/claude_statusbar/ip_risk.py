"""Egress-IP risk segment (``show_ip_risk``) — DISABLED in this local fork.

Upstream's version spawns a detached prober (``_ip_risk_refresh``) that calls
two third-party services (api.ipify.org, api.ipapi.is) to score egress-IP
ban risk. That prober module has been deleted and ``ensure_fresh()`` /
``ip_risk_line()`` below are neutered to no-ops — see .security/patches.md
Patch 7. This fork makes zero calls to those services regardless of the
``show_ip_risk`` config value.
"""
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# proxycheck.io re-probe cadence for a successful reading (rate-limited API:
# free tier ~100/day, so this stays coarse).
IP_RISK_TTL_S = 30 * 60.0
# Egress-IP re-verify cadence. We now hit our own service (ip-check.leeguoo.com,
# self quota bucket), so a network change is caught within ~1 min instead of
# waiting minutes. The daemon also runs this on its own heartbeat (see
# daemon.py), so a VPN toggle reflects even while you're idle and Claude Code
# isn't re-rendering the statusline.
IP_CHECK_TTL_S = 60.0
# A failed probe retries sooner, but not so fast that a dead network loops.
FAIL_RETRY_S = 5 * 60.0
# Inflight marker older than this is a crashed prober — allow a new spawn.
INFLIGHT_EXPIRY_S = 60.0
# proxycheck.io's documented bands: 0-33 clean, 34-66 suspicious, 67+ bad.
WARN_RISK = 34
CRIT_RISK = 67
# The warning line only appears above this risk score (user rule: a clean
# IP earns silence, not a green checkmark taking up a whole line).
SHOW_THRESHOLD = 40


def _cache_root() -> Path:
    return Path(os.path.expanduser("~/.cache/claude-statusbar"))


def cache_path() -> Path:
    return _cache_root() / "ip_risk.json"


def _inflight_path() -> Path:
    return _cache_root() / "ip_risk.inflight"


def read_cache() -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(cache_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def write_cache_atomic(entry: Dict[str, Any]) -> None:
    from .cache import atomic_write_text
    try:
        atomic_write_text(cache_path(), json.dumps(entry))
    except OSError:
        pass


def is_fresh(entry: Optional[Dict[str, Any]], now: Optional[float] = None) -> bool:
    """Whether the proxycheck RISK reading is still current (ts vs its TTL).
    Used by the prober to decide if it can skip the proxycheck call."""
    if not isinstance(entry, dict):
        return False
    if now is None:
        now = time.time()
    try:
        age = now - float(entry.get("ts", 0))
    except (TypeError, ValueError):
        return False
    return age < (IP_RISK_TTL_S if entry.get("ok") else FAIL_RETRY_S)


def should_refresh(entry: Optional[Dict[str, Any]], now: Optional[float] = None) -> bool:
    """Whether to spawn the prober. Gated on the cheap egress-IP CHECK cadence
    (``checked_ts``), not the risk TTL — so a VPN toggle is noticed within
    IP_CHECK_TTL_S even though proxycheck itself is re-run far less often."""
    if not isinstance(entry, dict):
        return True
    if now is None:
        now = time.time()
    if not entry.get("ok"):
        return is_fresh(entry, now) is False   # failed → FAIL_RETRY_S backoff
    checked = entry.get("checked_ts", entry.get("ts", 0))
    try:
        return (now - float(checked)) >= IP_CHECK_TTL_S
    except (TypeError, ValueError):
        return True


def is_inflight(now: Optional[float] = None) -> bool:
    try:
        mtime = _inflight_path().stat().st_mtime
    except OSError:
        return False
    if now is None:
        now = time.time()
    return (now - mtime) < INFLIGHT_EXPIRY_S


def mark_inflight() -> None:
    try:
        _inflight_path().write_text(str(time.time()), encoding="utf-8")
    except OSError:
        pass


def clear_inflight() -> None:
    try:
        _inflight_path().unlink()
    except OSError:
        pass


def risk_level(entry: Dict[str, Any]) -> str:
    """"ok" / "warn" / "crit" per proxycheck bands; a proxy/VPN verdict is at
    least warn even at a low score (the flag itself is the risk signal)."""
    try:
        risk = int(entry.get("risk", 0))
    except (TypeError, ValueError):
        risk = 0
    if risk >= CRIT_RISK:
        return "crit"
    if risk >= WARN_RISK or str(entry.get("proxy", "")).lower() == "yes":
        return "warn"
    return "ok"


def line_text(entry: Dict[str, Any]) -> str:
    """Warning as TWO lines (summary + action), or "" when the IP is clean
    enough (≤ SHOW_THRESHOLD). Two lines because the single-line form is too
    long for a terminal statusline and gets truncated. The renderer splits on
    "\\n" and colors each line. English + explicit about the login/ban risk.
    """
    try:
        risk = int(entry.get("risk", 0))
    except (TypeError, ValueError):
        risk = 0
    if risk <= SHOW_THRESHOLD:
        return ""
    kind = str(entry.get("type", "") or "").strip()
    kind_part = f" ({kind})" if kind else ""
    if risk >= CRIT_RISK:
        # Name the specific dangerous action: logging in / re-authenticating
        # Claude from a flagged datacenter/proxy IP is what triggers the ban.
        return (f"✗ ip risk {risk}/100{kind_part} — account-ban risk\n"
                f"   ↳ do NOT log in / re-auth Claude here: "
                f"account WILL be banned — switch network first")
    return (f"⚠ ip risk {risk}/100{kind_part} — account-ban risk\n"
            f"   ↳ avoid logging in / re-authenticating Claude on this IP")


def ip_risk_line(*, spawn: bool = True) -> Tuple[str, str]:
    """Always ("", "ok") — this fork never shows the egress-IP risk line.

    Upstream would render the last-cached ipapi.is reading here and spawn a
    refresh. Disabled unconditionally, regardless of ``show_ip_risk`` or any
    cache file left over from a prior install — see .security/patches.md
    Patch 7.
    """
    return "", "ok"


def ensure_fresh(entry=None) -> None:
    """No-op. Disabled in this local fork — see .security/patches.md Patch 7.

    Upstream spawns a detached prober that calls api.ipify.org and
    api.ipapi.is; that prober module has been deleted."""
    return None
