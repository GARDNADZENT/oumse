# BestMDMTool Windows installer

This directory contains a reproducible Inno Setup installer for
[BestMDMTool](../bestmdmtool/README.md), a separate, no-login, authorized-service
application. It is **not** a copy of the legacy compiled OumseGSM executable and
does not include MDM/FRP bypass, credential, or licensing-bypass logic.

> Use only on devices you own or are explicitly authorized to service.

## Outputs

| File | Produced by |
|---|---|
| `frozen/BestMDMTool/BestMDMTool.exe` | `build_exe.ps1` (PyInstaller standalone GUI) |
| `artifacts/BestMDMToolSetup-0.4.0.exe` | `build_installer.bat` on Windows / GitHub Actions |
| `artifacts/BestMDMTool-Portable-0.4.0.zip` | `build_portable.py` on any OS |

The real Windows installer is built with **Inno Setup 6**. This Linux sandbox does
not include `ISCC.exe`, so the `.exe` is produced by the Windows CI workflow or
by running the build script on a Windows machine.

## Build on Windows

From the repository root, in **PowerShell** or **cmd**:

```powershell
.\BUILD_BESTMDMTOOL_INSTALLER.bat
```

> In PowerShell you must prefix a file in the current folder with `.\`.
> Typing `installer-bestmdmtool\build_installer.bat` without `.\` makes
> PowerShell try to load it as a module and fail with
> "The module 'installer-bestmdmtool' could not be loaded".

You can also double-click `BUILD_BESTMDMTOOL_INSTALLER.bat` in Explorer.

The script:

- builds the standalone `frozen/BestMDMTool/BestMDMTool.exe` with PyInstaller
  (skipped automatically if Python with Tkinter is unavailable);
- finds `ISCC.exe` on `PATH` or in the usual install locations;
- if Inno Setup is missing, installs it automatically (winget, then a direct
  download from jrsoftware.org) — no manual setup needed;
- compiles `installer-bestmdmtool\BestMDMTool.iss`;
- writes `installer-bestmdmtool\artifacts\BestMDMToolSetup-0.4.0.exe`;
- writes `installer-bestmdmtool\artifacts\SHA256SUMS.txt`.

Equivalent direct invocation:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\installer-bestmdmtool\build_installer.ps1
```

End users need Python 3.10+ with Tkinter to run the GUI (the installer warns if
it is missing). Only the machine that *builds* the installer needs Inno Setup.

## Build in CI

`.github/workflows/build-bestmdmtool-installer.yml` runs on `windows-latest`,
installs Inno Setup with Chocolatey, builds the installer, verifies the SHA-256,
and uploads `installer-bestmdmtool/artifacts/*` as a workflow artifact. Trigger
it manually with `workflow_dispatch`, on version tags, or on pull requests to the
working branch.

## Build a portable ZIP

On any OS with Python 3.10+:

```bash
python installer-bestmdmtool/build_portable.py
```

This writes `installer-bestmdmtool/artifacts/BestMDMTool-Portable-0.4.0.zip` and
a matching `.sha256` file. It is a convenience artifact, not a substitute for a
signed Windows installer.

## What the installer contains

- `BestMDMTool/` — standalone `BestMDMTool.exe` (PyInstaller, bundled Python +
  Tkinter), so **end users do not need to install Python**
- `bestmdmtool/` — BestMDMTool GUI sources (used by the Python fallback launcher)
- `servicecore/` — shared session, patching, safety, and config code
- `runtime/bin/` — bundled headless Python 3.12 runtime for the BROM runner
- `runtime/lib/` — vendored `mtkclient` and the two BROM runners
- `Bin/`, `adb_assets/`, `certifi/` — flashing/ADB tools and CA bundle
- `launcher/` — hidden PowerShell/VBS launcher that finds Python with Tkinter
- `app_icon.ico`, `START_BEST_MDM_TOOL.bat`, `run_bestmdmtool.sh`
- documentation, requirements, GPLv3 license text, and version metadata

It also replaces the stale `runtime/bin/python312._pth` with a portable one that
adds `runtime/bin/Lib/site-packages` and `runtime/lib` to the runner's path.

## What the installer excludes

- `legacy/OumseGsmToolPro.exe` and all other legacy login binaries
- the original `app/` front-end (BestMDMTool is a separate product)
- `runtime/lib/logs/`, `hwparam.json`, and generated dumps/backups
- `tests/`, `.github/`, `.git/`, `__pycache__/`, and `*.pyc`
- Tcl/Tk and CustomTkinter assets from the old compiled GUI
- root-level DLLs used only by the legacy executable

## Start Menu / Desktop

The installer creates:

- Start Menu shortcut: **BestMDMTool**
- Start Menu README shortcut
- Start Menu uninstall shortcut
- optional Desktop shortcut (unchecked by default)
- optional “Launch BestMDMTool” checkbox after setup (unchecked by default)

Shortcuts run `wscript.exe` with `launcher\Launch-BestMDMTool.vbs`, which hides
the PowerShell window and calls `Start-BestMDMTool.ps1`. That script checks
`py -3`, `python`, and `python3` for Tkinter, prefers `pythonw.exe`, and starts
`python -m bestmdmtool` with no login screen.

## Requirements for end users

None beyond Windows 10/11 — the installer ships the standalone `BestMDMTool.exe`.

If the frozen executable is missing (a source-only build made with
`-SkipFrozenExe`), the installer falls back to the Python launch scripts and
warns during setup when Python 3.10+ with Tkinter is not installed. The bundled
`runtime/bin` Python is x86 and only drives the headless BROM runner; it has no
Tkinter, so it cannot host the GUI.

## Code signing

The build scripts intentionally do **not** sign the installer because no
certificate is available in this repository. Before public distribution, sign the
generated `.exe` with `signtool.exe` and publish the SHA-256 checksum. Update
`SECURITY.md` and the release notes accordingly.

## Versioning

Update `installer-bestmdmtool/version.txt` and the `#define MyAppVersion` value
in `BestMDMTool.iss` together. Keep the `AppId` GUID unchanged so upgrades
replace the same installation.
