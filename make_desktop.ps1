<#
.SYNOPSIS
    HY-TUTOR Windows shortcut installer — creates a Desktop .lnk pointing
    at launch_engine.bat in the repo root.

.DESCRIPTION
    Usage:
        powershell -File .\make_desktop.ps1
        powershell -File .\make_desktop.ps1 -Uninstall
#>

[CmdletBinding()]
param(
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LauncherBat = Join-Path $ScriptDir "launch_engine.bat"
$IconPath = Join-Path $ScriptDir "hytutor_main.png"
$DesktopDir = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $DesktopDir "HY-TUTOR.lnk"
$StartMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\HY-TUTOR"
$StartMenuShortcut = Join-Path $StartMenuDir "HY-TUTOR.lnk"

function Remove-ShortcutIfExists($path) {
    if (Test-Path $path) {
        Remove-Item $path -Force
        Write-Host "[ok]   Removed $path"
    }
}

if ($Uninstall) {
    Write-Host "[uninstall] Removing HY-TUTOR shortcuts..."
    Remove-ShortcutIfExists $ShortcutPath
    if (Test-Path $StartMenuDir) {
        Remove-ShortcutIfExists $StartMenuShortcut
        Remove-Item $StartMenuDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host "[ok] Done."
    exit 0
}

if (-not (Test-Path $LauncherBat)) {
    Write-Host "[fatal] $LauncherBat not found. Run install.ps1 first." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $IconPath)) {
    Write-Host "[warn] hytutor_main.png not found — the shortcut will use a generic icon." -ForegroundColor Yellow
    $IconPath = $null
}

Write-Host "[install] Creating HY-TUTOR shortcuts..."

# Use WScript.Shell COM object to create a real .lnk shortcut.
$WshShell = New-Object -ComObject WScript.Shell

# Desktop shortcut
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $LauncherBat
$Shortcut.WorkingDirectory = $ScriptDir
$Shortcut.WindowStyle = 1  # 1 = Normal window
$Shortcut.Description = "HY-TUTOR Socratic Study Engine"
if ($null -ne $IconPath) {
    $Shortcut.IconLocation = "$IconPath,0"
}
$Shortcut.Save()
Write-Host "[ok]   Created desktop shortcut: $ShortcutPath"

# Start Menu shortcut
if (-not (Test-Path $StartMenuDir)) {
    New-Item -ItemType Directory -Path $StartMenuDir -Force | Out-Null
}
$StartShortcut = $WshShell.CreateShortcut($StartMenuShortcut)
$StartShortcut.TargetPath = $LauncherBat
$StartShortcut.WorkingDirectory = $ScriptDir
$StartShortcut.WindowStyle = 1
$StartShortcut.Description = "HY-TUTOR Socratic Study Engine"
if ($null -ne $IconPath) {
    $StartShortcut.IconLocation = "$IconPath,0"
}
$StartShortcut.Save()
Write-Host "[ok]   Created Start Menu shortcut: $StartMenuShortcut"

# Release the COM object
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($WshShell) | Out-Null
[System.GC]::Collect()

Write-Host ""
Write-Host "==== HY-TUTOR shortcut installed ====" -ForegroundColor Green
Write-Host "  Look for 'HY-TUTOR' on your Desktop and in the Start Menu."
Write-Host "  To uninstall: powershell -File .\make_desktop.ps1 -Uninstall"
