@echo off
setlocal EnableDelayedExpansion
==============================================================================
# HY-TUTOR — Smart One-Click Start (Windows)
# ------------------------------------------------------------------------------
# This script handles EVERYTHING on first run:
#   1. Checks for Python 3.10+ (offers to install if missing)
#   2. Creates virtual environment
#   3. Installs all dependencies
#   4. Seeds config\.env and prompts for API key
#   5. Creates a Desktop shortcut with HY-TUTOR icon
#   6. Launches the app and opens your browser
#
# After first run, use the desktop shortcut to launch directly.
#
# Usage:
#   Double-click start.bat
==============================================================================

cd /d "%~dp0"

echo.
echo ====================================================
echo       HY-TUTOR — SMART START
echo ====================================================
echo.

REM === STEP 1: Python 3.10+ Detection ===
echo [hy-tutor] Checking for Python 3.10+...

set "PYTHON_BIN="

REM Try common Python executables
for %%P in (python3.12 python3.11 python3.10 python) do (
    where %%P >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        for /f "delims=" %%V in ('%%P -c "import sys; print(f\"{sys.version_info.major}.{sys.version_info.minor}\")" 2^>nul') do (
            set "PY_VER=%%V"
            for /f "tokens=1 delims=." %%A in ("%%V") do set "PY_MAJOR=%%A"
            for /f "tokens=2 delims=." %%A in ("%%V") do set "PY_MINOR=%%A"
            if !PY_MAJOR! GEQ 3 if !PY_MINOR! GEQ 10 (
                set "PYTHON_BIN=%%P"
                echo [ok] Found %%P (!PY_VER!)
                goto :python_found
            )
        )
    )
)

REM Python not found — try to install via winget
echo [warn] Python 3.10+ not found. Attempting automatic installation...
where winget >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    echo [hy-tutor] Installing Python via winget...
    winget install Python.Python.3.11 --silent --accept-source-agreements --accept-package-agreements
    REM Refresh PATH
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
    set "PYTHON_BIN=python"
    echo [ok] Python installed via winget.
    goto :python_found
)

REM Try downloading Python installer
echo [warn] winget not available. Downloading Python installer...
echo [hy-tutor] Please install Python 3.10+ from: https://www.python.org/downloads/
echo.
echo After installing Python, run this script again.
pause
exit /b 1

:python_found

REM === STEP 2: Virtual Environment ===
if not exist ".venv" (
    echo [hy-tutor] Creating virtual environment...
    %PYTHON_BIN% -m venv .venv
    echo [ok] Virtual environment created.
) else (
    echo [ok] Virtual environment already exists.
)

REM Activate venv
call ".venv\Scripts\activate.bat"

echo [hy-tutor] Upgrading pip...
python -m pip install --upgrade pip --quiet 2>nul

REM === STEP 3: Install Dependencies ===
python -c "import streamlit" 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo [hy-tutor] Installing Python dependencies (this may take a minute)...
    python -m pip install -r requirements.txt --quiet
    echo [ok] Dependencies installed.
) else (
    echo [ok] Dependencies already installed.
)

REM === STEP 4: API Key Setup ===
if not exist "config\.env" (
    if exist "config\.env.example" (
        copy "config\.env.example" "config\.env" >nul
        echo [ok] Created config\.env from template.
    ) else (
        echo GEMINI_API_KEY= > "config\.env"
        echo [ok] Created empty config\.env.
    )
)

REM Check if API key is set
set "GEMINI_API_KEY="
for /f "usebackq tokens=1,* delims==" %%A in ("config\.env") do (
    if /i "%%A"=="GEMINI_API_KEY" set "GEMINI_API_KEY=%%B"
)

if "!GEMINI_API_KEY!"=="" (
    echo.
    echo ====================================================
    echo   Gemini API Key Setup
    echo ====================================================
    echo   HY-TUTOR uses Google Gemini for AI tutoring.
    echo   Get a free key at: https://aistudio.google.com/app/apikey
    echo.
    echo   You can also skip this and enter the key in-app.
    echo.
    set /p "INPUT_KEY=  Paste your GEMINI_API_KEY (or press Enter to skip): "
    if not "!INPUT_KEY!"=="" (
        REM Simple validation: check if it starts with AIza
        set "VALID_KEY=0"
        echo !INPUT_KEY! | findstr /b "AIza" >nul 2>&1 && set "VALID_KEY=1"
        if !VALID_KEY! EQU 1 (
            REM Replace or append the key
            findstr /v "GEMINI_API_KEY=" "config\.env" > "config\.env.tmp" 2>nul
            echo GEMINI_API_KEY=!INPUT_KEY! >> "config\.env.tmp"
            move /y "config\.env.tmp" "config\.env" >nul
            echo [ok] API key saved.
        ) else (
            echo [warn] Invalid key format. You can set it later via the in-app wizard.
        )
    ) else (
        echo [warn] Skipped. The in-app wizard will ask for the key on first launch.
    )
) else (
    echo [ok] API key already configured.
)

REM === STEP 5: Create Desktop Shortcut (first run only) ===
if exist "make_desktop.ps1" (
    if not exist "%USERPROFILE%\Desktop\HY-TUTOR.lnk" (
        echo [hy-tutor] Creating desktop shortcut...
        powershell -ExecutionPolicy Bypass -File "make_desktop.ps1"
        echo [ok] Desktop shortcut created.
    )
)

REM === STEP 6: Launch HY-TUTOR ===
echo.
echo ====================================================
echo   Launching HY-TUTOR...
echo ====================================================
echo.
echo   Your browser will open automatically.
echo   If not, visit: http://localhost:8501
echo   Press Ctrl+C to stop the server.
echo.

REM Open browser after 3 seconds (background)
start "" /b cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8501"

REM Launch Streamlit
streamlit run interface\app.py

REM Keep window open on error
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [fatal] Streamlit exited with code %ERRORLEVEL%.
    pause
)

endlocal