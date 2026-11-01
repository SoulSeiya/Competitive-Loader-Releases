import tempfile
from pathlib import Path
import unittest
from player_profile import ProfileStore
from rising_room import Room,PROTOCOL


class PlayerProfileTests(unittest.TestCase):
    def test_avatar_survives_reopen_and_invalid_import_preserves_previous_image(self):
        import os,struct,zlib
        if os.name!='nt':self.skipTest('El importador usa el decodificador de Windows')
        def chunk(kind,data):
            return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);store=ProfileStore(folder/'profile.sqlite3')
            source=folder/'source.png'
            source.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',4,2,8,6,0,0,0))+
                chunk(b'IDAT',zlib.compress((b'\x00'+b'\x20\x90\xc0\xff'*4)*2))+chunk(b'IEND',b''))
            store.set_avatar(source);saved=store.avatar_path().read_bytes()
            self.assertEqual(struct.unpack('>II',saved[16:24]),(256,256))
            self.assertEqual(ProfileStore(store.path).avatar_path().read_bytes(),saved)
            invalid=folder/'invalid.jpg';invalid.write_bytes(b'not an image')
            with self.assertRaises(ValueError):store.set_avatar(invalid)
            self.assertEqual(store.avatar_path().read_bytes(),saved)
            store.clear_avatar();self.assertFalse(store.avatar_path().exists())

    def test_identity_persists_and_only_confirmed_results_are_saved_once(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'profile.sqlite3';store=ProfileStore(path)
            store.rename('Rising');identity=store.profile()['id']
            self.assertEqual(ProfileStore(path).profile(),dict(id=identity,name='Rising'))
            room=Room('Prueba','Rising');host=room.host_token
            guest=room.handle(dict(op='join',name='Rival',key=room.key,protocol=PROTOCOL,edition='BTC'))
            def send(token,op,**values):return room.handle(dict(token=token,op=op,**values))
            offer=send(host,'duel_offer',target=guest['self_id'],ft=2,characters=2,seconds=180)['duel']
            battle=send(guest['token'],'duel_accept',duel_id=offer['id'])['combat']
            send(host,'tournament_report',tournament_id=battle['id'],match=1,score=[2,1])
            store.observe(send(host,'poll'));self.assertEqual(store.stats()['played'],0)
            send(guest['token'],'tournament_report',tournament_id=battle['id'],match=1,score=[2,1])
            store.observe(send(host,'poll'));store.observe(send(host,'poll'))
            self.assertEqual(store.stats(),dict(played=1,wins=1,tournaments=0))
            row=store.history()[0]
            self.assertEqual((row['opponent'],row['mine'],row['theirs']),('Rival',2,1))
            store.rename('Nuevo nombre');self.assertEqual(store.profile()['id'],identity)
            self.assertEqual(store.stats()['played'],1)

    def test_registration_is_separate_from_fights_and_names_fit_the_engine(self):
        with tempfile.TemporaryDirectory() as folder:
            store=ProfileStore(Path(folder)/'profile.sqlite3')
            for name in ('','\n','x'*20,'á'*10,'A\x00B'):
                with self.assertRaises(ValueError):store.rename(name)
            snapshot=dict(self_id=1,tournament=dict(id='t1',title='Copa',status='registration',self_enrolled=True,matches=[]))
            store.observe(snapshot);store.observe(snapshot)
            self.assertEqual(store.stats(),dict(played=0,wins=0,tournaments=1))
            snapshot['tournament']['status']='finished';store.observe(snapshot)
            self.assertEqual(store.participations()[0]['status'],'finished')
