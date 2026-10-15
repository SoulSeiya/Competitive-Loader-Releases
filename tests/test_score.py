from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest


class ScoreTests(unittest.TestCase):
    def test_confirmed_results_survive_rematches_and_rollback(self):
        compiler = os.environ.get("CXX") or shutil.which("g++") or shutil.which("clang++") or shutil.which("cl")
        if not compiler:
            self.skipTest("Se necesita un compilador C++ para comprobar el contador nativo")
        source = Path(__file__).with_name("test_score_native.cpp").resolve()
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "score-test.exe"
            if Path(compiler).stem.lower() == "cl":
                command = [compiler, "/nologo", "/EHsc", str(source), "/Fe:" + str(executable)]
            else:
                command = [compiler, str(source), "-o", str(executable)]
            built = subprocess.run(command, cwd=directory, capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            tested = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(tested.returncode, 0, tested.stdout + tested.stderr)
            self.assertIn("Score OK", tested.stdout)
