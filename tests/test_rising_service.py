import unittest
from unittest.mock import patch
from rising_room import PROTOCOL, RoomError
from rising_service import Coordinator, ServiceClient, ServiceServer, room_code


class ServiceTests(unittest.TestCase):
    def test_four_player_lab_human_bot_semis_then_both_humans_even_after_losses(self):
        with patch('rising_game_bots.GameBotProcesses') as manager:
            coordinator=Coordinator(combat_test_runtime='mock-runtime')
            server=ServiceServer(port=0,coordinator=coordinator)
            try:
                url=f'http://127.0.0.1:{server.port}'
                host=ServiceClient(url)
                s=host.send('create',name='Host',title='Four',capacity=8,protocol=PROTOCOL,edition='BTC')
                self.assertEqual(len(s['users']),3);self.assertEqual(s['capacity'],4)
                guest=ServiceClient(url,s['room_code'])
                s=guest.send('join',name='Friend',protocol=PROTOCOL,edition='BTC')
                self.assertEqual(s['tournament']['enrolled'],4)
                human_ids={host.send('poll')['self_id'],s['self_id']}
                room=coordinator.rooms[host.code]
                clients={u['id']:ServiceClient(url,host.code,token) for token,u in room.users.items()}
                s=host.send('tournament_start')
                for mid in (1,2):
                    t=s['tournament'];m=t['matches'][mid-1]
                    self.assertIn(m['p1'],human_ids)
                    self.assertNotIn(m['p2'],human_ids)
                    for uid in (m['p1'],m['p2']):s=clients[uid].send('tournament_report',tournament_id=t['id'],match=mid,score=[0,1])
                t=s['tournament'];m=t['matches'][2]
                self.assertEqual({m['p1'],m['p2']},human_ids)
                for uid in human_ids:s=clients[uid].send('tournament_report',tournament_id=t['id'],match=3,score=[1,0])
                self.assertEqual(s['tournament']['status'],'finished')
                self.assertEqual(s['tournament']['champion'],m['p1'])
            finally:server.close()
            manager.return_value.close.assert_called_once()

    def test_room_code_and_combat_code_do_not_collide(self):
        server=ServiceServer(port=0)
        try:
            url=f"http://127.0.0.1:{server.port}"
            host=ServiceClient(url)
            s=host.send("create",name="Host",title="Codes",capacity=3,protocol=PROTOCOL,edition="BTC")
            guest=ServiceClient(url,s["room_code"])
            guest.send("join",name="Guest",protocol=PROTOCOL,edition="BTC")
            for c in (host,guest):c.send("tournament_register",roster=["A"])
            s=host.send("tournament_start");t=s["tournament"]
            owner=host if t["matches"][0]["p1"]==s["self_id"] else guest
            room=owner.code
            owner.send("tournament_code",tournament_id=t["id"],match=1,code="ABCDEF")
            self.assertEqual(owner.code,room)
            self.assertEqual(guest.send("poll")["tournament"]["matches"][0]["code"],"ABCDEF")
            self.assertEqual(host.send("poll")["room_code"],"BTC-"+room)
        finally:server.close()
    def test_remote_host_bots_chat_permissions_kick_and_cleanup(self):
        server=ServiceServer(port=0)
        try:
            host=ServiceClient(f"http://127.0.0.1:{server.port}")
            s=host.send("create",name="Host",title="Friends",capacity=5,protocol=PROTOCOL,edition="BTC")
            guest=ServiceClient(f"http://127.0.0.1:{server.port}",s["room_code"])
            guest.send("join",name="Friend",protocol=PROTOCOL,edition="BTC")
            for op in ("bots_add","bots_remove"):
                with self.assertRaises(RoomError):guest.send(op,count=2)
            s=host.send("bots_add",count=2)
            self.assertEqual(len(s["users"]),4)
            bots=[u for u in s["users"] if u["bot"]]
            self.assertEqual(len(bots),2)
            self.assertTrue(all(u["ready"] and not u["game_bot"] for u in bots))
            self.assertTrue(any("Bot de sala conectado" in m["text"] for m in guest.send("poll")["messages"]))
            host.send("kick",target=bots[0]["id"])
            self.assertEqual(len(guest.send("poll")["users"]),3)
            self.assertEqual(len(host.send("bots_remove")["users"]),2)
            host.send("leave")
            with self.assertRaises(RoomError):guest.send("poll")
            self.assertFalse(server.coordinator.bots)
        finally:server.close()

    def test_service_bot_heartbeat_does_not_keep_host_alive(self):
        now=[0];service=Coordinator(clock=lambda:now[0])
        s=service.handle(dict(op="create",name="Host",title="Expiry",capacity=4,protocol=PROTOCOL,edition="BTC"))
        args=dict(code=s["room_code"],token=s["token"])
        service.handle(dict(op="bots_add",count=2,**args))
        now[0]=25;service.handle(dict(op="poll",**args))
        now[0]=50
        self.assertEqual(len(service.handle(dict(op="poll",**args))["users"]),3)
        now[0]=81
        with self.assertRaises(RoomError):service.handle(dict(op="poll",**args))
        self.assertFalse(service.bots)

    def test_32_members_and_capacity(self):
        service=Coordinator()
        first=service.handle(dict(op="create",name="Host",title="Full",capacity=32,protocol=PROTOCOL,edition="BTC"))
        for i in range(31):
            state=service.handle(dict(op="join",code=first["room_code"],name=f"Player {i}",protocol=PROTOCOL,edition="BTC"))
        self.assertEqual(len(state["users"]),32)
        self.assertEqual(len({u["id"] for u in state["users"]}),32)
        with self.assertRaisesRegex(RoomError,"llena"):
            service.handle(dict(op="join",code=first["room_code"],name="Extra",protocol=PROTOCOL,edition="BTC"))

    def test_four_clients_share_code_chat_bracket_and_results(self):
        server=ServiceServer(port=0)
        url=f"http://127.0.0.1:{server.port}"
        clients=[]
        try:
            host=ServiceClient(url);clients.append(host)
            created=host.send("create",name="Host",title="BTC test",capacity=4,protocol=PROTOCOL,edition="BTC")
            self.assertEqual(len(created["room_code"]),10)
            for name in ("Two","Three","Four"):
                client=ServiceClient(url,created["room_code"]);clients.append(client)
                client.send("join",name=name,protocol=PROTOCOL,edition="BTC")
            with self.assertRaises(RoomError):
                ServiceClient(url,host.code).send("join",name="Five",protocol=PROTOCOL,edition="BTC")
            with self.assertRaises(RoomError):clients[1].send("kick",target=1)
            with self.assertRaises(RoomError):clients[1].send("tournament_start")
            host.send("tournament_config",title="Four",ft=1,characters=1)
            for c in clients:c.send("tournament_register",roster=["A"])
            host.send("tournament_start")
            clients[2].send("chat",text="Todos vemos el torneo")
            for c in clients:
                s=c.send("poll")
                self.assertEqual(len(s["users"]),4)
                self.assertEqual(s["messages"][-1]["text"],"Todos vemos el torneo")
            by_id={c.send("poll")["self_id"]:c for c in clients}
            for _ in range(3):
                t=host.send("poll")["tournament"];m=t["matches"][t["current"]-1]
                for uid in (m["p1"],m["p2"]):
                    by_id[uid].send("tournament_report",tournament_id=t["id"],match=m["id"],score=[1,0])
            self.assertTrue(all(c.send("poll")["tournament"]["status"]=="finished" for c in clients))
            host.send("kick",target=clients[1].send("poll")["self_id"])
            with self.assertRaises(RoomError):clients[1].send("poll")
            host.send("leave")
            with self.assertRaises(RoomError):clients[2].send("poll")
        finally:server.close()

    def test_isolation_expiry_and_no_guest_bot_privileges(self):
        now=[0];service=Coordinator(clock=lambda:now[0])
        def create(name):return service.handle(dict(op="create",name=name,title=name,capacity=32,protocol=PROTOCOL,edition="BTC"))
        a,b=create("A"),create("B")
        guest=service.handle(dict(op="join",code=a["room_code"],name="Guest",bot=True,game_bot=True,protocol=PROTOCOL,edition="BTC"))
        self.assertFalse(guest["users"][-1]["bot"])
        self.assertFalse(guest["users"][-1]["game_bot"])
        with self.assertRaises(RoomError):service.handle(dict(op="poll",code=b["room_code"],token=guest["token"]))
        now[0]=31
        with self.assertRaises(RoomError):service.handle(dict(op="poll",code=a["room_code"],token=a["token"]))
        self.assertFalse(service.rooms)

    def test_invalid_codes_transport_and_rate(self):
        for value in (None,"", "AAAAA", "ABC/DE", "IIIIII"):
            with self.assertRaises(RoomError):room_code(value)
        for url in ("http://example.com", "https://user:secret@example.com", "file:///tmp", "https://example.com/a"):
            with self.assertRaises(RoomError):ServiceClient(url)
        service=Coordinator()
        for _ in range(60):
            with self.assertRaises(RoomError):service.handle(dict(op="join",code="AAAAAA"))
        with self.assertRaisesRegex(RoomError,"Demasiados"):
            service.handle(dict(op="join",code="AAAAAA"))
