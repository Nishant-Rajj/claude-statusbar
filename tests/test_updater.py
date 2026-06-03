"""Tests for the neutered updater stub.

The auto-update mechanism was removed as a security patch — this fork must
never silently install packages from PyPI. These tests verify the stub
invariants hold so an upstream merge can't accidentally re-enable upgrades.
"""
import claude_statusbar.updater as updater


def test_get_latest_version_returns_none():
    """Must never make a network call — always returns None."""
    assert updater.get_latest_version() is None


def test_auto_upgrade_returns_false():
    """Must never invoke pip/uv/pipx — always returns False."""
    assert updater.auto_upgrade() is False


def test_check_and_upgrade_returns_disabled_message():
    success, message = updater.check_and_upgrade()
    assert success is False
    assert "disabled" in message.lower() or "local" in message.lower()


def test_compare_versions_always_false():
    """No version is ever 'newer' — upgrade is disabled."""
    assert updater.compare_versions("1.0.0", "9.9.9") is False
    assert updater.compare_versions("0.0.1", "0.0.2") is False


def test_no_network_symbols():
    """updater module must not contain urllib or subprocess."""
    mod_file = updater.__file__
    assert mod_file is not None
    mod_src = open(mod_file).read()
    assert "urllib" not in mod_src, "urllib found in updater — network call re-introduced"
    assert "subprocess" not in mod_src, "subprocess found in updater — package-manager call re-introduced"
