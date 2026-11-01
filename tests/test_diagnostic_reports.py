import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from diagnostic_reports import DesyncCapture, ReportManager, preference, duel_context
from player_profile import ProfileStore

META={'loader_version':'2.0.1','decomp_release':'v0.1.38.1','exe_sha256':'a'*64,
      'memory_sha256':'b'*64,'dat_sha256':'c'*64,'payload_sha256':{'competitive_score.o':'d'*64},
      'runtime':r'C:\Users\private\secret','token':'secret','chat':'private message'}
DIFFER='bt3: net: the two games differ at blank 3648 (this copy f3491de612a8250d, the other 9cc9bd601e60b2af)'
END='bt3: net: The two games no longer agree (desync): the match has ended. (blank 3649)'

class ReportTests(unittest.TestCase):
    def test_only_confirmed_desync_emits_and_payload_excludes_arbitrary_logs(self):
        out=[];p=DesyncCapture(META,out.append)
        p.line('a chat message: desync');p.line(DIFFER);self.assertEqual(out,[])
        p.line(END);p.line(END);p.line(DIFFER)
        self.assertEqual(len(out),1);r=out[0]
        self.assertEqual(r['divergence']['blank'],3648)
        for value in ('private','secret','token','runtime','chat'):self.assertNotIn(value,json.dumps(r))
        self.assertIsNone(r['character']);self.assertIsNone(r['technique'])

    def test_actual_event_order_keeps_direct_connection_and_next_session_is_independent(self):
        out=[];p=DesyncCapture(META,out.append)
        for _ in range(2):
            p.line('bt3: net: connected directly; input delay 1 blanks, rollback')
            p.line('btc: session_begin online=1');p.line('bt3: net: rollback of up to 8 blanks')
            for i in range(50):p.line(f'net: blank {i}: 19 rollbacks (1.1 blanks each), 0 waits')
            p.line(DIFFER);p.line(END)
        self.assertEqual(len(out),2);self.assertNotEqual(out[0]['report_id'],out[1]['report_id'])
        self.assertEqual(out[-1]['network']['connection'],'direct');self.assertEqual(out[-1]['network']['rollback'],8)
        self.assertEqual(len(out[-1]['network']['samples']),12)

    def test_default_enabled_persists_opt_out_and_does_not_queue_existing_reports(self):
        with tempfile.TemporaryDirectory() as folder:
            store=ProfileStore(Path(folder)/'profile.sqlite3','QA');self.assertTrue(preference(store))
            manager=ReportManager(store,folder);manager.enabled(False)
            self.assertFalse(preference(ProfileStore(store.path)))
            manager.accept({'report_id':'a'*32,'context':{}})
            with patch('social_client.protect',side_effect=AssertionError('must not touch credentials')):
                manager._persist(manager.incoming.get_nowait())
            self.assertEqual(list(manager.root.glob('*.json')),[])

    def test_match_binding_is_copied_and_spectators_have_no_side(self):
        room={'room_code':'BTC-ABCDEF','token':'proof','self_id':1,'combat':{'id':'a'*24,'current':1,'status':'running','ft':2,'seconds':360,'characters':2,'matches':[{'id':1,'p1':1,'p2':2}]}}
        out=[];p=DesyncCapture(META,out.append);p.bind(duel_context(room));room['combat']['seconds']=180
        p.line(DIFFER);p.line(END);self.assertEqual(out[0]['context']['rules']['seconds'],360)
        room['self_id']=3;self.assertEqual(duel_context(room),{})

    def test_room_proof_is_encrypted_locally_not_written_in_plain_report(self):
        with tempfile.TemporaryDirectory() as folder:
            store=ProfileStore(Path(folder)/'profile.sqlite3','QA');manager=ReportManager(store,folder)
            out=[];p=DesyncCapture(META,out.append);p.bind({'battle_id':'a'*24,'_room_token':'do-not-store-plaintext'})
            p.line(DIFFER);p.line(END)
            with patch('social_client.protect',return_value=b'encrypted-proof'):
                manager._persist(copy.deepcopy(out[0]))
            text=next(manager.root.glob('*.json')).read_text();self.assertNotIn('do-not-store-plaintext',text)
            manager.enabled(False);self.assertEqual(list(manager.root.glob('*.json')),[])

    def test_game_thread_only_enqueues_and_transport_keeps_credentials_outside_report(self):
        import io
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as folder:
            store=ProfileStore(Path(folder)/'profile.sqlite3','QA');manager=ReportManager(store,folder)
            out=[];p=DesyncCapture(META,out.append);p.bind({'battle_id':'a'*24,'_room_token':'proof'})
            p.line(DIFFER);p.line(END)
            with patch('diagnostic_reports.preference',side_effect=AssertionError('no SQLite on reader')):
                manager.accept(out[0])
            report=manager.incoming.get_nowait()
            with patch('social_client.protect',return_value=b'sealed'):manager._persist(report)
            saved=json.loads(next(manager.root.glob('*.json')).read_text())
            class Response(io.BytesIO):
                def __enter__(self):return self
                def __exit__(self,*a):self.close()
            def opened(request,timeout):
                body=json.loads(request.data)
                self.assertEqual(body['room_token'],'proof');self.assertEqual(body['token'],'auth-secret')
                self.assertNotIn('_sealed_proof',body['report']);self.assertNotIn('_room_token',body['report']['context'])
                return Response(json.dumps({'accepted':True,'report_id':report['report_id']}).encode())
            checked=SimpleNamespace(url='https://example.test/v1/rooms',opener=SimpleNamespace(open=opened))
            with patch('rising_service.ServiceClient',return_value=checked),patch('social_client.credentials',return_value={'id':'a'*32,'token':'auth-secret'}),patch('social_client.protect',return_value=b'proof'):
                manager._send(saved)

if __name__=='__main__':unittest.main()
