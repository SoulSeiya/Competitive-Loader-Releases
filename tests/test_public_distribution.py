from pathlib import Path
import unittest
from unittest import mock

import competitive_loader as core


class PublicDistributionTests(unittest.TestCase):
    def test_native_menu_chat_and_pad_functions_remain_original(self):
        names = ("PATCHES", "CALL_WRAPPERS", "ENTRY_PATCH_TARGETS", "CALL_WRAPPER_TARGETS",
                 "PATCH_TARGETS", "PATCH_OBJECTS", "PATCH_SYMBOLS", "ONLINE_TIME_LABEL_PATCHES")
        with (mock.patch.multiple(core, **{name: getattr(core, name) for name in names}),
              mock.patch.object(core, "sha256_file", return_value=next(iter(core.REVIEWED_DECOMP_HASHES)))):
            core.use_official_online_profile(Path("reviewed.exe"), True, True, True)
            for name in ("MainMenu_Run", "PortTbo_Run", "Port_PadRead", "_ZL9build_netv",
                         "_ZN5ImGui5BeginEPKcPbi", "PortChat_Count", "PortChat_Line", "PortChat_Say"):
                self.assertNotIn(name, core.CALL_WRAPPER_TARGETS)
            self.assertEqual(core.PATCH_SYMBOLS["Ui_Event"], "Competitive_WindowEvent")
            self.assertEqual(core.PATCH_SYMBOLS["Port_NetRulesSet"], "Competitive_FtRulesSet")
            self.assertIn("Port_NetBeginTick", core.CALL_WRAPPER_TARGETS)

    def test_distributed_score_object_contains_no_room_bot_or_tournament_hooks(self):
        obj = core.CoffObject(core.PAYLOAD / "competitive_score.o")
        symbols = set(obj.by_name)
        self.assertIn("Competitive_ScoreRender", symbols)
        self.assertIn("Competitive_WindowEvent", symbols)
        for name in symbols:
            self.assertFalse(name.startswith(("Competitive_Rising", "Competitive_Tournament", "Competitive_Bot")), name)
        for marker in (b"Torneos BTC", b"ESPECTADOR LOCAL", b"risingTournamentPump"):
            self.assertNotIn(marker, obj.data)
