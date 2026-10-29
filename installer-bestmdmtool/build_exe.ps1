#Requires -Version 5.1
<#
.SYNOPSIS
Builds the standalone BestMDMTool.exe (PyInstaller) used inside the installer.

.DESCRIPTION
Produces a folder-based bundle in installer-bestmdmtool\frozen\BestMDMTool that
contains BestMDMTool.exe plus its own Python/Tk runtime. The installer copies
that folder to {app}\BestMDMTool, so end users do not need Python installed.

.PARAMETER PythonExe
Python interpreter used for the build (default: py -3 or python on PATH).

.PARAMETER Skip
Do not build the frozen bundle; the installer then falls back to the
source-mode launcher that requires Python with Tkinter.
#>

[CmdletBinding()]
param(
    [string]$PythonExe,
    [switch]$Skip
)

$ErrorActionPreference = "Stop"

if ($Skip) {
    Write-Host "Skipping frozen executable build (-Skip)." -ForegroundColor Yellow
    exit 0
}

function Resolve-Python {
    if ($PythonExe) { return @{ Exe = $PythonExe; Args = @() } }
    foreach ($candidate in @(
            @{ Exe = "py"; Args = @("-3") },
            @{ Exe = "python"; Args = @() }
        )) {
        $command = Get-Command $candidate.Exe -ErrorAction SilentlyContinue
        if ($command) { return @{ Exe = $command.Source; Args = $candidate.Args } }
    }
    return $null
}

$root = Split-Path -Parent $PSScriptRoot
$python = Resolve-Python
if (-not $python) {
    Write-Warning "Python was not found; skipping the standalone BestMDMTool.exe build."
    exit 0
}

& $python.Exe @($python.Args) @("-c", "import tkinter") | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Python without Tkinter was found; skipping the standalone BestMDMTool.exe build."
    exit 0
}

Write-Host "Installing PyInstaller..."
& $python.Exe @($python.Args) @("-m", "pip", "install", "--quiet", "--disable-pip-version-check", "pyinstaller")
if ($LASTEXITCODE -ne 0) {
    throw "Could not install PyInstaller."
}

$frozenDir = Join-Path $PSScriptRoot "frozen"
$workDir = Join-Path $PSScriptRoot "build\pyinstaller"
Remove-Item -Recurse -Force -Path $frozenDir, $workDir -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $frozenDir | Out-Null

$icon = Join-Path $root "app_icon.ico"
$entry = Join-Path $PSScriptRoot "pyinstaller_entry.py"

Write-Host "Building BestMDMTool.exe with PyInstaller..."
& $python.Exe @($python.Args) @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--windowed",
    "--onedir",
    "--name", "BestMDMTool",
    "--icon", $icon,
    "--paths", $root,
    "--collect-submodules", "bestmdmtool",
    "--collect-submodules", "servicecore",
    "--distpath", $frozenDir,
    "--workpath", $workDir,
    "--specpath", $workDir,
    $entry
)
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

$exe = Join-Path $frozenDir "BestMDMTool\BestMDMTool.exe"
if (-not (Test-Path $exe)) {
    throw "Expected frozen executable was not created: $exe"
}

$sizeMiB = [math]::Round((Get-ChildItem -Recurse $frozenDir | Measure-Object Length -Sum).Sum / 1MB, 2)
Write-Host "Frozen bundle ready: $frozenDir ($sizeMiB MiB)" -ForegroundColor Green
