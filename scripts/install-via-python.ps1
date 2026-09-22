<#
.SYNOPSIS
    Installs CoverCraft as a Start Menu app that launches via the Python
    interpreter instead of the compiled CoverCraft.exe.

.DESCRIPTION
    Windows Smart App Control blocks unsigned/unrecognized exe's outright,
    with no per-file override - unlike classic SmartScreen, there's no
    "Run anyway" once it's enforced, and it can't be turned off short of
    resetting/reinstalling Windows. It only evaluates the executable image
    actually being launched though, so running CoverCraft through
    pythonw.exe (already installed and trusted) instead of our own unsigned
    CoverCraft.exe sidesteps it entirely - no Windows settings touched.

    Requires this repo's venv to already exist (.venv\Scripts\pythonw.exe).
    Set one up first if needed:
        python -m venv .venv
        .venv\Scripts\python.exe -m pip install -r requirements.txt

.EXAMPLE
    scripts\install-via-python.ps1
#>
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
$PythonW = Join-Path $RepoRoot ".venv\Scripts\pythonw.exe"
$GuiScript = Join-Path $RepoRoot "gui.py"
$IconPath = Join-Path $RepoRoot "assets\icon.ico"

if (-not (Test-Path $PythonW)) {
    throw "venv not found at $PythonW`nSet it up first:`n  python -m venv .venv`n  .venv\Scripts\python.exe -m pip install -r requirements.txt"
}
if (-not (Test-Path $GuiScript)) {
    throw "gui.py not found at $GuiScript"
}

$shortcutPath = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\CoverCraft.lnk"
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $PythonW
$shortcut.Arguments = "`"$GuiScript`""
$shortcut.WorkingDirectory = $RepoRoot
if (Test-Path $IconPath) {
    $shortcut.IconLocation = $IconPath
}
$shortcut.Description = "CoverCraft (runs via Python - not affected by Smart App Control)"
$shortcut.Save()

Write-Host "Start Menu shortcut created: $shortcutPath"
Write-Host "It launches: $PythonW `"$GuiScript`""
Write-Host "`nSearch for 'CoverCraft' in the Start Menu to launch it."
