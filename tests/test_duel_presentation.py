import unittest
from duel_presentation import present_duel

class DuelPresentationTests(unittest.TestCase):
    def room(self):
        return {'room_code':'BTC-ABCD23','self_id':2,'combat':{'id':'set1','status':'running','ft':2,'seconds':180,'characters':2,'current':1,
          'matches':[{'id':1,'p1':1,'p2':2,'name1':'Rising','name2':'Štørm','score':None,'winner':None}]}}

    def test_confirmed_wins_keep_p1_p2_order_and_do_not_accumulate(self):
        room=self.room();live={'combat_id':'set1','score':[1,0],'online':True}
        for _ in range(3):
            v=present_duel(room=room,live=live)
            self.assertEqual(v['score'],[1,0]);self.assertEqual(v['players'][1]['name'],'Štørm')
            self.assertTrue(v['players'][1]['is_self']);self.assertEqual(v['players'][1]['remaining'],2)
            self.assertEqual(v['phase'],'active')

    def test_result_of_different_set_is_ignored(self):
        v=present_duel(room=self.room(),live={'combat_id':'old','score':[2,0],'online':True})
        self.assertEqual(v['score'],[0,0]);self.assertIsNone(v['winner_name'])

    def test_native_final_is_pending_until_server_confirms_winner(self):
        v=present_duel(room=self.room(),live={'combat_id':'set1','score':[2,1],'completed':True})
        self.assertEqual(v['phase'],'confirming');self.assertIsNone(v['winner_name'])
        self.assertFalse(any(p['winner'] for p in v['players']))

    def test_server_result_wins_over_stale_native_score(self):
        room=self.room();room['combat'].update(status='finished',current=0,champion_name='Štørm')
        room['combat']['matches'][0].update(score=[1,2],winner=2)
        v=present_duel(room=room,live={'combat_id':'set1','score':[2,0]})
        self.assertEqual(v['score'],[1,2]);self.assertEqual(v['winner_name'],'Štørm')
        self.assertTrue(v['players'][1]['winner']);self.assertEqual(v['score_source'],'server')

    def test_new_pending_challenge_hides_old_finished_result(self):
        old=self.room();old['combat']['status']='finished'
        v=present_duel(room={'room_code':'BTC-NEW123'},last=old,peer_name='Nuevo rival',profile={'name':'Rising'},pending_rules={'ft':3,'seconds':240,'characters':2})
        self.assertEqual(v['phase'],'pending');self.assertEqual(v['ft'],3);self.assertEqual(v['players'][1]['name'],'Nuevo rival')
        self.assertIsNone(v['winner_name']);self.assertEqual(v['score'],[0,0])

    def test_invalid_scores_and_all_ft_targets(self):
        for ft in range(1,6):
            room=self.room();room['combat']['ft']=ft
            for bad in [[-1,0],[ft+1,0],[True,0],['1',0]]:
                self.assertEqual(present_duel(room=room,live={'combat_id':'set1','score':bad})['score'],[0,0])
            self.assertEqual(present_duel(room=room,live={'combat_id':'set1','score':[ft,0]})['players'][0]['remaining'],0)

    def test_idle_and_incoming_challenge(self):
        v=present_duel();self.assertEqual(v['phase'],'idle');self.assertIsNone(v['winner_name'])
        v=present_duel(room={'self_id':2,'duel':{'status':'pending','from':1,'to':2,'name1':'A','name2':'B','ft':2}})
        self.assertTrue(v['can_accept']);self.assertEqual(v['phase'],'pending')
