@echo off
title BestMDMTool - No Login
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%"

rem BestMDMTool needs a Python with Tkinter; the bundled runtime is used only for
rem the headless BROM runner. Try the Windows launcher first, then python.
set "GUI_PYTHON=py -3"
%GUI_PYTHON% -c "import tkinter" >nul 2>nul
if errorlevel 1 set "GUI_PYTHON=python"
%GUI_PYTHON% -c "import tkinter" >nul 2>nul
if errorlevel 1 (
  echo.
  echo Python with Tkinter is required to start BestMDMTool.
  echo Install Python 3.10 or newer from python.org with the tcl/tk option enabled.
  pause
  exit /b 1
)

echo Starting BestMDMTool - Authorized Device Service (no login)...
%GUI_PYTHON% -m bestmdmtool
if errorlevel 1 (
  echo.
  echo The application exited with an error.
  pause
)
