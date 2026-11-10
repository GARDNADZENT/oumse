# BestMDMTool

BestMDMTool is a separate, no-login product. The **current unreleased source** is intentionally reduced to one screen for **MTK BootROM detection and partition reading only**. It does not expose SPD, flashing, writing, erase/format, reboot, unlock, ADB, PAC, or diagnostic tools.

> **Important:** the current screen performs a passive USB scan only. It does not open an MTK session or read device storage. The partition table is intentionally empty and **Read selected partition** is disabled pending an independent security review of the MTK backend.

## Why MTK reads are not enabled

The withdrawn v0.5.2 MTK backend could invoke unaudited security code automatically and reported a failed userdata erase as successful. The device's data state after that incident is unknown. v0.5.3 was a containment release that disabled MTK sessions and removed the MTK backend from its installer. A read-only request does not make that unaudited connection path safe to re-enable.

The currently published [v0.5.3 installer](https://github.com/GARDNADZENT/oumse/releases/tag/v0.5.3) is unchanged and remains SPD/Unisoc-only. It is not the same as this unreleased, simplified source UI.

## Current screen

- **Scan for MTK BootROM** passively enumerates USB devices and identifies BROM mode. It does not send device commands.
- **Device partitions** is a read-only table placeholder. Passive USB detection cannot provide a partition table.
- **Read selected partition** is visibly disabled until an independently reviewed, stock-only MTK reader is available.
- There are no write, erase, format, flash, unlock, reboot, ADB, PAC, DIAG, or SPD controls in the launched app.
- No login, account, telemetry, or remote service is used.

Use only on devices you own or are explicitly authorized to service.

## Run from source

Requires Python 3.10+ with Tkinter:

```powershell
py -3 -m bestmdmtool
```

Or run `START_BEST_MDM_TOOL.bat` from the repository root.

## Installer

The PowerShell build command must include the `.` prefix:

```powershell
.\BUILD_BESTMDMTOOL_INSTALLER.bat
```

The published v0.5.3 installer and its checksum are documented in [GET_BESTMDMTOOL.md](../GET_BESTMDMTOOL.md). Do not use the published installer for MTK operations.

## Safety boundary

No MDM/FRP bypass, credential bypass, licensing bypass, or bypass instructions are included. MTK device access will remain unavailable until the backend is independently reviewed and can be shown to use a documented stock-only read path with strict operation-result validation.
