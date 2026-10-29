@echo off
rem Builds BestMDMToolSetup-<version>.exe
rem Run from PowerShell as:  .\BUILD_BESTMDMTOOL_INSTALLER.bat
rem Double-clicking this file also works.
title Build BestMDMTool Installer
setlocal
cd /d "%~dp0"

echo ============================================================
echo  BestMDMTool - building the Windows installer (.exe)
echo  Output: installer-bestmdmtool\artifacts\BestMDMToolSetup-*.exe
echo ============================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer-bestmdmtool\build_installer.ps1" %*
set "EXITCODE=%ERRORLEVEL%"

echo.
if "%EXITCODE%"=="0" (
  echo Done. The installer is in: %~dp0installer-bestmdmtool\artifacts
) else (
  echo Installer build failed with exit code %EXITCODE%.
  echo See the messages above for the reason.
)
echo.
pause
exit /b %EXITCODE%
