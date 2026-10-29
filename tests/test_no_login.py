from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
SOURCE_DIRS = [APP_DIR, ROOT / "servicecore", ROOT / "bestmdmtool"]

# Split the login endpoint so this test file itself does not look like app code.
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


class NoLoginGuaranteeTests(unittest.TestCase):
    def test_first_party_source_has_no_login_or_network_code(self) -> None:
        sources = {
            path: path.read_text(encoding="utf-8")
            for directory in SOURCE_DIRS
            for path in directory.glob("*.py")
        }
        self.assertTrue(sources, "No first-party source files found.")
        for path, text in sources.items():
            for token in FORBIDDEN_TOKENS:
                with self.subTest(path=path.relative_to(ROOT).as_posix(), token=token):
                    self.assertNotIn(token, text)

    def test_gui_opens_directly(self) -> None:
        gui = (APP_DIR / "gui.py").read_text(encoding="utf-8")
        entry = (APP_DIR / "__main__.py").read_text(encoding="utf-8")
        self.assertIn("def main()", gui)
        self.assertIn("app.mainloop()", gui)
        self.assertIn("main()", entry)
        self.assertIn("self._build_ui()", gui)
        self.assertNotIn("login_window", gui)


if __name__ == "__main__":
    unittest.main()
