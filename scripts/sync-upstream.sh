#!/usr/bin/env bash
# sync-upstream.sh — safely pull features from the original repo
#
# Usage:
#   ./scripts/sync-upstream.sh            # show new upstream commits, categorized by risk
#   ./scripts/sync-upstream.sh pick <sha> # cherry-pick one commit, then verify security
#   ./scripts/sync-upstream.sh diff <sha> # show full diff for a commit before picking
#
# After any pick, the verify script runs automatically.
# Never run this without reading the output first.

set -euo pipefail

UPSTREAM_URL="https://github.com/leeguooooo/claude-code-usage-bar"
UPSTREAM_REMOTE="upstream"
VERIFY_SCRIPT="$(dirname "$0")/verify-security.sh"

# ── Files where our security patches live.
# A commit touching ANY of these is flagged RISKY — review the diff manually.
SECURITY_SENSITIVE=(
  "src/claude_statusbar/updater.py"
  "src/claude_statusbar/core.py"
  "install.sh"
  "web-install.sh"
  "pyproject.toml"
  ".claude-plugin/plugin.json"
  "demo/record_demo.sh"
  ".github/FUNDING.yml"
  ".github/workflows/ci.yml"
)

# ── Colors
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

# ────────────────────────────────────────────────────────────────────────────
ensure_upstream() {
  if ! git remote | grep -q "^${UPSTREAM_REMOTE}$"; then
    echo -e "${BLUE}Adding upstream remote (fetch-only)...${NC}"
    git remote add "${UPSTREAM_REMOTE}" "${UPSTREAM_URL}"
    git remote set-url --push "${UPSTREAM_REMOTE}" DISABLED
  fi
  echo -e "${BLUE}Fetching upstream...${NC}"
  git fetch "${UPSTREAM_REMOTE}" --quiet
}

# ── Return 0 if the commit touches any security-sensitive file
commit_touches_security() {
  local sha="$1"
  local files
  files=$(git diff-tree --no-commit-id -r --name-only "$sha" 2>/dev/null)
  for f in "${SECURITY_SENSITIVE[@]}"; do
    if echo "$files" | grep -qF "$f"; then
      return 0
    fi
  done
  return 1
}

# ── Print which security files a commit touches
security_files_in_commit() {
  local sha="$1"
  local files
  files=$(git diff-tree --no-commit-id -r --name-only "$sha" 2>/dev/null)
  for f in "${SECURITY_SENSITIVE[@]}"; do
    if echo "$files" | grep -qF "$f"; then
      echo "    ⚠  $f"
    fi
  done
}

# ────────────────────────────────────────────────────────────────────────────
cmd_list() {
  ensure_upstream

  # Find commits on upstream/main that are NOT in our history
  local new_commits
  new_commits=$(git log HEAD.."${UPSTREAM_REMOTE}/main" --oneline 2>/dev/null)

  if [[ -z "$new_commits" ]]; then
    echo -e "${GREEN}✓ Already up to date with upstream.${NC}"
    exit 0
  fi

  local count
  count=$(echo "$new_commits" | wc -l | tr -d ' ')
  echo -e "${BOLD}${count} new upstream commit(s):${NC}"
  echo ""

  local safe=0 risky=0
  while IFS= read -r line; do
    local sha subject
    sha=$(echo "$line" | awk '{print $1}')
    subject=$(echo "$line" | cut -d' ' -f2-)

    if commit_touches_security "$sha"; then
      echo -e "  ${RED}[RISKY]${NC}  $sha  $subject"
      security_files_in_commit "$sha"
      (( risky++ )) || true
    else
      echo -e "  ${GREEN}[SAFE] ${NC}  $sha  $subject"
      (( safe++ )) || true
    fi
  done <<< "$new_commits"

  echo ""
  echo -e "  ${GREEN}${safe} safe${NC}  |  ${RED}${risky} risky${NC}"
  echo ""
  echo "To inspect a commit:   ./scripts/sync-upstream.sh diff <sha>"
  echo "To cherry-pick a safe: ./scripts/sync-upstream.sh pick <sha>"
  echo ""
  echo -e "${YELLOW}After every pick, verify-security.sh runs automatically.${NC}"
  echo -e "${YELLOW}Never pick a RISKY commit without manually reviewing the diff first.${NC}"
}

# ────────────────────────────────────────────────────────────────────────────
cmd_diff() {
  local sha="${1:-}"
  if [[ -z "$sha" ]]; then
    echo "Usage: $0 diff <sha>" >&2; exit 1
  fi
  ensure_upstream
  echo -e "${BOLD}Diff for ${sha}:${NC}"
  git show "$sha" --stat
  echo ""
  git show "$sha"
}

# ────────────────────────────────────────────────────────────────────────────
cmd_pick() {
  local sha="${1:-}"
  if [[ -z "$sha" ]]; then
    echo "Usage: $0 pick <sha>" >&2; exit 1
  fi
  ensure_upstream

  # Warn loudly if this commit touches security files
  if commit_touches_security "$sha"; then
    echo -e "${RED}${BOLD}WARNING: this commit touches security-sensitive files:${NC}"
    security_files_in_commit "$sha"
    echo ""
    echo -e "${RED}Cherry-picking it may overwrite your security patches.${NC}"
    printf "Are you sure you want to continue? (yes/N): "
    read -r reply < /dev/tty
    if [[ "$reply" != "yes" ]]; then
      echo "Aborted."
      exit 1
    fi
  fi

  echo -e "${BLUE}Cherry-picking ${sha}...${NC}"
  if ! git cherry-pick "$sha"; then
    echo -e "${RED}Cherry-pick failed (conflicts). Resolve conflicts, then:${NC}"
    echo "  git cherry-pick --continue"
    echo "  ./scripts/verify-security.sh"
    exit 1
  fi

  echo ""
  echo -e "${BLUE}Running security verification...${NC}"
  if bash "$VERIFY_SCRIPT"; then
    echo ""
    echo -e "${GREEN}✓ Security patches intact. Safe to push.${NC}"
    echo "  git push origin main"
  else
    echo ""
    echo -e "${RED}✗ Security patches broken by this cherry-pick!${NC}"
    echo "  Fix the issues above, or revert with: git cherry-pick --abort / git reset HEAD~1"
    exit 1
  fi
}

# ────────────────────────────────────────────────────────────────────────────
case "${1:-list}" in
  list|"")  cmd_list ;;
  diff)     cmd_diff "${2:-}" ;;
  pick)     cmd_pick "${2:-}" ;;
  *)
    echo "Usage: $0 [list|diff <sha>|pick <sha>]" >&2
    exit 1
    ;;
esac
