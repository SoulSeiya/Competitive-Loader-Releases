import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import sys
import io

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import competitive_loader as loader
import local_online_test as lab


class OnlineLabTests(unittest.TestCase):
    def setUp(self):
        output = mock.patch("sys.stdout", new=io.StringIO())
        output.start()
        self.addCleanup(output.stop)

    def test_profile_rejects_unreviewed_build_before_mutating_hooks(self):
        previous = loader.CALL_WRAPPERS
        with mock.patch.object(loader, "sha256_file", return_value="unknown"):
            with self.assertRaises(loader.LoaderError):
                loader.use_official_online_profile(Path("unknown.exe"))
        self.assertIs(loader.CALL_WRAPPERS, previous)

    def test_analyzer_keeps_corrected_rollback_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for side in ("host", "guest"):
                (root / side).mkdir()
            good = "32 aaaa bbbb hp 100 100 pos 0 0 0 0 0 0 clock 60 rnd 0\n"
            wrong = good.replace("hp 100 100", "hp 80 100")
            (root / "host/state-hashes.txt").write_text(wrong + good + "33 aaaa bbbb hp 100")
            (root / "guest/state-hashes.txt").write_text(good)
            self.assertEqual(lab.analyze(root)["result"], "NO_DIVERGENCE_OBSERVED")
            (root / "guest/state-hashes.txt").write_text(wrong)
            self.assertEqual(lab.analyze(root)["first_observed_fight_difference"], 32)

    def test_no_fight_is_inconclusive_and_native_desync_is_not_hidden(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "host").mkdir()
            self.assertEqual(lab.analyze(root)["result"], "INCONCLUSIVE")
            (root / "host/game.log").write_text("bt3: the two games differ at blank 256")
            self.assertEqual(lab.analyze(root)["result"], "DIVERGENCE")


if __name__ == "__main__":
    unittest.main()
