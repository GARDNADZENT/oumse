# Get BestMDMTool

BestMDMTool is a **separate, no-login** app in this repository. It opens
straight to a full device workspace — no account, no server, no remote service.

The workspace has eight pages: Dashboard, Partition Manager, Firmware Flasher,
Advanced Tools (raw flash + memory peek/poke), Bootloader, ADB & Fastboot,
Settings, and About.

> Use only on devices you own or are explicitly authorized to service.

---

## What's new in 0.3.2

**Self-diagnosis.** Settings now has a **Run backend self-test** button. It asks
the device runner to check itself - Python version, mtkclient import, libusb
backend, DA loaders and visible USB devices - and prints the result in the
activity log. If something is missing it names the piece instead of failing
later with a bare "connection failed".

**Verified install layout.** CI now copies the built runner into a fake
`{app}\runtime\runner` tree and runs it with no environment help, proving the
installed app finds its own `runtime\lib` and libusb DLLs.

0.3.1 fixed the release that could not open a BROM session at all: the vendored
`runtime\bin` interpreter has no C extensions (so `_socket` was always missing),
which is why the backend now ships as a frozen `BestMDMToolRunner.exe`.

## What's new in 0.3.3

**Logs and crash reports.** Every line in the activity log is also written to
`%LOCALAPPDATA%\BestMDMTool\logs\activity.log`, and an unexpected error now
writes `crash-<timestamp>.log` and shows a dialog pointing at it instead of the
window silently disappearing. **Settings -> Open log folder** opens the folder.

**Whole-window tests.** The build now constructs the real window with all eight
pages, switches pages, feeds it a simulated device and drives a partition read in
CI, plus static checks that every page only touches real controller and theme
members.

## What's new in 0.3.4

**Export support bundle.** Settings -> **Export support bundle** writes one zip
to your Desktop with `activity.log`, the newest crash report, a backend
self-test result, and the device/partition snapshot. Attach that single file to a
bug report instead of describing symptoms.

**Every page action is exercised in CI.** Besides building the window and
switching pages, the tests now drive partition read/backup/erase/GPT export,
flash-to-partition, raw range reads, peek and seccfg against a simulated device,
so a broken callback fails the build instead of the user.

## What's new in 0.3.5

**The window remembers where you left it.** Size, position and whether the
activity log was expanded are saved on close and restored on the next start.

**Keyboard shortcuts.** `Ctrl+1` .. `Ctrl+8` jump between pages, `Ctrl+L` clears
the activity log, `F5` refreshes the partition table.

**Stricter tests.** The headless test double now refuses unknown private members,
so a typo such as `self._toggle_log()` (silently swallowed before) fails the
build instead of the user.

## 1. Download the finished installer (easiest)

**Direct link:**

<https://github.com/GARDNADZENT/oumse/releases/download/v0.3.5/BestMDMToolSetup-0.3.5.exe>

**Release page** (also has `SHA256SUMS.txt`):

<https://github.com/GARDNADZENT/oumse/releases/tag/v0.3.5>

| Item | Value |
| --- | --- |
| File | `BestMDMToolSetup-0.3.5.exe` |
| Size | ~64 MiB |
| Built by | GitHub Actions, Windows `windows-latest` |
| Signing | **Not signed** — SmartScreen will warn (see below) |

Install steps:

1. Run `BestMDMToolSetup-0.3.5.exe`.
2. Because the file is not code-signed, Windows shows
   *"Windows protected your PC"*. Click **More info → Run anyway**.
3. Finish setup, then launch **BestMDMTool** from the Start Menu.
4. The app opens directly — no login screen.
5. Connect a phone in BROM mode and press **Connect device**.

Python is **not required** on the target PC: the installer ships a standalone
`BestMDMTool.exe` with its own Python + Tkinter runtime.

### Verify the download (optional but recommended)

```powershell
Get-FileHash .\BestMDMToolSetup-0.3.5.exe -Algorithm SHA256
```

Compare the output with the contents of `SHA256SUMS.txt` on the release page.

---

## 2. Why your folder had nothing

`C:\Users\user\Downloads\GARDNADZENT_oumse\oumse-main` is a snapshot of the
**`main` branch**, which only contains the old compiled `OumseGsmToolPro.exe`,
the vendored runtime, and the uninstaller files. It has no `bestmdmtool\`,
`installer-bestmdmtool\`, or `START_BEST_MDM_TOOL.bat`.

All new work lives on branch `arena/010a7cc2-oumse`:

<https://github.com/GARDNADZENT/oumse/archive/refs/heads/arena/010a7cc2-oumse.zip>

Only download that source ZIP if you want to run the app from source or rebuild
the installer. If you just want the app, use the installer in section 1.

---

## 3. Build the installer yourself (Windows)

From a checkout of `arena/010a7cc2-oumse`:

```powershell
.\BUILD_BESTMDMTOOL_INSTALLER.bat
```

> **PowerShell requires `.\` for a file in the current folder.**
> That is exactly why your earlier attempt failed:
>
> ```text
> PS> installer-bestmdmtool\build_installer.bat
> The module 'installer-bestmdmtool' could not be loaded.
> ```
>
> PowerShell treated `installer-bestmdmtool` as a module name. Use a leading
> `.\`, or run `cmd.exe` and call it without the prefix.

The script:

1. builds the standalone `BestMDMTool.exe` with PyInstaller (needs Python 3.10+
   with Tkinter on the *build* machine);
2. installs Inno Setup 6 automatically if `ISCC.exe` is missing (winget, then a
   direct download);
3. compiles the installer to
   `installer-bestmdmtool\artifacts\BestMDMToolSetup-0.3.5.exe`;
4. writes `installer-bestmdmtool\artifacts\SHA256SUMS.txt`.

Alternative entry points:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\installer-bestmdmtool\build_installer.ps1
installer-bestmdmtool\build_installer.bat      # from cmd.exe only
```

Useful switches: `-SkipFrozenExe` (source-only, needs Python on the target PC)
and `-SkipInnoSetupInstall` (do not auto-install Inno Setup).

### Run from source instead of installing

```powershell
.\START_BEST_MDM_TOOL.bat
```

Requires Python 3.10+ with Tkinter on the same machine.

---

## 4. Common problems

| Symptom | Cause | Fix |
| --- | --- | --- |
| Window closes by itself | An unexpected error | Open the log folder (Settings) and send the newest `crash-*.log` |
| "Connection failed" with no detail | The backend could not start | **Settings -> Run backend self-test**; the log shows the runner path and the failing piece |
| `OUMSE_FAIL:import:No module named '_socket'` then "0 partitions" | **Fixed in 0.3.1.** The vendored `runtime\bin` Python has no `*.pyd` C extensions, so the old build used it as the runner | Install 0.3.1 or newer: it ships a frozen `BestMDMToolRunner.exe` with a complete interpreter |
| `The module 'installer-bestmdmtool' could not be loaded` | PowerShell needs `.\` | Run `.\installer-bestmdmtool\build_installer.bat` or use `cmd.exe` |
| `START_BEST_MDM_TOOL.bat is not recognized` | Same missing `.\` | Run `.\START_BEST_MDM_TOOL.bat` |
| `Python with Tkinter is required` when running from source | Python missing or installed without tcl/tk | Install Python from python.org with the tcl/tk option, or use the installer (ships its own) |
| SmartScreen blocks the installer | Unsigned binary | More info → Run anyway. Sign with `signtool.exe` before public distribution |
| Installer builds but app does not start | `frozen\BestMDMTool` missing | Run `installer-bestmdmtool\build_exe.ps1` first, or rerun without `-SkipFrozenExe` |

---

## 5. What is inside

- `BestMDMTool\BestMDMTool.exe` — standalone GUI (bundled Python + Tkinter)
- `bestmdmtool\`, `servicecore\` — sources and shared core
- `runtime\bin` — bundled headless Python 3.12 (x86) used by the BROM runner
- `runtime\lib` — vendored `mtkclient` 2.1.4 plus the two BROM runners
- `Bin\`, `adb_assets\`, `certifi\` — flashing/ADB tools and CA bundle
- docs, GPLv3 license text, uninstaller

Not included: the legacy login executable, device logs, device identifiers,
MDM/FRP bypass or licensing-bypass logic.
