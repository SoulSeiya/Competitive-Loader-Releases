import unittest
from unittest.mock import MagicMock
from rising_room_bridge import RoomBridge,Command
from rising_room import RoomError

class RoomCleanupTests(unittest.TestCase):
    def bridge(self):
        bridge=object.__new__(RoomBridge)
        bridge.observer=bridge.game_bots=bridge.bots=bridge.server=None
        bridge.preserve_membership=False;bridge.client=MagicMock();bridge.snapshot={'combat':{'status':'finished'}}
        bridge.local_address='127.0.0.1';bridge.log=MagicMock();bridge.invite='BTC-TEST12'
        return bridge

    def test_detach_does_not_close_room_before_peer_fetches_result(self):
        bridge=self.bridge();client=bridge.client
        bridge._execute(Command(op=46))
        client.send.assert_not_called();self.assertIsNone(bridge.client);self.assertIsNone(bridge.snapshot);self.assertEqual(bridge.invite,'')

    def test_unfinished_room_cannot_be_detached_silently(self):
        bridge=self.bridge();bridge.snapshot['combat']['status']='running'
        with self.assertRaises(RoomError):bridge._execute(Command(op=46))
        self.assertIsNotNone(bridge.client)

    def test_leave_clears_local_membership_even_when_network_is_unavailable(self):
        bridge=self.bridge();bridge.client.send.side_effect=OSError('offline')
        bridge._leave();self.assertIsNone(bridge.client);self.assertIsNone(bridge.snapshot);self.assertEqual(bridge.invite,'')


class TerminalRoomErrorTests(unittest.TestCase):
    def test_declined_or_expired_direct_room_is_released_without_waiting(self):
        from rising_room_bridge import terminal_room_error
        for message in ('La sala no existe o ha caducado','El anfitrión cerró la sala','Ya no perteneces a esta sala (expulsión o desconexión)'):
            self.assertTrue(terminal_room_error(message),message)

    def test_transient_network_errors_keep_the_membership(self):
        from rising_room_bridge import terminal_room_error
        for message in ('No se pudo conectar con el servicio','El servicio de salas no está disponible temporalmente',''):
            self.assertFalse(terminal_room_error(message),message)
