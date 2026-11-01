import unittest
from unittest.mock import MagicMock
from ranked_client import RankedManager
from session_diagnostics import SessionDiagnostics


class RankedClientTests(unittest.TestCase):
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
        session.summary={};session.local=MagicMock();session.online=MagicMock()
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
        session.summary={};session.local=MagicMock();session.online=MagicMock()
        session.record_engine_line('the two games no longer agree')
        self.assertTrue(session.summary['ranked_failed'])
        session.record_engine_line('btc: session_begin online=1')
        self.assertFalse(session.summary['ranked_failed']);self.assertTrue(session.summary['desync_observed'])

    def test_explicit_pause_exit_and_result_survive_native_session_end(self):
        session=object.__new__(SessionDiagnostics)
        session.summary={};session.local=MagicMock();session.online=MagicMock()
        session.record_engine_line('btc: session_begin online=1')
        session.record_engine_line('btc: pause_exit loser=P1 P1=1 P2=2 target=2')
        session.record_engine_line('btc: session_end')
        self.assertEqual(session.summary['duel_exit_score'],[1,2])
        self.assertFalse(session.summary.get('ranked_completed'))
        session.record_engine_line('btc: session_begin online=1')
        self.assertIsNone(session.summary['duel_exit_score'])
        session.record_engine_line('btc: set_result P1=2 P2=0 target=2')
        self.assertTrue(session.summary['ranked_completed']);self.assertEqual(session.summary['ranked_score'],[2,0])
