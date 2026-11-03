#Requires -Version 5.1
<#
.SYNOPSIS
Builds the frozen Windows executables used by the BestMDMTool installer.

.DESCRIPTION
Produces two PyInstaller bundles in installer-bestmdmtool\frozen:

  BestMDMTool\BestMDMTool.exe            GUI (windowed, own Python + Tkinter)
  BestMDMToolRunner\BestMDMToolRunner.exe device runner (console, full stdlib)

The runner is frozen because the vendored runtime\bin interpreter ships without
all of its C extensions. It contains the first-party SPD protocol engine and the
USB libraries only; the MediaTek DA backend is intentionally not bundled.

.PARAMETER PythonExe
Build interpreter (default: py -3 or python on PATH). Must be 3.11/3.12 x64.

.PARAMETER Skip
Skip both builds; the installer falls back to the source launcher, which needs
an installed Python with Tkinter.
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

Write-Host "Installing build dependencies..."
# Install only the packages used by the GUI USB scan and SPD runner.
$runtimeDeps = @(
    "pyinstaller",
    "pyusb",
    "pyserial",
    "colorama"
)
& $python.Exe @($python.Args) @("-m", "pip", "install", "--quiet", "--disable-pip-version-check") @runtimeDeps
if ($LASTEXITCODE -ne 0) { throw "Could not install the build dependencies." }

& $python.Exe @($python.Args) @("-c", "import usb.core, serial, colorama; print('build deps ok')") | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Build dependencies are incomplete (pyusb/pyserial/colorama)." }

$frozenDir = Join-Path $PSScriptRoot "frozen"
$workDir = Join-Path $PSScriptRoot "build\pyinstaller"
Remove-Item -Recurse -Force -Path $frozenDir, $workDir -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $frozenDir | Out-Null

$icon = Join-Path $root "app_icon.ico"
$libDir = Join-Path $root "runtime\lib"

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
    # The GUI scans USB itself, so it needs the same device libraries as the
    # runner. Without these every scan silently reported "no device".
    "--collect-all", "usb",
    "--collect-all", "serial",
    "--collect-all", "libusb",
    "--collect-all", "colorama",
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
    "--collect-submodules", "servicecore",
    "--collect-all", "usb",
    "--collect-all", "serial",
    "--collect-all", "libusb",
    "--collect-all", "colorama",
    "--distpath", $frozenDir,
    "--workpath", (Join-Path $workDir "runner"),
    "--specpath", (Join-Path $workDir "runner"),
    (Join-Path $PSScriptRoot "runner_entry.py")
)
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed for the runner (exit $LASTEXITCODE)." }

# The GUI and the SPD engine need the USB transports and libusb beside each exe.
$libusbSource = Join-Path $libDir "mtkclient\Windows"
foreach ($target in @(
        (Join-Path $frozenDir "BestMDMToolRunner"),
        (Join-Path $frozenDir "BestMDMTool")
    )) {
    foreach ($dll in @("libusb-1.0.dll", "libusb32-1.0.dll")) {
        $source = Join-Path $libusbSource $dll
        if (Test-Path $source) {
            Copy-Item -Path $source -Destination (Join-Path $target $dll) -Force
            Write-Host "Bundled $dll -> $(Split-Path -Leaf $target)"
        } else {
            Write-Warning "libusb DLL not found: $source"
        }
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
