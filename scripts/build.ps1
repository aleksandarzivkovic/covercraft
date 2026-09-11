<#
.SYNOPSIS
    Builds CoverCraft.exe locally (same command the GitHub Actions release
    workflow runs), for testing packaging changes without pushing a tag.

.PARAMETER Install
    Also install the freshly built exe directly via scripts\install.ps1
    (skips the installer wizard - handy for a fast dev loop).

.PARAMETER Installer
    Also build dist\CoverCraftSetup.exe via Inno Setup (requires ISCC.exe -
    winget install JRSoftware.InnoSetup). This is what actually gets
    released from GitHub; -Install is a shortcut around it for dev use.

.PARAMETER Version
    Version to stamp the installer with (only used with -Installer).
    Defaults to 0.0.0-dev.

.EXAMPLE
    scripts\build.ps1 -Install

.EXAMPLE
    scripts\build.ps1 -Installer -Version 1.2.0
#>
param(
    [switch]$Install,
    [switch]$Installer,
    [string]$Version = "0.0.0-dev"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
$Python = Join-Path $RepoRoot ".venv\Scripts\pyinstaller.exe"

if (-not (Test-Path $Python)) {
    throw "PyInstaller not found in .venv. Run: .venv\Scripts\python.exe -m pip install -r requirements-dev.txt"
}

Push-Location $RepoRoot
try {
    & $Python --onefile --noconsole --name CoverCraft --icon assets\icon.ico --add-data "assets\icon.ico;assets" gui.py
} finally {
    Pop-Location
}

Write-Host "Built: $RepoRoot\dist\CoverCraft.exe"

if ($Install) {
    & (Join-Path $PSScriptRoot "install.ps1") -ExePath (Join-Path $RepoRoot "dist\CoverCraft.exe")
}

if ($Installer) {
    $iscc = @(
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1

    if (-not $iscc) {
        throw "Inno Setup (ISCC.exe) not found. Install it: winget install JRSoftware.InnoSetup"
    }

    Push-Location $RepoRoot
    try {
        & $iscc installer\CoverCraft.iss "/DMyAppVersion=$Version"
    } finally {
        Pop-Location
    }

    Write-Host "Built: $RepoRoot\dist\CoverCraftSetup.exe"
}
