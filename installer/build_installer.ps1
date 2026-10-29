#Requires -Version 5.1
<#
.SYNOPSIS
Builds the Windows installer for the no-login Oumse GSM Tool Pro community GUI.
#>

[CmdletBinding()]
param(
    [string]$OutputDir = (Join-Path $PSScriptRoot "artifacts")
)

$ErrorActionPreference = "Stop"

$version = (Get-Content -Path (Join-Path $PSScriptRoot "version.txt") -Raw).Trim()
$outputDir = [System.IO.Path]::GetFullPath($OutputDir)
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$iscc = $null
$command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
if ($command) {
    $iscc = $command.Source
} else {
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
    }
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            $iscc = $candidate
            break
        }
    }
}

if (-not $iscc) {
    throw "Inno Setup 6 (ISCC.exe) was not found. Install it from https://jrsoftware.org/isdl.php or run the build-installer GitHub Actions workflow."
}

$outputName = "OumseNoLoginSetup-$version"
Push-Location $PSScriptRoot
try {
    Write-Host "Using ISCC: $iscc"
    Write-Host "Output: $outputDir\$outputName.exe"
    & $iscc @("/O$outputDir", "/F$outputName", "OumseNoLogin.iss")
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

Write-Host ""
Write-Host "Installer built: $installer"
Write-Host "SHA256: $($hash.Hash)"
Write-Host "Checksums: $sumFile"
