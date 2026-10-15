import unittest
from unittest.mock import patch,Mock
from btc_matchmaking import environment,validate_url,LOCAL_MATCHMAKING,DEFAULT_MATCHMAKING


class MatchmakingTests(unittest.TestCase):
    def test_default_is_own_worker_and_empty_explicitly_disables_codes(self):
        self.assertEqual(environment({}),{"BT3_MATCH_URL":DEFAULT_MATCHMAKING,"BTC_MATCH_UNCONFIGURED":None})
        self.assertEqual(environment({"btc_matchmaking_url":""}),{"BT3_MATCH_URL":LOCAL_MATCHMAKING,"BTC_MATCH_UNCONFIGURED":"1"})

    def test_custom_worker_and_local_test_endpoint(self):
        self.assertEqual(environment({"btc_matchmaking_url":"https://btc.example.workers.dev/"}),
                         {"BT3_MATCH_URL":"https://btc.example.workers.dev","BTC_MATCH_UNCONFIGURED":None})
        self.assertEqual(validate_url("http://127.0.0.1:8787"),LOCAL_MATCHMAKING)
        self.assertEqual(environment({}, {"BT3_MATCH_URL":"https://btc.example.workers.dev"})["BTC_MATCH_UNCONFIGURED"],None)

    def test_reject_official_and_unsafe_urls(self):
        for value in ("https://odd-surf-0af7.bt3decomp.workers.dev","https://other.bt3decomp.workers.dev",
                      "http://example.com","https://user:secret@example.com","https://example.com/v1/host",
                      "file:///tmp","https://example.com?q=a","https://example.com/#a","https://example.com:99999",
                      "https://exam\nple.com","https://example .com"):
            with self.subTest(url=value),self.assertRaises(ValueError):validate_url(value)

    def test_configuration_dialog_preserves_other_preferences(self):
        import competitive_release_gui as gui
        app=gui.ReleaseApp.__new__(gui.ReleaseApp);app.root=Mock();app.busy=False;app.session=None;app._append=Mock()
        with patch.object(gui.core,"load_config",return_value={"runtime":"keep"}),patch.object(gui.core,"save_config") as save,patch.object(gui.simpledialog,"askstring",return_value="https://btc.example.workers.dev"):
            app.configure_matchmaking()
        self.assertEqual(save.call_args.args[0],{"runtime":"keep","btc_matchmaking_url":"https://btc.example.workers.dev"})

    def test_room_service_dialog_preserves_runtime(self):
        import competitive_release_gui as gui
        app=gui.ReleaseApp.__new__(gui.ReleaseApp);app.root=Mock();app.busy=False;app.session=None;app._append=Mock()
        with patch.object(gui.core,"load_config",return_value={"runtime":"keep"}),patch.object(gui.core,"save_config") as save,patch.object(gui.simpledialog,"askstring",return_value="https://btc-test.trycloudflare.com/"):
            app.configure_room_service()
        self.assertEqual(save.call_args.args[0],{"runtime":"keep","btc_room_service_url":"https://btc-test.trycloudflare.com"})
