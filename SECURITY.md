# Security Policy and Posture

## Current state

The new `app/` front-end is designed to be offline and login-free. It does not contain a
licensing client, heartbeat, telemetry, anti-analysis logic, or network code. Unit tests in
`tests/test_no_login.py` enforce this.

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
| Vendor DA binary provenance | `runtime/lib/mtkclient/Loader/MTK_DA_V6.bin` differs from upstream and contains internal vendor build paths. Legal review required. |
| GPLv3 compliance | `runtime/lib/LICENSE` is present, but a full compliance review for the compiled product and bundled binaries is still required. |
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
