# Start-OumseNoLogin.ps1
# Finds a Python interpreter with Tkinter and launches the no-login GUI without
# keeping a console window open.

$ErrorActionPreference = "Stop"

$launcherDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$appDir = Split-Path -Parent $launcherDir
$env:PYTHONPATH = $appDir

function Show-Error {
    param([string]$Message)
    try {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show(
            $Message,
            "Oumse GSM Tool Pro - No Login",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        ) | Out-Null
    } catch {
        Write-Host $Message
    }
}

function Get-PythonCandidate {
    $candidates = @(
        @{ Name = "py"; Args = @("-3") },
        @{ Name = "python"; Args = @() },
        @{ Name = "python3"; Args = @() }
    )

    foreach ($candidate in $candidates) {
        $command = Get-Command $candidate.Name -ErrorAction SilentlyContinue
        if ($null -eq $command) { continue }

        $checkArgs = @($candidate.Args) + @("-c", "import tkinter")
        & $command.Source @checkArgs | Out-Null
        if ($LASTEXITCODE -ne 0) { continue }

        $exeArgs = @($candidate.Args) + @("-c", "import sys; print(sys.executable)")
        $pythonExe = (& $command.Source @exeArgs | Select-Object -Last 1)
        if ($null -eq $pythonExe) { continue }
        $pythonExe = $pythonExe.Trim()
        if (-not (Test-Path $pythonExe)) { continue }

        $pythonDir = Split-Path -Parent $pythonExe
        $pythonw = Join-Path $pythonDir "pythonw.exe"
        if (Test-Path $pythonw) {
            return $pythonw
        }
        return $pythonExe
    }
    return $null
}

try {
    $guiPython = Get-PythonCandidate
    if (-not $guiPython) {
        throw "Python 3.10+ with Tkinter was not found. Install Python from python.org with the tcl/tk option enabled."
    }

    Start-Process -FilePath $guiPython -ArgumentList @("-m", "app") `
        -WorkingDirectory $appDir -WindowStyle Hidden | Out-Null
    exit 0
} catch {
    $logDir = Join-Path $env:LOCALAPPDATA "OumseNoLogin"
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $logFile = Join-Path $logDir "launcher.log"
    Add-Content -Path $logFile -Value ("[{0}] {1}" -f (Get-Date).ToString("s"), $_.Exception.Message)
    Show-Error $_.Exception.Message
    exit 1
}
