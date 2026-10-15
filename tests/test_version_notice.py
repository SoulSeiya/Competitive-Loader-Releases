import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import competitive_loader as core


class VersionNoticeTests(unittest.TestCase):
    def test_notes_appear_once_per_version_and_after_an_upgrade(self):
        previous_profile = core.RELEASE_PROFILE
        try:
            import competitive_release_gui as gui
        finally:
            core.RELEASE_PROFILE = previous_profile
        app = gui.ReleaseApp.__new__(gui.ReleaseApp)
        app.root = mock.Mock()
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(core, "HERE", Path(folder)), mock.patch.object(gui.messagebox, "showinfo") as show:
            app.show_version_notes()
            app.show_version_notes()
            self.assertEqual(show.call_count, 1)
            self.assertIn(core.VERSION_HIGHLIGHTS, show.call_args.args[1])
            marker = Path(folder) / "loader-version-seen.json"
            marker.write_text(json.dumps({"version": "1.1.0"}), encoding="utf-8")
            app.show_version_notes()
            self.assertEqual(show.call_count, 2)
            self.assertEqual(json.loads(marker.read_text())["version"], core.APP_VERSION_TEXT)
