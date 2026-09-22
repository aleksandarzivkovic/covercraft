<#
.SYNOPSIS
    Assembles a fully self-contained, portable CoverCraft bundle (interpreter
    + trimmed stdlib + Tcl/Tk + runtime dependencies + app source) with no
    dependency on Python being installed on the target machine.

.DESCRIPTION
    Ships CoverCraft as its own private copy of Python rather than a
    PyInstaller-compiled exe, launched via pythonw.exe. Two reasons:
      1. Windows 11 Smart App Control blocks unsigned/unrecognized exe's
         outright with no override. The official python.exe/pythonw.exe are
         signed by the Python Software Foundation and already trusted, so
         launching through them sidesteps the block entirely.
      2. It means the installer can place a real, complete app under
         Program Files without requiring Python to already be installed.

    Assembled from an existing full (non-embeddable) Python install, which
    is where the DLLs/, tcl/ (Tcl/Tk runtime) and Lib/ (stdlib) all come
    from - the official "embeddable package" distribution deliberately
    excludes Tkinter, so it can't be used here.

.PARAMETER PythonRoot
    Source Python install to copy from (must have Lib\, DLLs\, tcl\,
    python.exe/pythonw.exe - i.e. a full install, not the embeddable zip).
    Defaults to $env:pythonLocation (set by actions/setup-python in CI), or
    this repo's venv's recorded base install for local builds.

.EXAMPLE
    scripts\build-portable.ps1
#>
param(
    [string]$PythonRoot
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
$StageDir = Join-Path $RepoRoot "dist\portable"
$PyStage = Join-Path $StageDir "python"
$AppStage = Join-Path $StageDir "app"

if (-not $PythonRoot) {
    if ($env:pythonLocation) {
        $PythonRoot = $env:pythonLocation
    } else {
        $cfg = Get-Content (Join-Path $RepoRoot ".venv\pyvenv.cfg") -Raw
        if ($cfg -match "home = (?<home>.+)") {
            $PythonRoot = $Matches.home.Trim()
        } else {
            throw "Could not determine a source Python install. Pass -PythonRoot explicitly, or create .venv first."
        }
    }
}
if (-not (Test-Path (Join-Path $PythonRoot "python.exe"))) {
    throw "No python.exe found at '$PythonRoot'"
}
if (-not (Test-Path (Join-Path $PythonRoot "tcl"))) {
    throw "'$PythonRoot' has no tcl\ folder - it looks like an embeddable install, which lacks Tkinter. Point -PythonRoot at a full Python install instead."
}
Write-Host "Source Python: $PythonRoot"

Remove-Item -Recurse -Force $StageDir -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $PyStage, $AppStage | Out-Null

# --- Interpreter + runtime DLLs ---
foreach ($f in @("python.exe", "pythonw.exe", "python3.dll", "python313.dll", "vcruntime140.dll", "vcruntime140_1.dll", "LICENSE.txt")) {
    $src = Join-Path $PythonRoot $f
    if (Test-Path $src) { Copy-Item $src $PyStage }
}

# --- C extension modules (includes _tkinter.pyd + tcl86t.dll/tk86t.dll) ---
Copy-Item (Join-Path $PythonRoot "DLLs") (Join-Path $PyStage "DLLs") -Recurse

# --- Tcl/Tk script library ---
Copy-Item (Join-Path $PythonRoot "tcl") (Join-Path $PyStage "tcl") -Recurse

# --- Trimmed standard library (drop test suite, docs tooling, base
#     install's own global site-packages - we install our own clean one) ---
$LibSrc = Join-Path $PythonRoot "Lib"
$LibDst = Join-Path $PyStage "Lib"
robocopy $LibSrc $LibDst /E `
    /XD "$LibSrc\test" "$LibSrc\idlelib" "$LibSrc\turtledemo" "$LibSrc\ensurepip" "$LibSrc\venv" "$LibSrc\pydoc_data" "$LibSrc\site-packages" "__pycache__" `
    /XF "*.pyc" `
    /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy failed copying stdlib (exit $LASTEXITCODE)" }

# --- Runtime dependencies only (fresh install; no pip/setuptools/pyinstaller) ---
# pip writes routine notices to stderr, which PowerShell wraps as a
# terminating NativeCommandError under $ErrorActionPreference = "Stop" even
# on success - switch to checking $LASTEXITCODE instead for this call.
$SitePackages = Join-Path $LibDst "site-packages"
New-Item -ItemType Directory -Force -Path $SitePackages | Out-Null
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& (Join-Path $PythonRoot "python.exe") -m pip install --target $SitePackages --no-compile -r (Join-Path $RepoRoot "requirements.txt")
$pipExitCode = $LASTEXITCODE
$ErrorActionPreference = $prevEap
if ($pipExitCode -ne 0) { throw "pip install failed (exit $pipExitCode)" }

# --- App source ---
Copy-Item (Join-Path $RepoRoot "gui.py") $AppStage
Copy-Item (Join-Path $RepoRoot "make_cover.py") $AppStage
Copy-Item (Join-Path $RepoRoot "assets") (Join-Path $AppStage "assets") -Recurse

$sizeMB = (Get-ChildItem $StageDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
Write-Host "`nPortable bundle assembled at $StageDir"
Write-Host ("Size: {0:N1} MB" -f $sizeMB)
