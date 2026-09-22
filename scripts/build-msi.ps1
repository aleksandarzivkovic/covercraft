<#
.SYNOPSIS
    Builds CoverCraftSetup.msi: assembles the portable Python+app bundle,
    then packages it with WiX. This is what the GitHub Actions release
    workflow runs too.

.DESCRIPTION
    Requires the WiX Toolset v7 CLI (dotnet tool install --global wix) and
    its Util extension. Both are set up automatically if missing.

.PARAMETER Version
    Version to stamp the MSI with. Defaults to 0.0.0 (see CoverCraft.wxs).

.PARAMETER PythonRoot
    Passed through to scripts\build-portable.ps1 - see there for defaults.

.EXAMPLE
    scripts\build-msi.ps1 -Version 1.3.0
#>
param(
    [string]$Version,
    [string]$PythonRoot
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
$InstallerDir = Join-Path $RepoRoot "installer"

if (-not (Get-Command wix -ErrorAction SilentlyContinue)) {
    throw "WiX Toolset CLI not found. Install it: dotnet tool install --global wix"
}

# Assemble the portable Python + app bundle (dist\portable\)
$buildPortableArgs = @{}
if ($PythonRoot) { $buildPortableArgs["PythonRoot"] = $PythonRoot }
& (Join-Path $PSScriptRoot "build-portable.ps1") @buildPortableArgs

# WiX's Util extension (for RemoveFolderEx) is cached per-directory
Push-Location $InstallerDir
try {
    wix extension add WixToolset.Util.wixext | Out-Null

    $wixArgs = @(
        "build", "CoverCraft.wxs",
        "-arch", "x64",
        "-ext", "WixToolset.Util.wixext",
        "-o", "..\dist\CoverCraftSetup.msi"
    )
    if ($Version) { $wixArgs += @("-d", "Version=$Version") }

    wix @wixArgs
    if ($LASTEXITCODE -ne 0) { throw "wix build failed (exit $LASTEXITCODE)" }
} finally {
    Pop-Location
}

Write-Host "`nBuilt: $RepoRoot\dist\CoverCraftSetup.msi"
