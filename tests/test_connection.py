"""Tests for the connect path: engine choice, runner arguments, scratch dir.

These cover the 0.5.1 field failure, where an SPD session silently ran the
MediaTek runner and mtkclient then died writing ``.hwparam.json`` into a
read-only ``Program Files`` directory.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from servicecore import adb, config, service_session, usbscan

ROOT = Path(__file__).resolve().parents[1]


def _device(vid, pid, **kwargs):
    return usbscan.UsbDevice(vid=vid, pid=pid, **kwargs)


def _report(devices):
    relevant = [d for d in devices if d.vendor]
    report = usbscan.UsbReport(devices=list(devices), relevant=relevant)
    report.verdict, report.detail, report.steps = usbscan._verdict(report)
    return {
        "devices": [d.as_dict() for d in devices],
        "relevant": [d.as_dict() for d in relevant],
        "verdict": report.verdict,
        "detail": report.detail,
        "steps": report.steps,
    }


class RunnerArgumentsTests(unittest.TestCase):
    """The frozen runner picks its engine from argv; losing it broke SPD."""

    def _capture(self, **kwargs) -> list[str]:
        captured: dict[str, list[str]] = {}

        class FakeProc:
            returncode = 0
            stdin = None
            stdout = None

            def poll(self):
                return 0

        def fake_popen(command, **popen_kwargs):
            captured["command"] = list(command)
            captured["cwd"] = popen_kwargs.get("cwd")
            captured["env"] = popen_kwargs.get("env") or {}
            return FakeProc()

        with mock.patch.object(service_session.subprocess, "Popen", side_effect=fake_popen):
            session = service_session.ServiceSession(**kwargs)
            session.start(wait=0.05)
        return captured

    def test_packaged_runner_receives_the_engine_argument(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        exe = tmp / "BestMDMToolRunner.exe"
        exe.write_bytes(b"")
        captured = self._capture(python_exe=exe, runner_path=exe, cwd=tmp, args=["--engine", "spd"])
        self.assertEqual(captured["command"][0], str(exe))
        self.assertEqual(captured["command"][1:], ["--engine", "spd"])

    def test_packaged_runner_without_arguments_stays_sequential(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        exe = tmp / "BestMDMToolRunner.exe"
        exe.write_bytes(b"")
        captured = self._capture(python_exe=exe, runner_path=exe, cwd=tmp)
        self.assertEqual(captured["command"], [str(exe)])

    def test_source_runner_also_receives_arguments(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        script = tmp / "runner.py"
        script.write_text("print('')", encoding="utf-8")
        captured = self._capture(
            python_exe=Path(sys.executable), runner_path=script, cwd=tmp, args=["--engine", "spd"]
        )
        self.assertEqual(captured["command"][1:3], ["-u", str(script)])
        self.assertEqual(captured["command"][3:], ["--engine", "spd"])

    def test_runner_starts_in_a_writable_directory(self) -> None:
        """Program Files is read-only; mtkclient writes .hwparam.json to cwd."""

        tmp = Path(tempfile.mkdtemp())
        exe = tmp / "BestMDMToolRunner.exe"
        exe.write_bytes(b"")
        captured = self._capture(python_exe=exe, runner_path=exe, cwd=config.work_dir())
        self.assertEqual(Path(captured["cwd"]), config.work_dir())
        self.assertTrue(os.access(captured["cwd"], os.W_OK))


class ConnectWiringTests(unittest.TestCase):
    """``Controller.connect`` must hand the engine to the frozen runner."""

    def setUp(self) -> None:
        from tests.tk_stub import install_fake_tkinter

        install_fake_tkinter()
        from bestmdmtool.ui.controller import Controller

        self.controller = Controller(
            log=lambda *_: None,
            on_device=lambda *_: None,
            on_disconnect=lambda *_: None,
            on_progress=lambda *_: None,
            on_busy=lambda *_: None,
            schedule=lambda callback: callback(),
        )
        self.logs: list[tuple[str, str]] = []
        self.controller._log = lambda message, level="INFO": self.logs.append((level, message))

    def _connect(self, engine: str, devices, argv):
        seen: dict[str, object] = {}

        class FakeSession:
            is_running = True
            last_error = ""
            device: dict = {}
            partitions: list = []

            def __init__(self, python_exe, runner_path, **kwargs):
                seen["args"] = kwargs.get("args")
                seen["cwd"] = kwargs.get("cwd")

            def start(self, **kwargs):
                return True

            def stop(self, **kwargs):
                return None

            def recent_output(self, _count=25):
                return []

        with mock.patch(
            "bestmdmtool.ui.controller.scan_report", return_value=_report(devices)
        ), mock.patch(
            "bestmdmtool.ui.controller.runner_command", return_value=(argv, config.work_dir())
        ), mock.patch(
            "bestmdmtool.ui.controller.frozen_runner_path", return_value=Path("/fake/BestMDMToolRunner.exe")
        ), mock.patch(
            "bestmdmtool.ui.controller.ServiceSession", FakeSession
        ), mock.patch.object(self.controller, "_start_polling", lambda *_: None):
            self.controller.connect(
                mode="brom",
                transport="auto",
                loader="",
                auth="",
                debug=False,
                engine=engine,
                spd_transport="auto",
                spd_port="",
            )
        return seen

    def test_frozen_spd_session_is_started_with_engine_spd(self) -> None:
        spd = _device(0x1782, 0x4D00, name="SPRD BSL", port="COM7")
        argv = ["/fake/BestMDMToolRunner.exe", "--engine", "spd"]
        seen = self._connect("auto", [spd], argv)
        self.assertEqual(seen["args"], ["--engine", "spd"])
        self.assertEqual(Path(seen["cwd"]), config.work_dir())

    def test_auto_without_a_download_device_never_starts_a_runner(self) -> None:
        seen = self._connect("auto", [], ["/fake/BestMDMToolRunner.exe"])
        self.assertEqual(self.controller.engine, "none")
        self.assertEqual(seen, {})
        self.assertEqual(self.controller._start_error, "no_download_mode_device")

    def test_mtk_session_is_blocked_before_any_runner_starts(self) -> None:
        mtk = _device(0x0E8D, 0x0003, name="MediaTek USB Port", service="wdm_usb", port="COM32")
        seen = self._connect("auto", [mtk], ["/fake/BestMDMToolRunner.exe"])
        self.assertEqual(self.controller.engine, "mtk")
        self.assertEqual(seen, {})
        self.assertIn("mtk_temporarily_disabled_security_review", self.controller._start_error)
        self.assertTrue(any("No runner was started" in message for _level, message in self.logs))

    def test_usb_report_distinguishes_pyusb_from_libusb_backend(self) -> None:
        self.controller._log_report(
            {
                "sources": {"pyusb": True, "libusb": False, "pnp": True, "serial": True},
                "errors": {"pyusb": "NoBackendError: No backend available"},
                "devices": [],
                "verdict": "backend",
                "detail": "backend unavailable",
                "steps": [],
            }
        )
        self.assertTrue(any("module yes / libusb backend unavailable" in text for _level, text in self.logs))

    def test_engine_mismatch_is_corrected_then_mtk_is_blocked(self) -> None:
        mtk = _device(0x0E8D, 0x0003, name="MediaTek USB Port", service="wdm_usb", port="COM32")
        seen = self._connect("spd", [mtk], ["/fake/BestMDMToolRunner.exe"])
        self.assertEqual(self.controller.engine, "mtk")
        self.assertEqual(seen, {})
        self.assertIn("mtk_temporarily_disabled_security_review", self.controller._start_error)
        self.assertTrue(any("Switching to MTK" in message for _level, message in self.logs))


class WorkDirTests(unittest.TestCase):
    def test_work_dir_is_created_and_writable(self) -> None:
        path = config.work_dir()
        self.assertTrue(path.is_dir())
        probe = path / "probe.txt"
        probe.write_text("ok", encoding="utf-8")
        self.assertEqual(probe.read_text(encoding="utf-8"), "ok")
        probe.unlink()

    def test_work_dir_prefers_local_appdata(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        config.work_dir.cache_clear()
        try:
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(tmp)}, clear=False):
                path = config.work_dir()
            self.assertEqual(path, tmp / "BestMDMTool" / "work")
            self.assertTrue(path.is_dir())
        finally:
            config.work_dir.cache_clear()

    def test_runner_command_never_returns_the_install_dir_as_cwd(self) -> None:
        argv, cwd = config.runner_command("spd")
        self.assertTrue(argv)
        self.assertEqual(cwd, config.work_dir())


class EngineChoiceTests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.tk_stub import install_fake_tkinter

        install_fake_tkinter()
        from bestmdmtool.ui.controller import Controller

        self.controller = Controller(
            log=lambda *_: None,
            on_device=lambda *_: None,
            on_disconnect=lambda *_: None,
            on_progress=lambda *_: None,
            on_busy=lambda *_: None,
            schedule=lambda callback: callback(),
        )
        self.logs: list[tuple[str, str]] = []
        self.controller._log = lambda message, level="INFO": self.logs.append((level, message))

    def _resolve(self, requested: str, devices) -> str:
        with mock.patch(
            "bestmdmtool.ui.controller.scan_report", return_value=_report(devices)
        ):
            return self.controller._resolve_engine(requested)

    def test_auto_follows_a_spreadtrum_phone(self) -> None:
        spd = _device(0x1782, 0x4D00, name="SPRD U2S Diag (COM7)", service="usbser", port="COM7")
        self.assertEqual(self._resolve("auto", [spd]), "spd")

    def test_auto_follows_a_mediatek_phone(self) -> None:
        mtk = _device(0x0E8D, 0x0003, name="MediaTek USB Port", service="wdm_usb", port="COM32")
        self.assertEqual(self._resolve("auto", [mtk]), "mtk")

    def test_auto_does_not_launch_an_engine_without_download_mode_hardware(self) -> None:
        self.assertEqual(self._resolve("auto", []), "none")

    def test_explicit_spd_is_overridden_by_mediatek_hardware(self) -> None:
        """The 0.5.1 field case: SPD selected, MediaTek phone plugged in."""

        mtk = _device(0x0E8D, 0x0003, name="MediaTek USB Port", service="wdm_usb", port="COM32")
        self.assertEqual(self._resolve("spd", [mtk]), "mtk")
        self.assertTrue(any("Switching to MTK" in message for _level, message in self.logs))

    def test_explicit_choice_is_kept_when_it_matches(self) -> None:
        spd = _device(0x1782, 0x4D00, name="SPRD BSL", port="COM7")
        self.assertEqual(self._resolve("spd", [spd]), "spd")

    def test_explicit_choice_is_kept_without_hardware(self) -> None:
        self.assertEqual(self._resolve("spd", []), "spd")

    def test_a_broken_usb_stack_does_not_block_connecting(self) -> None:
        with mock.patch(
            "bestmdmtool.ui.controller.scan_report", side_effect=RuntimeError("boom")
        ):
            self.assertEqual(self.controller._resolve_engine("spd"), "spd")
        self.assertTrue(any("USB pre-check failed" in message for _level, message in self.logs))

    def test_an_android_mode_phone_does_not_start_a_download_runner(self) -> None:
        phone = _device(0x2D95, 0x6002, name="Y04", service="WUDFWpdMtp")
        self.assertEqual(self._resolve("auto", [phone]), "none")


class InterfaceCheckTests(unittest.TestCase):
    def test_a_missing_backend_attribute_is_not_an_error(self) -> None:
        """pyusb has no ``usb.core.backend``; probing it produced a false alarm."""

        fake_core = type("core", (), {"find": staticmethod(lambda **kwargs: [1, 2, 3])})
        fake_usb = type("usb", (), {"core": fake_core})
        with mock.patch.dict(sys.modules, {"usb": fake_usb, "usb.core": fake_core}):
            status = usbscan.interface_status()
        self.assertTrue(status["pyusb"])
        self.assertEqual(status["pyusb_error"], "")
        self.assertEqual(status["libusb"], "available")

    def test_frozen_windows_uses_the_dll_beside_the_executable(self) -> None:
        import types

        temp = Path(tempfile.mkdtemp())
        exe = temp / "BestMDMTool.exe"
        exe.write_bytes(b"")
        dll = temp / "libusb-1.0.dll"
        dll.write_bytes(b"dll")
        seen: dict[str, object] = {}
        backend_obj = object()
        core = types.ModuleType("usb.core")

        def find(**kwargs):
            seen.update(kwargs)
            return []

        core.find = find
        usb = types.ModuleType("usb")
        usb.__path__ = []
        backend_pkg = types.ModuleType("usb.backend")
        backend_pkg.__path__ = []
        libusb1 = types.ModuleType("usb.backend.libusb1")

        def get_backend(*, find_library):
            seen["dll"] = find_library("libusb-1.0.dll")
            return backend_obj

        libusb1.get_backend = get_backend
        backend_pkg.libusb1 = libusb1
        usb.core = core
        usb.backend = backend_pkg
        modules = {"usb": usb, "usb.core": core, "usb.backend": backend_pkg, "usb.backend.libusb1": libusb1}
        with mock.patch.dict(sys.modules, modules), mock.patch.object(
            usbscan.sys, "platform", "win32"
        ), mock.patch.object(usbscan.sys, "executable", str(exe)), mock.patch.object(
            usbscan.sys, "frozen", True, create=True
        ):
            status = usbscan.interface_status()
        self.assertEqual(seen["dll"], str(dll))
        self.assertIs(seen["backend"], backend_obj)
        self.assertEqual(status["libusb"], "available")
        self.assertEqual(status["pyusb_error"], "")

    def test_a_real_backend_failure_is_reported(self) -> None:
        def boom(**kwargs):
            raise OSError("No backend available")

        fake_core = type("core", (), {"find": staticmethod(boom)})
        fake_usb = type("usb", (), {"core": fake_core})
        with mock.patch.dict(sys.modules, {"usb": fake_usb, "usb.core": fake_core}):
            status = usbscan.interface_status()
        self.assertIn("No backend available", status["pyusb_error"])


class AdbParsingTests(unittest.TestCase):
    def _devices(self, text: str):
        tool = adb.AdbTool()
        output = adb.CommandOutput(True, 0, text, "adb devices")
        with mock.patch.object(adb.AdbTool, "run", return_value=output):
            return tool.devices()

    def test_daemon_chatter_is_not_a_phone(self) -> None:
        text = (
            "* daemon not running; starting now at tcp:5037\n"
            "* daemon started successfully\n"
            "List of devices attached\n"
        )
        self.assertEqual(self._devices(text), [])

    def test_real_devices_are_kept(self) -> None:
        text = (
            "* daemon not running; starting now at tcp:5037\n"
            "List of devices attached\n"
            "ABC123\tdevice\n"
            "DEF456\tunauthorized\n"
        )
        self.assertEqual(self._devices(text), [("ABC123", "device"), ("DEF456", "unauthorized")])

    def test_headers_and_blank_lines_are_ignored(self) -> None:
        text = "\nList of devices attached\n\n"
        self.assertEqual(self._devices(text), [])


class DoctorVerdictTests(unittest.TestCase):
    def test_pyusb_failure_with_visible_devices_is_not_a_backend_error(self) -> None:
        report = usbscan.UsbReport(
            devices=[_device(0x1D6B, 0x0002, name="USB Hub")],
            relevant=[],
            sources={"pyusb": True, "pnp": True},
            errors={"pyusb": "NoBackendError: no backend"},
        )
        report.verdict, report.detail, report.steps = usbscan._verdict(report)
        self.assertEqual(report.verdict, "nothing")
        self.assertIn("Windows sees 1 USB device", report.detail)
        self.assertIn("NoBackendError", report.detail)

    def test_an_mtp_phone_is_recognised_even_without_a_vendor_id(self) -> None:
        """The field log showed 'Y04' bound to WUDFWpdMtp: a booted phone."""

        phone = _device(0x2D95, 0x6002, name="Y04", service="WUDFWpdMtp")
        report = usbscan.UsbReport(devices=[phone], relevant=[], sources={"pnp": True})
        report.verdict, report.detail, report.steps = usbscan._verdict(report)
        self.assertEqual(report.verdict, "android")
        self.assertIn("WUDFWpdMtp", report.detail)
        self.assertTrue(any("different phone" in step.lower() for step in report.steps))

    def test_mediatek_download_mode_does_not_claim_openability(self) -> None:
        report = usbscan.UsbReport(
            devices=[_device(0x0E8D, 0x0003, name="MediaTek USB Port", service="wdm_usb", port="COM32")],
            relevant=[_device(0x0E8D, 0x0003, name="MediaTek USB Port", service="wdm_usb", port="COM32")],
            sources={"pyusb": True, "pnp": True},
        )
        report.verdict, report.detail, report.steps = usbscan._verdict(report)
        self.assertEqual(report.verdict, "download")
        self.assertTrue(any("sessions pending a security review" in step for step in report.steps))
        self.assertFalse(any("Press Connect" in step for step in report.steps))


if __name__ == "__main__":
    unittest.main()
