"""Multi-account (CLAUDE_CONFIG_DIR): opt-in `show_account` identity segment.

Config: `show_account` (bool, default False) + `account_style`
("email" | "name" | "both", default "email" — email disambiguates accounts,
displayName can collide across a team).
Render: the account rides the identity line when show_project_branch is on
(alongside cwd_text), else gets its own `⤷` line — same placement rules as
show_cwd (see test_show_cwd.py).
"""

from pathlib import Path

import pytest

from claude_statusbar import config
from claude_statusbar.identity import IdentityInfo
from claude_statusbar.styles import render, render_identity_line
from claude_statusbar.themes import get_theme


THEME = get_theme("graphite")


def _info(name="proj"):
    return IdentityInfo(project_name=name, in_git=True, branch="main",
                        detached=False, worktree_name=None, toplevel="/x")


# --- config -------------------------------------------------------------------

def test_show_account_defaults_off():
    cfg = config.StatusbarConfig()
    assert cfg.show_account is False
    assert cfg.account_style == "email"


def test_show_account_roundtrip(tmp_path: Path):
    p = tmp_path / "cfg.json"
    cfg = config.StatusbarConfig(show_account=True, account_style="both")
    config.save_config(cfg, p)
    loaded = config.load_config(p)
    assert loaded.show_account is True
    assert loaded.account_style == "both"


def test_set_value_show_account(tmp_path: Path):
    p = tmp_path / "cfg.json"
    cfg = config.set_value("show_account", "true", p)
    assert cfg.show_account is True
    cfg = config.set_value("show_account", "off", p)
    assert cfg.show_account is False


def test_set_value_account_style_validates(tmp_path: Path):
    p = tmp_path / "cfg.json"
    cfg = config.set_value("account_style", "name", p)
    assert cfg.account_style == "name"
    with pytest.raises(ValueError):
        config.set_value("account_style", "nickname", p)


def test_keys_registered():
    assert "show_account" in config.VALID_KEYS
    assert "account_style" in config.VALID_KEYS
    assert "show_account" in config._BOOL_KEYS


# --- identity-line rendering ----------------------------------------------------

def test_account_on_identity_line():
    s = render_identity_line(_info(), theme=THEME, dirty=False,
                             account_text="a@b.c", use_color=False)
    assert "· a@b.c" in s


def test_account_and_cwd_both_appear():
    s = render_identity_line(_info(), theme=THEME, dirty=False,
                             cwd_text="subdir", account_text="a@b.c",
                             use_color=False)
    assert "· subdir" in s
    assert "· a@b.c" in s


def test_no_account_text_no_segment():
    s = render_identity_line(_info(), theme=THEME, dirty=False,
                             use_color=False)
    assert "·" not in s.replace("· v", "")  # only the version separator allowed


# --- full render plumbing -------------------------------------------------------

_BASE = dict(msgs_pct=10, weekly_pct=5, reset_5h="1h00m", reset_7d="2d00h",
             model="Test", lang_body="", use_color=False, theme=THEME)


def test_render_passes_account_to_identity_line():
    out = render("classic", **_BASE,
                 show_project_branch=True, identity=_info(),
                 identity_dirty=False, account_text="a@b.c")
    lines = out.split("\n")
    assert any("⤷" in ln and "· a@b.c" in ln for ln in lines)


def test_render_standalone_account_line_when_identity_off():
    out = render("classic", **_BASE, account_text="a@b.c")
    assert "\n⤷ a@b.c" in out


def test_render_standalone_line_combines_cwd_and_account():
    out = render("classic", **_BASE, cwd_text="subdir", account_text="a@b.c")
    assert "\n⤷ subdir · a@b.c" in out


def test_render_without_account_adds_no_extra_line():
    with_none = render("classic", **_BASE)
    assert "⤷" not in with_none
