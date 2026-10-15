import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import competitive_loader as core


class CompatibleDownloadTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        patch = mock.patch.object(core, "GITHUB_RELEASE_CACHE", Path(folder.name) / "cache.json")
        patch.start()
        self.addCleanup(patch.stop)

    def test_release_profile_fetches_reviewed_tag_instead_of_latest(self):
        data = {"tag_name": core.SUPPORTED_DECOMP_TAG, "assets": [{
            "name": core.WINDOWS_ASSET_NAME, "id": 642111011,
            "browser_download_url": core.SUPPORTED_WINDOWS_RELEASE,
        }]}
        with (mock.patch.object(core, "RELEASE_PROFILE", True),
              mock.patch.object(core.urllib.request, "urlopen",
                                return_value=io.BytesIO(json.dumps(data).encode())) as fetch):
            info = core.installation_release_info()
        self.assertEqual(info["tag"], core.SUPPORTED_DECOMP_TAG)
        self.assertTrue(fetch.call_args.args[0].full_url.endswith("/tags/" + core.SUPPORTED_DECOMP_TAG))

    def test_metadata_failure_falls_back_to_reviewed_download(self):
        class StopDownload(Exception):
            pass
        with (tempfile.TemporaryDirectory() as folder,
              mock.patch.object(core, "RELEASE_PROFILE", True),
              mock.patch.object(core.urllib.request, "urlopen", side_effect=StopDownload) as fetch):
            with self.assertRaises(StopDownload):
                core._download_latest_release(Path(folder), {})
        self.assertEqual(fetch.call_args.args[0].full_url, core.SUPPORTED_WINDOWS_RELEASE)

    def test_auto_update_uses_compatible_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = Path(folder)
            (runtime / "Tenkaichi3Decomp.exe").write_bytes(b"existing")
            info = {"tag": core.SUPPORTED_DECOMP_TAG, "asset_id": "reviewed"}
            with (mock.patch.object(core, "installation_release_info", return_value=info),
                  mock.patch.object(core, "latest_release_info", side_effect=AssertionError("unreviewed")),
                  mock.patch.object(core, "load_config", return_value={}),
                  mock.patch.object(core, "update_from_github", return_value={}) as update):
                core.ensure_latest_release(runtime)
            update.assert_called_once_with(runtime, info)


if __name__ == "__main__":
    unittest.main()
