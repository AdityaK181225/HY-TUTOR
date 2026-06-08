#!/usr/bin/env bash
# ==============================================================================
# HY-TUTOR — Linux/macOS Installer
# ------------------------------------------------------------------------------
# One-shot bootstrap for a fresh clone:
#   1. Verifies Python 3.10+
#   2. Creates .venv and installs requirements.txt
#   3. Seeds config/.env from config/.env.example
#   4. Prompts (optional, masked) for GEMINI_API_KEY
#   5. Validates and writes the key
#
# Usage:
#   bash install.sh
#
# Idempotent: safe to re-run. Re-running will refresh pip packages and
# leave the existing GEMINI_API_KEY untouched unless --reset-key is passed.
# ==============================================================================

set -euo pipefail

# --- ANSI Colors (best-effort, falls back to plain text) -----------------------
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    RED='\033[0;31m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    GREEN=''; YELLOW=''; RED=''; CYAN=''; BOLD=''; NC=''
fi

log()   { echo -e "${CYAN}[install]${NC} $*"; }
ok()    { echo -e "${GREEN}[ok]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC} $*"; }
fatal() { echo -e "${RED}[fatal]${NC} $*" >&2; exit 1; }

# --- Parse args ----------------------------------------------------------------
RESET_KEY=0
for arg in "$@"; do
    case "$arg" in
        --reset-key) RESET_KEY=1 ;;
        -h|--help)
            echo "Usage: bash install.sh [--reset-key]"
            echo "  --reset-key  Re-prompt for GEMINI_API_KEY even if one is already set"
            exit 0
            ;;
        *) fatal "Unknown argument: $arg" ;;
    esac
done

# --- Pre-flight: must be run from repo root -----------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

[ -f "requirements.txt" ] || fatal "requirements.txt not found. Run install.sh from the HY-TUTOR repo root."
[ -f "config/.env.example" ] || fatal "config/.env.example not found. Repo layout looks broken."

echo -e "${BOLD}====================================================${NC}"
echo -e "${BOLD}   HY-TUTOR INSTALLER (Linux/macOS)                  ${NC}"
echo -e "${BOLD}====================================================${NC}"
log "Repo root: $SCRIPT_DIR"

# --- 1. Python 3.10+ detection -----------------------------------------------
log "Looking for Python 3.10+..."
PYTHON_BIN=""
for candidate in python3.11 python3.12 python3.13 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        version="$("$candidate" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "0.0")"
        major="$(echo "$version" | cut -d. -f1)"
        minor="$(echo "$version" | cut -d. -f2)"
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON_BIN="$candidate"
            ok "Found $candidate ($version)"
            break
        fi
    fi
done

[ -n "$PYTHON_BIN" ] || fatal "Python 3.10+ not found. Install it via your package manager (e.g. 'sudo apt install python3.11 python3.11-venv')."

# --- 2. Virtual environment ---------------------------------------------------
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
    log "Creating virtual environment at $VENV_DIR..."
    "$PYTHON_BIN" -m venv "$VENV_DIR" || fatal "venv creation failed."
    ok "Virtual environment created."
else
    ok "Virtual environment already exists at $VENV_DIR."
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

log "Upgrading pip..."
python -m pip install --upgrade pip --quiet || warn "pip upgrade failed (non-fatal)."

# --- 3. Install requirements --------------------------------------------------
log "Installing Python dependencies (this may take a minute)..."
python -m pip install -r requirements.txt --quiet
ok "Dependencies installed."

# --- 4. config/.env setup -----------------------------------------------------
ENV_FILE="config/.env"
EXAMPLE_FILE="config/.env.example"

if [ ! -f "$ENV_FILE" ]; then
    log "Seeding $ENV_FILE from $EXAMPLE_FILE..."
    cp "$EXAMPLE_FILE" "$ENV_FILE"
    ok "Created $ENV_FILE."
else
    ok "$ENV_FILE already exists."
fi

# --- 5. API key prompt (masked, optional) ------------------------------------
prompt_for_api_key() {
    local current_key
    current_key="$(grep -E '^GEMINI_API_KEY=' "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | tr -d '[:space:]' || true)"

    if [ "$RESET_KEY" -eq 0 ] && [ -n "$current_key" ]; then
        ok "GEMINI_API_KEY already set in $ENV_FILE (use --reset-key to change)."
        return 0
    fi

    echo
    echo -e "${BOLD}Gemini API key${NC}"
    echo -e "  HY-TUTOR uses Google Gemini for content generation and tutoring."
    echo -e "  Get a free key at: ${CYAN}https://aistudio.google.com/app/apikey${NC}"
    echo -e "  You can skip this step and enter the key later from the in-app wizard."
    echo

    local api_key=""
    while true; do
        read -r -s -p "Paste GEMINI_API_KEY (or press Enter to skip): " api_key
        echo
        if [ -z "$api_key" ]; then
            warn "Skipped. The in-app wizard will ask for the key on first launch."
            return 0
        fi
        # Light validation: Google AI Studio keys start with "AIza" and are ~39 chars
        if [[ "$api_key" =~ ^AIza[A-Za-z0-9_-]{30,50}$ ]]; then
            break
        fi
        warn "That doesn't look like a valid Gemini key (expected to start with 'AIza')."
        read -r -p "Try again? [y/N] " retry
        if [[ ! "$retry" =~ ^[Yy]$ ]]; then
            warn "Skipped. You can re-run 'bash install.sh --reset-key' or use the in-app wizard."
            return 0
        fi
    done

    # Atomically replace the key in config/.env
    local tmp
    tmp="$(mktemp)"
    if grep -qE '^GEMINI_API_KEY=' "$ENV_FILE"; then
        # Replace existing line
        grep -vE '^GEMINI_API_KEY=' "$ENV_FILE" > "$tmp"
        echo "GEMINI_API_KEY=$api_key" >> "$tmp"
    else
        # Append new line
        cp "$ENV_FILE" "$tmp"
        echo "GEMINI_API_KEY=$api_key" >> "$tmp"
    fi
    mv "$tmp" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    ok "GEMINI_API_KEY saved to $ENV_FILE (mode 600)."
}

prompt_for_api_key

# --- 6. Done ------------------------------------------------------------------
echo
echo -e "${GREEN}====================================================${NC}"
echo -e "${GREEN} ✅ HY-TUTOR installation complete!                  ${NC}"
echo -e "${GREEN}====================================================${NC}"
echo
echo -e "  Next steps:"
echo -e "    ${BOLD}bash make_desktop.sh${NC}   # install the HY-TUTOR icon (Linux)"
echo -e "    ${BOLD}bash launch_engine.sh${NC}  # start the Streamlit UI in your browser"
echo
ok "Streamlit will serve on http://localhost:8501 by default."
