import unittest
from unittest.mock import MagicMock
from ranked_client import RankedManager
from session_diagnostics import SessionDiagnostics


class RankedClientTests(unittest.TestCase):
    def test_partial_confirmed_score_and_attempt_are_forwarded_for_checkpoint(self):
        telemetry={'session':'old','serial':0,'running':True,'connected':False}
        manager=RankedManager(None,lambda:dict(telemetry))
        manager._receive({'match':{'id':'set','attempt':0,'finished':None}})
        telemetry.update(serial=1,connected=True,score=[1,0])
        beat=manager._heartbeat();self.assertEqual(beat['score'],[1,0]);self.assertFalse(beat['completed']);self.assertEqual(beat['attempt'],0)
        telemetry.update(failed=True,connected=False,desync_proof={'blank':100,'local_hash':'1'*16,'peer_hash':'2'*16})
        beat=manager._heartbeat();self.assertTrue(beat['closed']);self.assertEqual(beat['desync_proof']['blank'],100)
        manager._receive({'match':{'id':'set','attempt':1,'finished':None}})
        beat=manager._heartbeat();self.assertFalse(beat['failed']);self.assertIsNone(beat['score']);self.assertEqual(beat['attempt'],1)
        telemetry.update(session='new',serial=1,failed=False,connected=True,score=[1,0])
        beat=manager._heartbeat();self.assertTrue(beat['connected']);self.assertEqual(beat['score'],[1,0])

    def test_native_resume_score_is_absolute_and_does_not_complete_the_set(self):
        session=object.__new__(SessionDiagnostics);session.summary={};session.local=MagicMock();session.online=MagicMock();session.report_capture=MagicMock()
        session.record_engine_line('btc: session_begin online=1')
        session.record_engine_line('btc: ranked_resume_score P1=1 P2=0 target=2')
        self.assertEqual(session.summary['ranked_score'],[1,0]);self.assertFalse(session.summary['ranked_completed'])
        session.record_engine_line('btc: session_begin online=1')
        self.assertIsNone(session.summary['ranked_score']);self.assertIsNone(session.summary['ranked_desync_proof'])
    def test_search_status_tracks_the_server_instead_of_a_stale_check_label(self):
        manager=RankedManager(None,lambda:{})
        manager._receive({'queued':True})
        self.assertEqual(manager.status,'Buscando un rival compatible…')
        manager._receive({'queued':False})
        self.assertEqual(manager.status,'Listo para buscar ranked.')
        manager._receive({'match':{'id':'set','finished':None,'phase':'connecting'}})
        self.assertEqual(manager.status,'Rival encontrado. Preparando la partida…')

    def test_queue_service_error_is_exposed_even_with_a_previous_snapshot(self):
        from unittest.mock import patch
        from rising_room import RoomError
        manager=RankedManager(None,lambda:{})
        manager.snapshot={'queued':False};manager.submit('queue',compat='a'*64)
        def reject(*args,**kwargs):
            manager.stop.set()
            raise RoomError('Error de búsqueda de prueba')
        client=MagicMock();client.send.side_effect=reject
        with patch('ranked_client.RankedClient',return_value=client):manager._work()
        self.assertEqual(manager.error,'Error de búsqueda de prueba')


    def test_protocol_accepts_migration_rules_but_rejects_other_ranked_formats(self):
        import io,json
        from ranked_client import RankedClient
        client=object.__new__(RankedClient);client._url='https://example.invalid/v1/ranked';client._identity={};client._opener=MagicMock()
        for rules,accepted in (({'ft':2,'seconds':180,'characters':2},True),({'ft':2,'seconds':360,'characters':2},True),({'ft':2,'seconds':360,'characters':1},False),({'ft':3,'seconds':360,'characters':2},False)):
            client._opener.open.return_value=io.BytesIO(json.dumps({'protocol':1,'me':{},'rules':rules}).encode())
            if accepted:self.assertEqual(client.send('poll')['rules'],rules)
            else:
                with self.assertRaises(Exception):client.send('poll')

    def test_a_previous_casual_session_does_not_count_as_ranked_connected(self):
        telemetry={'session':'game1','serial':2,'running':True,'connected':False}
        manager=RankedManager(None,lambda:dict(telemetry))
        manager._receive({'match':{'id':'rank1','finished':None}})
        self.assertFalse(manager._heartbeat()['connected'])
        telemetry.update(serial=3,connected=True)
        self.assertTrue(manager._heartbeat()['connected'])
        telemetry.update(connected=False,running=False)
        self.assertTrue(manager._heartbeat()['closed'])
        telemetry.update(session='game2',serial=1,running=True,connected=True)
        self.assertTrue(manager._heartbeat()['closed'])

    def test_completed_score_is_forwarded_without_computing_a_local_winner(self):
        telemetry={'session':'game1','serial':0,'running':True}
        manager=RankedManager(None,lambda:dict(telemetry))
        manager._receive({'match':{'id':'rank1','finished':None}})
        telemetry.update(serial=1,connected=True,completed=True,score=[2,1])
        beat=manager._heartbeat();self.assertEqual(beat['score'],[2,1]);self.assertNotIn('winner',beat)

    def test_native_lifecycle_and_confirmed_score_telemetry(self):
        session=object.__new__(SessionDiagnostics)
        session.summary={};session.local=MagicMock();session.online=MagicMock();session.report_capture=MagicMock()
        session.record_engine_line('btc: session_begin online=1')
        self.assertEqual(session.summary['ranked_serial'],1)
        session.record_engine_line('net: score confirmed tick=80 P1=2 P2=1 draws=0')
        session.record_engine_line('net: FT complete target=2 winner=P1; GG; leaving session')
        self.assertTrue(session.summary['ranked_completed']);self.assertEqual(session.summary['ranked_score'],[2,1])
        session.record_engine_line('btc: session_end');self.assertFalse(session.summary['ranked_connected'])
        session.record_engine_line('btc: session_begin online=1')
        self.assertEqual(session.summary['ranked_serial'],2);self.assertFalse(session.summary['ranked_completed'])

    def test_previous_result_and_fault_are_not_forwarded_to_next_set(self):
        telemetry={'session':'game1','serial':2,'running':True,'completed':True,'score':[2,0],'failed':True}
        manager=RankedManager(None,lambda:dict(telemetry))
        manager._receive({'match':{'id':'next','finished':None}})
        beat=manager._heartbeat()
        self.assertFalse(beat['completed']);self.assertFalse(beat['failed']);self.assertIsNone(beat['score'])

    def test_desync_is_reset_for_next_native_session_only(self):
        session=object.__new__(SessionDiagnostics)
        session.summary={};session.local=MagicMock();session.online=MagicMock();session.report_capture=MagicMock()
        session.record_engine_line('the two games no longer agree')
        self.assertTrue(session.summary['ranked_failed'])
        session.record_engine_line('btc: session_begin online=1')
        self.assertFalse(session.summary['ranked_failed']);self.assertTrue(session.summary['desync_observed'])

    def test_explicit_pause_exit_and_result_survive_native_session_end(self):
        session=object.__new__(SessionDiagnostics)
        session.summary={};session.local=MagicMock();session.online=MagicMock();session.report_capture=MagicMock()
        session.record_engine_line('btc: session_begin online=1')
        session.record_engine_line('btc: pause_exit loser=P1 P1=1 P2=2 target=2')
        session.record_engine_line('btc: session_end')
        self.assertEqual(session.summary['duel_exit_score'],[1,2])
        self.assertFalse(session.summary.get('ranked_completed'))
        session.record_engine_line('btc: session_begin online=1')
        self.assertIsNone(session.summary['duel_exit_score'])
        session.record_engine_line('btc: set_result P1=2 P2=0 target=2')
        self.assertTrue(session.summary['ranked_completed']);self.assertEqual(session.summary['ranked_score'],[2,0])
