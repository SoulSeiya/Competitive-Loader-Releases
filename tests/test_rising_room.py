import ctypes as C
import json
import os
import time
import unittest
import urllib.error
import urllib.request

from rising_room import PROTOCOL, Room, RoomClient, RoomError, RoomServer


def join(room, name="Invitado"):
    return room.handle(dict(op="join", name=name, key=room.key, protocol=PROTOCOL, edition="BTC"))


class RoomTests(unittest.TestCase):
    def test_membership_capacity_names_and_invitation(self):
        room = Room("Torneo de androides", "Host", 2)
        for change in ({"key": "incorrecta"}, {"protocol": 999}, {"edition": "otro"}):
            data = dict(op="join", name="P2", key=room.key, protocol=PROTOCOL, edition="BTC")
            data.update(change)
            with self.assertRaises(RoomError): room.handle(data)
        with self.assertRaises(RoomError): join(room, "host")
        result = join(room)
        self.assertEqual(len(result["users"]), 2)
        with self.assertRaises(RoomError): join(room, "P3")
        self.assertNotIn("seen", result["users"][0])
        self.assertNotIn(room.host_token, json.dumps(result))
        self.assertNotIn(room.key, json.dumps(result))

    def test_host_only_kick_revokes_token_and_announces(self):
        room = Room("BTC", "Host")
        a, b = join(room, "A"), join(room, "B")
        with self.assertRaises(RoomError):
            room.handle(dict(op="kick", token=a["token"], target=b["self_id"]))
        result = room.handle(dict(op="kick", token=room.host_token, target=a["self_id"]))
        self.assertEqual([u["name"] for u in result["users"]], ["Host", "B"])
        self.assertIn("expulsado", result["messages"][-1]["text"])
        with self.assertRaises(RoomError): room.handle(dict(op="poll", token=a["token"]))
        with self.assertRaises(RoomError): room.handle(dict(op="kick", token=room.host_token, target=room.host_id))

    def test_chat_ready_and_history_bounds(self):
        now = [100.0]
        room = Room("Sala", "Host", clock=lambda: now[0])
        a = join(room)
        token = a["token"]
        self.assertTrue(room.handle(dict(op="ready", token=token))["users"][1]["ready"])
        for i in range(70):
            now[0] += 0.6
            room.handle(dict(op="poll", token=room.host_token))
            result = room.handle(dict(op="chat", token=token, text="Hola ñ 世界 " + str(i)))
        self.assertEqual(len(result["messages"]), 64)
        self.assertEqual(result["messages"][-1]["author"], "Invitado")
        with self.assertRaises(RoomError): room.handle(dict(op="chat", token=token, text="spam"))

    def test_heartbeat_expiry_and_host_closure(self):
        now = [100.0]
        room = Room("Sala", "Host", clock=lambda: now[0])
        a = join(room)
        now[0] += 20
        room.handle(dict(op="poll", token=room.host_token))
        now[0] += 11
        result = room.handle(dict(op="poll", token=room.host_token))
        self.assertEqual(len(result["users"]), 1)
        with self.assertRaises(RoomError): room.handle(dict(op="poll", token=a["token"]))
        room.handle(dict(op="leave", token=room.host_token))
        with self.assertRaises(RoomError): join(room)

    def test_real_http_roster_chat_kick_and_close(self):
        server = RoomServer("BTC en red", "Host", 0, bind="127.0.0.1")
        try:
            host = RoomClient("127.0.0.1", server.port, server.room.host_token)
            a, b = [RoomClient("127.0.0.1", server.port) for _ in range(2)]
            for client, name in ((a, "Jugador A"), (b, "Jugador B")):
                client.send("join", name=name, key=server.room.key, protocol=PROTOCOL, edition="BTC")
            self.assertEqual(len(host.send("poll")["users"]), 3)
            a.send("chat", text="Combate: A vs B, FT2")
            self.assertIn("FT2", b.send("poll")["messages"][-1]["text"])
            host.send("kick", target=a.send("poll")["self_id"])
            with self.assertRaises(RoomError): a.send("poll")
            host.send("leave")
            with self.assertRaises(RoomError): b.send("poll")
        finally:
            server.close()

    def test_http_rejects_malformed_and_oversized_requests(self):
        server = RoomServer("BTC", "Host", 0, bind="127.0.0.1")
        try:
            for body in (b"[]", b"not json", b"x" * 4097):
                req = urllib.request.Request(f"http://127.0.0.1:{server.port}/btc-room", body)
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(req, timeout=2)
                self.assertEqual(error.exception.code, 400)
                error.exception.close()
        finally:
            server.close()

    def test_client_accepts_hosts_only(self):
        for address in ("http://127.0.0.1", "host/path", "host:7001", "user@host", ""):
            with self.assertRaises(RoomError): RoomClient(address, 7001)


@unittest.skipUnless(os.name == "nt", "Windows named shared memory")
class BridgeTests(unittest.TestCase):
    def test_shared_memory_two_loaders_chat_ready_and_expulsion(self):
        from rising_room_bridge import RoomBridge, Shared, Command, State, User, decoded
        self.assertEqual([C.sizeof(t) for t in (User, State, Command, Shared)], [76, 34140, 844, 35004])
        # Bind only loopback for the real HTTP server in this test.
        from unittest.mock import patch
        import rising_room_bridge as bridge_module
        original = bridge_module.RoomServer
        def local_server(*args):
            return original(*args, bind="127.0.0.1")
        host, guest = RoomBridge(), RoomBridge()
        def wait(predicate):
            until = time.monotonic() + 6
            while time.monotonic() < until:
                if predicate(): return
                time.sleep(.03)
            self.fail("Bridge did not reach expected state")
        def command(bridge, op, **values):
            c = Command(op=op, **values)
            bridge.shared.command = c
            bridge.shared.command_seq += 1
            wait(lambda: bridge.shared.command_seq == bridge.shared.ack_seq)
        try:
            # Find a free loopback port, then close the reservation before creating the host.
            import socket
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]
            with patch.object(bridge_module, "RoomServer", local_server):
                command(host, 1, name=b"Host", title=b"BTC Lab", port=port, capacity=4)
            self.assertEqual(host.shared.state.connected, 1)
            command(guest, 2, name=b"Guest", address=b"127.0.0.1", key=host.shared.state.key, port=port)
            wait(lambda: host.shared.state.count == 2)
            command(guest, 3, text=b"Pelea Host vs Guest")
            wait(lambda: host.shared.state.chat_count >= 3)
            self.assertIn("Pelea Host", decoded(host.shared.state.chat[2]))
            command(guest, 6)
            wait(lambda: host.shared.state.users[1].flags == 1)
            command(host, 4, target=guest.shared.state.self_id)
            wait(lambda: guest.shared.state.connected == 0)
            self.assertIn("perteneces", decoded(guest.shared.state.notice))
        finally:
            guest.close(); host.close()
        self.assertFalse(host.thread.is_alive())
        self.assertFalse(guest.thread.is_alive())
