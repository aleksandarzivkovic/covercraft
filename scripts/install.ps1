<#
.SYNOPSIS
    Installs (or updates) CoverCraft as a Start Menu app for the current user.

.DESCRIPTION
    Copies CoverCraft.exe into %LOCALAPPDATA%\Programs\CoverCraft and creates a
    Start Menu shortcut for it. No admin rights required.

.PARAMETER ExePath
    Path to a locally built CoverCraft.exe (e.g. dist\CoverCraft.exe from
    scripts\build.ps1). If omitted, downloads the latest GitHub Release asset
    instead (requires the GitHub CLI: winget install GitHub.cli, then gh auth login).

.PARAMETER Repo
    "owner/repo" to download the release from. Defaults to this checkout's
    "origin" remote.

.EXAMPLE
    scripts\install.ps1 -ExePath dist\CoverCraft.exe

.EXAMPLE
    scripts\install.ps1
    # downloads the latest release from GitHub via gh
#>
param(
    [string]$ExePath,
    [string]$Repo
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent

if (-not $ExePath) {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw "No -ExePath given and GitHub CLI (gh) isn't installed. Either run scripts\build.ps1 first, or install gh (winget install GitHub.cli; gh auth login)."
    }

    if (-not $Repo) {
        $originUrl = git -C $RepoRoot remote get-url origin 2>$null
        if ($originUrl -match 'github\.com[:/](?<repo>[^/]+/[^/.]+)') {
            $Repo = $Matches.repo -replace '\.git$', ''
        } else {
            throw "Couldn't infer the GitHub repo from 'git remote'. Pass -Repo owner/repo explicitly."
        }
    }

    $ExePath = Join-Path $env:TEMP "CoverCraft.exe"
    Write-Host "Downloading latest CoverCraft release from $Repo ..."
    gh release download --repo $Repo --pattern "CoverCraft.exe" --output $ExePath --clobber
}

if (-not (Test-Path $ExePath)) {
    throw "Exe not found at $ExePath"
}

$installDir = Join-Path $env:LOCALAPPDATA "Programs\CoverCraft"
New-Item -ItemType Directory -Force -Path $installDir | Out-Null

$destExe = Join-Path $installDir "CoverCraft.exe"
Copy-Item -Path $ExePath -Destination $destExe -Force
Write-Host "Installed to $destExe"

$startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$shortcutPath = Join-Path $startMenuDir "CoverCraft.lnk"
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $destExe
$shortcut.WorkingDirectory = $installDir
$shortcut.Description = "CoverCraft - Tidal album cover/tracklist PDF generator"
$shortcut.Save()
Write-Host "Start Menu shortcut created: $shortcutPath"

Write-Host "`nDone. Search for 'CoverCraft' in the Start Menu to launch it."
