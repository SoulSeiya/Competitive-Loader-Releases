import os
from pathlib import Path
import tempfile
import unittest
from player_profile import ProfileStore
from social_client import credentials,SocialClient,SocialManager
from rising_room import RoomError


class SocialClientTests(unittest.TestCase):
    @unittest.skipUnless(os.name=='nt','DPAPI requiere Windows')
    def test_device_credential_survives_restart_without_plaintext_in_database(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'profile.sqlite3';store=ProfileStore(path)
            first=credentials(store);second=credentials(ProfileStore(path))
            self.assertEqual(first,second)
            self.assertEqual(first['id'],store.profile()['id'])
            self.assertEqual(len(first['token']),64)
            self.assertNotIn(first['token'].encode(),path.read_bytes())

    def test_device_credential_is_not_sent_to_an_unencrypted_remote_service(self):
        with self.assertRaises(RoomError):SocialClient(dict(id='a'*32,token='b'*64),'http://example.com')

    def test_direct_launch_keeps_peer_for_a_future_mutual_rematch(self):
        manager=SocialManager(None)
        manager._receive({'launch':{'room_code':'BTC-ABC234'},'events':[]},direct_duel=True,duel_peer='peer')
        launch=manager.launches.get_nowait()
        self.assertTrue(launch['_direct_duel']);self.assertEqual(launch['_duel_peer'],'peer')
