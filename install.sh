#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  clenv installer
#  Usage (from GitHub):
#    curl -fsSL https://raw.githubusercontent.com/AnasNafees1802/clenv/main/install.sh | bash
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

REPO="https://github.com/AnasNafees1802/clenv"
RAW="https://raw.githubusercontent.com/AnasNafees1802/clenv/main"
CLENV_VERSION="1.0.0"

CYAN="\033[1;36m"
GREEN="\033[1;32m"
YELLOW="\033[1;33m"
RED="\033[1;31m"
DIM="\033[2m"
RESET="\033[0m"

banner() {
cat << 'BANNER'

  ██████╗██╗     ███████╗███╗   ██╗██╗   ██╗
 ██╔════╝██║     ██╔════╝████╗  ██║██║   ██║
 ██║     ██║     █████╗  ██╔██╗ ██║██║   ██║
 ██║     ██║     ██╔══╝  ██║╚██╗██║╚██╗ ██╔╝
 ╚██████╗███████╗███████╗██║ ╚████║ ╚████╔╝
  ╚═════╝╚══════╝╚══════╝╚═╝  ╚═══╝  ╚═══╝

BANNER
  echo -e "${DIM}  Your CLI junk drawer, finally cleaned up.${RESET}"
  echo ""
}

info()    { echo -e "${CYAN}  →${RESET} $*"; }
success() { echo -e "${GREEN}  ✔${RESET} $*"; }
warn()    { echo -e "${YELLOW}  ⚠${RESET}  $*"; }
fail()    { echo -e "${RED}  ✗${RESET} $*"; exit 1; }

# ── Detect OS ────────────────────────────────────────────────────────────────
OS="$(uname -s)"
case "$OS" in
  Darwin) OS_NAME="macOS" ;;
  Linux)  OS_NAME="Linux" ;;
  *)      fail "Unsupported OS: $OS" ;;
esac

# ── Check Python ─────────────────────────────────────────────────────────────
PYTHON=""
for py in python3 python; do
  if command -v "$py" &>/dev/null; then
    ver=$("$py" -c "import sys; print(sys.version_info >= (3,9))" 2>/dev/null || echo False)
    if [ "$ver" = "True" ]; then
      PYTHON="$py"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  fail "Python 3.9+ is required. Install it from https://python.org"
fi

# ── Install method ────────────────────────────────────────────────────────────
banner

echo -e "${CYAN}  Installing clenv on ${OS_NAME}...${RESET}"
echo ""

# Prefer pipx (cleanest, isolated)
if command -v pipx &>/dev/null; then
  info "Using pipx (isolated environment, recommended)"
  pipx install "git+${REPO}.git" --force
  INSTALLED_VIA="pipx"

# Try pip with --user
elif "$PYTHON" -m pip install --version &>/dev/null 2>&1; then
  info "Using pip (--user install)"
  "$PYTHON" -m pip install --user "git+${REPO}.git" --quiet
  INSTALLED_VIA="pip"

  # Ensure ~/.local/bin is in PATH
  LOCAL_BIN="$HOME/.local/bin"
  if [[ ":$PATH:" != *":$LOCAL_BIN:"* ]]; then
    warn "~/.local/bin is not in your PATH."
    warn "Add this to your shell profile (~/.bashrc, ~/.zshrc, etc.):"
    echo ""
    echo -e "    ${DIM}export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}"
    echo ""
  fi
else
  fail "Neither pipx nor pip found. Install pip: https://pip.pypa.io"
fi

echo ""
success "clenv ${CLENV_VERSION} installed via ${INSTALLED_VIA}!"
echo ""
echo -e "${DIM}  Run it with:${RESET}"
echo ""
echo -e "    ${CYAN}clenv${RESET}"
echo ""
echo -e "${DIM}  Or jump straight to scanning:${RESET}"
echo -e "    ${CYAN}clenv${RESET}"
echo ""
