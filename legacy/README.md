# Legacy executable — reference only

`OumseGsmToolPro.exe` in this directory is the original compiled Windows client. It is retained
only so the historical release can be inspected.

**Do not use or redistribute it as the primary application.** The binary:

- displays a login screen and depends on a separate licensing server;
- contains a hardcoded remember-me obfuscation key;
- contains anti-analysis/HWID-flagging logic;
- is unsigned and has no reproducible build recipe in this repository.

Use `START_NO_LOGIN.bat` in the repository root instead. That launcher starts the new
`app/` front-end, which opens directly and contains no login, licensing, or telemetry code.
