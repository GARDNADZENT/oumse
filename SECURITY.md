# Security Policy and Posture

## Current state

The new `app/` front-end is designed to be offline and login-free. It does not contain a
licensing client, heartbeat, telemetry, anti-analysis logic, or network code. Unit tests in
`tests/test_no_login.py` enforce this.

## v0.5.2 field incident and containment

The v0.5.2 MediaTek log showed the bundled `DaHandler.configure_da()` path
invoking a security-bypass/exploitation routine (`Kamakiri`) and patching the
Download Agent. The same session reported an `Exceed available range` error
while formatting `userdata`, then surfaced **"Erase complete"** because the
runner ignored the per-partition result. Further erase attempts failed. The
phone's final data state cannot be determined from logs; do not claim that the
erase completed or that the data is intact.

BestMDMTool v0.5.3 is a containment release: MTK connect is refused before the
runner starts, the frozen runner itself fails closed, and the BestMDMTool
installer no longer includes mtkclient, DA loaders, or legacy Oumse runners.
Erase/read result handling also fails closed. Only the SPD/Unisoc engine is
currently enabled. v0.5.2 is withdrawn; do not use it for device operations.

## Completed in the security/cleanup pass

- Removed `runtime/lib/logs/log.txt` (20 MiB, 532k lines, developer paths, USB traces).
- Removed `runtime/lib/hwparam.json` (MEID, hardware code, SOC ID).
- Removed the empty `runtime/lib/python` file.
- Removed duplicate executables:
  - `OumseGsmToolPro.exe,` (VB6 wrapper containing a copy of the main executable);
  - `oumsegsmtoolpro.exe ` with a trailing non-breaking space (byte-identical duplicate).
- Removed `unins000.exe` and `unins000.dat` installer artifacts.
- Moved the original compiled client to `legacy/` so it is not the default launch target.
- Added `legacy/README.md` warning that the old binary must not be used or redistributed.
- Hardened `.gitignore` for logs, device identifiers, remember-me files, server config,
  secrets, backups, and accidental Windows copy filenames.
- Added `README.md`, `SECURITY.md`, CI, and unit tests.
- Added safe local patching with validation, backups, checksums, and atomic writes.
- Added partition-name validation and critical-partition erase guards.
- Added reproducible Windows installers for both no-login apps; they exclude the legacy login
  executable, committed logs, device identifiers, tests, and Git metadata. The `.exe` files build
  on Windows CI runners.
- Added BestMDMTool as a separate no-login product. It does not include the legacy login,
  MDM/FRP bypass, credential, or licensing-bypass code.

## Residual risks

| Risk | Status |
|---|---|
| Hardcoded remember-me key in legacy executable | Still present in `legacy/OumseGsmToolPro.exe`; do not use that binary. |
| Login/licensing server dependency | Removed from the new GUI; server source is still absent from this repository. |
| Unsigned Windows executables | All shipped binaries remain unsigned. Code signing and reproducible builds are still needed. |
| Vendor DA binary provenance | DA loaders remain in the source checkout but are excluded from the BestMDMTool v0.5.3 installer. Provenance and legal review remain open before any future MTK distribution. |
| GPLv3 compliance | A full compliance review for the repository and any future compiled MTK distribution is still required. |
| Third-party SBOM | No complete software bill of materials with versions, hashes, and licenses yet. |
| Device-destructive operations | The new GUI adds confirmations and guards, but device writes have no rollback. Keep full dumps. |
| Runtime monkey patches | The two original runners in `runtime/lib/` still patch `pyserial`/`mtkclient` internals and should be refactored. |
| Binary wrapper analysis | The deleted VB6 wrapper had process/registry/download imports. Static indicators only; dynamic analysis was not performed here. |

## Recommendations still open

1. Build and sign all Windows executables from source.
2. Publish SHA-256 checksums and a complete SBOM for every release.
3. Replace the legacy compiled client entirely; do not ship it to end users.
4. Refactor `oumse_brom_runner.py` and `oumse_brom_session_runner.py` into one maintained
   package with a versioned JSON protocol.
5. Add hardware-in-the-loop tests and driver/device compatibility matrix.
6. Complete GPLv3 and vendor-binary redistribution review.
7. Add explicit operator authorization and audit logging for MDM/FRP operations.

## Reporting a security issue

Do not commit credentials, device identifiers, logs, or dump files. If you find a security
problem, report it privately to the repository maintainer and include reproduction steps
without attaching real customer device data.
