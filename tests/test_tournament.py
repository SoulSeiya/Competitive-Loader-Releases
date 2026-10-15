import unittest
from rising_tournament import Tournament, TournamentError
from rising_room import Room, RoomError, RoomServer, RoomClient, PROTOCOL


def player(uid, bot=False):
    return dict(id=uid, name=f"P{uid}", bot=bot)


class TournamentTests(unittest.TestCase):
    def engine(self, count=6, bots=False):
        events = []
        t = Tournament(events.append, shuffle=lambda values: None)
        t.configure("Androides", 2, 2)
        for uid in range(1, count+1):
            t.register(player(uid, bots), ["A16", "A17"])
        return t, events

    def test_all_bracket_sizes_two_to_32(self):
        for count in range(2, 33):
            with self.subTest(count=count):
                t, events = self.engine(count)
                t.start()
                self.assertEqual(len(t.matches), (1 << (count-1).bit_length()) - 1)
                fights = 0
                while t.status == "running":
                    m = t.matches[t.current-1]
                    self.assertTrue(m["p1"] and m["p2"])
                    first = t.current
                    t.report(m["p1"], t.id, first, [2, 1])
                    self.assertEqual(t.current, first)
                    t.report(m["p2"], t.id, first, [2, 1])
                    revision = t.revision
                    t.report(m["p1"], t.id, first, [2, 1])
                    self.assertEqual(t.revision, revision)
                    fights += 1
                self.assertEqual(fights, count-1)
                self.assertIn(t.champion, t.entrants)
                self.assertEqual(sum("Campeón:" in e for e in events), 1)

    def test_six_players_have_two_byes_and_five_real_matches(self):
        t, events = self.engine()
        t.start()
        self.assertEqual(sum(m["state"] == "done" for m in t.matches), 2)
        self.assertEqual(len(t.matches), 7)
        self.assertTrue(any("Próxima pelea" in e for e in events))

    def test_bad_rosters_config_and_closed_registration(self):
        t, _ = self.engine(2)
        for roster in ([], ["A", "B", "C"], ["A", "a"], [""], [None]):
            with self.assertRaises(TournamentError): t.register(player(9), roster)
        for ft in (0, 6, True):
            with self.assertRaises(TournamentError): t.configure("Torneo", ft, 1)
        with self.assertRaises(TournamentError): t.configure("\n", 2, 1)
        self.assertEqual(len(t.entrants), 2)
        t.start()
        with self.assertRaises(TournamentError): t.register(player(3), ["A"])
        with self.assertRaises(TournamentError): t.start()

    def test_mismatched_reports_stale_tournament_and_unauthorized(self):
        t, events = self.engine(2)
        t.start(); mid=t.current
        with self.assertRaises(TournamentError): t.report(999, t.id, mid, [2, 0])
        with self.assertRaises(TournamentError): t.report(1, "old", mid, [2, 0])
        with self.assertRaises(TournamentError): t.report(1, t.id, mid, [2, 2])
        t.report(1, t.id, mid, [2, 0]); t.report(2, t.id, mid, [0, 2])
        self.assertEqual(t.status, "running")
        self.assertTrue(any("distintos" in e for e in events))
        t.report(2, t.id, mid, [2, 0])
        self.assertEqual(t.champion, 1)
        with self.assertRaises(TournamentError): t.report(2, t.id, mid, [0, 2])

    def test_bot_simulation_and_role_of_nonplaying_host(self):
        t, _ = self.engine(5, bots=True)
        t.start()
        self.assertEqual(t.snapshot(999)["role"], 0)
        while t.status == "running": t.simulate()
        self.assertTrue(t.champion)
        t, _ = self.engine(2)
        t.start()
        with self.assertRaises(TournamentError): t.simulate()

    def test_departures_and_forfeit_propagation(self):
        t, _ = self.engine(8)
        t.start()
        for uid in range(2, 9): t.disqualify(uid)
        self.assertEqual(t.status, "finished")
        self.assertEqual(t.champion, 1)
        t, _ = self.engine(2)
        t.withdraw(2)
        with self.assertRaises(TournamentError): t.start()

    def test_match_code_owned_by_current_p1(self):
        t, _ = self.engine(4)
        t.start(); m=t.matches[t.current-1]
        with self.assertRaises(TournamentError): t.match_code(m["p2"], t.id, m["id"], "ABCDEF")
        t.match_code(m["p1"], t.id, m["id"], "ABCDEF")
        t.match_code(m["p1"], t.id, m["id"], "ABCDEF")
        self.assertEqual(t.snapshot(m["p2"])["matches"][m["id"]-1]["code"], "ABCDEF")

    def test_http_room_host_controls_bracket_and_bots(self):
        server = RoomServer("Sala", "Host", 0, bind="127.0.0.1")
        try:
            host=RoomClient("127.0.0.1", server.port, server.room.host_token)
            a=RoomClient("127.0.0.1", server.port)
            a.send("join",name="P2",key=server.room.key,edition="BTC",protocol=PROTOCOL)
            with self.assertRaises(RoomError): a.send("tournament_start")
            host.send("tournament_config",title="Androides",ft=2,characters=2)
            host.send("tournament_register",roster=["A16"])
            a.send("tournament_register",roster=["A17"])
            state=host.send("tournament_start")["tournament"]
            self.assertEqual(state["enrolled"],2)
            m=state["matches"][0]
            for client in (host,a): client.send("tournament_report",tournament_id=state["id"],match=m["id"],score=[2,1])
            self.assertEqual(a.send("poll")["tournament"]["status"],"finished")
            old=state["id"]
            state=host.send("tournament_reset")["tournament"]
            self.assertNotEqual(state["id"],old)
            self.assertEqual(state["enrolled"],0)
        finally: server.close()
