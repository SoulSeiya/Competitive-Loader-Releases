import unittest
from rising_room import PROTOCOL, RoomError
from rising_service import Coordinator, ServiceClient, ServiceServer, room_code


class ServiceTests(unittest.TestCase):
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
