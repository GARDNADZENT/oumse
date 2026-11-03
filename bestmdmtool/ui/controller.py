"""Device controller: owns the runner session, ADB helpers, and worker threads."""

from __future__ import annotations

import queue
import threading
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

from servicecore.adb import AdbTool, FastbootTool, find_adb, find_fastboot
from servicecore.chipsets import scan_report
from servicecore.config import frozen_runner_path, python_executable, runner_command, service_runner_path
from servicecore.service_session import CommandResult, ServiceSession

from ..settings import Settings


class Controller:
    """Single source of truth for device state and background work."""

    def __init__(
        self,
        *,
        log: Callable[[str, str], None],
        on_device: Callable[[dict[str, Any]], None],
        on_disconnect: Callable[[str], None],
        on_progress: Callable[[int, int], None],
        on_busy: Callable[[bool, str], None],
        schedule: Callable[[Callable[[], None]], None],
    ) -> None:
        self.settings = Settings.load()
        self.session: ServiceSession | None = None
        self.adb = AdbTool()
        self.fastboot = FastbootTool()
        self.device: dict[str, Any] = {}
        self.partitions: list[dict[str, Any]] = []
        self.busy = False
        self.last_progress = 0
        self._start_error = ""
        self.engine = "mtk"

        self._log = log
        self._on_device = on_device
        self._on_disconnect = on_disconnect
        self._on_progress = on_progress
        self._on_busy = on_busy
        self._schedule = schedule
        self._poll_job: str | None = None

    # -- helpers -----------------------------------------------------------
    @property
    def connected(self) -> bool:
        return self.session is not None and self.session.is_running

    def log(self, message: str, level: str = "INFO") -> None:
        self._schedule(lambda: self._log(message, level))

    def _set_busy(self, busy: bool, text: str = "") -> None:
        self.busy = busy
        self._schedule(lambda: self._on_busy(busy, text))

    def run_async(self, label: str, work: Callable[[], Any], done: Callable[[Any], None] | None = None) -> None:
        """Run ``work`` in a worker thread, keeping the UI responsive."""

        def _target() -> None:
            self._set_busy(True, label)
            try:
                result = work()
            except Exception as exc:  # surfaced in the log, never crashes the UI
                self.log("%s failed: %s" % (label, exc), "ERROR")
                # Windowed builds have no console, so log the traceback in-app.
                for line in traceback.format_exc().splitlines()[-6:]:
                    self.log(line, "DEBUG")
                result = None
            finally:
                self._set_busy(False, "")
            if done is not None:
                self._schedule(lambda: done(result))
            else:
                del result

        threading.Thread(target=_target, name="svc-worker", daemon=True).start()

    # -- session -----------------------------------------------------------
    def _resolve_engine(self, requested: str) -> str:
        """Pick the engine that matches the hardware on USB.

        ``auto`` follows the detected phone. An explicit choice wins unless it
        contradicts a phone that is sitting in the other vendor's download mode,
        which can never work — then the hardware wins and the switch is logged.
        """

        requested = (requested or "auto").strip().lower()
        try:
            report = scan_report()
        except Exception as exc:  # a broken USB stack must not block connecting
            self.log("USB pre-check failed: %s" % exc, "WARN")
            return requested if requested in ("mtk", "spd") else "mtk"

        download = [item for item in report.get("relevant") or [] if item.get("protocol") not in ("", "unknown")]
        vendors = {str(item.get("vendor") or "").lower() for item in download}
        detected = "spd" if vendors == {"spd"} else "mtk" if vendors == {"mtk"} else ""

        if requested == "auto":
            if detected:
                self.log(
                    "Engine: auto -> %s (matching the phone detected on USB)." % detected.upper(),
                    "INFO",
                )
                return detected
            if not report.get("relevant"):
                self.log(
                    "Engine: auto -> MTK. No download-mode phone detected yet; the MediaTek "
                    "engine also handles PreLoader devices.",
                    "INFO",
                )
                return "mtk"
            return "mtk"

        if detected and detected != requested:
            self.log(
                "Engine: you selected %s, but the phone on USB is %s hardware (%s). Switching to %s."
                % (requested.upper(), detected.upper(), report.get("detail") or "detected", detected.upper()),
                "WARN",
            )
            return detected
        return requested

    def connect(
        self,
        *,
        mode: str,
        transport: str,
        loader: str,
        auth: str,
        debug: bool,
        engine: str = "mtk",
        spd_transport: str = "auto",
        spd_port: str = "",
    ) -> None:
        """Open a session for the chosen engine (``mtk`` BROM or ``spd`` BSL)."""
        if self.connected:
            self.log("A device session is already open.", "WARN")
            return

        def _work() -> bool:
            requested = (engine or "auto").strip().lower()
            self.engine = self._resolve_engine(requested)
            label = "Spreadtrum BSL" if self.engine == "spd" else mode.upper()
            detail = spd_transport if self.engine == "spd" else transport
            self.log("Opening %s session (transport: %s)..." % (label, detail), "STEP")

            argv, cwd = runner_command(self.engine)
            frozen = frozen_runner_path()
            if frozen is not None:
                # The frozen runner reads its engine from argv, so it must be
                # passed through or an SPD session silently runs the MTK stack.
                session = ServiceSession(frozen, frozen, cwd=cwd, args=argv[1:])
            elif self.engine == "spd":
                from servicecore.config import spd_runner_path

                session = ServiceSession(python_executable(), spd_runner_path(), cwd=cwd)
            else:
                session = ServiceSession(python_executable(), service_runner_path(), cwd=cwd)
            self.log("Runner: %s (%s)" % (" ".join(argv), self.engine), "DEBUG")
            self.log("Runner working directory: %s" % cwd, "DEBUG")

            extra_env: dict[str, str] | None = None
            if self.engine == "spd":
                extra_env = {"SPD_TRANSPORT": (spd_transport or "auto").strip().lower()}
                if spd_port:
                    extra_env["SPD_PORT"] = spd_port
            try:
                ok = session.start(
                    mode=mode,
                    transport=transport,
                    loader=loader or None,
                    auth=auth or None,
                    debug=debug,
                    extra_env=extra_env,
                )
            except (FileNotFoundError, RuntimeError) as exc:
                self._start_error = str(exc)
                self.log("Device session failed: %s" % exc, "ERROR")
                self.log("The installed device runner is missing or unusable; reinstall BestMDMTool.", "WARN")
                return False
            if not ok:
                reason = session.last_error or "no response from the runner"
                self.log("Device session failed: %s" % reason, "ERROR")
                for line in session.recent_output(25):
                    self.log(line, "DEBUG")
                session.stop()
                self._start_error = reason
                return False
            self.session = session
            self.device = dict(session.device)
            self.partitions = list(session.partitions)
            self._start_polling(session)
            return True

        def _done(ok: Any) -> None:
            if ok:
                if self.partitions:
                    self.log("Device connected. %d partitions found." % len(self.partitions), "OK")
                else:
                    self.log("Session opened but the partition table is empty.", "WARN")
                self._on_device(self.device)
            else:
                self.log(
                    "Connection failed: %s" % getattr(self, "_start_error", "unknown error"),
                    "ERROR",
                )
                if self.engine == "spd":
                    self.log(
                        "Check the USB cable and the SPD/Unisoc driver, and that the phone is in "
                        "download mode (usually Volume- held while plugging in).",
                        "WARN",
                    )
                else:
                    self.log("Check the cable, USB drivers (UsbDk), and that the phone is in BROM mode.", "WARN")
                self._on_disconnect("connection failed")
                self.session = None
                self.diagnose_connection()

        self.run_async("Connecting to device", _work, _done)

    def run_command(
        self,
        label: str,
        command: dict[str, Any],
        done: Callable[[Any], None] | None = None,
    ) -> None:
        """Send one runner command in a worker thread and hand back the result."""
        session = self.require_session()
        if session is None:
            return

        def _work() -> Any:
            return session.send(command, wait=180.0)

        self.run_async(label, _work, done)

    def scan_usb_devices(self, done: Callable[[list[dict[str, Any]]], None] | None = None) -> None:
        """Look for connected MediaTek/Spreadtrum download devices."""

        def _work() -> dict[str, Any]:
            return scan_report()

        def _done(result: Any) -> None:
            report = dict(result or {})
            devices = list(report.get("relevant") or [])
            self._log_report(report)
            if done is not None:
                done(devices)

        self.run_async("Scanning USB devices", _work, _done)

    def _log_report(self, report: dict[str, Any]) -> None:
        """Print a USB scan the way a technician reads it: facts, then advice."""

        sources = report.get("sources") or {}
        self.log(
            "USB check — pyusb: %s · device tree: %s · serial: %s"
            % (
                "yes" if sources.get("pyusb") else "no",
                "yes" if sources.get("pnp") else "no",
                "yes" if sources.get("serial") else "no",
            ),
            "DEBUG",
        )
        for name, message in (report.get("errors") or {}).items():
            self.log("%s unavailable: %s" % (name, message), "DEBUG")
        devices = list(report.get("devices") or [])
        if devices:
            for entry in devices[:12]:
                self.log(
                    "USB %s  %s  %s%s"
                    % (
                        entry.get("usb"),
                        (entry.get("chip") or "")[:44],
                        ("driver " + str(entry.get("service"))) if entry.get("service") else "no driver",
                        ("  " + str(entry.get("port"))) if entry.get("port") else "",
                    ),
                    "INFO",
                )
        else:
            self.log("No USB devices are visible at all.", "WARN")
        verdict = str(report.get("verdict") or "")
        detail = str(report.get("detail") or "")
        if detail:
            self.log(detail, "OK" if verdict == "download" else "WARN")
        for step in report.get("steps") or []:
            self.log("  -> %s" % step, "INFO")

    def usb_snapshot(self) -> None:
        """One log line at startup: what USB currently looks like."""

        def _work() -> dict[str, Any]:
            return scan_report()

        def _done(result: Any) -> None:
            report = dict(result or {})
            devices = report.get("devices") or []
            level = "OK" if report.get("verdict") == "download" else "INFO"
            self.log(
                "%s (%d USB device%s visible)"
                % (report.get("detail") or "USB scan finished", len(devices), "" if len(devices) == 1 else "s"),
                level,
            )

        self.run_async("Checking USB", _work, _done)

    def diagnose_connection(self, done: Callable[[dict[str, Any]], None] | None = None) -> None:
        """Explain why a connection does not work, including what is on USB."""

        def _work() -> dict[str, Any]:
            report = scan_report()
            adb_lines: list[str] = []
            try:
                for serial, state in self.adb.devices():
                    adb_lines.append("%s (%s)" % (serial, state))
            except Exception:
                adb_lines = []
            report["adb"] = adb_lines
            report["engine"] = getattr(self, "engine", "mtk")
            return report

        def _done(result: Any) -> None:
            report = dict(result or {})
            self.log("Connection doctor", "STEP")
            self._log_report(report)
            adb = list(report.get("adb") or [])
            if adb:
                self.log("ADB sees: %s" % ", ".join(adb), "INFO")
                self.log(
                    "The phone answers ADB, so it is booted into Android. Power it off before "
                    "trying a BROM/BSL connection.",
                    "WARN",
                )
            elif report.get("verdict") == "nothing":
                self.log(
                    "ADB sees nothing either, so the phone is not enumerating as Android or as a "
                    "download port. Try another cable or port, and watch Device Manager while "
                    "plugging it in.",
                    "WARN",
                )
            if done is not None:
                done(report)

        self.run_async("Diagnosing the connection", _work, _done)

    def disconnect(self, *, reboot: bool = False) -> None:
        session = self.session
        self._stop_polling()
        if session is None:
            self._on_disconnect("idle")
            return

        def _work() -> None:
            session.stop(reboot=reboot)

        def _done(_result: Any) -> None:
            self.session = None
            self.device = {}
            self.partitions = []
            self.log("Session closed.", "INFO")
            self._on_disconnect("disconnected")

        self.run_async("Closing session", _work, _done)

    def _start_polling(self, session: ServiceSession) -> None:
        self._stop_polling()

        def _poll() -> None:
            try:
                while True:
                    event = session.events.get_nowait()
                    self._handle_event(event)
            except queue.Empty:
                pass
            except Exception:
                pass
            if self.session is session and session.is_running:
                self._poll_job = self._schedule_after(120, _poll)
            else:
                self._poll_job = None

        self._poll_job = self._schedule_after(120, _poll)

    def _stop_polling(self) -> None:
        if self._poll_job is not None:
            try:
                self._cancel_after(self._poll_job)
            except Exception:
                pass
            self._poll_job = None

    def _handle_event(self, event) -> None:
        kind = event.kind
        if kind == "step":
            matter = event.topic if not event.message else "%s %s" % (event.topic, event.message)
            self._log("» %s" % matter, "STEP")
        elif kind == "log":
            level = (event.topic or "INFO").upper()
            mapped = {"WARNING": "WARN", "ERROR": "ERROR", "DEBUG": "DEBUG"}.get(level, "INFO")
            self._log(event.message, mapped)
        elif kind == "info":
            self.device[event.topic] = event.message
            self._schedule(lambda: self._on_device(self.device))
        elif kind == "progress":
            try:
                value = int(event.topic)
            except (TypeError, ValueError):
                return
            if value != self.last_progress:
                self.last_progress = value
                self._schedule(lambda: self._on_progress(value, 0))
        elif kind == "ok":
            if event.topic not in ("ping",):
                self._log("%s: done%s" % (event.topic, (" (%s)" % event.message) if event.message else ""), "OK")
        elif kind == "fail":
            self._log("%s: failed (%s)" % (event.topic, event.message), "ERROR")
        elif kind == "bye":
            self._log("Device session finished.", "INFO")
        elif kind == "raw":
            text = (event.message or "").strip()
            if text:
                self._log(text, "DEBUG")

    # -- scheduling indirection (keeps this module tkinter-free for tests) --
    def bind_scheduler(
        self,
        after: Callable[[int, Callable[[], None]], str],
        cancel: Callable[[str], None],
    ) -> None:
        self._schedule_after = after
        self._cancel_after = cancel

    def _schedule_after(self, _delay: int, _callback: Callable[[], None]) -> str:  # pragma: no cover
        return ""

    def _cancel_after(self, _job: str) -> None:  # pragma: no cover
        return None

    # -- convenience -------------------------------------------------------
    def require_session(self) -> ServiceSession | None:
        if not self.connected or self.session is None:
            self.log("Connect a device first.", "WARN")
            return None
        return self.session

    def result_ok(self, result: CommandResult | None) -> bool:
        if result is None:
            return False
        if not result.ok:
            self.log("%s failed: %s" % (result.op, result.detail), "ERROR")
        return result.ok

    def refresh_partitions(self, done: Callable[[list[dict[str, Any]]], None] | None = None) -> None:
        session = self.require_session()
        if session is None:
            return

        def _work():
            return session.refresh_gpt()

        def _done(parts: Any) -> None:
            self.partitions = list(parts or [])
            if done is not None:
                done(self.partitions)

        self.run_async("Reading partition table", _work, _done)

    def run_backend_selftest(self, done: Callable[[dict[str, Any]], None] | None = None) -> None:
        """Ask the device runner to check itself and log the outcome."""
        from servicecore import selfcheck

        def _work() -> dict[str, Any]:
            return selfcheck.run()

        def _done(result: Any) -> None:
            report = result if isinstance(result, dict) else {}
            healthy = bool(report.get("ok"))
            self.log(
                "Backend self-test %s in %.2fs."
                % ("passed" if healthy else "FAILED", float(report.get("duration") or 0.0)),
                "OK" if healthy else "ERROR",
            )
            for line in report.get("lines") or []:
                self.log(line, "INFO")
            if not healthy:
                self.log("Cause: %s" % selfcheck.describe_failure(report), "ERROR")
                self.log(selfcheck.environment_hint(), "WARN")
            if done is not None:
                done(report)

        self.run_async("Backend self-test", _work, _done)

    def export_support_bundle(self, done: Callable[[Any], None] | None = None) -> None:
        """Collect logs, a self-test result and device state into one zip."""
        from servicecore import selfcheck

        from ..support import build as build_bundle

        device = dict(self.device)
        partitions = list(self.partitions)
        settings = {
            "mode": self.settings.mode,
            "transport": self.settings.transport,
            "debug_log": self.settings.debug_log,
            "confirm_destructive": self.settings.confirm_destructive,
            "loader": self.settings.loader,
            "auth": self.settings.auth,
        }

        def _work() -> Any:
            report: dict[str, Any] = {}
            try:
                report = selfcheck.run()
            except Exception as exc:  # a broken self-test must not lose the log
                report = {"ok": False, "error": str(exc)}
            return build_bundle(
                device=device,
                partitions=partitions,
                settings=settings,
                selftest=report,
            )

        def _done(path: Any) -> None:
            if not path:
                self.log("Could not write the support bundle.", "ERROR")
                return
            self.log("Support bundle written to %s" % path, "OK")
            self.log("Attach that file to a bug report; it contains no credentials.", "INFO")
            if done is not None:
                done(path)

        self.run_async("Writing support bundle", _work, _done)

    def report_tools(self) -> None:
        adb = find_adb()
        fastboot = find_fastboot()
        self.log("ADB: %s" % (adb if adb else "not found"), "INFO")
        self.log("Fastboot: %s" % (fastboot if fastboot else "not found"), "INFO")
        frozen = frozen_runner_path()
        if frozen is not None:
            self.log("Runner: %s (frozen)" % frozen, "INFO")
        else:
            self.log("Runner: %s (source)" % Path(service_runner_path()).name, "INFO")
            self.log("Python: %s" % python_executable(), "INFO")
