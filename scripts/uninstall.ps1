<#
.SYNOPSIS
    Removes the CoverCraft Start Menu app and its session/cache data for the
    current user.

.DESCRIPTION
    Deletes %LOCALAPPDATA%\Programs\CoverCraft, its Start Menu shortcut, and
    the Tidal session cache (%APPDATA%\CoverCraft - login token + cached
    cover art). Generated PDFs in Documents\CoverCraft are left alone by
    default, since those are output you made, not app state - pass
    -PurgeOutput to remove those too.

.PARAMETER PurgeOutput
    Also delete the default output folder (Documents\CoverCraft), including
    any generated PDFs in it. Irreversible.

.EXAMPLE
    scripts\uninstall.ps1

.EXAMPLE
    scripts\uninstall.ps1 -PurgeOutput
#>
param(
    [switch]$PurgeOutput
)

$ErrorActionPreference = "Stop"

$installDir = Join-Path $env:LOCALAPPDATA "Programs\CoverCraft"
$shortcutPath = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\CoverCraft.lnk"
$configDir = Join-Path $env:APPDATA "CoverCraft"

if (Test-Path $installDir) {
    Remove-Item -Recurse -Force $installDir
    Write-Host "Removed $installDir"
} else {
    Write-Host "Not installed: $installDir"
}

if (Test-Path $shortcutPath) {
    Remove-Item -Force $shortcutPath
    Write-Host "Removed $shortcutPath"
} else {
    Write-Host "No Start Menu shortcut found: $shortcutPath"
}

if (Test-Path $configDir) {
    Remove-Item -Recurse -Force $configDir
    Write-Host "Removed $configDir (Tidal session + cache)"
} else {
    Write-Host "No session/cache data found: $configDir"
}

if ($PurgeOutput) {
    $outputDir = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "CoverCraft"
    if (Test-Path $outputDir) {
        Remove-Item -Recurse -Force $outputDir
        Write-Host "Purged $outputDir (generated PDFs)"
    }
}

Write-Host "`nCoverCraft uninstalled."
