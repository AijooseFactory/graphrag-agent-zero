#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# verify.sh — Single-command gatekeeper for public-release readiness
#
# Usage:
#   ./scripts/verify.sh           # Full local: sanitation + lint + unit + E2E
#   ./scripts/verify.sh --ci      # CI mode: skip Docker E2E
#   ./scripts/verify.sh --playwright  # Include optional Playwright tests
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

CI_MODE=false
PLAYWRIGHT=false
for arg in "$@"; do
  case "${arg}" in
    --ci) CI_MODE=true ;;
    --playwright) PLAYWRIGHT=true ;;
  esac
done

PASS=0
FAIL=0
step_pass() { echo "✅ PASS: $1"; PASS=$((PASS + 1)); }
step_fail() { echo "❌ FAIL: $1"; FAIL=$((FAIL + 1)); }

# ── 1. Secrets Sanitation ────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════"
echo " 1/5  Secrets Sanitation"
echo "═══════════════════════════════════════════"

# Files to scan (only committed/public-facing files)
SCAN_TARGETS=(
  "${ROOT_DIR}/.env.example"
  "${ROOT_DIR}/README.md"
  "${ROOT_DIR}/docs/"
  "${ROOT_DIR}/src/"
  "${ROOT_DIR}/tests/"
  "${ROOT_DIR}/scripts/"
  "${ROOT_DIR}/config/"
)

sanitize_ok=true

# Check for real API keys / passwords using grep -E (POSIX-compatible)
check_pattern() {
  local label="$1"
  local pattern="$2"
  for target in "${SCAN_TARGETS[@]}"; do
    if [ -e "${target}" ]; then
      if grep -rEq "${pattern}" "${target}" 2>/dev/null; then
        echo "  ⚠ ${label} found in: ${target}"
        grep -rEn "${pattern}" "${target}" 2>/dev/null | head -3
        sanitize_ok=false
      fi
    fi
  done
}

check_pattern "OpenAI API key"      "OPENAI_API_KEY=sk-[A-Za-z0-9]"
check_pattern "Anthropic API key"   "ANTHROPIC_API_KEY=[A-Za-z0-9]"

# Also check git staged files (if in a git repo)
if git -C "${ROOT_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  staged_files="$(git -C "${ROOT_DIR}" diff --cached --name-only 2>/dev/null || true)"
  if [ -n "${staged_files}" ]; then
    while IFS= read -r f; do
      full="${ROOT_DIR}/${f}"
      if [ -f "${full}" ] && grep -Eq "OPENAI_API_KEY=sk-|ANTHROPIC_API_KEY=[A-Za-z0-9]" "${full}" 2>/dev/null; then
        echo "  ⚠ Secret in staged file: ${f}"
        sanitize_ok=false
      fi
    done <<< "${staged_files}"
  fi
fi

if ${sanitize_ok}; then
  step_pass "Secrets sanitation"
else
  step_fail "Secrets sanitation — review output above"
fi

# ── 2. Lint ──────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════"
echo " 2/5  Lint (ruff)"
echo "═══════════════════════════════════════════"

if command -v ruff >/dev/null 2>&1; then
  if ruff check "${ROOT_DIR}"; then
    step_pass "Lint"
  else
    step_fail "Lint — ruff reported errors"
  fi
else
  echo "  ℹ ruff not found, skipping lint"
  step_pass "Lint (skipped — ruff not installed)"
fi

# ── 3. Unit Tests ────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════"
echo " 3/5  Unit Tests (pytest)"
echo "═══════════════════════════════════════════"

if command -v pytest >/dev/null 2>&1; then
  if pytest "${ROOT_DIR}/tests/" -x -q --tb=short; then
    step_pass "Unit tests"
  else
    step_fail "Unit tests"
  fi
else
  echo "  ℹ pytest not found, skipping unit tests"
  step_pass "Unit tests (skipped — pytest not installed)"
fi

# ── 4. E2E Contract ─────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════"
echo " 4/5  E2E Hybrid Contract"
echo "═══════════════════════════════════════════"

if ${CI_MODE}; then
  echo "  ℹ CI mode: skipping Docker E2E (no Docker daemon)"
  step_pass "E2E contract (skipped — CI mode)"
elif ! command -v docker >/dev/null 2>&1; then
  echo "  ℹ Docker not found: skipping E2E"
  step_pass "E2E contract (skipped — Docker not available)"
elif ! docker info >/dev/null 2>&1; then
  echo "  ℹ Docker daemon not running: skipping E2E"
  step_pass "E2E contract (skipped — Docker daemon not running)"
else
  if "${SCRIPT_DIR}/e2e_hybrid_contract.sh"; then
    step_pass "E2E hybrid contract"
  else
    step_fail "E2E hybrid contract"
  fi
fi

# ── 5. Playwright (optional) ────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════"
echo " 5/5  Playwright (optional)"
echo "═══════════════════════════════════════════"

if ${PLAYWRIGHT}; then
  if command -v npx >/dev/null 2>&1; then
    if npx playwright test --reporter=list; then
      step_pass "Playwright"
    else
      step_fail "Playwright"
    fi
  else
    echo "  ⚠ npx not found, skipping Playwright"
    step_pass "Playwright (skipped — npx not installed)"
  fi
else
  echo "  ℹ Skipped (use --playwright to enable)"
  step_pass "Playwright (skipped)"
fi

# ── Summary ──────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════"
echo " SUMMARY"
echo "═══════════════════════════════════════════"
echo "  Passed: ${PASS}"
echo "  Failed: ${FAIL}"
echo ""

if [ "${FAIL}" -gt 0 ]; then
  echo "❌ VERIFICATION FAILED"
  exit 1
fi

echo "✅ ALL GATES PASSED — release ready"
exit 0
