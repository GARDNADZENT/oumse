"""Regression tests for the field-reported security and erase failures."""
import ast
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[1] / "servicecore/runner/service_runner.py"


def load_handler(name, **extra):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    namespace = {
        "json": json,
        "os": os,
        "flash_capacity": lambda mtk: int(mtk.daloader.daconfig.storage.flashsize),
        **extra,
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(SOURCE), "exec"), namespace)
    return namespace[name]


class FailSafeTests(unittest.TestCase):
    def test_connect_fails_before_mtk_code_or_saved_state_can_run(self):
        fail = Mock(side_effect=SystemExit(1))
        connect = load_handler("connect", fail=fail)
        with self.assertRaises(SystemExit):
            connect()
        fail.assert_called_once_with("connect", "mtk_temporarily_disabled_security_review", 1)

    def test_runner_entry_selftest_proves_mtk_refusal_without_hardware(self):
        root = SOURCE.parents[2]
        entry = root / "installer-bestmdmtool" / "runner_entry.py"
        spec = importlib.util.spec_from_file_location("bestmdmtool_runner_entry_test", entry)
        module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "mtk-disabled.json"
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = module.selftest_mtk_disabled(str(report_path))
            report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(result, 0)
        self.assertTrue(report["ok"])
        self.assertTrue(report["refused"])
        self.assertIn("mtk_temporarily_disabled_security_review", output.getvalue())

    def test_seccfg_never_calls_device(self):
        fail = Mock()
        device = Mock()
        load_handler("op_seccfg", fail=fail)(device, Mock(), {"state": "unlock"})
        fail.assert_called_once_with("seccfg", "unavailable_security_policy")
        device.assert_not_called()
        self.assertEqual(device.mock_calls, [])

    def test_erase_backend_refusal_is_never_success(self):
        events = []
        entry = {"name": "userdata", "sector": 1, "pagesize": 512, "size": 512}
        loader = SimpleNamespace(
            daconfig=SimpleNamespace(storage=SimpleNamespace(flashsize=1024)),
            formatflash=Mock(return_value=False),
        )
        fail = Mock()
        erase = load_handler("op_erase", partition_table=lambda _: [entry], fail=fail, emit=events.append)
        erase(SimpleNamespace(daloader=loader), None, {"parts": ["userdata"]})
        fail.assert_called_once_with("erase", "format_failed:userdata:operation_may_be_partial")
        self.assertFalse(any(line.startswith("SVC_OK") for line in events))

    def test_erase_rejects_out_of_range_before_touching_device(self):
        entry = {"name": "userdata", "sector": 1, "pagesize": 512, "size": 1024}
        loader = SimpleNamespace(
            daconfig=SimpleNamespace(storage=SimpleNamespace(flashsize=1024)), formatflash=Mock()
        )
        fail = Mock()
        erase = load_handler("op_erase", partition_table=lambda _: [entry], fail=fail, emit=Mock())
        erase(SimpleNamespace(daloader=loader), None, {"parts": ["userdata"]})
        fail.assert_called_once_with("erase", "partition_out_of_range:userdata")
        loader.formatflash.assert_not_called()

    def test_dump_partial_read_is_failure_not_success(self):
        entry = {"name": "userdata", "sector": 0, "pagesize": 512, "size": 512}
        fail, events = Mock(), []
        loader = SimpleNamespace(readflash=Mock(return_value=False))
        handler = load_handler("op_dump", partition_table=lambda _: [entry], fail=fail, emit=events.append)
        with tempfile.TemporaryDirectory() as directory:
            handler(SimpleNamespace(daloader=loader), None, {"dir": directory})
        self.assertEqual(fail.call_args.args[0], "dump")
        self.assertIn("partial:0_of_1", fail.call_args.args[1])
        self.assertFalse(any(line.startswith("SVC_OK") for line in events))

    def test_partition_write_rejects_image_larger_than_partition(self):
        entry = {"name": "boot", "sector": 1, "pagesize": 512, "size": 512}
        fail, emit = Mock(), Mock()
        loader = SimpleNamespace(writeflash=Mock())
        handler = load_handler(
            "op_write", find_partition=lambda _mtk, _name: entry, fail=fail, emit=emit,
            log=Mock(), ProgressBus=object,
        )
        with tempfile.NamedTemporaryFile() as image:
            image.write(b"x" * 513)
            image.flush()
            handler(SimpleNamespace(daloader=loader), None, {"part": "boot", "in": image.name})
        fail.assert_called_once_with("write", "image_exceeds_partition:boot")
        loader.writeflash.assert_not_called()
        emit.assert_not_called()

    def test_bestmdmtool_installer_excludes_the_legacy_mtk_backend(self):
        root = SOURCE.parents[2]
        iss = (root / "installer-bestmdmtool" / "BestMDMTool.iss").read_text(encoding="utf-8-sig")
        pyinstaller = (root / "installer-bestmdmtool" / "build_exe.ps1").read_text(encoding="utf-8")
        entry = (root / "installer-bestmdmtool" / "runner_entry.py").read_text(encoding="utf-8")
        self.assertNotIn('Source: "{#SourcePath}..\\runtime\\lib', iss)
        self.assertIn('Name: "{app}\\runtime\\runner"', iss)
        self.assertIn('Name: "{app}\\runtime\\lib\\mtkclient"', iss)
        self.assertIn('Name: "{app}\\runtime\\lib\\*.py"', iss)
        self.assertIn('Name: "{app}\\runtime\\lib\\hwparam.json"', iss)
        self.assertNotIn('"--collect-submodules", "mtkclient"', pyinstaller)
        self.assertNotIn("from mtkclient", entry)
        self.assertIn("mtk_available\"] = False", entry)
        portable = (root / "installer-bestmdmtool" / "build_portable.py").read_text(encoding="utf-8")
        self.assertNotIn('add_tree(archive, ROOT / "runtime" / "lib"', portable)

    def test_gpt_empty_is_failure(self):
        fail, emit = Mock(), Mock()
        load_handler("op_gpt", partition_table=lambda _: [], fail=fail, emit=emit)(None, None, {})
        fail.assert_called_once_with("gpt", "partition_table_unavailable")
        emit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
