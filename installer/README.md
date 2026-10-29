# Windows installer — Oumse GSM Tool Pro (No Login)

This directory contains a reproducible installer for the new `app/` front-end.
The installer **does not include the old login executable**, device logs, device
identifiers, tests, or Git metadata.

## Outputs

| File | Produced by |
|---|---|
| `artifacts/OumseNoLoginSetup-1.0.0.exe` | `build_installer.bat` on Windows / GitHub Actions |
| `artifacts/OumseNoLogin-Portable-1.0.0.zip` | `build_portable.py` on any OS |

The real Windows installer is built with **Inno Setup 6**. This Linux sandbox does
not include `ISCC.exe`, so the `.exe` is produced by the Windows CI workflow or
by running the build script on a Windows machine.

## Build on Windows

1. Install [Inno Setup 6](https://jrsoftware.org/isdl.php).
2. Install Python 3.10+ with Tkinter (for end users of the GUI).
3. From the repository root, run:

```bat
installer\build_installer.bat
```

Or directly:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File installer\build_installer.ps1
```

The script:

- finds `ISCC.exe` on `PATH` or in the usual install locations;
- compiles `installer\OumseNoLogin.iss`;
- writes `installer\artifacts\OumseNoLoginSetup-1.0.0.exe`;
- writes `installer\artifacts\SHA256SUMS.txt`.

## Build in CI

`.github/workflows/build-installer.yml` runs on `windows-latest`, installs Inno
Setup with Chocolatey, builds the installer, verifies the SHA-256, and uploads
`installer/artifacts/*` as a workflow artifact. Trigger it manually with
`workflow_dispatch`, on version tags, or on pull requests to the working branch.

## Build a portable ZIP

On any OS with Python 3.10+:

```bash
python installer/build_portable.py
```

This writes `installer/artifacts/OumseNoLogin-Portable-1.0.0.zip` and a matching
`.sha256` file. It is a convenience artifact, not a substitute for the signed
Windows installer.

## What the installer contains

- `app/` — original no-login Tkinter GUI
- `servicecore/` — shared session, patching, safety, and config code
- `runtime/bin/` — bundled headless Python 3.12 runtime for the BROM runner
- `runtime/lib/` — vendored `mtkclient` and the two BROM runners
- `Bin/`, `adb_assets/`, `certifi/` — flashing/ADB tools and CA bundle
- `launcher/` — hidden PowerShell/VBS launcher that finds Python with Tkinter
- `app_icon.ico`, `START_NO_LOGIN.bat`, `run_gui.sh`
- documentation, requirements, GPLv3 license text, and version metadata

It also replaces the stale `runtime/bin/python312._pth` with a portable one that
adds `runtime/bin/Lib/site-packages` and `runtime/lib` to the runner's path.

## What the installer excludes

- `legacy/OumseGsmToolPro.exe` and all other legacy login binaries
- `runtime/lib/logs/`, `hwparam.json`, and generated dumps/backups
- `tests/`, `.github/`, `.git/`, `__pycache__/`, and `*.pyc`
- Tcl/Tk and CustomTkinter assets from the old compiled GUI
- root-level DLLs used only by the legacy executable

## Start Menu / Desktop

The installer creates:

- Start Menu shortcut: **Oumse GSM Tool Pro (No Login)**
- Start Menu README shortcut
- Start Menu uninstall shortcut
- optional Desktop shortcut (unchecked by default)
- optional “Launch” checkbox after setup (unchecked by default)

Shortcuts run `wscript.exe` with `launcher\Launch-OumseNoLogin.vbs`, which hides
the PowerShell window and calls `Start-OumseNoLogin.ps1`. That script checks
`py -3`, `python`, and `python3` for Tkinter, prefers `pythonw.exe`, and starts
`python -m app` with no login screen.

## Prerequisite warning

During installation, the Inno Setup script checks for Python with Tkinter. If it
is not found, installation still continues but a warning is shown. The GUI cannot
start until Python with Tkinter is installed. The bundled Python runtime is only
for the headless BROM runner.

## Code signing

The build scripts intentionally do **not** sign the installer because no
certificate is available in this repository. Before public distribution, sign the
generated `.exe` with `signtool.exe` and publish the SHA-256 checksum. Update
`SECURITY.md` and the release notes accordingly.

## Versioning

Update `installer/version.txt` and the `#define MyAppVersion` value in
`OumseNoLogin.iss` together. Keep the `AppId` GUID unchanged so upgrades replace
the same installation.
