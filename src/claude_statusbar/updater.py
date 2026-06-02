#!/usr/bin/env python3
"""
Auto-updater for claude-statusbar — DISABLED (local fork, no upstream updates).
All network and package-manager calls have been neutered.
"""
from __future__ import annotations

from typing import Optional, Tuple
import importlib.metadata as metadata

DIST_NAME = "claude-statusbar"


def get_current_version() -> str:
    try:
        return metadata.version(DIST_NAME)
    except metadata.PackageNotFoundError:
        return "0.0.0"


def get_latest_version() -> Optional[str]:
    return None


def compare_versions(_current: str, _latest: str) -> bool:
    return False


def auto_upgrade() -> bool:
    return False


def check_and_upgrade() -> Tuple[bool, str]:
    return False, "Auto-update disabled (local fork)"


if __name__ == "__main__":
    print("Auto-update disabled (local fork)")
    import sys
    sys.exit(1)
