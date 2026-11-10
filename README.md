# Oumse GSM Tool Pro / BestMDMTool

> **Security advisory:** v0.5.2 is withdrawn. Its MediaTek backend could run unaudited security code and report a failed userdata erase as successful. The device's data state after that incident is unknown; do not retry erase, write, or flash operations on it.
>
> **Published BestMDMTool v0.5.3:** [download](https://github.com/GARDNADZENT/oumse/releases/download/v0.5.3/BestMDMToolSetup-0.5.3.exe) · SHA-256 `f21e81642e99db6dab0e91c28a7ecf2ca08e4c0693e03492ce52bd914511e7c5`. This containment release blocks MTK sessions and supports SPD/Unisoc only.

## Current BestMDMTool source direction

The current, unreleased source has been simplified to a single-purpose **MTK BootROM partition-reader screen**. It offers passive USB detection only; the MTK session backend remains disabled pending independent security review. The partition-read control is visibly unavailable, and no write, erase, format, flash, reboot, unlock, ADB, PAC, DIAG, or SPD controls appear in the launched app.

The source UI change does **not** alter the published v0.5.3 installer. See [bestmdmtool/README.md](bestmdmtool/README.md) for the prototype's exact limits and [GET_BESTMDMTOOL.md](GET_BESTMDMTOOL.md) for the published release.

## Applications

- `bestmdmtool/` — BestMDMTool, separately branded, no-login app. Launches directly into the one-screen MTK BROM prototype.
- `app/` — the separate Oumse community front-end.
- `legacy/` — the original compiled client, retained for reference and not used as the default application.

Neither new front-end requires login or a remote account. BestMDMTool includes no MDM/FRP bypass, credential bypass, or licensing-bypass functionality.

## Run BestMDMTool from source

Requires Python 3.10+ with Tkinter:

```powershell
py -3 -m bestmdmtool
```

Or double-click `START_BEST_MDM_TOOL.bat` from the repository root. The app opens without login. Its **Scan for MTK BootROM** button only enumerates USB devices; it does not open a phone session.

## Build the BestMDMTool installer

The mandatory PowerShell invocation uses the `.` prefix:

```powershell
.\BUILD_BESTMDMTOOL_INSTALLER.bat
```

The current GitHub release remains v0.5.3. Building this source produces an unreleased development build; it does not make MTK partition reads available.

## Tests

Run the test suite with:

```bash
python -m unittest discover -s tests -v
```

The suite covers the no-login entry point, passive BROM detection, fail-closed MTK behavior, partition-result validation, the independent SPD protocol modules, and packaging checks.

## Repository layout

```text
app/                       # Oumse community GUI
bestmdmtool/               # BestMDMTool UI and branding
servicecore/               # USB discovery, session and chipset code
installer-bestmdmtool/     # BestMDMTool installer/build project
installer/                 # Oumse community installer project
tests/                     # Unit and headless UI tests
legacy/                    # Original compiled client, reference only
.github/workflows/         # CI and Windows installer workflows
SECURITY.md                # Security posture and incident notes
PROJECT_ANALYSIS.md        # Repository audit notes
GET_BESTMDMTOOL.md         # Published BestMDMTool release/download instructions
```
