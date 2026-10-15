import io
import json
from pathlib import Path
import tempfile
import sys
import unittest
from unittest import mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import competitive_loader as core
from session_diagnostics import SessionDiagnostics


class Response(io.BytesIO):
    headers = {}


class DiagnosticsTests(unittest.TestCase):
    def test_network_and_local_logs_and_desync_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            diag = SessionDiagnostics(root / "logs", root)
            try:
                diag.record_engine_line("renderer started")
                diag.record_engine_line("bt3: net: connected; input delay 2 blanks")
                diag.record_engine_line("bt3: net: the two games differ at blank 256")
                diag.finish("desync")
                data = json.loads((diag.path / "session.json").read_text())
                self.assertTrue(data["online_observed"])
                self.assertTrue(data["desync_observed"])
                self.assertIn("renderer started", (diag.path / "local.log").read_text())
                self.assertNotIn("renderer started", (diag.path / "online.log").read_text())
                self.assertIn("blank 256", (diag.path / "online.log").read_text())
            finally:
                diag.dispose()

    def test_only_new_crash_report_is_collected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            crash = root / "bt3_crash.txt"
            crash.write_text("old crash")
            diag = SessionDiagnostics(root / "logs", root)
            try:
                diag.finish("closed")
                self.assertFalse((diag.path / "bt3_crash.txt").exists())
                crash.write_text("new access violation and backtrace")
                diag.finish("abnormal_exit")
                self.assertEqual(diag.summary["status"], "crash")
                self.assertEqual((diag.path / "bt3_crash.txt").read_text(), crash.read_text())
            finally:
                diag.dispose()

    def test_incompatible_download_never_replaces_working_executable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            runtime = root / "runtime"
            runtime.mkdir()
            installed = runtime / "Tenkaichi3Decomp.exe"
            installed.write_bytes(b"MZ-working-existing-build")
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("release/Tenkaichi3Decomp.exe", b"MZ-unknown-upstream-build")
                z.writestr("release/Tenkaichi3Decomp.dat", b"BT3D")
            with (mock.patch.object(core, "RELEASE_PROFILE", True),
                  mock.patch.object(core, "CONFIG", root / "config.json"),
                  mock.patch.object(core, "_is_game_running", return_value=False),
                  mock.patch.object(core.urllib.request, "urlopen", return_value=Response(archive.getvalue())),
                  mock.patch.object(core, "_install_release_transactional") as install):
                with self.assertRaises(core.IncompatibleDecompError):
                    core.update_from_github(runtime, {"download_url": "https://example.invalid/release.zip"})
                install.assert_not_called()
            self.assertEqual(installed.read_bytes(), b"MZ-working-existing-build")


if __name__ == "__main__":
    unittest.main()
