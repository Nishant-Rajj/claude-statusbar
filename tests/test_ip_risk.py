# Egress-IP risk warning line (show_ip_risk) — DISABLED in this local fork.
#
# Upstream spawns a detached `_ip_risk_refresh` prober that calls two
# third-party services (api.ipify.org, api.ipapi.is). That prober module has
# been deleted and ip_risk.ensure_fresh() / ip_risk.ip_risk_line() are
# neutered to no-ops — see .security/patches.md Patch 7. These tests verify
# the neutering holds even against a lingering cache file from a prior
# (non-hardened) install, and that the pure local helpers (risk_level,
# line_text, cache freshness math) still work — the renderer's ip_line_*
# kwargs are unaffected, they just never receive real data now.
import time

import claude_statusbar.ip_risk as ip_risk


def _iso(tmp_path, monkeypatch):
    monkeypatch.setattr(ip_risk, "_cache_root", lambda: tmp_path)


# --- disabled by default, unconditionally ---

def test_no_ip_risk_refresh_module():
    """The network-calling prober module must not exist."""
    import importlib
    with __import__("pytest").raises(ModuleNotFoundError):
        importlib.import_module("claude_statusbar._ip_risk_refresh")


def test_no_network_symbols():
    """ip_risk.py must not contain urllib — no network call is reachable."""
    mod_src = open(ip_risk.__file__).read()
    assert "urllib" not in mod_src, "urllib found in ip_risk — network call re-introduced"


def test_ensure_fresh_never_spawns(tmp_path, monkeypatch):
    """Even with a stale cache that would normally trigger a re-check,
    ensure_fresh() must never spawn a subprocess."""
    _iso(tmp_path, monkeypatch)
    ip_risk.write_cache_atomic({"ok": True, "ip": "1.1.1.1", "risk": 0,
                                "ts": time.time() - 999,
                                "checked_ts": time.time() - 999})
    spawned = []
    monkeypatch.setattr(ip_risk, "mark_inflight", lambda: spawned.append(1))
    import subprocess
    monkeypatch.setattr(subprocess, "Popen",
                        lambda *a, **k: spawned.append("popen"))
    ip_risk.ensure_fresh()
    assert not spawned


def test_ip_risk_line_always_empty_even_with_risky_cache(tmp_path, monkeypatch):
    """A dangerous cached reading (e.g. left over from a prior non-hardened
    install) must never surface — the line is unconditionally disabled."""
    _iso(tmp_path, monkeypatch)
    ip_risk.write_cache_atomic({"ok": True, "risk": 100, "proxy": "yes",
                                "type": "VPN", "ts": time.time()})
    spawned = []
    monkeypatch.setattr(ip_risk, "mark_inflight", lambda: spawned.append(1))
    text, level = ip_risk.ip_risk_line()
    assert text == ""
    assert level == "ok"
    assert not spawned


def test_ip_risk_line_empty_with_no_cache():
    text, level = ip_risk.ip_risk_line()
    assert text == ""
    assert level == "ok"


def test_fp_risk_default_on_ip_risk_default_off():
    from claude_statusbar.config import StatusbarConfig
    cfg = StatusbarConfig()
    assert cfg.show_fp_risk is True     # local-only, silent unless risk
    assert cfg.show_ip_risk is False    # no-op in this fork either way


# --- pure local helpers (risk_level / line_text / cache freshness math) ---
# Still exercised: they don't touch the network and remain available to
# anyone reading a manually-supplied entry dict.

def test_levels_follow_proxycheck_bands():
    assert ip_risk.risk_level({"risk": 0, "proxy": "no"}) == "ok"
    assert ip_risk.risk_level({"risk": 33, "proxy": "no"}) == "ok"
    assert ip_risk.risk_level({"risk": 34, "proxy": "no"}) == "warn"
    assert ip_risk.risk_level({"risk": 67, "proxy": "no"}) == "crit"
    # proxy verdict is at least warn even with a low score
    assert ip_risk.risk_level({"risk": 5, "proxy": "yes"}) == "warn"


def test_line_hidden_at_or_below_threshold():
    assert ip_risk.line_text({"risk": 0}) == ""
    assert ip_risk.line_text({"risk": 40}) == ""


def test_line_warn_and_crit_wording():
    warn = ip_risk.line_text({"risk": 55, "type": "VPN"})
    assert warn.split("\n")[0].startswith("⚠ ip risk 55/100 (VPN)")
    assert "log" in warn.lower() and "account-ban" in warn
    crit = ip_risk.line_text({"risk": 82, "type": "VPN"})
    assert crit.split("\n")[0].startswith("✗ ip risk 82/100 (VPN)")
    # crit must name the login action and the certain consequence
    assert "log in" in crit and "WILL be banned" in crit
    assert "switch network" in crit


def test_line_is_two_lines_summary_then_action():
    for risk in (55, 100):
        lines = ip_risk.line_text({"risk": risk, "type": "hosting"}).split("\n")
        assert len(lines) == 2
        assert "ip risk" in lines[0]          # summary
        assert "↳" in lines[1]                # indented action line


def test_failed_entry_retries_sooner_than_ok(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    now = time.time()
    assert ip_risk.is_fresh({"ok": False, "ts": now - ip_risk.FAIL_RETRY_S - 1},
                            now=now) is False
    assert ip_risk.is_fresh({"ok": True, "ts": now - ip_risk.FAIL_RETRY_S - 1},
                            now=now) is True


def test_should_refresh_on_check_ttl_not_risk_ttl(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    now = 1000.0
    entry = {"ok": True, "ip": "1.1.1.1", "risk": 0, "ts": now,
             "checked_ts": now}
    assert ip_risk.should_refresh(entry, now=now + ip_risk.IP_CHECK_TTL_S + 1)
    assert not ip_risk.should_refresh(entry, now=now + 10)


# --- dedicated line rendering (NOT on the git identity line) ---
# The renderer itself still accepts ip_line_text/ip_line_level — it just
# never receives real data from ip_risk.ip_risk_line() anymore.

def test_render_colors_each_wrapped_ip_line():
    from claude_statusbar.styles import render
    out = render("classic", msgs_pct=10, weekly_pct=5, reset_5h="1h",
                 reset_7d="2d", model="M", use_color=False,
                 ip_line_text="✗ ip risk 100/100 (hosting) — account-ban risk\n"
                              "   ↳ do NOT log in / re-auth Claude here",
                 ip_line_level="crit")
    tail = out.split("\n")[-2:]
    assert tail[0].startswith("✗ ip risk 100/100")
    assert tail[1].strip().startswith("↳")


def test_render_appends_dedicated_ip_line():
    from claude_statusbar.styles import render
    out = render("classic", msgs_pct=10, weekly_pct=5, reset_5h="1h",
                 reset_7d="2d", model="M", use_color=False,
                 ip_line_text="⚠ ip risk 66/100 (VPN) — current ip may risk account ban",
                 ip_line_level="warn")
    lines = out.split("\n")
    assert lines[-1].startswith("⚠ ip risk 66/100")


def test_render_no_ip_line_when_clean():
    from claude_statusbar.styles import render
    out = render("classic", msgs_pct=10, weekly_pct=5, reset_5h="1h",
                 reset_7d="2d", model="M", use_color=False)
    assert "ip risk" not in out
