import json
from pathlib import Path
import tempfile
import unittest
from diagnostic_history import history_reports
from diagnostic_reports import ReportManager
from player_profile import ProfileStore
from unittest.mock import patch

class HistoryTests(unittest.TestCase):
    def test_closed_sessions_are_summaries_not_desync_and_ids_are_stable(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);session=root/'20261031-200240-1d2086e1';session.mkdir()
            (session/'session.json').write_text(json.dumps({'status':'closed','exit_code':'0x00000000','runtime':'C:/Users/Private','token':'SECRET','online_observed':False,'loader_version':'2.0.0'}))
            (session/'online.log').write_text('private chat: SECRET\nSESSION_END status=closed online=False desync=False')
            a=history_reports(root,'a'*32);b=history_reports(root,'a'*32)
            self.assertEqual(len(a),1);self.assertEqual(a[0]['report_id'],b[0]['report_id'])
            self.assertEqual(a[0]['kind'],'session');self.assertFalse(a[0]['summary']['desync'])
            self.assertIsNone(a[0]['divergence']);self.assertNotIn('SECRET',json.dumps(a));self.assertNotIn('Private',json.dumps(a))
            self.assertNotEqual(a[0]['report_id'],history_reports(root,'b'*32)[0]['report_id'])

    def test_history_does_not_scan_unrelated_folders_and_is_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'private').mkdir();(root/'private/session.json').write_text('{}')
            self.assertEqual(history_reports(root,'a'*32),[])
            store=ProfileStore(root/'profile.sqlite3','QA');manager=ReportManager(store,root)
            self.assertFalse(manager.history_requested.is_set());manager.request_history();self.assertTrue(manager.history_requested.is_set())
            manager.enabled(False)
            with self.assertRaises(ValueError):manager.request_history()

    def test_acknowledged_reports_are_not_queued_on_next_bulk_request(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);session=root/'20261031-200240-1d2086e1';session.mkdir();(session/'session.json').write_text('{"status":"crash"}')
            store=ProfileStore(root/'profile.sqlite3','QA');manager=ReportManager(store,root)
            report=history_reports(root,store.profile()['id'])[0]
            with store.connect() as db:db.execute('INSERT INTO settings VALUES(?,?)',('diagnostic_sent:'+report['report_id'],b'1'))
            with patch('social_client.protect',side_effect=AssertionError('should not persist')):manager._history()
            self.assertEqual(list(manager.root.glob('*.json')),[])

if __name__=='__main__':unittest.main()
