#Requires -Version 5.1
<#
.SYNOPSIS
Builds the Windows installer (.exe) for BestMDMTool.

.DESCRIPTION
Looks for Inno Setup 6 (ISCC.exe). If it is not installed, this script can
download and install it automatically, then compile the installer and print
its SHA-256 checksum.

.PARAMETER OutputDir
Folder that receives BestMDMToolSetup-<version>.exe (default: artifacts).

.PARAMETER SkipInnoSetupInstall
Fail instead of downloading Inno Setup when ISCC.exe is missing.

.EXAMPLE
.\installer-bestmdmtool\build_installer.ps1
#>

[CmdletBinding()]
param(
    [string]$OutputDir = (Join-Path $PSScriptRoot "artifacts"),
    [switch]$SkipInnoSetupInstall
)

$ErrorActionPreference = "Stop"

function Find-Iscc {
    $command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }

    $candidates = @()
    if ($env:ProgramFiles) {
        $candidates += (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    }
    $programFilesX86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
    if ($programFilesX86) {
        $candidates += (Join-Path $programFilesX86 "Inno Setup 6\ISCC.exe")
    }
    if ($env:LOCALAPPDATA) {
        $candidates += (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
        $candidates += (Join-Path $env:LOCALAPPDATA "Inno Setup 6\ISCC.exe")
    }
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { return $candidate }
    }
    return $null
}

function Install-InnoSetup {
    Write-Host "Inno Setup 6 not found - trying to install it automatically..." -ForegroundColor Yellow

    $winget = Get-Command "winget.exe" -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Host "Installing via winget (JRSoftware.InnoSetup)..."
        & $winget.Source install --id JRSoftware.InnoSetup -e `
            --accept-source-agreements --accept-package-agreements --silent --disable-interactivity
        $found = Find-Iscc
        if ($found) { return $found }
    }

    $tempSetup = Join-Path $env:TEMP "innosetup-setup.exe"
    $sources = @(
        "https://jrsoftware.org/download.php/is.exe",
        "https://files.jrsoftware.org/is/6/innosetup-6.4.3.exe"
    )
    foreach ($uri in $sources) {
        try {
            Write-Host "Downloading $uri"
            Invoke-WebRequest -Uri $uri -OutFile $tempSetup -UseBasicParsing -MaximumRedirection 10
            if ((Get-Item $tempSetup).Length -gt 1MB) { break }
        } catch {
            Write-Warning "Download failed: $($_.Exception.Message)"
        }
    }
    if (-not (Test-Path $tempSetup) -or (Get-Item $tempSetup).Length -lt 1MB) {
        throw "Could not download Inno Setup. Install it manually from https://jrsoftware.org/isdl.php and rerun this script."
    }

    Write-Host "Running the Inno Setup installer silently..."
    $process = Start-Process -FilePath $tempSetup `
        -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-" -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Inno Setup installer exited with code $($process.ExitCode)."
    }

    $found = Find-Iscc
    if (-not $found) {
        throw "Inno Setup installed but ISCC.exe was not found. Install it manually from https://jrsoftware.org/isdl.php."
    }
    return $found
}

$version = (Get-Content -Path (Join-Path $PSScriptRoot "version.txt") -Raw).Trim()
$outputDir = [System.IO.Path]::GetFullPath($OutputDir)
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$iscc = Find-Iscc
if (-not $iscc) {
    if ($SkipInnoSetupInstall) {
        throw "Inno Setup 6 (ISCC.exe) was not found. Install it from https://jrsoftware.org/isdl.php or rerun without -SkipInnoSetupInstall."
    }
    $iscc = Install-InnoSetup
}

$outputName = "BestMDMToolSetup-$version"
Push-Location $PSScriptRoot
try {
    Write-Host "Using ISCC: $iscc"
    Write-Host "Output: $outputDir\$outputName.exe"
    & $iscc @("/O$outputDir", "/F$outputName", "/Qp", "BestMDMTool.iss")
    if ($LASTEXITCODE -ne 0) {
        throw "ISCC.exe failed with exit code $LASTEXITCODE."
    }
} finally {
    Pop-Location
}

$installer = Join-Path $outputDir "$outputName.exe"
if (-not (Test-Path $installer)) {
    throw "Expected installer was not created: $installer"
}

$hash = Get-FileHash -Path $installer -Algorithm SHA256
$sumFile = Join-Path $outputDir "SHA256SUMS.txt"
"$($hash.Hash)  $(Split-Path $installer -Leaf)" | Set-Content -Path $sumFile -Encoding UTF8

$sizeMiB = [math]::Round((Get-Item $installer).Length / 1MB, 2)
Write-Host ""
Write-Host "Installer built: $installer" -ForegroundColor Green
Write-Host "Size: $sizeMiB MiB"
Write-Host "SHA256: $($hash.Hash)"
Write-Host "Checksums: $sumFile"
