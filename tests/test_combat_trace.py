import copy
import json
import struct
import unittest
from combat_trace import MAGIC,SIZE,FRAMES,FRAME,CAPACITY,NAMES,STAGE_NAMES,decode_snapshot,clean_combat,CombatTrace
from diagnostic_reports import DesyncCapture

def fixture():
    raw=bytearray(SIZE)
    struct.pack_into('<6I',raw,0,MAGIC,4,2,1,101,104)
    raw[NAMES+8*128:NAMES+8*128+12]=b'Bardock SSJ\0'
    raw[STAGE_NAMES+2*96:STAGE_NAMES+2*96+13]=b'Planet Namek\0'
    for blank,action in [(100,1),(101,253),(102,254),(104,260)]:
        sides=[8,8,0,2,1,action,-1,-1,blank-100,1,9,9,1,2,2,1,-1,-1,blank-100,2]
        FRAME.pack_into(raw,FRAMES+blank%CAPACITY*FRAME.size,1,blank,3,0,*sides,2,2)
    return raw

def evidence():return decode_snapshot(fixture(),102)

class TraceTests(unittest.TestCase):
    def test_costume_number_is_captured_and_filters_invalid_values(self):
        data=evidence();side=data['observations'][-1]['sides']
        self.assertEqual([f['costume'] for f in side],[1,2])
        self.assertEqual(clean_combat(data),data)
        bad=copy.deepcopy(data);bad['observations'][0]['sides'][0]['costume']=0
        self.assertIsNone(clean_combat(bad))
    def test_stage_id_and_destruction_survive_snapshot_report_and_cpu_journal(self):
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from combat_trace import PracticeCharacterJournal
        raw=fixture();struct.pack_into('<I',raw,24,2)
        # Same fighters: only the stage changes, e.g. a destroyed arena.
        struct.pack_into('<i',raw,FRAMES+102*FRAME.size+96,3)
        captured=decode_snapshot(raw,102)
        self.assertEqual(captured['observations'][-1]['stage']['id'],3)
        self.assertEqual(captured['observations'][-1]['stage']['start_id'],2)
        self.assertEqual(captured['observations'][0]['stage']['catalog_name'],'Planet Namek')
        self.assertEqual(clean_combat(captured),captured)
        with tempfile.TemporaryDirectory() as folder:
            journal=PracticeCharacterJournal(SimpleNamespace(snapshot=lambda **kw:decode_snapshot(raw,None,True)),folder)
            journal.sample()
            text=journal.text_path.read_text(encoding='utf-8')
            self.assertIn('Mapa ID 3 (inicial 2)',text)
            self.assertIn('catálogo del motor: Planet Namek',text)
        bad=copy.deepcopy(captured);bad['observations'][0]['stage']['id']=-1
        self.assertIsNone(clean_combat(bad))

    def test_cpu_journal_records_real_sampled_identities_and_transformations_only_locally(self):
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from combat_trace import PracticeCharacterJournal
        raw=fixture();struct.pack_into('<I',raw,24,2)
        trace=SimpleNamespace(snapshot=lambda **kwargs:decode_snapshot(raw,None,True))
        with tempfile.TemporaryDirectory() as folder:
            journal=PracticeCharacterJournal(trace,Path(folder));journal.sample();journal.sample()
            rows=[json.loads(line) for line in journal.path.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['mode'],'cpu_ft')
            self.assertEqual(rows[0]['sides'][0]['name'],'Bardock SSJ')
            # A new action alone is not a new character detection.
            struct.pack_into('<I',raw,20,105)
            FRAME.pack_into(raw,FRAMES+105*FRAME.size,1,105,3,0,8,10,0,2,1,200,-1,-1,5,1,9,9,1,2,2,1,-1,-1,5,2,2,2)
            journal.sample()
            rows=[json.loads(line) for line in journal.path.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(rows),2);self.assertEqual(rows[-1]['sides'][0]['character_id'],10)
            self.assertIn('Bardock SSJ',journal.text_path.read_text(encoding='utf-8'))
            self.assertNotIn('action_id',json.dumps(rows))
            struct.pack_into('<I',raw,24,1)
            self.assertIsNone(trace.snapshot()) # Going online never writes a CPU log.

    def test_characters_and_action_before_desync_survive_report(self):
        out=[];p=DesyncCapture({},out.append)
        p.line('btc: combat_trace '+json.dumps(evidence()))
        p.line('the two games differ at blank 102 (this copy aaaaaaaaaaaaaaaa, the other bbbbbbbbbbbbbbbb)')
        p.line('the two games no longer agree (desync)')
        self.assertEqual(out[0]['combat']['observations'][-1]['sides'][0]['name'],'Bardock SSJ')
        self.assertEqual(out[0]['combat']['observations'][-1]['sides'][0]['action_id'],254)
        self.assertEqual(out[0]['combat']['nearest_distance'],0)

    def test_frontier_is_conservative_and_future_frames_excluded(self):
        rows=evidence()['observations']
        self.assertEqual([r['blank'] for r in rows],[100,101,102])
        self.assertEqual([r['input_confirmed'] for r in rows],[True,True,False])

    def test_rollback_overwrites_prediction_and_other_session_is_excluded(self):
        raw=fixture();offset=FRAMES+102*FRAME.size
        struct.pack_into('<i',raw,offset+16+5*4,258)
        self.assertEqual(decode_snapshot(raw,102)['observations'][-1]['sides'][0]['action_id'],258)
        struct.pack_into('<I',raw,12,2)
        self.assertIsNone(decode_snapshot(raw,102))

    def test_no_future_stale_wrapped_or_incomplete_data_claimed(self):
        raw=fixture();self.assertIsNone(decode_snapshot(raw,99))
        self.assertIsNone(decode_snapshot(raw,10000))
        struct.pack_into('<I',raw,8,3);self.assertIsNone(decode_snapshot(raw,102))
        self.assertIsNone(decode_snapshot(raw[:-1],102))

    def test_reconstructed_dto_is_bounded_and_drops_unknown_fields(self):
        value=evidence();value['token']='private';value['observations'][0]['sides'][0]['path']='private'
        text=json.dumps(clean_combat(value));self.assertNotIn('private',text)
        for mutate in [lambda v:v.update(observations=v['observations']*20),
                       lambda v:v['observations'][0]['sides'][0].update(action_id=316),
                       lambda v:v['observations'][0]['sides'][0].update(name='x\nsecret')]:
            bad=copy.deepcopy(value);mutate(bad);self.assertIsNone(clean_combat(bad))
        value['observations'][-1]['input_confirmed']=True
        self.assertFalse(clean_combat(value)['observations'][-1]['input_confirmed'])

    def test_old_reports_unavailable_and_connection_reset_clears_old_combat(self):
        p=DesyncCapture({},lambda r:None);self.assertIsNone(p.report()['combat'])
        p.line('btc: combat_trace '+json.dumps(evidence()));self.assertIsNotNone(p.combat)
        p.line('connected directly;');self.assertIsNone(p.combat)

    def test_windows_mapping_matches_native_size_and_is_read_only_to_snapshot(self):
        t=CombatTrace()
        try:
            t.mapping[:]=fixture();before=t.mapping[:]
            self.assertEqual(t.snapshot(102),evidence());self.assertEqual(t.mapping[:],before)
        finally:t.close()

    def test_engine_reader_captures_before_emitting_and_keeps_history_line(self):
        from session_diagnostics import SessionDiagnostics
        from types import SimpleNamespace
        from unittest.mock import Mock
        d=object.__new__(SessionDiagnostics);out=[]
        d.summary={'desync_observed':False};d.local=Mock();d.online=Mock()
        d.report_capture=DesyncCapture({},out.append)
        d._combat_trace=SimpleNamespace(snapshot=lambda blank:evidence())
        d.record_engine_line('the two games differ at blank 102 (this copy aaaaaaaaaaaaaaaa, the other bbbbbbbbbbbbbbbb)')
        d.record_engine_line('the two games no longer agree (desync)')
        self.assertEqual(out[0]['combat'],evidence())
        self.assertTrue(any('combat_trace' in str(c) for c in d.online.info.call_args_list))
        # A delayed log from an older session must not attach the new fight's state.
        out.clear();d.report_capture.reset()
        d.record_engine_line('btc: session_begin online=1 trace_epoch=2')
        d.record_engine_line('the two games differ at blank 102 (this copy aaaaaaaaaaaaaaaa, the other bbbbbbbbbbbbbbbb)')
        d.record_engine_line('the two games no longer agree (desync)')
        self.assertIsNone(out[0]['combat'])

    def test_history_recovers_trace_without_uploading_raw_log(self):
        import tempfile
        from pathlib import Path
        from diagnostic_history import history_reports
        with tempfile.TemporaryDirectory() as folder:
            session=Path(folder)/'20261102-190000-abcdef12';session.mkdir()
            (session/'session.json').write_text('{"status":"desync","loader_version":"2.0.7"}',encoding='utf-8')
            (session/'online.log').write_text('btc: combat_trace '+json.dumps(evidence())+'\n'
                'the two games differ at blank 102 (this copy aaaaaaaaaaaaaaaa, the other bbbbbbbbbbbbbbbb)\n'
                'the two games no longer agree (desync)\nCHAT SECRET',encoding='utf-8')
            reports=history_reports(Path(folder),'a'*32)
            self.assertEqual(reports[0]['combat'],evidence())
            self.assertNotIn('SECRET',json.dumps(reports))

    def test_old_receiver_cannot_silently_discard_combat(self):
        import io
        from unittest.mock import Mock,patch
        from types import SimpleNamespace
        from diagnostic_reports import ReportManager
        manager=object.__new__(ReportManager)
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.read.return_value=b'{"combat_trace":0}'
        opener=Mock();opener.open.return_value=response
        with patch('rising_service.ServiceClient',return_value=SimpleNamespace(url='https://example.test/v1/rooms',opener=opener)),patch('social_client.credentials',side_effect=AssertionError('no credentials needed for capability check')):
            with self.assertRaises(ValueError):manager._send({'combat':evidence()})
        self.assertEqual(opener.open.call_count,1)
        self.assertEqual(opener.open.call_args.args[0].get_method(),'GET')

if __name__=='__main__':unittest.main()
