# BestMDMTool

A no-login MediaTek service workspace. It opens straight into the device
screen — no account, no server, no heartbeat — and drives the bundled
mtkclient BROM/DA layer over a persistent session.

> Use only on devices you own or are explicitly authorized to service.

## Logs and crash reports

Every activity-log line is mirrored to
`%LOCALAPPDATA%\BestMDMTool\logs\activity.log` (rotated at 1 MB, three
generations). If the window closes unexpectedly, a `crash-<timestamp>.log` lands
in the same folder and a dialog names it. **Settings -> Open log folder** opens
it; attach `activity.log` plus the newest crash report to a bug report.

## Diagnosing a failed connection

**Settings -> Run backend self-test** executes `BestMDMToolRunner.exe --selftest`
and reports the Python version, mtkclient import, libusb backend, DA loaders and
USB devices it can see. The same summary goes to the activity log, so a support
report can name the failing piece instead of guessing.

## Interface

Sidebar navigation with a shared activity log dock and a live status bar.

| Page | What it does |
| --- | --- |
| **Dashboard** | Chipset, hardware code, storage type, partition count, ADB state, quick actions |
| **Partition Manager** | Filterable GPT table: read, write, erase, back up all, export GPT |
| **Firmware Flasher** | Flash an image to a partition, batch queue with auto-matching, raw offset write |
| **Advanced Tools** | Raw flash read/erase at a byte offset, live memory peek/poke with hex viewer |
| **Bootloader** | Lock-state probe via ADB, seccfg unlock/lock over DA, fastboot helpers |
| **ADB & Fastboot** | Device list, reboot targets, shell, APK install, push/pull |
| **Settings** | Session mode (BROM/preloader), transport, custom DA loader, auth file, verbose logging |
| **About** | Product identity and safety boundaries |

Keyboard: `F5` refreshes the partition table.

## Operations

Everything runs locally through the device runner, which keeps one BROM/DA
connection open and accepts JSON commands on stdin. The installer ships it as
`BestMDMToolRunner.exe` (a frozen build with a complete CPython, pyusb,
pyserial and libusb) because the vendored `runtime/bin` interpreter has no
C extension modules:

```
info, gpt, gpt_export, read, write, erase, dump,
readflash, writeflash, eraseflash, peek, poke,
seccfg, reboot, quit
```

Progress, per-step events, and failures stream back as `SVC_*` lines
(`SVC_STEP`, `SVC_PROGRESS`, `SVC_LOG`, `SVC_INFO`, `SVC_READY`, `SVC_OK`,
`SVC_FAIL`, `SVC_DATA`, `SVC_BYE`).

Destructive actions (write, erase, poke, seccfg, raw flash) always require
confirmation, and protected partitions are flagged in the table.

## Run from source

```bat
START_BEST_MDM_TOOL.bat
```

Requires Python 3.10+ with Tkinter on that machine.

```bash
python -m bestmdmtool      # from the repository root
```

## Installer

`installer-bestmdmtool/` builds `BestMDMToolSetup-<version>.exe` with Inno
Setup. The installer ships a standalone `BestMDMTool.exe` (PyInstaller with its
own Python + Tkinter), so end users do not need Python at all. The bundled
x86 `runtime/bin` Python is only used headlessly by the BROM runner.

```powershell
.\BUILD_BESTMDMTOOL_INSTALLER.bat
```

See [../GET_BESTMDMTOOL.md](../GET_BESTMDMTOOL.md) for download and build steps.

## What it is not

- No MDM/FRP bypass, credential extraction, or licensing circumvention.
- No login, no account, no remote service, no telemetry.
- Not a rebrand of the legacy compiled executable: the UI is first-party
  Tkinter code in `bestmdmtool/ui/`.

## Layout

```
bestmdmtool/
  gui.py            # BestMDMToolApp (MainWindow subclass) + main()
  branding.py       # product name, version, safety strings
  settings.py       # per-user settings (LOCALAPPDATA/BestMDMTool)
  ui/
    theme.py        # dark palette + ttk styles
    widgets.py      # Card, ActionButton, Pill, StatTile, LogConsole, PathRow
    controller.py   # session lifecycle, worker threads, event pump
    main_window.py  # header, sidebar, pages, log dock, status bar
    pages/          # dashboard, partitions, flasher, advanced,
                    # bootloader, adb_tools, settings, about
servicecore/
  service_session.py  # client for the runner protocol
  runner/service_runner.py  # persistent BROM/DA backend
  adb.py              # ADB / Fastboot wrappers
```
