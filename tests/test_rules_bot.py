import time
import unittest
from unittest.mock import patch
from rising_room_bridge import RoomBridge,Command

class RulesBotTests(unittest.TestCase):
    def test_private_fixture_has_one_real_bot_and_negotiates_rules(self):
        class NoProcesses:
            def __init__(self,*args,**kwargs):pass
            def close(self):pass
        bridge=RoomBridge()
        try:
            bridge.runtime='unused-in-this-controller-test'
            with patch('rising_game_bots.GameBotProcesses',NoProcesses):
                bridge._execute(Command(op=26,name=b'Rising'))
            state=bridge.snapshot
            self.assertEqual(len(state['users']),2)
            self.assertEqual(sum(u.get('game_bot',False) for u in state['users']),1)
            bridge.client.send('tournament_config',title='Reglas',ft=3,characters=2,seconds=360)
            state=bridge.client.send('tournament_start')
            t=state['tournament']
            self.assertEqual((t['ft'],t['characters'],t['seconds'],t['role']),(3,2,360,1))
            self.assertEqual(len(t['matches']),1)
            bridge.snapshot=state;bridge._publish()
            native=bridge.shared.state.tournament
            self.assertEqual((native.ft,native.characters,native.seconds),(3,2,360))
            del native
        finally:bridge.close()
