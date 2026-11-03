import tempfile
import threading
import unittest
from pathlib import Path
from background_update import BackgroundUpdate

class BackgroundUpdateTests(unittest.TestCase):
    def test_concurrent_prepare_and_install_share_verified_download(self):
        with tempfile.TemporaryDirectory() as folder:
            calls=[];entered=threading.Event();release=threading.Event()
            def stage(info):
                calls.append(info);entered.set();release.wait(3)
                p=Path(folder)/'staged.exe';p.write_bytes(b'MZ');return p
            u=BackgroundUpdate(stage);info={'tag':'v2.2.0','digest':'sha256:abc'}
            u.prepare(info);self.assertTrue(entered.wait(2));u.prepare(info)
            self.assertEqual(u.snapshot()['phase'],'downloading')
            release.set();self.assertEqual(u.wait_ready(info).read_bytes(),b'MZ')
            u.prepare(info);self.assertEqual(len(calls),1)
            self.assertEqual(u.snapshot()['phase'],'ready')

    def test_failure_keeps_current_executable_and_does_not_become_ready(self):
        with tempfile.TemporaryDirectory() as folder:
            installed=Path(folder)/'current.exe';installed.write_bytes(b'original')
            def stage(info):raise OSError('digest mismatch')
            u=BackgroundUpdate(stage)
            with self.assertRaisesRegex(OSError,'digest mismatch'):u.wait_ready({'tag':'v2.2'})
            self.assertEqual(installed.read_bytes(),b'original')
            self.assertEqual(u.snapshot()['phase'],'error')

    def test_changed_digest_requires_new_download(self):
        with tempfile.TemporaryDirectory() as folder:
            calls=[]
            def stage(info):
                calls.append(info);p=Path(folder)/'staged.exe';p.write_bytes(b'MZ');return p
            u=BackgroundUpdate(stage)
            u.wait_ready({'tag':'v2.2','digest':'one'});u.wait_ready({'tag':'v2.2','digest':'two'})
            self.assertEqual(len(calls),2)
