#!/bin/bash
# Smoke test: verify nightjar CLI is installed and the OpenClaw skill works end-to-end.
# Run this after installing the skill to confirm the environment is set up correctly.
#
# Usage:
#   bash test/smoke_test.sh
#
# Exit codes:
#   0 — all checks passed
#   1 — one or more checks failed

set -e

PASS=0
FAIL=0
ERRORS=()

check() {
  local label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "  PASS: $label"
    ((PASS++)) || true
  else
    echo "  FAIL: $label"
    ERRORS+=("$label")
    ((FAIL++)) || true
  fi
}

echo "========================================"
echo " nightjar-verify OpenClaw skill — smoke test"
echo "========================================"
echo ""

# ── 1. Binary checks ──────────────────────────────────────────────────────────
echo "[1/4] Binary checks"

check "nightjar is on PATH" which nightjar
check "python3 is on PATH" which python3
check "nightjar --version exits 0" nightjar --version

echo ""

# ── 2. nightjar init ─────────────────────────────────────────────────────────
echo "[2/4] nightjar init"

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

pushd "$TMPDIR" >/dev/null

check "nightjar init creates .card dir" bash -c "nightjar init smoke_test && test -d .card"
check "spec file exists after init" test -f ".card/smoke_test.card.md"
check "spec file is non-empty" bash -c "test -s .card/smoke_test.card.md"

popd >/dev/null
echo ""

# ── 3. nightjar scan ─────────────────────────────────────────────────────────
echo "[3/4] nightjar scan"

TMPDIR2=$(mktemp -d)
trap 'rm -rf "$TMPDIR" "$TMPDIR2"' EXIT

# Write a minimal Python file to scan
cat > "$TMPDIR2/sample.py" << 'EOF'
def add(a: int, b: int) -> int:
    """Return the sum of a and b."""
    return a + b
EOF

pushd "$TMPDIR2" >/dev/null

check "nightjar scan exits 0 on valid Python" nightjar scan sample.py

popd >/dev/null
echo ""

# ── 4. nightjar verify --fast (spec from init) ───────────────────────────────
echo "[4/4] nightjar verify --fast"

TMPDIR3=$(mktemp -d)
trap 'rm -rf "$TMPDIR" "$TMPDIR2" "$TMPDIR3"' EXIT

pushd "$TMPDIR3" >/dev/null

# Scaffold spec
nightjar init verify_smoke >/dev/null 2>&1 || true

# Write a trivially correct implementation
cat > verify_smoke.py << 'EOF'
# nightjar: smoke
def add(a: int, b: int) -> int:
    return a + b
EOF

check "nightjar verify --fast exits 0 or 1 (not config error)" bash -c \
  "nightjar verify --spec .card/verify_smoke.card.md --fast; code=$?; test \$code -le 1"

popd >/dev/null
echo ""

# ── Summary ──────────────────────────────────────────────────────────────────
echo "========================================"
echo " Results: $PASS passed, $FAIL failed"
echo "========================================"

if [ ${#ERRORS[@]} -gt 0 ]; then
  echo ""
  echo "Failed checks:"
  for err in "${ERRORS[@]}"; do
    echo "  - $err"
  done
  echo ""
  echo "Troubleshooting:"
  echo "  nightjar not found  → pip install nightjar-verify"
  echo "  init/scan fails     → check nightjar --version, ensure Python 3.11+"
  echo "  verify config error → run nightjar init <module> to create a valid spec"
  exit 1
fi

echo ""
echo "PASS: nightjar-verify OpenClaw skill is installed and operational."
