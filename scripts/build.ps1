<#
.SYNOPSIS
    Builds CoverCraft.exe locally (same command the GitHub Actions release
    workflow runs), for testing packaging changes without pushing a tag.

.PARAMETER Install
    Also install the freshly built exe via scripts\install.ps1.

.EXAMPLE
    scripts\build.ps1 -Install
#>
param(
    [switch]$Install
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
