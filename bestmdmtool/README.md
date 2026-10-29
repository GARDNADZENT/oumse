# BestMDMTool

**BestMDMTool** is a separate, no-login desktop application for authorized
device servicing. It is inspired by the layout and workflow of the open-source
no-login community front-end, but it is its own product with its own branding,
installer, and documentation.

> Use only on devices you own or are explicitly authorized to service.

## What it is

- A directly opening Tkinter GUI with **no login screen**.
- Offline by default: no licensing server, heartbeat, telemetry, or account
  system.
- Built on the shared `servicecore/` package for session management, safe local
  patching, and partition safety checks.
- Uses the existing local BROM runner in `runtime/lib/` for device operations.
- Ships with its own Windows installer in `installer-bestmdmtool/`.

## What it is not

- It is **not** a copy of the legacy compiled OumseGSM executable.
- It does **not** include the legacy login/anti-analysis/licensing code.
- It does **not** include MDM/FRP bypass algorithms, server-side patch
  algorithms, or credential/licensing bypass logic.
- It is not affiliated with or endorsed by OumseGSM.

## Quick start

Requirements:

- Windows with Python 3.10+ and Tkinter.
- MediaTek USB / preloader VCOM / UsbDk drivers for device work.
- A powered-off device connected in BROM/preloader mode.

From the repository root:

```bat
START_BEST_MDM_TOOL.bat
```

Or:

```bat
py -3 -m bestmdmtool
```

For development on Linux/macOS (GUI only; hardware operations are Windows-only):

```bash
./run_bestmdmtool.sh
# or
BEST_MDM_TOOL_PYTHON=python3 python3 -m bestmdmtool
```

## Features

- Start/stop a persistent BROM runner session.
- Choose `brom` or `preloader` mode.
- Optional custom DA loader and auth file.
- Partition inventory from `OUMSE_READY`.
- Read, write, and erase partitions with explicit confirmation.
- Reboot the device.
- Safe local patching with validation, checksums, backups, and atomic writes.
- Partition-name validation and critical-partition guards.
- Live color-coded logs.

## Installer

A reproducible Inno Setup installer is in `installer-bestmdmtool/`.

On Windows:

```bat
installer-bestmdmtool\build_installer.bat
```

This produces:

```text
installer-bestmdmtool\artifacts\BestMDMToolSetup-0.1.0.exe
```

The `.exe` can also be built by
`.github/workflows/build-bestmdmtool-installer.yml` on a Windows runner.

A portable ZIP can be generated on any OS:

```bash
python installer-bestmdmtool/build_portable.py
```

See `installer-bestmdmtool/README.md` for details.

## Architecture

```text
bestmdmtool/       # BestMDMTool GUI and branding
servicecore/       # Shared session, patching, safety, and config code
runtime/lib/       # Vendored mtkclient and BROM runners
runtime/bin/       # Bundled headless Python runtime for the runner
Bin/, adb_assets/  # Third-party Windows flashing/ADB utilities
```

The original no-login app in `app/` also uses `servicecore/`, so fixes to the
core benefit both products.

## Legal and compliance

This tool can read, write, and erase device partitions. Use it only with proper
authorization. The vendored `mtkclient` is GPLv3; review
`runtime/lib/LICENSE` and all bundled third-party licenses before distributing
an installer. See the repository root `SECURITY.md` and `PROJECT_ANALYSIS.md`.
