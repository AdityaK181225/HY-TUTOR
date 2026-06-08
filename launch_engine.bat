@echo off
REM ==============================================================================
REM HY-TUTOR: Windows Launcher (launch_engine.bat)
REM
REM Activates the .venv, exports GEMINI_API_KEY from config\.env, and starts
REM the Streamlit interface. Mirrors launch_engine.sh for Linux.
REM
REM Usage:  launch_engine.bat
REM ==============================================================================

setlocal EnableDelayedExpansion

REM --- Move to repo root (where this .bat lives) --------------------------------
cd /d "%~dp0"

echo.
echo ====================================================
echo         HY-TUTOR INTEGRATED STARTUP ENGINE
echo ====================================================
echo.

REM --- 1. Activate virtual environment ----------------------------------------
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
    echo [ok] Activated .venv
) else (
    echo [fatal] .venv not found. Run install.ps1 first.
    pause
    exit /b 1
)

REM --- 2. Load GEMINI_API_KEY from config\.env --------------------------------
set "ENV_FILE=config\.env"
if not exist "%ENV_FILE%" (
    echo [fatal] %ENV_FILE% not found. Run install.ps1 to set it up.
    pause
    exit /b 1
)

REM Parse the GEMINI_API_KEY line (ignore comments and blank lines)
set "GEMINI_API_KEY="
for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
    if /i "%%A"=="GEMINI_API_KEY" set "GEMINI_API_KEY=%%B"
)

if "!GEMINI_API_KEY!"=="" (
    echo [fatal] GEMINI_API_KEY is empty in %ENV_FILE%. Run install.ps1 -ResetKey to set it.
    pause
    exit /b 1
)
echo [ok] Loaded GEMINI_API_KEY from %ENV_FILE%

REM --- 3. Launch Streamlit -----------------------------------------------------
echo.
echo ====================================================
echo  Launching HY-TUTOR presentation client...
echo ====================================================
echo.

streamlit run interface\app.py

REM Keep the window open on error so the user can read the trace
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [fatal] Streamlit exited with code %ERRORLEVEL%.
    pause
)

endlocal
