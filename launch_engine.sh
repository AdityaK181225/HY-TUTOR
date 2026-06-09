#!/bin/bash
# ==============================================================================
# HY-TUTOR: SYSTEM LAUNCH ENGINE (Linux/macOS)
# ------------------------------------------------------------------------------
# Activates the .venv, exports GEMINI_API_KEY from config/.env, and starts the
# Streamlit interface. Mirrors launch_engine.bat for Windows.
#
# Usage:
#   bash launch_engine.sh
# ==============================================================================

# Color codes (silently degrade to plain text if not a TTY)
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    RED='\033[0;31m'
    YELLOW='\033[0;33m'
    CYAN='\033[0;36m'
    BLUE='\033[0;34m'
    NC='\033[0m'
else
    GREEN=''; RED=''; YELLOW=''; CYAN=''; BLUE=''; NC=''
fi

# Always run from the repo root (where this script lives)
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}        HY-TUTOR INTEGRATED STARTUP ENGINE          ${NC}"
echo -e "${BLUE}====================================================${NC}"

# --- 1. Activate virtual environment -----------------------------------------
echo -e "${CYAN}[PROCESS] Activating virtual environment...${NC}"
if [ -d ".venv" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
    echo -e "${GREEN}[ok] Activated .venv${NC}"
elif [ -d "venv" ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
    echo -e "${GREEN}[ok] Activated venv${NC}"
else
    echo -e "${RED}[fatal] No .venv/ or venv/ directory found.${NC}"
    echo -e "${RED}        Run 'bash install.sh' first.${NC}"
    exit 1
fi

# --- 2. Load GEMINI_API_KEY from config/.env --------------------------------
echo -e "${CYAN}[PROCESS] Loading GEMINI_API_KEY from config/.env...${NC}"
ENV_FILE="config/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}[fatal] $ENV_FILE not found.${NC}"
    echo -e "${RED}        Run 'bash install.sh' first, or use the in-app wizard.${NC}"
    exit 1
fi

# Source only GEMINI_API_KEY, ignoring comments and other vars
GEMINI_API_KEY=$(grep -E '^GEMINI_API_KEY=' "$ENV_FILE" | cut -d'=' -f2- | tr -d '[:space:]' || true)
if [ -z "$GEMINI_API_KEY" ]; then
    echo -e "${RED}[warn] GEMINI_API_KEY is empty in $ENV_FILE.${NC}"
    echo -e "${YELLOW}       The in-app First-Run Wizard will guide you through setup.${NC}"
else
    export GEMINI_API_KEY
    echo -e "${GREEN}[ok] Loaded GEMINI_API_KEY${NC}"
fi

# --- 3. Launch Streamlit -----------------------------------------------------
echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN} 🚀 LAUNCHING HY-TUTOR PRESENTATION CLIENT...       ${NC}"
echo -e "${BLUE}====================================================${NC}"

streamlit run interface/app.py
