#!/usr/bin/env bash
# Run the full HomieProxy test suite (unit + integration + security).
#
# This script is self-contained — it creates a local virtualenv at .venv-tests/
# and installs everything pytest needs, so a fresh checkout can `./run-tests.sh`
# with nothing pre-installed beyond a working Python 3.11+.
#
# Usage:
#   ./run-tests.sh                    # full suite, verbose
#   ./run-tests.sh -k token           # forward args to pytest (filter, etc.)
#   FAST=1 ./run-tests.sh             # skip dep install (env already prepared)
#   PYTHON=python3.12 ./run-tests.sh  # pin which python to use for the venv
#   NO_VENV=1 ./run-tests.sh          # use the current python directly (CI)
#
# Exit code is pytest's — non-zero on any failure.

set -euo pipefail

cd "$(dirname "$0")"

# ── Colour helpers (skip when not a tty / NO_COLOR set) ────────────────────────
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  C_BOLD=$'\033[1m'; C_DIM=$'\033[2m'
  C_GREEN=$'\033[32m'; C_RED=$'\033[31m'; C_YEL=$'\033[33m'; C_RESET=$'\033[0m'
else
  C_BOLD=""; C_DIM=""; C_GREEN=""; C_RED=""; C_YEL=""; C_RESET=""
fi

step()  { printf "%s── %s ──%s\n" "$C_BOLD" "$1" "$C_RESET"; }
ok()    { printf "  %s✓%s %s\n" "$C_GREEN" "$C_RESET" "$1"; }
warn()  { printf "  %s!%s %s\n" "$C_YEL" "$C_RESET" "$1"; }
fail()  { printf "  %s✗%s %s\n" "$C_RED" "$C_RESET" "$1"; }

# ── Pick a Python interpreter ──────────────────────────────────────────────────
PY="${PYTHON:-}"
if [[ -z "$PY" ]]; then
  for cand in python3.13 python3.12 python3.11 python3 python; do
    if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
  done
fi
if [[ -z "$PY" ]] || ! command -v "$PY" >/dev/null 2>&1; then
  fail "no Python interpreter found on PATH"
  echo "  set PYTHON=/path/to/python or install python3.11+"
  exit 127
fi

PY_VERSION="$("$PY" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])')"
PY_MAJOR_MINOR="$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"

# Hard-fail on Python <3.11 (HA's minimum).
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' || {
  fail "Python $PY_VERSION is too old (need 3.11+)"
  exit 1
}

step "Environment"
ok   "interpreter:  $PY ($PY_VERSION)"

# ── Set up / activate venv unless NO_VENV ──────────────────────────────────────
VENV_DIR=".venv-tests"

if [[ "${NO_VENV:-}" == "1" ]]; then
  warn "NO_VENV=1 — using current Python directly, no venv"
  VPY="$PY"
else
  # Pre-flight: ensurepip must be importable, else `python -m venv` will create
  # a broken (no-pip) env. Common on Debian/Ubuntu where python3-venv ships
  # separately from python3. Detect early and emit an actionable message.
  if ! "$PY" -c 'import ensurepip' 2>/dev/null; then
    fail "python -m venv won't work: ensurepip is missing"
    echo "  This is the standard split-package layout on Debian/Ubuntu."
    echo "  Install the venv extras for your interpreter and retry:"
    echo
    echo "    sudo apt install python${PY_MAJOR_MINOR}-venv"
    echo
    echo "  …or rerun this script with NO_VENV=1 to use the system Python"
    echo "  (note: PEP 668 may block pip on managed system pythons)."
    exit 1
  fi

  if [[ ! -d "$VENV_DIR" ]]; then
    step "Creating virtualenv at $VENV_DIR"
    if ! "$PY" -m venv "$VENV_DIR"; then
      fail "venv creation failed — removing partial dir"
      rm -rf "$VENV_DIR"
      exit 1
    fi
    ok   "venv created"
    # First-run always installs deps regardless of FAST.
    FAST=""
  fi
  # POSIX shells use bin/, Windows would use Scripts/ (this script is bash).
  VPY="$VENV_DIR/bin/python"
  if [[ ! -x "$VPY" ]]; then
    fail "venv broken: missing $VPY — removing and bailing (rerun to recreate)"
    rm -rf "$VENV_DIR"
    exit 1
  fi
  ok "venv:         $VENV_DIR (python $("$VPY" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])'))"
fi

# ── Install / refresh test dependencies ────────────────────────────────────────
# In a venv we can pip-install freely. With NO_VENV=1 on a PEP-668 managed
# system Python (Debian/Ubuntu 23.04+, recent Fedora) plain pip fails with
# "externally-managed-environment" — auto-add --user --break-system-packages
# in that case so CI / WSL fallback still works.
PIP_FLAGS=()
if [[ "${NO_VENV:-}" == "1" ]]; then
  if "$VPY" -m pip install --dry-run --quiet pip >/dev/null 2>&1; then
    :  # plain pip works
  else
    warn "system Python is PEP-668 managed; using --user --break-system-packages"
    PIP_FLAGS=(--user --break-system-packages)
  fi
fi

if [[ "${FAST:-}" != "1" ]]; then
  step "Installing test dependencies"
  "$VPY" -m pip install --quiet "${PIP_FLAGS[@]}" --upgrade pip || true
  "$VPY" -m pip install --quiet "${PIP_FLAGS[@]}" \
    pytest \
    pytest-asyncio \
    pytest-aiohttp \
    aiohttp
  ok "pytest, pytest-asyncio, pytest-aiohttp, aiohttp installed"
else
  step "Skipping dep install (FAST=1)"
fi

# ── Run pytest ─────────────────────────────────────────────────────────────────
step "Running pytest"
# -ra prints the reasons for any skipped/xfailed tests so dead xfails don't
# accumulate silently. Forward extra CLI args ("$@") to pytest.
"$VPY" -m pytest tests/ -v -ra "$@"

# ── Validate JSON manifests (only after tests pass) ───────────────────────────
step "Validating JSON manifests"
"$VPY" - <<'PY'
import json, glob, sys

def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)

ok = True
def report(label, status, extra=""):
    sym = "\033[32m✓\033[0m" if status else "\033[31m✗\033[0m"
    print(f"  {sym} {label:<46}{extra}")

try:
    load("hacs.json"); report("hacs.json", True)
except Exception as e:
    report("hacs.json", False, f"  {e}"); ok = False

try:
    m = load("custom_components/homie_proxy/manifest.json")
    assert m["domain"] == "homie_proxy", f"domain mismatch: {m.get('domain')!r}"
    assert "version" in m, "manifest.json missing 'version'"
    report("custom_components/.../manifest.json", True, f"  v{m['version']}")
except Exception as e:
    report("custom_components/.../manifest.json", False, f"  {e}"); ok = False

count = 0
for f in glob.glob("custom_components/homie_proxy/translations/*.json"):
    try:
        load(f); count += 1
    except Exception as e:
        report(f, False, f"  {e}"); ok = False
report(f"translations  ({count} file(s))", count > 0)

sys.exit(0 if ok else 1)
PY

echo
printf "%sAll tests + JSON validations passed.%s\n" "$C_GREEN$C_BOLD" "$C_RESET"
