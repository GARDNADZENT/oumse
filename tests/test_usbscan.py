"""Tests for USB discovery, driver reporting and the connection verdicts."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from servicecore import chipsets, usbscan

ROOT = Path(__file__).resolve().parents[1]

PNP_PAYLOAD = json.dumps(
    [
        {
            "Name": "MediaTek USB Port (COM3)",
            "DeviceID": "USB\\VID_0E8D&PID_0003&MI_00\\7&1A2B3C4D&0&0000",
            "Service": "usbser",
            "Status": "OK",
            "ConfigManagerErrorCode": 0,
        },
        {
            "Name": "SPRD U2S Diag",
            "DeviceID": "USB\\VID_1782&PID_4D00\\5&2B3C4D5E&0&1",
            "Service": "WinUSB",
            "Status": "OK",
            "ConfigManagerErrorCode": 0,
        },
        {
            "Name": "USB Composite Device",
            "DeviceID": "USB\\VID_1D6B&PID_0002\\0000",
            "Service": "usbccgp",
            "Status": "OK",
            "ConfigManagerErrorCode": 0,
        },
    ]
)


def _device(vid, pid, **kwargs):
    return usbscan.UsbDevice(vid=vid, pid=pid, **kwargs)


def _report(devices, **kwargs):
    report = usbscan.UsbReport(devices=list(devices), relevant=[d for d in devices if d.vendor], **kwargs)
    report.verdict, report.detail, report.steps = usbscan._verdict(report)
    return report


class ParsingTests(unittest.TestCase):
    def test_powershell_json_shapes(self) -> None:
        self.assertEqual(usbscan._loads(""), [])
        self.assertEqual(usbscan._loads("noise"), [])
        self.assertEqual(len(usbscan._loads('{"Name": "one"}')), 1)
        self.assertEqual(len(usbscan._loads('[{"Name": "a"}, {"Name": "b"}]')), 2)
        self.assertEqual(len(usbscan._loads('warning: something\n[{"Name": "a"}]')), 1)

    def test_device_id_and_port_parsing(self) -> None:
        match = usbscan.DEVICE_ID_RE.search("USB\\VID_0e8d&PID_2000&MI_00\\7&1")
        self.assertIsNotNone(match)
        self.assertEqual(int(match.group(1), 16), 0x0E8D)
        self.assertEqual(int(match.group(2), 16), 0x2000)
        self.assertEqual(usbscan.COMPORT_RE.search("MediaTek USB Port (COM12)").group(1), "12")

    def test_pnp_devices_are_parsed_with_driver_and_port(self) -> None:
        with mock.patch.object(usbscan, "_run_powershell", return_value=PNP_PAYLOAD):
            with mock.patch.object(usbscan.os, "name", "nt"):
                devices = usbscan.pnp_devices()
        self.assertEqual(len(devices), 3)
        mtk = next(d for d in devices if d.vid == 0x0E8D)
        self.assertEqual(mtk.pid, 0x0003)
        self.assertEqual(mtk.port, "COM3")
        self.assertEqual(mtk.service, "usbser")
        self.assertEqual(mtk.download_mode, "PreLoader")
        spd = next(d for d in devices if d.vid == 0x1782)
        self.assertEqual(spd.download_mode, "BSL")
        self.assertTrue(spd.openable)
        self.assertFalse(mtk.openable)

    def test_serial_ports_become_devices_only_with_a_vendor_id(self) -> None:
        ports = [
            {"device": "COM7", "description": "MTK USB Port", "hwid": "USB VID:PID=0E8D:0003"},
            {"device": "COM9", "description": "Communications Port", "hwid": "ACPI\\PNP0501"},
        ]
        devices = usbscan.serial_devices(ports)
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].port, "COM7")
        self.assertEqual(devices[0].download_mode, "PreLoader")


class VerdictTests(unittest.TestCase):
    def test_download_mode_is_recognised(self) -> None:
        report = _report([_device(0x0E8D, 0x2000, name="MTK BROM", service="WinUSB")], sources={"pyusb": True})
        self.assertEqual(report.verdict, "download")
        self.assertIn("BROM", report.detail)
        self.assertTrue(any("WinUSB" in step or "winusb" in step.lower() for step in report.steps))

    def test_wrong_driver_names_the_problem(self) -> None:
        report = _report(
            [_device(0x0E8D, 0x0003, name="MediaTek USB Port", service="usbser")],
            sources={"pyusb": True},
        )
        self.assertEqual(report.verdict, "download")
        self.assertTrue(any("cannot be opened" in step for step in report.steps))
        self.assertTrue(any("usbser" in step for step in report.steps))

    def test_spreadtrum_on_a_com_port_uses_the_serial_transport(self) -> None:
        report = _report(
            [_device(0x1782, 0x4D00, name="SPRD U2S Diag (COM7)", service="usbser", port="COM7")],
            sources={"serial": True},
        )
        self.assertEqual(report.verdict, "download")
        self.assertTrue(any("SPD transport to 'serial'" in step for step in report.steps))
        self.assertFalse(any("Bind WinUSB" in step for step in report.steps))

    def test_vendor_present_but_not_downloading(self) -> None:
        report = _report([_device(0x1782, 0x9999, name="SPRD something")], sources={"pyusb": True})
        self.assertEqual(report.verdict, "present_not_download")
        self.assertIn("not in a download mode", report.detail)
        self.assertTrue(any("hold the download keys" in step for step in report.steps))

    def test_android_mode_gets_power_off_advice(self) -> None:
        report = _report(
            [_device(0x18D1, 0x4EE7, name="Android ADB Interface")], sources={"pyusb": True}
        )
        self.assertEqual(report.verdict, "android")
        self.assertTrue(any("Power the phone off" in step for step in report.steps))

    def test_missing_pyusb_is_reported_as_a_backend_problem(self) -> None:
        report = _report([], sources={"pyusb": True, "pnp": True}, errors={"pyusb": "NoBackendError: no backend"})
        self.assertEqual(report.verdict, "backend")
        self.assertIn("NoBackendError", report.detail)

    def test_nothing_visible_has_a_checklist(self) -> None:
        report = _report([], sources={"pyusb": True, "pnp": True})
        self.assertEqual(report.verdict, "nothing")
        self.assertGreaterEqual(len(report.steps), 2)

    def test_no_usb_library_at_all(self) -> None:
        report = _report([], sources={"pyusb": False, "pnp": False, "serial": False})
        self.assertEqual(report.verdict, "no_tools")


class ScanTests(unittest.TestCase):
    def test_scan_merges_sources_and_prefers_the_device_tree(self) -> None:
        pnp = [_device(0x0E8D, 0x2000, name="MTK USB Port", service="WinUSB", source="pnp")]
        pyusb = [_device(0x0E8D, 0x2000, name="", source="pyusb"), _device(0x1D6B, 0x0002, source="pyusb")]
        with mock.patch.object(usbscan, "pnp_devices", return_value=pnp), mock.patch.object(
            usbscan, "pyusb_devices", return_value=pyusb
        ), mock.patch.object(usbscan, "serial_ports", return_value=[]), mock.patch.object(
            usbscan, "interface_status", return_value={"pyusb": True, "pyserial": True}
        ):
            report = usbscan.scan()
        self.assertEqual(report.verdict, "download")
        self.assertEqual(len(report.devices), 2)
        mtk = next(d for d in report.devices if d.vid == 0x0E8D)
        self.assertEqual(mtk.source, "pnp")
        self.assertEqual(mtk.name, "MTK USB Port")

    def test_scan_does_not_hide_programming_errors(self) -> None:
        """A broken environment raises, so the console shows the real cause."""

        with mock.patch.object(usbscan, "pnp_devices", return_value=[]), mock.patch.object(
            usbscan, "pyusb_devices", return_value=[]
        ), mock.patch.object(usbscan, "serial_ports", side_effect=ImportError("broken")), mock.patch.object(
            usbscan, "interface_status", return_value={"pyusb": True, "pyserial": True}
        ):
            report = usbscan.scan()
        self.assertEqual(report.devices, [])

    def test_scan_report_shape(self) -> None:
        with mock.patch.object(usbscan, "pnp_devices", return_value=[]), mock.patch.object(
            usbscan, "pyusb_devices", return_value=[]
        ), mock.patch.object(usbscan, "serial_ports", return_value=[]), mock.patch.object(
            usbscan, "interface_status", return_value={"pyusb": True, "pyserial": True}
        ):
            report = chipsets.scan_report()
        for key in ("devices", "relevant", "ports", "sources", "verdict", "detail", "steps"):
            self.assertIn(key, report)
        self.assertEqual(report["devices"], [])

    def test_scan_usb_keeps_the_old_entry_shape(self) -> None:
        device = _device(0x0E8D, 0x2000, name="MTK BROM", service="WinUSB", source="pnp")
        fake = usbscan.UsbReport(devices=[device], relevant=[device], verdict="download")
        with mock.patch.object(usbscan, "scan", return_value=fake):
            entries = chipsets.scan_usb()
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        for key in ("vid", "pid", "usb", "vendor", "chip", "protocol"):
            self.assertIn(key, entry)
        self.assertEqual(entry["usb"], "0E8D:2000")


class BuildConfigTests(unittest.TestCase):
    """The GUI has to carry the USB libraries: without them detection is blind."""

    def test_gui_bundle_collects_the_usb_libraries(self) -> None:
        script = (ROOT / "installer-bestmdmtool" / "build_exe.ps1").read_text(encoding="utf-8")
        gui_block = script.split("Building BestMDMTool.exe (GUI)")[1].split("Building BestMDMToolRunner.exe")[0]
        for package in ("usb", "serial", "libusb"):
            with self.subTest(package=package):
                self.assertIn('--collect-all", "%s"' % package, gui_block)

    def test_frozen_selftest_requires_the_usb_libraries(self) -> None:
        entry = (ROOT / "installer-bestmdmtool" / "pyinstaller_entry.py").read_text(encoding="utf-8")
        self.assertIn("usb_interfaces", entry)
        self.assertIn('report["usb_ok"]', entry)
        self.assertIn('and report["usb_ok"]', entry)

    def test_workflow_fails_when_usb_libraries_are_missing(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "build-bestmdmtool-installer.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("$json.usb_ok", workflow)


if __name__ == "__main__":
    unittest.main()
