from pathlib import Path
import queue
import unittest
from unittest import mock
import competitive_gui as gui
import competitive_loader as core


class VersionRefreshTests(unittest.TestCase):
    def test_manual_check_can_repeat_without_restarting_or_overlapping(self):
        app = gui.CompetitiveApp.__new__(gui.CompetitiveApp)
        app.events = queue.Queue()
        app.checking_versions = False
        app.busy = False
        app._runtime = lambda: Path("not-installed")
        app._append = mock.Mock()
        for name in ("root", "check_updates_button", "update_button", "decomp_remote_label",
                     "decomp_installed_label", "loader_remote_label", "loader_installed_label", "version_status_label"):
            setattr(app, name, mock.Mock())
        release = {"version": (99, 0, 0), "tag": "v99.0.0", "download_url": "https://example.invalid/update.zip"}
        with mock.patch.object(core, "load_config", return_value={}), mock.patch.object(core, "latest_release_info", return_value={"tag": "v0.1.35.2"}), mock.patch.object(core, "latest_loader_release_info", return_value=release) as check, mock.patch.object(gui.threading, "Thread") as thread:
            thread.side_effect = lambda **kwargs: mock.Mock(start=kwargs["target"])
            app._check_versions()
            app._check_versions()
            self.assertEqual(check.call_count, 1)
            app._poll()
            self.assertFalse(app.checking_versions)
            self.assertEqual(app.pending_update, release)
            app._check_versions()
            app._poll()
            self.assertEqual(check.call_count, 2)
