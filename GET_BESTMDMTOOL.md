# Get BestMDMTool

BestMDMTool is a **separate, no-login** app in this repository. It opens
straight to a full device workspace — no account, no server, no remote service.

The workspace has eight pages: Dashboard, Partition Manager, Firmware Flasher,
Advanced Tools (raw flash + memory peek/poke), Bootloader, ADB & Fastboot,
Settings, and About.

> Use only on devices you own or are explicitly authorized to service.

---

## 1. Download the finished installer (easiest)

**Direct link:**

<https://github.com/GARDNADZENT/oumse/releases/download/v0.3.0/BestMDMToolSetup-0.3.0.exe>

**Release page** (also has `SHA256SUMS.txt`):

<https://github.com/GARDNADZENT/oumse/releases/tag/v0.3.0>

| Item | Value |
| --- | --- |
| File | `BestMDMToolSetup-0.3.0.exe` |
| Size | ~48.7 MiB |
| Built by | GitHub Actions, Windows `windows-latest` |
| Signing | **Not signed** — SmartScreen will warn (see below) |

Install steps:

1. Run `BestMDMToolSetup-0.3.0.exe`.
2. Because the file is not code-signed, Windows shows
   *"Windows protected your PC"*. Click **More info → Run anyway**.
3. Finish setup, then launch **BestMDMTool** from the Start Menu.
4. The app opens directly — no login screen.

Python is **not required** on the target PC: the installer ships a standalone
`BestMDMTool.exe` with its own Python + Tkinter runtime.

### Verify the download (optional but recommended)

```powershell
Get-FileHash .\BestMDMToolSetup-0.3.0.exe -Algorithm SHA256
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
   `installer-bestmdmtool\artifacts\BestMDMToolSetup-0.3.0.exe`;
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
