# Build artifacts

Generated installers and portable ZIPs are written to this directory by:

- `installer-bestmdmtool\build_installer.bat` (Windows, Inno Setup 6)
- `python installer-bestmdmtool/build_portable.py` (cross-platform portable ZIP)

Generated binaries are ignored by Git. This directory is kept only so build
scripts have a stable output location. Do not commit `.exe`, `.zip`, `.sha256`,
or `SHA256SUMS.txt` files.
