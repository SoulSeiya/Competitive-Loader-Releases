import unittest
from unittest.mock import Mock, patch
from temporary_room_host import TestHost


class TemporaryHostTests(unittest.TestCase):
    def test_stop_only_terminates_owned_children_and_cancels_monitor(self):
        host=TestHost.__new__(TestHost)
        host.root=Mock();host.timer="owned-timer"
        running,finished=Mock(),Mock()
        running.poll.return_value=None;finished.poll.return_value=0
        host.children=[running,finished];host.files=[Mock()]
        stream=host.files[0]
        host.address=Mock();host.status=Mock();host.start_button=Mock();host.copy_button=Mock()
        host.url="https://test.trycloudflare.com"
        host.stop()
        running.terminate.assert_called_once();running.wait.assert_called_once_with(timeout=4)
        finished.terminate.assert_not_called();stream.close.assert_called_once()
        host.root.after_cancel.assert_called_once_with("owned-timer")
        self.assertEqual(host.children,[]);self.assertEqual(host.files,[])

    def test_hostname_is_not_ready_until_connection_is_registered(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        host=TestHost.__new__(TestHost);host.root=Mock();host.children=[Mock()]
        host.children[0].poll.return_value=None
        host.url="";host.started=0;host.address=Mock();host.status=Mock();host.copy_button=Mock()
        with TemporaryDirectory() as directory:
            host.logdir=Path(directory)
            log=host.logdir/'tunnel.log'
            log.write_text('https://test.trycloudflare.com')
            with patch('temporary_room_host.core.save_config') as save,patch('temporary_room_host.core.load_config',return_value={'runtime':'keep'}):
                host.check();save.assert_not_called()
                log.write_text('https://test.trycloudflare.com Registered tunnel connection')
                host.check()
                save.assert_called_once_with({'runtime':'keep','btc_room_service_url':'https://test.trycloudflare.com'})
