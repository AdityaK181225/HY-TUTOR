<#
.SYNOPSIS
    HY-TUTOR Windows installer (PowerShell 5.1+ compatible)

.DESCRIPTION
    One-shot bootstrap for a fresh clone on Windows:
      1. Verifies Python 3.10+ (via 'py' launcher or 'python')
      2. Creates .venv and installs requirements.txt
      3. Seeds config\.env from config\.env.example
      4. Prompts (optional, masked) for GEMINI_API_KEY
      5. Validates and writes the key

.PARAMETER ResetKey
    Re-prompt for GEMINI_API_KEY even if one is already set.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\install.ps1
    powershell -ExecutionPolicy Bypass -File .\install.ps1 -ResetKey
#>

[CmdletBinding()]
param(
    [switch]$ResetKey
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# --- Pretty output -------------------------------------------------------------
function Write-Section($msg)  { Write-Host ""; Write-Host "==== $msg ====" -ForegroundColor Cyan }
function Write-Ok($msg)       { Write-Host "[ok]    $msg" -ForegroundColor Green }
function Write-Warn($msg)     { Write-Host "[warn]  $msg" -ForegroundColor Yellow }
function Write-Fatal($msg)    { Write-Host "[fatal] $msg" -ForegroundColor Red }

# --- Pre-flight: must run from repo root --------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

if (-not (Test-Path "requirements.txt")) {
    Write-Fatal "requirements.txt not found. Run install.ps1 from the HY-TUTOR repo root."
    exit 1
}
if (-not (Test-Path "config\.env.example")) {
    Write-Fatal "config\.env.example not found. Repo layout looks broken."
    exit 1
}

Write-Section "HY-TUTOR INSTALLER (Windows)"
Write-Host "Repo root: $ScriptDir"

# --- 1. Python 3.10+ detection ------------------------------------------------
$python = $null
foreach ($cand in @("py", "python", "python3")) {
    $cmd = Get-Command $cand -ErrorAction SilentlyContinue
    if ($null -eq $cmd) { continue }
    try {
        $versionOutput = & $cand -3 -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>&1
        if ($LASTEXITCODE -ne 0) {
            $versionOutput = & $cand -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>&1
        }
        if ($LASTEXITCODE -ne 0) { continue }
        $version = $versionOutput.ToString().Trim()
        $parts = $version.Split('.')
        if ($parts.Length -ge 2 -and [int]$parts[0] -ge 3 -and [int]$parts[1] -ge 10) {
            $python = $cand
            Write-Ok "Found $cand ($version)"
            break
        }
    } catch {
        continue
    }
}
if ($null -eq $python) {
    Write-Fatal "Python 3.10+ not found. Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH' during install)."
    exit 1
}

# --- 2. Virtual environment ----------------------------------------------------
$VenvDir = Join-Path $ScriptDir ".venv"
if (-not (Test-Path $VenvDir)) {
    Write-Host "[install] Creating virtual environment at .venv..."
    & $python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { Write-Fatal "venv creation failed."; exit 1 }
    Write-Ok "Virtual environment created."
} else {
    Write-Ok "Virtual environment already exists at .venv."
}

# Activate venv
$Activate = Join-Path $VenvDir "Scripts\Activate.ps1"
. $Activate

# --- 3. Install requirements --------------------------------------------------
Write-Host "[install] Upgrading pip..."
python -m pip install --upgrade pip --quiet 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Warn "pip upgrade failed (non-fatal)." }

Write-Host "[install] Installing Python dependencies (this may take a minute)..."
python -m pip install -r requirements.txt --quiet 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Fatal "pip install failed. Check the error above (you may need Visual Studio Build Tools for chromadb on Windows)."
    exit 1
}
Write-Ok "Dependencies installed."

# --- 4. config\.env setup ------------------------------------------------------
$EnvFile = Join-Path $ScriptDir "config\.env"
$ExampleFile = Join-Path $ScriptDir "config\.env.example"

if (-not (Test-Path $EnvFile)) {
    Write-Host "[install] Seeding config\.env from config\.env.example..."
    Copy-Item $ExampleFile $EnvFile
    Write-Ok "Created config\.env."
} else {
    Write-Ok "config\.env already exists."
}

# --- 5. API key prompt (masked, optional) -------------------------------------
function Get-CurrentApiKey {
    if (-not (Test-Path $EnvFile)) { return "" }
    $line = Select-String -Path $EnvFile -Pattern '^GEMINI_API_KEY=' -ErrorAction SilentlyContinue
    if ($null -eq $line) { return "" }
    $value = ($line.Line -split '=', 2)[1].Trim()
    return $value
}

function Save-ApiKey($apiKey) {
    $content = Get-Content $EnvFile -ErrorAction SilentlyContinue
    $found = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^GEMINI_API_KEY=') {
            $newContent += "GEMINI_API_KEY=$apiKey"
            $found = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $found) {
        $newContent += "GEMINI_API_KEY=$apiKey"
    }
    $newContent | Set-Content -Path $EnvFile -Encoding UTF8
    # Lock the file down (read/write owner only)
    try { icacls $EnvFile /inheritance:r /grant:r "$env:USERNAME:(R,W)" | Out-Null } catch {}
}

$currentKey = Get-CurrentApiKey
if (-not $ResetKey -and $currentKey) {
    Write-Ok "GEMINI_API_KEY already set in config\.env (use -ResetKey to change)."
} else {
    Write-Host ""
    Write-Host "Gemini API key" -ForegroundColor White
    Write-Host "  HY-TUTOR uses Google Gemini for content generation and tutoring."
    Write-Host "  Get a free key at: https://aistudio.google.com/app/apikey" -ForegroundColor Cyan
    Write-Host "  You can skip this step and enter the key later from the in-app wizard."
    Write-Host ""

    $secureKey = Read-Host "Paste GEMINI_API_KEY (or press Enter to skip)" -AsSecureString
    $plainKey = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    )

    if ([string]::IsNullOrWhiteSpace($plainKey)) {
        Write-Warn "Skipped. The in-app wizard will ask for the key on first launch."
    } elseif ($plainKey -notmatch '^AIza[A-Za-z0-9_-]{30,50}$') {
        Write-Warn "That doesn't look like a valid Gemini key (expected to start with 'AIza'). Skipping."
        Write-Warn "You can re-run 'powershell -File .\install.ps1 -ResetKey' or use the in-app wizard."
    } else {
        Save-ApiKey $plainKey
        Write-Ok "GEMINI_API_KEY saved to config\.env."
    }
}

# --- 6. Done ------------------------------------------------------------------
Write-Section "INSTALLATION COMPLETE"
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host "    powershell -File .\make_desktop.ps1   # install the HY-TUTOR icon" -ForegroundColor White
Write-Host "    .\launch_engine.bat                    # start the Streamlit UI in your browser" -ForegroundColor White
Write-Host ""
Write-Ok "Streamlit will serve on http://localhost:8501 by default."
