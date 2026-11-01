from pathlib import Path
import tempfile
import unittest
from live_spectator import game_fingerprint
from observer_lab import ObserverMapping,Header

class LiveSpectatorTests(unittest.TestCase):
    def test_game_hash_uses_contents_and_ignores_installer_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            r=Path(directory);g=r/'gamedata';g.mkdir();(g/'001.bin').write_bytes(b'game')
            first=game_fingerprint(r);(g/'.competitive-v8.4.1.json').write_text('different installation time')
            self.assertEqual(game_fingerprint(r),first)
            (g/'001.bin').write_bytes(b'other');self.assertNotEqual(game_fingerprint(r),first)
            mods=r/'mods';mods.mkdir();(mods/'001.bin').write_bytes(b'mod')
            self.assertNotEqual(game_fingerprint(r),first)

    def test_receiver_prebuffers_before_activation_and_never_sends_player_input(self):
        m=ObserverMapping()
        try:
            h=Header();h.first=1;h.seed=123;h.rules=4;h.names[0].value=b'A';h.names[1].value=b'B'
            m.prepare_view(h)
            self.assertTrue(m.feed(1,b'\xff'*36*48));self.assertEqual(m.shared.header.mode,0)
            self.assertTrue(m.feed(49,b'\xff'*36*48));self.assertEqual(m.shared.header.mode,0)
            self.assertTrue(m.feed(97,b'\xff'*36*48));self.assertEqual(m.shared.header.mode,2)
            self.assertEqual(m.shared.header.seed,123)
            with self.assertRaises(ValueError):m.feed(1,b'\xff'*36)
            m.stop();self.assertEqual(m.shared.header.mode,4)
        finally:m.close()
