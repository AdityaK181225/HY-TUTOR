#!/usr/bin/env bash
==============================================================================
# HY-TUTOR — Smart One-Click Start (Linux/macOS)
# ------------------------------------------------------------------------------
# This script handles EVERYTHING on first run:
#   1. Checks for Python 3.10+ (installs if missing)
#   2. Creates virtual environment
#   3. Installs all dependencies
#   4. Seeds config/.env and prompts for API key
#   5. Creates a Desktop shortcut with HY-TUTOR icon
#   6. Launches the app and opens your browser
#
# After first run, use the desktop shortcut to launch directly.
#
# Usage:
#   bash start.sh
==============================================================================

set -euo pipefail

# --- Colors -------------------------------------------------------------------
if [ -t 1 ]; then
    GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[0;33m'
    CYAN='\033[0;36m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
else
    GREEN=''; RED=''; YELLOW=''; CYAN=''; BLUE=''; BOLD=''; NC=''
fi

log()   { echo -e "${CYAN}[hy-tutor]${NC} $*"; }
ok()    { echo -e "${GREEN}[ok]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC} $*"; }
fatal() { echo -e "${RED}[fatal]${NC} $*" >&2; exit 1; }

# --- Move to repo root --------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BOLD}====================================================${NC}"
echo -e "${BOLD}     HY-TUTOR — SMART START                         ${NC}"
echo -e "${BOLD}====================================================${NC}"
echo

# =============================================================================
# STEP 1: Python 3.10+ Detection
# =============================================================================
log "Checking for Python 3.10+..."
PYTHON_BIN=""

for candidate in python3.12 python3.11 python3.10 python3; do
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

if [ -z "$PYTHON_BIN" ]; then
    warn "Python 3.10+ not found. Attempting automatic installation..."
    if command -v apt >/dev/null 2>&1; then
        # Debian/Ubuntu
        log "Detected apt package manager. Installing Python..."
        sudo apt update -qq && sudo apt install -y python3.11 python3.11-venv python3-pip
        PYTHON_BIN="python3.11"
    elif command -v dnf >/dev/null 2>&1; then
        # Fedora
        log "Detected dnf. Installing Python..."
        sudo dnf install -y python3.11
        PYTHON_BIN="python3.11"
    elif command -v brew >/dev/null 2>&1; then
        # macOS
        log "Detected Homebrew. Installing Python..."
        brew install python@3.11
        PYTHON_BIN="python3.11"
    elif command -v pacman >/dev/null 2>&1; then
        # Arch
        log "Detected pacman. Installing Python..."
        sudo pacman -S --noconfirm python python-pip
        PYTHON_BIN="python3"
    else
        fatal "Could not auto-install Python. Please install Python 3.10+ manually."
    fi
    ok "Python installed: $PYTHON_BIN"
fi

# =============================================================================
# STEP 2: Virtual Environment
# =============================================================================
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
    log "Creating virtual environment..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    ok "Virtual environment created."
else
    ok "Virtual environment already exists."
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

log "Upgrading pip..."
python -m pip install --upgrade pip --quiet 2>/dev/null || true

# =============================================================================
# STEP 3: Install Dependencies
# =============================================================================
log "Checking dependencies..."
if ! python -c "import streamlit" 2>/dev/null; then
    log "Installing Python dependencies (this may take a minute)..."
    python -m pip install -r requirements.txt --quiet
    ok "Dependencies installed."
else
    ok "Dependencies already installed."
fi

# =============================================================================
# STEP 4: API Key Setup
# =============================================================================
ENV_FILE="config/.env"
EXAMPLE_FILE="config/.env.example"

if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$EXAMPLE_FILE" ]; then
        cp "$EXAMPLE_FILE" "$ENV_FILE"
        ok "Created config/.env from template."
    else
        echo "GEMINI_API_KEY=" > "$ENV_FILE"
        ok "Created empty config/.env."
    fi
fi

# Check if API key is set
GEMINI_API_KEY="$(grep -E '^GEMINI_API_KEY=' "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | tr -d '[:space:]' || true)"

if [ -z "$GEMINI_API_KEY" ]; then
    echo
    echo -e "${BOLD}Gemini API Key Setup${NC}"
    echo -e "  HY-TUTOR uses Google Gemini for AI tutoring."
    echo -e "  Get a free key at: ${CYAN}https://aistudio.google.com/app/apikey${NC}"
    echo
    read -r -s -p "  Paste your GEMINI_API_KEY (or press Enter to skip): " input_key
    echo
    if [ -n "$input_key" ]; then
        if [[ "$input_key" =~ ^AIza[A-Za-z0-9_-]{30,50}$ ]]; then
            local tmp; tmp="$(mktemp)"
            grep -vE '^GEMINI_API_KEY=' "$ENV_FILE" > "$tmp" 2>/dev/null || true
            echo "GEMINI_API_KEY=$input_key" >> "$tmp"
            mv "$tmp" "$ENV_FILE"
            chmod 600 "$ENV_FILE"
            ok "API key saved."
        else
            warn "Invalid key format. You can set it later via the in-app wizard."
        fi
    else
        warn "Skipped. The in-app wizard will ask for the key on first launch."
    fi
else
    ok "API key already configured."
fi

# Export for the session
export GEMINI_API_KEY

# =============================================================================
# STEP 5: Create Desktop Shortcut (first run only)
# =============================================================================
if [ -f "make_desktop.sh" ]; then
    if [ ! -f "$HOME/.local/share/applications/hytutor.desktop" ]; then
        log "Creating desktop shortcut..."
        bash make_desktop.sh
        ok "Desktop shortcut created."
    fi
fi

# =============================================================================
# STEP 6: Launch HY-TUTOR
# =============================================================================
echo
echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}  Launching HY-TUTOR...                             ${NC}"
echo -e "${BLUE}====================================================${NC}"
echo
echo -e "  Your browser will open automatically."
echo -e "  If not, visit: ${CYAN}http://localhost:8501${NC}"
echo -e "  Press Ctrl+C to stop the server."
echo

# Try to open browser (best-effort)
(
    sleep 3
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open http://localhost:8501 2>/dev/null || true
    elif command -v open >/dev/null 2>&1; then
        open http://localhost:8501 2>/dev/null || true
    fi
) &

streamlit run interface/app.py