import ctypes as C
import os
import socket
import time
import unittest
from unittest.mock import patch
from rising_invite import make_invite, read_invite
from rising_room import PROTOCOL, RoomClient, RoomError, RoomServer
from rising_room_bots import RoomBots


def wait(test, predicate, timeout=6):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if predicate(): return
        time.sleep(.03)
    test.fail("No se alcanzó el estado esperado")


class InviteBotTests(unittest.TestCase):
    def test_invite_roundtrip_and_corruption(self):
        key = "abcdefghijklmnop"
        for address in ("127.0.0.1", "192.168.1.100", "btc-host.local"):
            code = make_invite(address, 7001, key)
            self.assertEqual(read_invite(code.lower()), (address, 7001, key))
            with self.assertRaises(RoomError): read_invite(code[:-4])
            changed = code[:12] + ("A" if code[12] != "A" else "B") + code[13:]
            with self.assertRaises(RoomError): read_invite(changed)
        for code in ("ABC123", "BTC1-", "BTC1-" + "A" * 301):
            with self.assertRaises(RoomError): read_invite(code)

    def test_invitation_connects_real_client(self):
        server = RoomServer("Codigo BTC", "Host", 0, bind="127.0.0.1")
        try:
            code = make_invite("127.0.0.1", server.port, server.room.key)
            address, port, key = read_invite(code)
            state = RoomClient(address, port).send("join", name="Invitado", key=key, protocol=PROTOCOL, edition="BTC")
            self.assertEqual(state["title"], "Codigo BTC")
            self.assertEqual(len(state["users"]), 2)
        finally: server.close()

    def test_real_bots_fill_32_ready_chat_kick_and_cleanup(self):
        server = RoomServer("Stress 32", "Host", 0, capacity=32, bind="127.0.0.1")
        bots = RoomBots(server, cycle=.15)
        host = RoomClient("127.0.0.1", server.port, server.room.host_token)
        try:
            self.assertEqual(bots.add(31), 31)
            state = host.send("poll")
            self.assertEqual(len(state["users"]), 32)
            self.assertEqual(sum(u["bot"] for u in state["users"]), 31)
            self.assertTrue(any(m["author"].startswith("Bot BTC") for m in state["messages"]))
            self.assertEqual(bots.add(1), 0)
            target = state["users"][-1]["id"]
            host.send("kick", target=target)
            wait(self, lambda: len(bots.users) == 30)
            time.sleep(.45)
            self.assertEqual(len(host.send("poll")["users"]), 31)  # No automatic rejoin.
            bots.close()
            self.assertEqual(len(host.send("poll")["users"]), 1)
            self.assertFalse(bots.thread.is_alive())
        finally:
            bots.close(); server.close()

    def test_guest_cannot_register_bot_identity(self):
        server = RoomServer("BTC", "Host", 0, bind="127.0.0.1")
        try:
            with self.assertRaises(RoomError):
                RoomClient("127.0.0.1", server.port).send("join", name="Bot falso", bot=True,
                    key=server.room.key, protocol=PROTOCOL, edition="BTC")
        finally: server.close()

    @unittest.skipUnless(os.name == "nt", "Windows bridge")
    def test_bridge_code_join_bots_and_guest_permissions(self):
        from rising_room_bridge import RoomBridge, Command, decoded
        host, guest = RoomBridge(), RoomBridge()
        def command(bridge, op, **values):
            bridge.shared.command = Command(op=op, **values)
            bridge.shared.command_seq += 1
            wait(self, lambda: bridge.shared.command_seq == bridge.shared.ack_seq)
        try:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0)); port=sock.getsockname()[1]
            with patch("rising_room_bridge.RoomServer", lambda *args: RoomServer(*args, bind="127.0.0.1")):
                command(host, 1, name=b"Host", title=b"Bots", address=b"127.0.0.1", port=port, capacity=4)
            self.assertTrue(decoded(host.shared.state.invite).startswith("BTC1-"))
            command(guest, 9, name=b"Code Guest", text=host.shared.state.invite)
            self.assertEqual(guest.shared.state.connected, 1)
            command(guest, 7, target=1)
            self.assertIn("anfitri", decoded(guest.shared.state.notice))
            command(host, 7, target=31)
            self.assertEqual(host.shared.state.count, 4)
            self.assertEqual(sum(bool(u.flags & 2) for u in host.shared.state.users[:4]), 2)
            command(host, 8)
            self.assertEqual(host.shared.state.count, 2)
        finally:
            guest.close(); host.close()
