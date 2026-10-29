from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = [ROOT / "app", ROOT / "servicecore", ROOT / "bestmdmtool"]

FORBIDDEN_TOKENS = (
    "_show_login",
    "_do_login",
    "OumseGsmServer",
    "check_server_reachable",
    "/api/log" + "in",
    "/api/heartbeat",
    "/api/",
    "http://",
    "https://",
    "urllib",
    "requests",
    "socket",
    "server_config",
    "remember.dat",
    "heartbeat",
)


class BestMDMToolTests(unittest.TestCase):
    def test_all_first_party_sources_parse(self) -> None:
        files = [path for directory in SOURCE_DIRS for path in directory.glob("*.py")]
        self.assertTrue(files, "No first-party Python sources found.")
        for path in files:
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_no_login_or_network_code_in_first_party_sources(self) -> None:
        for directory in SOURCE_DIRS:
            for path in directory.glob("*.py"):
                text = path.read_text(encoding="utf-8")
                for token in FORBIDDEN_TOKENS:
                    with self.subTest(path=path.relative_to(ROOT).as_posix(), token=token):
                        self.assertNotIn(token, text)

    def test_bestmdmtool_is_independent_of_app_package(self) -> None:
        for path in (ROOT / "bestmdmtool").glob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("from app", text)
            self.assertNotIn("import app", text)

    def test_bestmdmtool_branding(self) -> None:
        branding = (ROOT / "bestmdmtool" / "branding.py").read_text(encoding="utf-8")
        self.assertIn('PRODUCT_NAME = "BestMDMTool"', branding)
        self.assertIn('PRODUCT_VERSION = "0.3.4"', branding)
        self.assertIn("AUTHORIZED_USE", branding)

    def test_bestmdmtool_gui_opens_directly(self) -> None:
        gui = (ROOT / "bestmdmtool" / "gui.py").read_text(encoding="utf-8")
        entry = (ROOT / "bestmdmtool" / "__main__.py").read_text(encoding="utf-8")
        self.assertIn("class BestMDMToolApp", gui)
        self.assertIn("self.title(PRODUCT_TITLE)", gui)
        self.assertIn("def main()", gui)
        self.assertIn("app.mainloop()", gui)
        self.assertIn("main()", entry)
        self.assertNotIn("Oumse", gui)

    def test_launchers_and_installer_target_bestmdmtool(self) -> None:
        launcher = (ROOT / "START_BEST_MDM_TOOL.bat").read_text(encoding="utf-8")
        self.assertIn("-m bestmdmtool", launcher)

        powershell = (
            ROOT / "installer-bestmdmtool" / "launcher" / "Start-BestMDMTool.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn('"-m", "bestmdmtool"', powershell)

        iss = (ROOT / "installer-bestmdmtool" / "BestMDMTool.iss").read_text(encoding="utf-8")
        self.assertIn("BestMDMToolSetup", iss)
        self.assertIn("bestmdmtool", iss)
        self.assertIn("servicecore", iss)
        self.assertIn("Launch-BestMDMTool.vbs", iss)
        self.assertNotIn(r"..\app\*", iss)

        workflow = (ROOT / ".github" / "workflows" / "build-bestmdmtool-installer.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("installer-bestmdmtool", workflow)


if __name__ == "__main__":
    unittest.main()
