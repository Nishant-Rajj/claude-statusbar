#!/usr/bin/env bash
# verify-security.sh — assert all security patches are still intact
#
# Usage:
#   ./scripts/verify-security.sh          # exits 0 if all pass, 1 if any fail
#
# Run after every cherry-pick or merge from upstream.
# Each check is deterministic — no network, no LLM, just grep + file tests.

set -uo pipefail

REPO="$(git rev-parse --show-toplevel)"
PASS=0; FAIL=0

GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'; BOLD='\033[1m'

ok()   { echo -e "  ${GREEN}✓${NC}  $1"; (( PASS++ )) || true; }
fail() { echo -e "  ${RED}✗${NC}  $1"; (( FAIL++ )) || true; }

echo -e "${BOLD}Security patch verification${NC}"
echo "────────────────────────────────────────"

# ── 1. updater.py must be a no-op stub (no network, no subprocess)
f="$REPO/src/claude_statusbar/updater.py"
if grep -qE 'urllib|urlopen|subprocess|pip install|uv tool|pipx upgrade' "$f" 2>/dev/null; then
  fail "updater.py: live network or package-manager code found — stub may have been overwritten"
else
  ok "updater.py: no network or package-manager calls"
fi

if grep -q 'return False' "$f" 2>/dev/null && grep -q 'auto_upgrade' "$f" 2>/dev/null; then
  ok "updater.py: auto_upgrade() returns False (neutered)"
else
  fail "updater.py: auto_upgrade() stub missing or altered"
fi

# ── 2. core.py must not call check_for_updates or _maybe_ensure_statusline
f="$REPO/src/claude_statusbar/core.py"
if grep -q 'check_for_updates(' "$f" 2>/dev/null; then
  fail "core.py: check_for_updates() is still being called"
else
  ok "core.py: check_for_updates() call removed"
fi

if grep -q '_maybe_ensure_statusline()' "$f" 2>/dev/null; then
  fail "core.py: _maybe_ensure_statusline() is still being called"
else
  ok "core.py: _maybe_ensure_statusline() call removed"
fi

# ── 3. core.py must not contain urlopen
if grep -q 'urlopen' "$f" 2>/dev/null; then
  fail "core.py: urlopen found — network call present"
else
  ok "core.py: no urlopen"
fi

# ── 4. install.sh and web-install.sh must not exist
for script in install.sh web-install.sh; do
  if [[ -f "$REPO/$script" ]]; then
    fail "$script: curl-pipe-bash installer is back — delete it"
  else
    ok "$script: does not exist (deleted)"
  fi
done

# ── 5. pyproject.toml [project.urls] must not contain upstream URLs
# (author attribution in [project] is fine — MIT requires keeping it)
f="$REPO/pyproject.toml"
if awk '/^\[project\.urls\]/,/^\[/' "$f" 2>/dev/null | grep -qE 'leeguooooo|github\.com/leeguooooo'; then
  fail "pyproject.toml: upstream URLs in [project.urls] still present"
else
  ok "pyproject.toml: no upstream URLs in [project.urls]"
fi

# ── 6. plugin.json must not contain upstream homepage/repository
f="$REPO/.claude-plugin/plugin.json"
if grep -qE 'leeguooooo|github\.com/leeguooooo' "$f" 2>/dev/null; then
  fail "plugin.json: upstream URLs still present"
else
  ok "plugin.json: no upstream URLs"
fi

# ── 7. demo/record_demo.sh must not contain curl | bash to upstream
f="$REPO/demo/record_demo.sh"
if grep -qE 'curl.*leeguooooo.*\|\s*bash|wget.*leeguooooo.*\|\s*sh' "$f" 2>/dev/null; then
  fail "demo/record_demo.sh: curl-pipe-bash to upstream still present"
else
  ok "demo/record_demo.sh: no curl-pipe-bash to upstream"
fi

# ── 8. No git remote pointing at upstream
if git -C "$REPO" remote -v 2>/dev/null | grep -qE 'leeguooooo.*\(push\)'; then
  fail "git remote: a push remote pointing at upstream exists — remove it"
else
  ok "git remotes: no push remote to upstream"
fi

# ── 9. FUNDING.yml must not exist
if [[ -f "$REPO/.github/FUNDING.yml" ]]; then
  fail ".github/FUNDING.yml: upstream funding file is back — delete it"
else
  ok ".github/FUNDING.yml: does not exist (deleted)"
fi

# ── Summary
echo "────────────────────────────────────────"
echo -e "  ${GREEN}${PASS} passed${NC}  |  ${RED}${FAIL} failed${NC}"
echo ""

if [[ $FAIL -gt 0 ]]; then
  echo -e "${RED}Security patches are broken. Fix before pushing.${NC}"
  echo "See .security/patches.md for what each patch does and how to reapply."
  exit 1
else
  echo -e "${GREEN}All security patches intact.${NC}"
  exit 0
fi
