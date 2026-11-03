> **Security advisory:** v0.5.2 is withdrawn. Its MediaTek backend could invoke
> security-bypass code automatically and falsely report an erase as successful.
> v0.5.3 disables MTK sessions before a runner starts and does not include the
> MTK backend or loaders. The phone's data state after a failed erase is unknown;
> do not retry erase or flash operations until the device has been checked.

# BestMDMTool

A no-login local service workspace with MediaTek USB detection and a working
**Spreadtrum/Unisoc** BSL/FDL engine. MediaTek connect/read/write/erase is
**temporarily disabled** pending a security review. The app opens straight into
the device screen — no account, server, heartbeat, or remote service.

> Use only on devices you own or are explicitly authorized to service.

## Workspace layout

The window is a three-column workspace, matching the OumseGSM tool:

| Column | Contents |
| --- | --- |
| **Left** | The tool list: 12 device tools, then the workspace pages (Dashboard, Firmware Flasher, Advanced Tools, Chipset Database, Settings, About) |
| **Middle** | Operations for the selected tool, grouped the way the original groups them (`Device`, `Reset shortcuts`, `Bootloader`, `Flash`, `Diagnostics`) |
| **Right** | The live page, a contextual action strip, the progress bar and a black/green console |

The title bar carries the local session card (engine, chip, uptime), the
language switch and a clock. The footer shows the current status and a **STOP**
button that cancels the running job and closes the session.

**Languages:** EN / FR / PT / AR switch the navigation, the operation buttons,
the header and the footer immediately, and the choice is saved. Arabic text
renders correctly but the columns stay left-to-right — Tk has no layout mirroring.

**Unavailable entries stay visible.** `MDM Regional Patcher`, `Direct Bypass
MTK`, `Direct Permanent MTK`, `Reset FRP` and `Factory + FRP` are part of the
OumseGSM button set but are lock or account bypasses, so in BestMDMTool they open
an explanation page instead of acting. Everything else on that list is wired to
a real operation.

## Keyboard shortcuts

| Keys | Action |
| --- | --- |
| `Ctrl+1` .. `Ctrl+9` | Switch between the first nine tools |
| `F5` | Refresh the partition table |
| `Ctrl+L` | Clear the console |

## Logs and crash reports

Every activity-log line is mirrored to
`%LOCALAPPDATA%\BestMDMTool\logs\activity.log` (rotated at 1 MB, three
generations). If the window closes unexpectedly, a `crash-<timestamp>.log` lands
in the same folder and a dialog names it. **Settings -> Open log folder** opens
it. **Settings -> Export support bundle** zips the activity log, the newest
crash report, a backend self-test result and the device snapshot into a single
file on the Desktop, ready to attach to a bug report.

## Choosing the engine

Settings has a **Chip family** selector with three values:

| Value | Behaviour |
| --- | --- |
| `auto` (default) | Reads USB first and opens the engine that matches the phone |
| `mtk` | MediaTek detected; device session currently blocked pending security review |
| `spd` | Always the Spreadtrum/Unisoc BSL engine |

With `auto`, the doctor identifies MediaTek PreLoader/BROM and Spreadtrum/Unisoc
BSL/FDL hardware. Spreadtrum sessions can proceed. A MediaTek connect request
is refused in the GUI before it launches a runner, and the frozen runner also
fails closed if called directly. No MediaTek DA/backend payload is installed.

The runner scratch directory is `%LOCALAPPDATA%\BestMDMTool\work`.

## MediaTek status and diagnostics

Seeing a port and its Windows driver does not establish whether a device can be
opened. The doctor reports the pyusb module and libusb backend separately. Do
not change or replace a driver based only on this diagnostic. MTK sessions are
currently blocked pending security review.

## When the phone is not detected

**Connection doctor** (Chipset Database page, or the button in the operations
column) is the first thing to press. It lists every USB device Windows reports,
with the driver bound to each one, then prints one verdict and the next steps:

| Verdict | What it means |
| --- | --- |
| `download` | A phone is in PreLoader/BROM or BSL/FDL mode — press Connect |
| `android` | The phone is booted into Android; power it off and use the download keys |
| `present_not_download` | MediaTek/Spreadtrum hardware is there but not in a download mode |
| `backend` | pyusb is installed but libusb could not enumerate — reinstall |
| `nothing` | Windows itself does not see the phone: cable, port or driver |

Detection uses three independent sources — pyusb, the Windows device tree
(PowerShell) and serial ports — so a missing library in one path cannot hide a
connected phone. Every launch also logs a one-line USB snapshot.

## Diagnosing a failed connection

**Settings -> Run backend self-test** executes `BestMDMToolRunner.exe --selftest`
and reports the Python version, SPD engine, pyusb/pyserial, libusb backend and
USB devices it can see. It also states that MTK is disabled. The same summary
goes to the activity log.

## Interface

Sidebar navigation with a shared activity log dock and a live status bar.

| Page | What it does |
| --- | --- |
| **Dashboard** | Chipset, hardware code, storage type, partition count, ADB state, quick actions |
| **Partition Manager** | SPD sessions: filterable partition table, read/write/erase; MTK actions unavailable |
| **Firmware Flasher** | SPD firmware workflows; MTK image writes unavailable |
| **Advanced Tools** | MTK raw flash and memory operations unavailable pending review |
| **Bootloader** | Lock-state probe via ADB and fastboot helpers; direct seccfg buttons are disabled |
| **ADB & Fastboot** | Device list, reboot targets, shell, APK install, push/pull |
| **SPD Toolkit** | Spreadtrum/Unisoc BSL session: transport, partition table, read/write/erase, reboot |
| **SPD Firmware** | Open a `.pac`, verify every CRC, flash it, extract it, or build a new package (ROM maker) |
| **SPD DIAG** | AT/DIAG console over the serial port: model, firmware, IMEI, SIM, signal |
| **Chipsets** | MediaTek + Spreadtrum/Unisoc database with USB ids and USB detection |
| **Settings** | SPD transport, safe defaults and diagnostics; MTK mode/loader/auth controls disabled |
| **About** | Product identity and safety boundaries |

Keyboard: `F5` refreshes the partition table.

## Operations

The frozen `BestMDMToolRunner.exe` contains the first-party SPD/Unisoc engine,
pyusb, pyserial and libusb. **The MediaTek runner is fail-closed**: the GUI stops
before launching it, and a direct `--engine mtk` invocation returns a failure
before importing a device backend or opening USB. The installer does not include
mtkclient, DA loaders, or the legacy Oumse runners.

The supported Spreadtrum/Unisoc command set is:

```
info, partitions, read, write, erase, readflash, writeflash, eraseflash,
pac_open, pac_flash, pac_extract, pac_build, reboot, quit
```

Progress, per-step events, and failures stream back as `SVC_*` lines. Empty
partition tables, incomplete reads, out-of-range writes, and failed format
operations return `SVC_FAIL`, not a successful empty result.

Direct MediaTek seccfg controls remain visible but disabled. This is a safety
containment release, not a MediaTek recovery tool.

## Spreadtrum/Unisoc engine

Spreadtrum/Unisoc is the only currently enabled chipset engine. The shared GUI,
log and session lifecycle also identify MediaTek hardware, but do not open an
MTK device session.

* **Transport** - `auto` (USB first, then the first serial port), `usb`, `serial`
  with an explicit port, or `simulator` for training without hardware.
* **Protocol** - the Boot Strap Loader: HDLC frames with CRC16-XMODEM, 32 KiB
  data blocks, `START`/`MID`/`END` uploads, 16-bit status per command.
* **Partition table** - read from the FDL when it supports the partition
  command; otherwise the page falls back to the table inside a PAC package and
  says so in the status line.
* **PAC firmware** - `.pac` containers are read, every partition CRC is checked,
  and a package that fails verification is refused before anything is written.
  The ROM maker packs a folder of images back into a `BP_R2` container.

The engine constants (command numbers, block sizes, timeouts) live in one file,
`servicecore/spd/constants.py`, so a device that behaves differently can be
adapted without touching the UI.

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
own Python + Tkinter), so end users do not need Python at all. The installer
includes no MediaTek DA backend or loader payload.

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
  runner/service_runner.py  # fail-closed MTK adapter (no device access)
  adb.py              # ADB / Fastboot wrappers
```
