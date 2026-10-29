# Oumse GSM Tool Pro — Project Analysis

> **Remediation status (2026-10-27):** A no-login front-end now lives in `app/` and is launched by `START_NO_LOGIN.bat`. A second independent product, `bestmdmtool/`, was added with its own launcher and installer; both apps share `servicecore/`. Committed logs, device identifiers, duplicate/wrapper executables, and installer artifacts were removed; the legacy compiled client was moved to `legacy/`. `.gitignore`, `SECURITY.md`, CI, unit tests, and reproducible installer projects were added. The original findings below remain for context; see `README.md`, `SECURITY.md`, `installer/README.md`, `bestmdmtool/README.md`, and `installer-bestmdmtool/README.md` for the current state.

_Static analysis performed on 2026-10-27. The Windows executables were not run: this environment is Linux and the tool requires physical MediaTek/Spreadtrum devices, Windows USB drivers, and BROM/preloader access._

## 1. Executive summary

`oumse` is a **Windows-only, 32-bit desktop GSM service tool** for MediaTek (MTK) and Spreadtrum/Unisoc (SPD) devices. It exposes partition read/write/erase, BROM/preloader/META workflows, FRP/userdata operations, ADB helpers, and MDM-related regional patching. It also has a client-side subscription/credit system backed by a server that is **not included in this repository**.

The checkout is best understood as a **snapshot of an installed Windows application plus a vendored `mtkclient` runtime**, rather than a source project:

- The main GUI exists only inside an unsigned, Nuitka-compiled `OumseGsmToolPro.exe`.
- The first-party Python source visible here consists mainly of two device runners in `runtime/lib/`.
- `runtime/lib/` is almost exactly a copy of upstream `bkerler/mtkclient` at commit `2c9f4d7860` (2026-06-09, version metadata `2.1.4`).
- There is no source for the `OumseGsmServer`, no root README, no first-party test suite, no CI, and no reproducible build recipe for the main app.
- The repository contains 3,345 tracked files / about 255 MiB of tracked data; the worktree is about 263 MiB.

Overall status: **functional prototype / packaged release**, but **not currently a maintainable source repository**. Highest priorities are source recovery, removal of sensitive/runtime artifacts, binary provenance, safer flashing logic, and tests.

## 2. What the project appears to do

### Main client

PE inspection and strings in `OumseGsmToolPro.exe` show a 32-bit Nuitka-compiled Python 3.12 application. Compiled module names include:

- `OumseGsmToolPro_ui` / `OumseGsmToolProPrivate_ui` — CustomTkinter GUI
- `oumse_core` — central operations
- `oumse_server_client` — login, billing, heartbeat, version checks
- `oumse_tool_i18n` — translations
- `oumse_spd_cli` / `SpdCliBridge` — Spreadtrum operations
- `oumse_adb_bypass_batch` — ADB workflows

The GUI includes tabs/workflows for:

- MTK BROM, preloader, and META modes
- Persistent BROM sessions, partition inventory, read/write/erase/reboot
- Direct MDM regional patching for MTK and SPD
- ADB-based MDM bypass and `OumseResConfig.apk` / TestDPC handling
- FRP reset, metadata/userdata erase, factory reset
- SPD partition manager, U-Boot/diag/ROM-maker features
- Login, server settings, theme/language switching, crash reporting

These are **dual-use capabilities**. They can support legitimate repair of owned devices, but also require strict authorization, chain-of-custody, and anti-theft compliance controls.

### Licensing/server integration

The binary contains an HTTP client for a separate server. Observed endpoints include:

`/api/login`, `/api/heartbeat`, `/api/operations`, `/api/check_op`, `/api/consume_op`, `/api/me`, `/api/flag_hwid`, `/api/get_algo`, `/api/run_spd`

Observed behavior includes:

- Login using username/password and a machine HWID
- Session token, account type, subscription expiry, credits, and a server-side session lock
- Heartbeat with version checks; HTTP 426 triggers a forced-update dialog
- Download/update URL `https://oumsegsm.com/download`
- `server_config.json` with a default server URL of `http://localhost:8000`
- Remember-me storage in `.remember.dat` using XOR + Base64 with a **hardcoded key embedded in the executable**
- Anti-analysis process monitoring and an account/HWID flag endpoint

The server implementation and API contract are absent from the repository, so end-to-end behavior cannot be verified here.

## 3. Repository structure and stack

| Area | Contents |
|---|---|
| `/OumseGsmToolPro.exe` | Main unsigned Nuitka-compiled Windows x86 application, Python 3.12 |
| `/OumseGsmToolPro.exe,` and `/oumsegsmtoolpro.exe ` (trailing NBSP) | Additional shipping artifacts with suspicious filenames |
| `/runtime/bin` | Embedded Windows Python 3.12 runtime and vendored site-packages |
| `/runtime/lib` | Copy of `mtkclient` 2.1.4 plus two custom Oumse runners |
| `/Bin` | Windows fastboot/erofs/lpmake/lpunpack utilities and support DLLs |
| `/adb_assets` | `adb.exe`, `testdpc.apk`, `OumseResConfig.apk`, ADB DLLs |
| `/customtkinter` | Only themes, fonts, and icons; no CustomTkinter Python source |
| `/tcl`, `/tk`, `/tcl8`, root DLLs | Tk/Tcl and C runtime dependencies for the packaged app |
| `unins000.exe` / `unins000.dat` | Installer/uninstaller artifacts, indicating this is an installed-directory snapshot |

`runtime/lib/logs/log.txt` is a 20 MiB runtime log with 532,355 lines. `runtime/lib/hwparam.json` contains device identifiers. `runtime/lib/python` is an empty file. These should not be checked in.

The only project-level metadata files are upstream `mtkclient` files under `runtime/lib` (`pyproject.toml`, `requirements.txt`, `uv.lock`, README files). They describe `mtkclient`, not how to build or run the Oumse application.

## 4. Provenance findings

### Vendored `mtkclient`

A blob-level comparison against upstream `bkerler/mtkclient` shows `runtime/lib` matches commit `2c9f4d78601e2b223cacfed773a5c4cbb1808189` (2026-06-09) for **1160 of 1161 comparable files**. The only different file is the MTK V6 DA binary. This is a useful, precise baseline.

Local additions relative to that commit:

- `oumse_brom_runner.py` — 411 lines, one-shot read/patch/write runner
- `oumse_brom_session_runner.py` — 939 lines, persistent JSON-over-stdin session runner
- `logs/log.txt` — 20 MiB runtime log
- `hwparam.json` — MEID, hardware code, SOC ID
- empty `python` file
- a different `mtkclient/Loader/MTK_DA_V6.bin`

The local V6 DA is 766,328 bytes; the upstream DA at that commit is 13,529,076 bytes. The local binary identifies itself as `MTK_DA_v6_2025-11-25` and includes internal vendor build-server source paths. Its redistribution rights and provenance should be reviewed.

The upstream project is GPLv3. The license text is retained in `runtime/lib/LICENSE`, but a compliance review is needed for the compiled commercial client, custom runners, replaced DA binary, bundled APKs, and other third-party binaries. Add a complete SBOM, licenses, checksums, and source offers where required.

### Executable duplication and wrappers

- `OumseGsmToolPro.exe` and the filename ending with a non-breaking space are byte-for-byte identical.
- `OumseGsmToolPro.exe,` is a separate VB6 outer executable. It contains an exact copy of the main Nuitka executable at offset 138,316, plus additional binary data.
- All three main PE artifacts are unsigned.
- The outer VB6 executable requests administrator privileges and contains imports/strings associated with process enumeration, process termination, thread resumption, registry access, and `URLDownloadToFileA`.

These are static indicators, not proof of malicious behavior. However, an unsigned self-extracting wrapper around another unsigned executable is a significant supply-chain risk. It should be built from source, code-signed, hashed, and scanned in an isolated Windows environment. The odd comma/NBSP filenames should be removed.

## 5. Code quality and reliability

### Verification performed

- All 124 Python files under `runtime/lib` parse successfully.
- A broad Ruff ruleset reports 158 findings on the two custom runners: 78 blind-exception catches, 32 swallowed failures, 38 old-style `%` formatting issues, 5 import-order issues, 2 unused imports, and 2 encoding-cookie issues.
- No first-party unit/integration tests were found. Existing `test*.py` files belong to vendored dependencies.
- No GitHub Actions, pre-commit, lint/test CI, root README, or app build script exists.

### Custom runners

The two runners use a line-oriented protocol with markers such as `OUMSE_STEP`, `OUMSE_READY`, `OUMSE_OK`, `OUMSE_FAIL`, `OUMSE_RESULT`, `OUMSE_READLEN`, and `OUMSE_PATCHED`, mixed with raw `mtkclient` output. This is fragile compared with structured JSON responses on a dedicated channel.

There are seven import-time monkey patches of `pyserial` and `mtkclient` internals, including `_reconfigure_port`, `usbread`, `usbwrite`, `usbreadwrite`, and `jump_da`. They work around Windows COM re-enumeration, DA jump timing, and blocking serial flushes. This makes the code highly sensitive to upstream and driver changes.

Other concerns:

- Several functions catch `BaseException`, which also catches `KeyboardInterrupt` and `SystemExit`.
- Watchdog threads time out but cannot cancel a blocked native USB call.
- The one-shot runner emits `OUMSE_RESULT:OK` **before** reboot, ignores shutdown failure, and calls `os._exit(0)`. It can therefore report success when the device reboot or USB shutdown failed.
- Entire partitions are read into RAM and rewritten with no backup, checksum, read-back verification, or rollback.
- `VERIFY` mode still rewrites the entire partition unchanged.
- Patch ranges are not fully validated: negative `start` values can wrap around due to Python negative indexing.
- Session `read`/`write`/`erase` commands accept arbitrary partition names and local paths with no allowlist, size limit, or dangerous-partition guard.
- One-shot and persistent runners duplicate connection/patching logic but have diverged behavior.
- `runtime/bin/python312._pth` references `..\OumseMode A1B`, a stale developer-machine path.

### Evidence from committed logs

`runtime/lib/logs/log.txt` contains:

- 521,584 repetitions of `[Errno None] Other error`
- 2,622 `Handshake failed, retrying...`
- 1,076 `Couldn't detect the device. Is it connected ?`
- Hundreds of long tracebacks around `upload_da1`, `jump_da`, `usbwrite`, `rword`, and `configure_da`
- Absolute Windows developer paths and low-level USB traces

This strongly suggests the transport/workaround layer remains unreliable and that production logging is unbounded.

## 6. Security, privacy, and compliance risks

### High priority

1. **Hardcoded remember-me key.** Credentials are obfuscated, not securely encrypted. Replace with Windows Credential Manager/DPAPI and rotate the current key.
2. **Cleartext default server URL.** `http://localhost:8000` is acceptable only for local development. Require HTTPS for production, with certificate validation and a pinned/known host.
3. **Sensitive files committed.** Remove `runtime/lib/logs/log.txt` and `runtime/lib/hwparam.json`; ignore `*.log`, `hwparam.json`, and generated device dumps. Purge them from history if this repository is or will be public.
4. **Unsigned executable wrappers.** Establish reproducible builds, code signing, SHA-256 manifests, and malware scanning.
5. **No source for the main GUI or server.** A binary-only application cannot be safely reviewed, tested, or maintained.
6. **GPL/vendor binary provenance.** Review redistribution rights for `mtkclient`, the vendor-built `MTK_DA_V6.bin`, TestDPC, and all bundled executables/DLLs/APKs.

### Medium priority

7. **Device-destructive operations without safeguards.** Add backups, confirmations, checksums, read-back verification, and an explicit allowlist for erasable partitions.
8. **Unvalidated local command protocol.** If stdin can be influenced by another local process, arbitrary file paths and partition names become a local attack surface.
9. **Anti-analysis behavior and HWID blocking.** The binary contains a large debugger/monitor process list and an automatic account/HWID flag endpoint. Confirm that this behavior is documented, proportionate, and compliant with privacy law and customer contracts.
10. **Unpinned app dependencies.** `requirements.txt` and `pyproject.toml` are unpinned and describe `mtkclient`, not the complete app. Use a lockfile and a reproducible Windows build environment.
11. **Dual-use authorization controls.** Add customer/device ownership attestation, operator identity, audit logs, and server-side authorization for MDM/FRP operations.

## 7. Recommended target architecture

```text
app/                  # GUI source, extracted from the Nuitka build
  ui/
  controllers/
core/                 # device abstractions and safe operation layer
  mtk/
  spd/
  adb/
runners/              # subprocess entry points, one shared implementation
server_contract/      # OpenAPI schema, typed client, mock server
vendor/               # third-party tools with hashes, licenses, and versions
packaging/            # signed installer, Nuitka spec, SBOM, checksums
tests/
  unit/               # patching, protocol, validation, server client
  integration/        # mocked mtkclient/spd/adb
  hardware/           # opt-in device-lab matrix
docs/
  README.md
  architecture.md
  legal-and-compliance.md
  operator-safety.md
```

Replace ad-hoc stdout markers with structured JSON over stdout (or a local IPC channel), keep diagnostics on stderr, and define a versioned schema. Keep upstream `mtkclient` as a pinned submodule/dependency with a small, documented patch set instead of editing a vendored copy.

## 8. Suggested immediate action plan

1. **Recover the missing source:** export `OumseGsmToolPro_ui.py`, `OumseGsmToolProPrivate_ui.py`, `oumse_core.py`, `oumse_server_client.py`, `oumse_tool_i18n.py`, `oumse_spd_cli.py`, and the server API into version control.
2. **Clean the repository:** remove duplicate executables, installer artifacts, the 20 MiB log, device identifiers, and stale runtime files; move large binaries to releases or Git LFS.
3. **Establish a reproducible signed build:** Nuitka/Python version, dependency lock, build script, code signing, checksums, and SBOM.
4. **Harden credentials and transport:** DPAPI/Credential Manager, HTTPS-only production server, token rotation, and removal of hardcoded keys.
5. **Refactor the runners:** merge the two implementations, add typed commands/responses, validate all offsets/paths/partitions, and replace monkey patches with a maintained upstream fork or adapter layer.
6. **Add safety controls:** backups, dry-run, checksums, read-back verification, size limits, dangerous-partition guards, and explicit operator confirmations.
7. **Add CI and tests:** Ruff/format/type checks, unit tests for patching and protocol, mocked hardware integration tests, and an opt-in device-lab harness.
8. **Complete a legal/security review:** GPLv3 obligations, vendor DA/APK redistribution, privacy policy, anti-analysis behavior, and dual-use authorization.

## 9. Bottom line

The artifact is a capable Windows device-service tool with substantial engineering around unreliable MTK USB/COM workflows. However, the repository currently exposes too little source, too many opaque binaries, and too much runtime data. It should be treated as a **release payload**, not a development repository. Recovering the GUI/server source and rebuilding the project around a clean, tested, signed, and license-compliant structure is the single most valuable next step.
