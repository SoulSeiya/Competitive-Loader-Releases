import unittest
from pathlib import Path
import tempfile
from rising_room import Room,RoomError,PROTOCOL
from existing_installation import find_installation

class DuelTests(unittest.TestCase):
    def test_two_guests_fight_host_stays_waiting_and_results_are_confirmed(self):
        room=Room('Sala libre','Host');host=room.host_token
        def join(name):return room.handle(dict(op='join',name=name,key=room.key,protocol=PROTOCOL,edition='BTC'))
        a,b=join('A'),join('B')
        def send(who,op,**values):return room.handle(dict(token=who,op=op,**values))
        offer=send(a['token'],'duel_offer',target=b['self_id'],ft=2,characters=3,seconds=240)['duel']
        with self.assertRaises(RoomError):send(host,'duel_accept',duel_id=offer['id'])
        battle=send(b['token'],'duel_accept',duel_id=offer['id'])['combat']
        self.assertEqual((battle['role'],battle['seconds'],battle['characters']),(2,240,3))
        self.assertEqual(send(host,'poll')['combat']['role'],0)
        self.assertEqual(send(host,'poll')['tournament']['enrolled'],0)
        self.assertEqual(send(b['token'],'duel_accept',duel_id=offer['id'])['combat']['id'],battle['id'])
        with self.assertRaises(RoomError):send(host,'tournament_code',tournament_id=battle['id'],match=1,code='ABCDEF')
        send(a['token'],'tournament_code',tournament_id=battle['id'],match=1,code='ABCDEF')
        for p in (a,b):state=send(p['token'],'tournament_report',tournament_id=battle['id'],match=1,score=[2,0])
        self.assertEqual(state['combat']['status'],'finished')
        new=send(a['token'],'duel_offer',target=b['self_id'],ft=1,characters=1,seconds=180)['duel']
        with self.assertRaises(RoomError):send(b['token'],'duel_accept',duel_id=offer['id'])
        send(b['token'],'duel_decline',duel_id=new['id'])
        self.assertNotIn('duel',send(host,'poll'))

    def test_existing_folder_reuses_generated_runtime_and_never_accepts_iso_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'game.iso').write_bytes(b'iso')
            with self.assertRaises(ValueError):find_installation(root)
            runtime=root/'CompetitiveRuntime';runtime.mkdir();(runtime/'gamedata').mkdir()
            for name in ('Tenkaichi3Decomp.exe','Tenkaichi3Decomp.exe.mem','Tenkaichi3Decomp.dat','SDL3.dll'):(runtime/name).write_bytes(b'x')
            self.assertEqual(find_installation(root),runtime.resolve())
            self.assertEqual(find_installation(runtime),runtime.resolve())
