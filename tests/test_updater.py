import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import competitive_loader as loader


class FakeResponse(io.BytesIO):
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class UpdaterTests(unittest.TestCase):
    def test_loader_release_channel_is_public_distribution_repo(self):
        self.assertEqual(
            loader.LOADER_RELEASE_API,
            "https://api.github.com/repos/SoulSeiya/Competitive-Loader-Releases/releases/latest",
        )

    def test_release_version(self):
        self.assertEqual(loader._release_version("v0.17"), (0, 17, 0))
        self.assertEqual(loader._release_version("1.2.3"), (1, 2, 3))
        self.assertIsNone(loader._release_version("release-next"))

    def test_new_release_is_selected(self):
        release = {
            "tag_name": "v1.4.0",
            "name": "Competitive Loader 1.4",
            "body": "Cambios de prueba",
            "assets": [{
                "name": loader.LOADER_ASSET_NAME,
                "browser_download_url": "https://example.invalid/update.zip",
                "size": 123,
                "digest": "sha256:" + "a" * 64,
            }],
        }
        response = FakeResponse(json.dumps(release).encode("utf-8"))
        with mock.patch("urllib.request.urlopen", return_value=response):
            update = loader.latest_loader_update()
        self.assertEqual(update["tag"], "v1.4.0")
        self.assertEqual(update["size"], 123)

    def test_current_release_is_ignored(self):
        release = {"tag_name": "v1.0.1", "assets": []}
        response = FakeResponse(json.dumps(release).encode("utf-8"))
        with mock.patch("urllib.request.urlopen", return_value=response):
            self.assertIsNone(loader.latest_loader_update())

    def test_release_package_stages_the_executable(self):
        built_exe = Path(__file__).resolve().parents[1] / "dist" / "Competitive Loader.exe"
        if not built_exe.is_file():
            self.skipTest("El ejecutable todavía no fue construido")
        with tempfile.TemporaryDirectory() as temp_text:
            temp = Path(temp_text)
            package = temp / "package.zip"
            with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.write(built_exe, "CompetitiveLoader-windows-x64/Competitive Loader.exe")

            def copy_package(_url, destination, _size=0):
                shutil.copy2(package, destination)

            with (
                mock.patch.object(loader, "LOADER_UPDATE_DIR", temp / "stage"),
                mock.patch.object(loader, "_download_to", side_effect=copy_package),
                mock.patch.object(sys, "frozen", True, create=True),
            ):
                staged = loader.stage_loader_update({
                    "tag": "v1.4.0", "download_url": "https://example.invalid/update.zip",
                    "size": package.stat().st_size, "digest": "",
                })
                self.assertEqual(staged.read_bytes()[:2], b"MZ")

    def test_scheduled_update_replaces_only_the_loader_and_reopens_it(self):
        with tempfile.TemporaryDirectory() as temp_text:
            temp = Path(temp_text)
            target = temp / "Competitive Loader.exe"
            target.write_bytes(b"MZ-current")
            update_dir = temp / ".competitive-update"
            update_dir.mkdir()
            staged = update_dir / "Competitive Loader.update.exe"
            staged.write_bytes(b"MZ-new")

            with (
                mock.patch.object(loader, "LOADER_UPDATE_DIR", update_dir),
                mock.patch.object(loader, "HERE", temp),
                mock.patch.object(sys, "frozen", True, create=True),
                mock.patch.object(sys, "executable", str(target)),
                mock.patch.object(loader.subprocess, "Popen") as popen,
            ):
                loader.schedule_loader_update(staged)

            command = popen.call_args.args[0]
            self.assertEqual(command[0], str(staged.resolve()))
            self.assertEqual(command[1], "--apply-loader-update")
            self.assertEqual(command[3], str(target.resolve()))
            self.assertEqual(command[4], str(temp))

    def test_staged_executable_copies_verifies_and_reopens_target(self):
        with tempfile.TemporaryDirectory() as temp_text:
            temp = Path(temp_text)
            update_dir = temp / ".competitive-update"
            update_dir.mkdir()
            source = update_dir / "Competitive Loader.update.exe"
            source.write_bytes(b"MZ-new-version")
            target = temp / "Competitive Loader.exe"
            target.write_bytes(b"MZ-old-version")

            with (
                mock.patch.object(sys, "executable", str(source)),
                mock.patch.object(loader, "_wait_for_process") as wait,
                mock.patch.object(loader, "_close_loader_processes_at") as close_instances,
                mock.patch.object(loader.subprocess, "Popen") as popen,
            ):
                loader.apply_loader_update(4321, target, temp)

            wait.assert_called_once_with(4321, 15000)
            close_instances.assert_called_once_with(target.resolve())
            self.assertEqual(target.read_bytes(), source.read_bytes())
            command = popen.call_args.args[0]
            self.assertEqual(command[0], str(target.resolve()))
            self.assertEqual(command[1], "--finish-loader-update")
            self.assertTrue(Path(command[3]).samefile(update_dir))


if __name__ == "__main__":
    unittest.main()

