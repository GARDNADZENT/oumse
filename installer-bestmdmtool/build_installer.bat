@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_installer.ps1" %*
if errorlevel 1 (
  echo.
  echo Installer build failed.
  pause
)
