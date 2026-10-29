# Oumse GSM Tool Pro / BestMDMTool — No-Login Community Front-Ends

This repository now contains **two directly opening, no-login front-ends** for the existing
MediaTek BROM runner:

- `app/` — Oumse GSM Tool Pro community edition.
- `bestmdmtool/` — **BestMDMTool**, a separate authorized-service product.

Both share `servicecore/` for session management, safe patching, safety checks, and path
configuration. Neither front-end has a login screen, licensing server, heartbeat, or telemetry.
The original compiled Windows client has been moved to `legacy/` and is no longer the default
entry point.

> Use `START_NO_LOGIN.bat` for the community app, or `START_BEST_MDM_TOOL.bat` for BestMDMTool.
> Both open the GUI immediately.

## What changed

- Added `app/`, a standard-library Python/Tkinter GUI that starts without authentication.
- Added `bestmdmtool/`, a separate no-login product with its own branding and compliance copy.
- Added `servicecore/`, shared session, patching, safety, and config code used by both apps.
- Added `app/session.py`, a structured client for `runtime/lib/oumse_brom_session_runner.py`.
- Added `app/patching.py`, a safe local patch engine with validation, checksums, backups, and
  atomic writes.
- Added `app/safety.py`, partition-name validation and critical-partition guards.
- Added `tests/`, `pyproject.toml`, `requirements-dev.txt`, and GitHub Actions CI.
- Added two Windows installer projects: `installer/` and `installer-bestmdmtool/`.
- Removed committed runtime logs, device identifiers, duplicate/wrapper executables, and Inno
  Setup uninstaller artifacts.
- Hardened `.gitignore` against logs, secrets, device dumps, and accidental Windows copies.
- Added `SECURITY.md` and an updated audit in `PROJECT_ANALYSIS.md`.

## Quick start (Windows)

1. Install **Python 3.10+ with Tkinter** (the official python.org installer includes it). The
   bundled `runtime\bin\python.exe` is used only for the headless BROM runner.
2. Install the normal MediaTek USB / preloader VCOM / UsbDk drivers for your device.
3. Power off the phone and connect it in BROM or preloader mode as required by the chipset.
4. Double-click one of the launchers:
   - **`START_NO_LOGIN.bat`** — Oumse community front-end.
   - **`START_BEST_MDM_TOOL.bat`** — BestMDMTool.

Or from a command prompt:

```bat
cd /d path\to\oumse
py -3 -m app
rem or: python -m app

rem BestMDMTool:
py -3 -m bestmdmtool
rem or: python -m bestmdmtool
```

For development on Linux/macOS (GUI only; hardware operations remain Windows-only):

```bash
./run_gui.sh
# or
OUMSE_GUI_PYTHON=python3 python3 -m app

./run_bestmdmtool.sh
# or
BEST_MDM_TOOL_PYTHON=python3 python3 -m bestmdmtool
```

On minimal Linux installs, install the OS package that provides Tkinter (for example
`python3-tk` on Debian/Ubuntu).

## Features

Both GUIs provide the same core feature set. BestMDMTool uses its own branding and an
authorized-use notice.

### Session tab

- Start/stop the persistent BROM runner.
- Choose `brom` or `preloader` mode.
- Optionally select a custom DA loader and auth file.
- Optional verbose runner debugging.
- Shows the resolved Python, runner, and runtime paths.

### Partitions tab

- Automatically loads the partition table from the runner's `OUMSE_READY` message.
- Read a selected partition to a local file.
- Write a local file to a selected partition.
- Erase one or more selected partitions.
- Reboot the device.
- Critical partitions are highlighted and blocked from erase.
- Destructive actions require typed confirmation.

### Patch file tab

- Select an input binary, a patches JSON file, and an output path.
- Validate the patch plan before writing anything.
- Apply patches locally with:
  - strict integer/offset/range validation;
  - no negative-index wraparound;
  - SHA-256 before/after;
  - backup of an existing output file;
  - atomic output replacement.
- Write the patched file to a selected partition through the active BROM session.

Patch JSON format:

```json
{
  "single_offsets": [
    { "offset": 16, "value": 255 }
  ],
  "fill_offsets": [
    { "start": 32, "end": 63, "value": 0 }
  ]
}
```

`offset`, `start`, `end`, and `value` accept integers or numeric strings; `0x` strings are also
accepted. `value` must be between 0 and 255. `end` is inclusive.

### Logs tab

- Live, color-coded runner output.
- Clear and auto-scroll controls.
- Log buffer is capped to avoid unbounded memory growth.

## No-login guarantee

`tests/test_no_login.py` and `tests/test_bestmdmtool.py` fail if login, licensing, heartbeat,
server, or network code is introduced into `app/`, `servicecore/`, or `bestmdmtool/`. The GUIs
call only local subprocesses and local files. They do not import `requests`, `urllib`, `socket`,
or any licensing client.

The legacy executable in `legacy/` still contains the old login workflow. It is retained for
reference only and should not be distributed as the primary application. See
`legacy/README.md` and `SECURITY.md`.

## Repository layout

```text
app/                       # Original no-login community GUI
bestmdmtool/               # Separate BestMDMTool no-login GUI
servicecore/               # Shared session, patching, safety, and config code
tests/                     # Unit tests for patching, protocol, safety, no-login guarantee
runtime/lib/               # Vendored mtkclient + original BROM runners
runtime/bin/               # Embedded Windows Python runtime
Bin/, adb_assets/          # Third-party Windows flashing/ADB utilities
certifi/                   # CA bundle
legacy/                    # Original compiled client (reference only)
START_NO_LOGIN.bat         # Oumse community Windows launcher
START_BEST_MDM_TOOL.bat    # BestMDMTool Windows launcher
run_gui.sh                 # Oumse development launcher for Unix-like systems
run_bestmdmtool.sh         # BestMDMTool development launcher for Unix-like systems
installer/                 # Oumse community Windows installer project
installer-bestmdmtool/     # BestMDMTool Windows installer project
.github/workflows/         # CI and installer build workflows
PROJECT_ANALYSIS.md        # Full static audit
SECURITY.md                # Security posture and residual risks
```

## Windows installers

Two reproducible Inno Setup projects are included.

### Oumse community installer

On Windows, run:

```bat
installer\build_installer.bat
```

It produces `installer\artifacts\OumseNoLoginSetup-1.0.0.exe`. See `installer/README.md`.

### BestMDMTool installer

On Windows, run:

```bat
installer-bestmdmtool\build_installer.bat
```

It produces `installer-bestmdmtool\artifacts\BestMDMToolSetup-0.1.0.exe`. See
`installer-bestmdmtool/README.md` and `bestmdmtool/README.md`.

Both installers create Start Menu and optional Desktop shortcuts that launch their respective
no-login GUI through a hidden PowerShell/VBS launcher. They exclude the legacy login
executable, logs, device identifiers, tests, and Git metadata.

Because this Linux sandbox has no Inno Setup compiler, the `.exe` files are built by
`.github/workflows/build-installer.yml` and
`.github/workflows/build-bestmdmtool-installer.yml` on Windows runners. Portable ZIPs can also
be generated locally with:

```bash
python installer/build_portable.py
python installer-bestmdmtool/build_portable.py
```

## BestMDMTool

**BestMDMTool** is a separate, no-login, authorized-service application inspired by the layout
and workflow of the community front-end. It has its own branding, version, installer, AppId,
launcher scripts, and documentation.

It is **not** a copy of the legacy compiled OumseGSM executable. It does not include the legacy
login/anti-analysis/licensing code, MDM/FRP bypass algorithms, server-side patch algorithms, or
credential/licensing-bypass logic. Use it only on devices you own or are explicitly authorized
to service.

See `bestmdmtool/README.md` for full details.

## Development

```bash
python -m pip install -r requirements-dev.txt
ruff check app bestmdmtool servicecore tests installer/build_portable.py installer-bestmdmtool/build_portable.py
python -m compileall -q app bestmdmtool servicecore tests installer/build_portable.py installer-bestmdmtool/build_portable.py
python -m unittest discover -s tests -v
```

CI runs the same lint, compile, portable-packaging, and unit-test steps on Python 3.12. GUI and
hardware behavior are not exercised in CI because they require Windows USB drivers and a
physical device.

## Known limitations

- Both GUIs currently cover the MTK BROM runner. SPD, ADB, server-side patch algorithms,
  and the original compiled GUI's full feature set are not reimplemented here.
- BestMDMTool deliberately does not include MDM/FRP bypass or legacy licensing/bypass logic.
- Device writes still cannot be rolled back. Always keep a full dump before writing.
- The vendored `mtkclient`, DA binaries, APKs, and Windows DLLs remain third-party artifacts
  with unresolved redistribution/provenance questions.
- The legacy executable is unsigned and contains a hardcoded remember-me key. Do not use it.

## Legal and compliance

These tools can read, write, and erase device partitions. Use them only on devices you own or
are explicitly authorized to service. The vendored `mtkclient` is GPLv3; review
`runtime/lib/LICENSE`, vendor DA redistribution rights, and all bundled third-party licenses
before distributing a release. See `SECURITY.md` and `PROJECT_ANALYSIS.md`.
