import time
import unittest

from rising_room_bridge import RoomBridge
from rising_service import ServiceServer


class HubCommandTests(unittest.TestCase):
    def wait_for(self, predicate):
        until = time.monotonic() + 5
        while time.monotonic() < until:
            if predicate(): return
            time.sleep(.03)
        self.fail("Desktop command did not complete")

    def test_desktop_room_chat_and_bracket_share_existing_identity(self):
        server = ServiceServer(port=0)
        host, guest = RoomBridge(), RoomBridge()
        try:
            url = f"http://127.0.0.1:{server.port}"
            host.submit(21, address=url, name="Rising", title="Prueba interfaz", capacity=4)
            self.wait_for(lambda: host.snapshot)
            token = host.client.token
            guest.submit(22, address=url, name="Rival", text=host.invite)
            self.wait_for(lambda: guest.snapshot)
            guest.submit(3, text="Chat desde la interfaz")
            self.wait_for(lambda: host.snapshot["messages"][-1]["text"] == "Chat desde la interfaz")
            host.submit(10, title="Copa BTC", ft=1, characters=1)
            host.submit(11, text="Androide 16")
            guest.submit(11, text="Goku")
            self.wait_for(lambda: host.snapshot["tournament"]["enrolled"] == 2)
            host.submit(12)
            self.wait_for(lambda: host.snapshot["tournament"]["status"] == "running")
            self.assertEqual(host.client.token, token)
            self.assertEqual(len(host.snapshot["users"]), 2)
            self.assertEqual(len(host.snapshot["tournament"]["matches"]), 1)
            self.assertIn(host.snapshot["tournament"]["role"], (1, 2))
            self.assertEqual(host.shared.command_seq, host.shared.ack_seq)
        finally:
            guest.close(); host.close(); server.close()
