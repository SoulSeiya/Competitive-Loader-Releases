import ctypes as C
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from rising_tournament import Tournament, TournamentError


class DemoTests(unittest.TestCase):
    def test_game_bot_is_not_a_simulated_result_and_human_keeps_p1(self):
        t=Tournament(lambda _:None,shuffle=lambda _:None)
        t.register(dict(id=1,name="Game bot",bot=True,game_bot=True),["A"])
        t.register(dict(id=2,name="Human",bot=False),["B"])
        t.start()
        self.assertEqual(t.matches[0]["p1"],2)
        self.assertTrue(t.snapshot(2)["matches"][0]["playable"])
        t=Tournament(lambda _:None,shuffle=lambda _:None)
        for uid in (1,2):t.register(dict(id=uid,name=str(uid),bot=True,game_bot=True),["A"])
        t.start()
        with self.assertRaises(TournamentError):t.simulate()

    @unittest.skipUnless(os.name=="nt","Windows room bridge")
    def test_four_members_three_game_bots_all_against_human(self):
        from rising_room_bridge import RoomBridge,Command
        bridge=RoomBridge();bridge.runtime=Path("unused-by-mocked-manager")
        def command(op,**kwargs):
            bridge.shared.command=Command(op=op,**kwargs);bridge.shared.command_seq+=1
            until=time.monotonic()+8
            while bridge.shared.command_seq!=bridge.shared.ack_seq and time.monotonic()<until:time.sleep(.03)
            self.assertEqual(bridge.shared.command_seq,bridge.shared.ack_seq)
        try:
            with patch("rising_game_bots.GameBotProcesses") as manager:
                command(19,name=b"UT Rising")
                state=type(bridge.shared.state).from_buffer_copy(bytes(bridge.shared.state))
                self.assertEqual(state.count,4)
                self.assertTrue(bridge.invite.startswith("BTC-"))
                self.assertEqual(len(bridge.invite),10)
                self.assertEqual(sum(bool(u.flags&4) for u in state.users[:4]),3)
                self.assertEqual(state.tournament.enrolled,4)
                self.assertEqual(state.tournament.ft,1)
                self.assertEqual(state.tournament.mode,1)
                command(12)
                state=type(bridge.shared.state).from_buffer_copy(bytes(bridge.shared.state))
                self.assertEqual(state.tournament.current,1)
                self.assertEqual(state.tournament.role,1)
                self.assertEqual(state.tournament.count,3)
                self.assertTrue(all(m.p1==state.self_id and m.bots==2 for m in state.tournament.matches[:3]))
                command(5)
                manager.return_value.close.assert_called_once()
        finally:bridge.close()

    def test_human_plays_every_bot_even_after_losing(self):
        from rising_tournament import validate_snapshot
        t=Tournament(lambda _:None)
        for uid in range(1,5):
            t.register(dict(id=uid,name=str(uid),bot=uid!=1,game_bot=uid!=1),["A"])
        t.prepare_challenge(1);t.start()
        for mid in range(1,4):
            self.assertEqual(t.current,mid)
            m=t.matches[mid-1]
            self.assertEqual(m["p1"],1)
            for uid in (1,m["p2"]):t.report(uid,t.id,mid,[0,t.ft])
            validate_snapshot(t.snapshot(1))
        self.assertEqual(t.status,"finished")
        self.assertIsNone(t.champion)

    @unittest.skipUnless(os.name=="nt","Windows owned job objects")
    def test_owned_job_terminates_only_its_helper(self):
        from rising_game_bots import OwnedJob,ExtendedLimits
        self.assertEqual(C.sizeof(ExtendedLimits),144)
        owned=subprocess.Popen([sys.executable,"-c","import time;time.sleep(20)"],creationflags=subprocess.CREATE_NO_WINDOW)
        other=subprocess.Popen([sys.executable,"-c","import time;time.sleep(20)"],creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            job=OwnedJob(owned);job.close();owned.wait(timeout=5)
            self.assertIsNone(other.poll())
        finally:
            for child in (owned,other):
                if child.poll() is None:child.terminate()
                child.wait(timeout=5)
