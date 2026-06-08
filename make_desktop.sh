#!/usr/bin/env bash
# ==============================================================================
# HY-TUTOR — Linux Desktop Icon Installer
# ------------------------------------------------------------------------------
# Reads hytutor.desktop.template (or the existing hytutor.desktop), patches
# the absolute paths to match THIS clone location, and installs to:
#   * ~/.local/share/applications/  (application menu)
#   * ~/Desktop/                    (desktop shortcut, if Desktop exists)
#
# Usage:
#   bash make_desktop.sh
#   bash make_desktop.sh --uninstall
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="$SCRIPT_DIR/hytutor.desktop"
APP_NAME="hytutor.desktop"
ICON_SRC="$SCRIPT_DIR/hytutor_main.png"
ICON_NAME="hytutor"

ACTION="install"
for arg in "$@"; do
    case "$arg" in
        --uninstall) ACTION="uninstall" ;;
        -h|--help)
            echo "Usage: bash make_desktop.sh [--uninstall]"
            exit 0
            ;;
    esac
done

if [ "$ACTION" = "uninstall" ]; then
    echo "[uninstall] Removing HY-TUTOR desktop entries..."
    rm -f "$HOME/.local/share/applications/$APP_NAME" 2>/dev/null || true
    rm -f "$HOME/Desktop/$APP_NAME" 2>/dev/null || true
    echo "[ok] Removed. Refresh your app menu / desktop to see changes."
    exit 0
fi

[ -f "$TEMPLATE" ] || { echo "[fatal] $TEMPLATE not found."; exit 1; }
[ -f "$ICON_SRC" ] || echo "[warn] $ICON_SRC not found — using generic icon."

# --- 1. Install icon to hicolor theme (so it works in app menus) --------------
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
mkdir -p "$ICON_DIR"
if [ -f "$ICON_SRC" ]; then
    cp "$ICON_SRC" "$ICON_DIR/$ICON_NAME.png"
    echo "[ok] Icon installed to $ICON_DIR/$ICON_NAME.png"
fi

# --- 2. Patch the .desktop file with absolute paths --------------------------
# We make a temp copy, swap in the actual paths, and write it to the right spots.
TMP_DESKTOP="$(mktemp)"
trap 'rm -f "$TMP_DESKTOP"' EXIT

# Replace the Exec/Path/Icon placeholders with the actual clone paths.
sed -e "s|@EXEC@|$SCRIPT_DIR/launch_engine.sh|g" \
    -e "s|@PATH@|$SCRIPT_DIR|g" \
    -e "s|@ICON@|$ICON_NAME|g" \
    "$TEMPLATE" > "$TMP_DESKTOP"
chmod +x "$TMP_DESKTOP"

# --- 3. Install to application menu -------------------------------------------
APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS_DIR"
cp "$TMP_DESKTOP" "$APPS_DIR/$APP_NAME"
echo "[ok] Installed app menu entry: $APPS_DIR/$APP_NAME"

# --- 4. Install to Desktop (if it exists) ------------------------------------
DESKTOP_DIR="$HOME/Desktop"
if [ -d "$DESKTOP_DIR" ]; then
    cp "$TMP_DESKTOP" "$DESKTOP_DIR/$APP_NAME"
    # On some desktops, the file needs to be marked executable AND trusted.
    chmod +x "$DESKTOP_DIR/$APP_NAME"
    # Mark as trusted (GNOME). If gio isn't available, this is a no-op.
    if command -v gio >/dev/null 2>&1; then
        gio set "$DESKTOP_DIR/$APP_NAME" "metadata::trusted" true 2>/dev/null || true
    fi
    echo "[ok] Installed desktop shortcut: $DESKTOP_DIR/$APP_NAME"
else
    echo "[info] No ~/Desktop folder detected — skipped desktop shortcut (menu entry is enough)."
fi

# --- 5. Refresh desktop / icon caches ----------------------------------------
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
fi

echo
echo "===================================================="
echo " ✅ HY-TUTOR desktop icon installed"
echo "===================================================="
echo "  Look for 'HY-TUTOR' in your app menu / on your desktop."
echo "  To uninstall: bash make_desktop.sh --uninstall"
