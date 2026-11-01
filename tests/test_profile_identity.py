import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
from player_profile import ProfileStore
from profile_link import ProfileLink,avatar_bytes
from challonge_client import ChallongeError


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'profile.sqlite3'

    def test_first_run_and_existing_profile_migration(self):
        s=ProfileStore(self.path)
        self.assertFalse(s.identity_state()['ready'])
        self.assertFalse(ProfileStore(self.path).identity_state()['ready'])
        s.complete_profile('Rising');self.assertTrue(s.identity_state()['ready'])
        with s.connect() as db:db.execute("DELETE FROM settings WHERE key='btc_profile_ready'")
        self.assertTrue(ProfileStore(self.path).identity_state()['ready'])

    def test_link_unlink_preserves_uuid_social_keys_history_and_local_avatar(self):
        s=ProfileStore(self.path,'Local');original=s.profile()
        avatar=s.avatar_path();avatar.parent.mkdir();avatar.write_bytes(b'local png')
        with s.connect() as db:db.execute("INSERT INTO settings VALUES('social_secret',?)",(b'unchanged',))
        s.link_identity({'id':'42','username':'Official','access_token':'not retained'})
        self.assertEqual(s.profile(),dict(original,name='Official'))
        self.assertNotIn('access_token',json.dumps(s.identity_state()))
        with self.assertRaises(ValueError):s.complete_profile('Another')
        with self.assertRaises(ValueError):s.link_identity({'id':'43','username':'Other'})
        s.link_identity({'id':'42','username':'NewOfficial'})
        s.unlink_identity();self.assertEqual(s.profile(),original)
        self.assertEqual(avatar.read_bytes(),b'local png')
        with s.connect() as db:self.assertEqual(bytes(db.execute("SELECT value FROM settings WHERE key='social_secret'").fetchone()[0]),b'unchanged')
        self.assertEqual(s.history(),[])

    def test_avatar_import_and_restore(self):
        s=ProfileStore(self.path,'Local')
        with patch('avatar_image.convert_avatar',side_effect=lambda src,dst:Path(dst).write_bytes(b'converted')):
            s.link_identity({'id':'1','username':'Online'},b'remote image')
        self.assertEqual(s.avatar_path().read_bytes(),b'converted')
        s.unlink_identity();self.assertFalse(s.avatar_path().exists())

    def test_linking_before_local_setup_restores_onboarding_on_unlink(self):
        s=ProfileStore(self.path)
        s.link_identity({'id':'1','username':'Official'})
        self.assertTrue(s.identity_state()['ready'])
        s.unlink_identity();self.assertFalse(s.identity_state()['ready'])

    def test_invalid_avatar_leaves_local_identity_unchanged(self):
        s=ProfileStore(self.path,'Local')
        with patch('avatar_image.convert_avatar',side_effect=ValueError('bad image')):
            with self.assertRaises(ValueError):s.link_identity({'id':'1','username':'Online'},b'bad')
        self.assertEqual(s.profile()['name'],'Local');self.assertIsNone(s.identity_state()['challonge'])

    def test_device_flow_only_requests_identity_and_seals_tokens(self):
        s=ProfileStore(self.path,'Local');m=ProfileLink(s,'public_client_id');m.generation=1
        api=Mock();api.device.return_value={'device_code':'private-device','user_code':'ABCDEF','verification_uri':'https://connect.challonge.com/oauth/device','expires_in':300}
        api.device_token.return_value={'access_token':'private-access','refresh_token':'private-refresh','expires_in':3600}
        api.me.return_value={'id':'7','username':'Official','image_url':''}
        clock=iter(range(0,1000,10))
        with patch('profile_link.ChallongeAPI',return_value=api),patch('profile_link.time.monotonic',side_effect=lambda:next(clock)),patch('social_client.protect',side_effect=lambda b,*args:b'sealed:'+b):
            m._run(1)
        api.device.assert_called_once_with(scope='me')
        self.assertEqual(s.profile()['name'],'Local') # application is deferred outside battle
        event=m.events.get_nowait();self.assertEqual(event[1]['username'],'Official')
        self.assertNotIn('private-',json.dumps(m.snapshot()))
        with s.connect() as db:self.assertTrue(bytes(db.execute('SELECT value FROM settings WHERE key=?',(m.TOKEN_KEY,)).fetchone()[0]).startswith(b'sealed:'))
        m.cancel(forget=True)
        with s.connect() as db:self.assertIsNone(db.execute('SELECT value FROM settings WHERE key=?',(m.TOKEN_KEY,)).fetchone())

    def test_cancel_discards_in_flight_token_response(self):
        s=ProfileStore(self.path,'Local');m=ProfileLink(s,'client');m.generation=2
        api=Mock();api.device.return_value={'device_code':'secret','user_code':'ABC','verification_uri':'https://connect.challonge.com/oauth/device','expires_in':300}
        with patch('profile_link.ChallongeAPI',return_value=api):m._run(1)
        self.assertTrue(m.events.empty());api.device_token.assert_not_called()

    def test_avatar_does_not_follow_untrusted_urls(self):
        for url in ('http://s3.amazonaws.com/image','https://example.com/x','https://user:pass@s3.amazonaws.com/x','https://s3.amazonaws.com:444/x'):
            with self.assertRaises(ChallongeError):avatar_bytes(url)


if __name__=='__main__':unittest.main()
