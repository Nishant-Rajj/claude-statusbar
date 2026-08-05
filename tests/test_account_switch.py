# Account switch must not leak the previous account's 5h/7d readings.
#
# Live incident 2026-06-11: user switched Claude accounts; the bar kept showing
# the OLD account's seven_day 15% (and its learned →NN% projection) because
# rate_latest.json / rate_projection.json are account-global with no account
# key — the old reading's later resets_at won every monotonic merge until the
# old window expired (days). Stores are now keyed by oauthAccount.accountUuid
# from ~/.claude.json.
import json
import os

import claude_statusbar.predict as predict
from claude_statusbar.predict import reconcile_account


def _fake_claude_json(tmp_path, uuid, mtime=None):
    p = tmp_path / "claude.json"
    p.write_text(json.dumps({
        "someOtherState": {"x": 1},
        "oauthAccount": {"accountUuid": uuid, "emailAddress": "a@b.c"},
    }))
    if mtime is not None:
        os.utime(p, (mtime, mtime))
    return p


# --- account_id: parse + memoization ---

def test_account_id_reads_oauth_account_uuid(tmp_path, monkeypatch):
    # Bypass the conftest-wide account_id() stub (autouse, pins to None for
    # every other test) by calling the underlying parser directly — same as
    # this test did pre-refactor via the (now merged-away) _read_account_id.
    p = _fake_claude_json(tmp_path, "cd5174d3-1111-2222-3333-444455556666", mtime=1000)
    monkeypatch.setattr(predict, "_CLAUDE_JSON_PATH", p)
    monkeypatch.setattr(predict, "_ACCOUNT_CACHE", {})
    assert predict._read_account()["id"] == "cd5174d3-1111-2222-3333-444455556666"


def test_account_id_tracks_file_change(tmp_path, monkeypatch):
    p = _fake_claude_json(tmp_path, "cd5174d3-1111-2222-3333-444455556666", mtime=1000)
    monkeypatch.setattr(predict, "_CLAUDE_JSON_PATH", p)
    monkeypatch.setattr(predict, "_ACCOUNT_CACHE", {})
    assert predict._read_account()["id"] == "cd5174d3-1111-2222-3333-444455556666"
    # same length uuid → same file size; mtime must invalidate the memo
    _fake_claude_json(tmp_path, "9e8f7a6b-1111-2222-3333-444455556666", mtime=2000)
    assert predict._read_account()["id"] == "9e8f7a6b-1111-2222-3333-444455556666"


def test_account_id_missing_file_is_none(tmp_path, monkeypatch):
    monkeypatch.setattr(predict, "_CLAUDE_JSON_PATH", tmp_path / "nope.json")
    monkeypatch.setattr(predict, "_ACCOUNT_CACHE", {})
    assert predict._read_account()["id"] is None


# --- per-account store isolation ---

def test_account_switch_does_not_leak_previous_readings(tmp_path, monkeypatch):
    """The bug: old account's seven_day reading has a LATER resets_at, so it
    won the monotonic merge against the new account's fresh (lower, earlier-
    reset) reading. With per-account stores the new account starts clean."""
    monkeypatch.setattr(predict, "_LATEST_PATH", tmp_path / "rate_latest.json")
    now = 1_781_000_000.0
    monkeypatch.setattr(predict, "account_id", lambda *a, **k: "old-account-uuid-1234")
    reconcile_account(42.0, now + 3600, 15.0, now + 6 * 86400, now=now)
    # switch accounts: fresh account, lower 7d used, EARLIER reset
    monkeypatch.setattr(predict, "account_id", lambda *a, **k: "new-account-uuid-5678")
    u5, r5, u7, r7 = reconcile_account(
        0.0, now + 17000, 2.0, now + 4 * 86400, now=now + 60)
    assert u7 == 2.0
    assert r7 == now + 4 * 86400
    assert u5 == 0.0


def test_switch_back_restores_own_account_data(tmp_path, monkeypatch):
    monkeypatch.setattr(predict, "_LATEST_PATH", tmp_path / "rate_latest.json")
    now = 1_781_000_000.0
    monkeypatch.setattr(predict, "account_id", lambda *a, **k: "acct-a")
    reconcile_account(50.0, now + 3600, 30.0, now + 6 * 86400, now=now)
    monkeypatch.setattr(predict, "account_id", lambda *a, **k: "acct-b")
    reconcile_account(1.0, now + 3600, 1.0, now + 5 * 86400, now=now)
    # back to A: its store still has the higher reading; a stale lower input
    # for the same resets must not win (normal monotonic behaviour preserved)
    monkeypatch.setattr(predict, "account_id", lambda *a, **k: "acct-a")
    _, _, u7, _ = reconcile_account(50.0, now + 3600, 10.0, now + 6 * 86400,
                                    now=now + 5)
    assert u7 == 30.0


def test_unknown_account_uses_legacy_path(tmp_path, monkeypatch):
    """account undetectable (no ~/.claude.json) → exact legacy file, so
    behaviour is unchanged for API-key/headless users."""
    legacy = tmp_path / "rate_latest.json"
    monkeypatch.setattr(predict, "_LATEST_PATH", legacy)
    monkeypatch.setattr(predict, "account_id", lambda *a, **k: None)
    now = 1_781_000_000.0
    r7 = now + 6 * 86400
    reconcile_account(10.0, now + 3600, 8.0, r7, now=now)
    assert legacy.exists()
    data = json.loads(legacy.read_text())
    # per-reset bucket schema: {window: {"<int reset>": {used, observed_at}}}
    assert data["seven_day"][str(int(r7))]["used"] == 8.0


def test_projection_store_is_per_account(tmp_path, monkeypatch):
    monkeypatch.setattr(predict, "_PROJECTION_PATH", tmp_path / "rate_projection.json")
    monkeypatch.setattr(predict, "account_id", lambda *a, **k: "acct-a")
    store = predict.empty_projection_store()
    store["five_hour"] = [{"observed_at": 1.0, "used_pct": 5.0, "resets_at": 100.0,
                           "session_id": "s"}]
    predict.save_projection_store(store)
    # account A sees its own samples back
    assert predict.load_projection_store()["five_hour"]
    # account B starts with an empty store — no leaked learning
    monkeypatch.setattr(predict, "account_id", lambda *a, **k: "acct-b")
    assert predict.load_projection_store()["five_hour"] == []


# --- CLAUDE_CONFIG_DIR: multi-account-on-one-machine isolation ---
#
# Live incident 2026-08-05: two accounts on one shared machine, each logged in
# via its own CLAUDE_CONFIG_DIR (Claude Code's documented way to run several
# accounts on one machine — it relocates ~/.claude.json to
# $CLAUDE_CONFIG_DIR/.claude.json). account_id() only ever looked at the
# hardcoded ~/.claude.json, so every account either fell through to the
# legacy unsuffixed store or all keyed off whichever account's real
# ~/.claude.json happened to exist — one account's usage repainting every
# other account's bar.

def _fake_config_dir(base_dir, uuid, email="x@y.z", name="Test User"):
    """<base_dir>/.claude.json with the given oauthAccount — what
    CLAUDE_CONFIG_DIR points a Claude Code account's config at."""
    base_dir.mkdir(parents=True, exist_ok=True)
    p = base_dir / ".claude.json"
    p.write_text(json.dumps({
        "oauthAccount": {"accountUuid": uuid, "emailAddress": email,
                         "displayName": name},
    }))
    return p


def _use_real_account_id(monkeypatch):
    """conftest's autouse fixture stubs account_id() to always return None
    (so unrelated tests get deterministic legacy paths regardless of the
    developer's real login) — restore the real env-aware resolution for
    tests that are specifically about that resolution."""
    monkeypatch.setattr(predict, "account_id",
                        lambda env=None: predict._read_account(env)["id"])


def test_claude_json_path_uses_env_config_dir(tmp_path):
    cfg_dir = tmp_path / "alt-config"
    got = predict._claude_json_path({"CLAUDE_CONFIG_DIR": str(cfg_dir)})
    assert got == cfg_dir / ".claude.json"


def test_claude_json_path_falls_back_without_config_dir(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(predict, "_CLAUDE_JSON_PATH", sentinel)
    assert predict._claude_json_path({}) is sentinel


def test_account_identity_reads_display_name_and_email(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "alt-config"
    _fake_config_dir(cfg_dir, "uuid-1", email="atul.sharma@ofbusiness.in",
                     name="atul sharma")
    monkeypatch.setattr(predict, "_ACCOUNT_CACHE", {})
    name, email = predict.account_identity({"CLAUDE_CONFIG_DIR": str(cfg_dir)})
    assert name == "atul sharma"
    assert email == "atul.sharma@ofbusiness.in"


def test_daemon_frozen_env_does_not_leak_across_accounts(tmp_path, monkeypatch):
    """Models the actual live bug end-to-end: a shared daemon's os.environ is
    frozen at whichever account started it (X); a session logged into a
    DIFFERENT account (Y) via its own CLAUDE_CONFIG_DIR renders through that
    daemon. render_thin stamps the session's real CLAUDE_CONFIG_DIR into
    `_cs_env`, and every predict.py entry point must use THAT `env=` — not
    the daemon's own frozen os.environ — to resolve which account's cache
    file to read/write. A regression here is silent: reconcile_account would
    write to the right file while projection/forecast still read the wrong
    one (or vice versa), so this checks every entry point core.py calls."""
    dir_x = tmp_path / "account-x"
    dir_y = tmp_path / "account-y"
    _fake_config_dir(dir_x, "11111111-1111-1111-1111-111111111111")
    _fake_config_dir(dir_y, "22222222-2222-2222-2222-222222222222")

    # The daemon's own process env — frozen on account X at spawn time.
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(dir_x))
    monkeypatch.setattr(predict, "_ACCOUNT_CACHE", {})
    _use_real_account_id(monkeypatch)
    monkeypatch.setattr(predict, "_LATEST_PATH", tmp_path / "rate_latest.json")
    monkeypatch.setattr(predict, "_PROJECTION_PATH", tmp_path / "rate_projection.json")

    now = 1_781_000_000.0
    resets_5h, resets_7d = now + 3600, now + 6 * 86400
    # THIS session's real env (what render_thin would have stamped into _cs_env).
    session_env = {"CLAUDE_CONFIG_DIR": str(dir_y)}

    predict.reconcile_account(30.0, resets_5h, 12.0, resets_7d, now=now, env=session_env)
    predict.projection(30.0, resets_5h, 12.0, resets_7d, now, session_id="s", env=session_env)
    predict.forecast(30.0, resets_5h, 12.0, resets_7d, now, env=session_env)
    predict.quota_cache_status(now=now, env=session_env)  # must not raise / mis-key

    x_uuid12, y_uuid12 = "11111111-111", "22222222-222"
    assert not (tmp_path / f"rate_latest.{x_uuid12}.json").exists()
    assert not (tmp_path / f"rate_projection.{x_uuid12}.json").exists()
    assert (tmp_path / f"rate_latest.{y_uuid12}.json").exists()
    assert (tmp_path / f"rate_projection.{y_uuid12}.json").exists()


def test_account_scoped_path_used_by_legacy_stdin_cache(tmp_path, monkeypatch):
    """core.py/render_thin.py account-key the legacy last_stdin.json fallback
    the same way — this pins the shared helper they both call."""
    cfg_dir = tmp_path / "alt-config"
    _fake_config_dir(cfg_dir, "33333333-3333-3333-3333-333333333333")
    monkeypatch.setattr(predict, "_ACCOUNT_CACHE", {})
    _use_real_account_id(monkeypatch)
    base = tmp_path / "last_stdin.json"
    scoped = predict.account_scoped_path(base, {"CLAUDE_CONFIG_DIR": str(cfg_dir)})
    assert scoped == tmp_path / "last_stdin.33333333-333.json"
