import copy,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from combat_activity import action_events,clean_events,describe_event
from combat_trace import PracticeCharacterJournal

def row(blank,action=11,slot=None,ability=None,counter=0):
    side={'side':1,'roster_id':3,'character_id':3,'name':'Goku (Fin)','member':0,'team_size':2,'variant':0,
          'action_id':action,'action_class':slot,'ability_id':ability,'action_frame':counter}
    return {'blank':blank,'phase':3,'input_confirmed':True,'resimulated':False,'stage':{'id':2,'start_id':2,'catalog_name':None,'catalog_source':None},'sides':[side,{**side,'side':2,'action_id':11,'action_class':None,'ability_id':None}]}

class ActivityTests(unittest.TestCase):
    def test_one_use_spans_native_phases_and_repeated_use_is_detected(self):
        frames=[row(1),row(2,253,0,111,0),row(3,255,0,111,0),row(4,255,0,111,1),row(5),row(6,253,0,111,0)]
        events=action_events(frames)
        self.assertEqual([e['blank'] for e in events],[2,6])
        self.assertEqual(events[0]['ability_id'],111);self.assertTrue(events[0]['observed_start'])
        self.assertEqual(clean_events(events,6),events)
        self.assertIn('Goku (Fin) usa habilidad Blast 1',describe_event(events[0],'Rising'))
        self.assertIn('(Rising, P1)',describe_event(events[0],'Rising'))

    def test_same_action_restart_and_initial_state_are_labelled_truthfully(self):
        events=action_events([row(2,253,0,7,5),row(3,253,0,7,6),row(4,253,0,7,0)])
        self.assertEqual(len(events),2);self.assertFalse(events[0]['observed_start']);self.assertTrue(events[1]['observed_start'])
        self.assertIn('en curso',describe_event(events[0]))

    def test_actor_is_bound_to_side_and_only_local_journal_contains_client_alias(self):
        events=action_events([row(1),row(2,253,0,111)])
        snapshot={'epoch':1,'observations':[],'events':events,'_mode':1,'_players':['Rising','Rival']}
        with tempfile.TemporaryDirectory() as folder:
            journal=PracticeCharacterJournal(SimpleNamespace(snapshot=lambda **kw:snapshot),folder,cpu=False)
            journal.sample();journal.sample()
            lines=journal.actions_text.read_text(encoding='utf-8')
            self.assertEqual(lines.count('usa habilidad'),1);self.assertIn('(Rising, P1)',lines)
            self.assertFalse(journal.text_path.exists())
            self.assertNotIn('Rising',json.dumps(clean_events(events,2)))

    def test_predictive_and_unknown_ability_are_not_claimed_confirmed(self):
        events=action_events([row(1),row(2,262,2,None)])
        filtered=clean_events(events,1)
        self.assertFalse(filtered[0]['input_confirmed']);self.assertIn('ID no capturado',describe_event(filtered[0]))
        bad=copy.deepcopy(events);bad[0]['ability_id']=32768
        with self.assertRaises(ValueError):clean_events(bad,2)

    def test_recent_ability_is_kept_when_many_movement_states_follow(self):
        frames=[row(1),row(2,253,0,11)]+[row(i,12+i%10,counter=0) for i in range(3,80)]
        events=action_events(frames)
        self.assertLessEqual(len(events),24);self.assertTrue(any(e['kind']=='ability' and e['blank']==2 for e in events))
        clean_events(events,80)

    def test_victim_rush_states_are_not_reported_as_using_their_own_ability(self):
        events=action_events([row(1),row(2,0x139,2,500)])
        self.assertEqual(events[-1]['kind'],'action');self.assertIsNone(events[-1]['ability_class'])
        self.assertNotIn('usa habilidad',describe_event(events[-1],'Víctima'))
        clean_events(events,2)

    def test_large_valid_evidence_stays_inside_receiver_envelope(self):
        from diagnostic_reports import DesyncCapture
        sample=row(100,253,0,111)
        for f in sample['sides']:f['name']='"'*127
        observations=[{**copy.deepcopy(sample),'blank':i} for i in range(100,116)]
        events=[{**action_events([row(1),row(2,253,0,111)])[0],'blank':i,'character_name':'"'*127} for i in range(100,124)]
        parser=DesyncCapture({'payload_sha256':{('p'+str(i)+'.o'):'a'*64 for i in range(32)}},lambda r:None)
        parser.combat={'observations':observations,'events':events}
        report=parser.report()
        self.assertLessEqual(len(json.dumps(report).encode('utf-8')),22000)
        self.assertEqual(len(parser.combat['observations']),16) # Trimming never mutates the captured evidence.

if __name__=='__main__':unittest.main()
