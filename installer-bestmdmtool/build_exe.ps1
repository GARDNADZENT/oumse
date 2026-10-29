#Requires -Version 5.1
<#
.SYNOPSIS
Builds the frozen Windows executables used by the BestMDMTool installer.

.DESCRIPTION
Produces two PyInstaller bundles in installer-bestmdmtool\frozen:

  BestMDMTool\BestMDMTool.exe            GUI (windowed, own Python + Tkinter)
  BestMDMToolRunner\BestMDMToolRunner.exe device runner (console, full stdlib)

The runner is frozen because the vendored runtime\bin interpreter ships without
any *.pyd C extensions, so it cannot import socket/ssl and therefore cannot run
mtkclient. Freezing gives a complete CPython plus pyusb, pyserial and libusb.

.PARAMETER PythonExe
Build interpreter (default: py -3 or python on PATH). Must be 3.11/3.12 x64.

.PARAMETER Skip
Skip both builds; the installer then falls back to the bundled runtime, which is
only usable when runtime\bin\*.pyd files are present.
#>

[CmdletBinding()]
param(
    [string]$PythonExe,
    [switch]$Skip
)

$ErrorActionPreference = "Stop"

if ($Skip) {
    Write-Host "Skipping frozen executable builds (-Skip)." -ForegroundColor Yellow
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
    Write-Warning "Python was not found; skipping the frozen builds."
    exit 0
}

& $python.Exe @($python.Args) @("-c", "import tkinter") | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Python without Tkinter was found; skipping the frozen builds."
    exit 0
}

Write-Host "Installing PyInstaller..."
& $python.Exe @($python.Args) @("-m", "pip", "install", "--quiet", "--disable-pip-version-check", "pyinstaller")
if ($LASTEXITCODE -ne 0) { throw "Could not install PyInstaller." }

$frozenDir = Join-Path $PSScriptRoot "frozen"
$workDir = Join-Path $PSScriptRoot "build\pyinstaller"
Remove-Item -Recurse -Force -Path $frozenDir, $workDir -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $frozenDir | Out-Null

$icon = Join-Path $root "app_icon.ico"
$libDir = Join-Path $root "runtime\lib"
$siteDir = Join-Path $root "runtime\bin\Lib\site-packages"

# ---------------------------------------------------------------- GUI bundle
Write-Host "Building BestMDMTool.exe (GUI)..."
& $python.Exe @($python.Args) @(
    "-m", "PyInstaller",
    "--noconfirm", "--clean", "--windowed", "--onedir",
    "--name", "BestMDMTool",
    "--icon", $icon,
    "--paths", $root,
    "--collect-submodules", "bestmdmtool",
    "--collect-submodules", "servicecore",
    "--distpath", $frozenDir,
    "--workpath", (Join-Path $workDir "gui"),
    "--specpath", (Join-Path $workDir "gui"),
    (Join-Path $PSScriptRoot "pyinstaller_entry.py")
)
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed for the GUI (exit $LASTEXITCODE)." }

# ------------------------------------------------------------- runner bundle
Write-Host "Building BestMDMToolRunner.exe (device backend)..."
& $python.Exe @($python.Args) @(
    "-m", "PyInstaller",
    "--noconfirm", "--clean", "--console", "--onedir",
    "--name", "BestMDMToolRunner",
    "--paths", $root,
    "--paths", $libDir,
    "--paths", $siteDir,
    "--collect-submodules", "mtkclient",
    "--collect-submodules", "servicecore",
    "--collect-all", "usb",
    "--collect-all", "serial",
    "--collect-all", "libusb",
    "--collect-all", "colorama",
    "--collect-all", "capstone",
    "--collect-all", "keystone",
    "--collect-all", "Cryptodome",
    "--distpath", $frozenDir,
    "--workpath", (Join-Path $workDir "runner"),
    "--specpath", (Join-Path $workDir "runner"),
    (Join-Path $PSScriptRoot "runner_entry.py")
)
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed for the runner (exit $LASTEXITCODE)." }

# mtkclient loads libusb by bare name, so it must sit next to the runner exe.
$runnerDir = Join-Path $frozenDir "BestMDMToolRunner"
$libusbSource = Join-Path $libDir "mtkclient\Windows"
foreach ($dll in @("libusb-1.0.dll", "libusb32-1.0.dll")) {
    $source = Join-Path $libusbSource $dll
    if (Test-Path $source) {
        Copy-Item -Path $source -Destination (Join-Path $runnerDir $dll) -Force
        Write-Host "Bundled $dll"
    } else {
        Write-Warning "libusb DLL not found: $source"
    }
}

foreach ($exe in @(
        (Join-Path $frozenDir "BestMDMTool\BestMDMTool.exe"),
        (Join-Path $frozenDir "BestMDMToolRunner\BestMDMToolRunner.exe")
    )) {
    if (-not (Test-Path $exe)) { throw "Expected frozen executable was not created: $exe" }
}

$sizeMiB = [math]::Round((Get-ChildItem -Recurse $frozenDir | Measure-Object Length -Sum).Sum / 1MB, 2)
Write-Host "Frozen bundles ready: $frozenDir ($sizeMiB MiB)" -ForegroundColor Green
