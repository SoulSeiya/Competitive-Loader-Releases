import unittest
from pathlib import Path
from unittest import mock
import competitive_loader as core

class CandidateProfileTests(unittest.TestCase):
    def select(self,digest):
        with mock.patch.object(core,'sha256_file',return_value=digest):
            core.use_official_online_profile(Path('fixture.exe'),audio_fix=True,competitive_times=True,session_score=True)
    def test_audio_abi_is_selected_per_version_in_both_directions(self):
        for digest,audio in [(core.BTC_1381_HASH,'competitive_audio_1381.o'),('9c9b496cda2e0388581a4debc742f2a606d0646c040f3de65f6e7bac7b1809b2','competitive_audio.o'),(core.BTC_1381_HASH,'competitive_audio_1381.o')]:
            self.select(digest)
            self.assertIn(audio,core.CALL_WRAPPERS)
            self.assertEqual(sum(k.startswith('competitive_audio') for k in core.CALL_WRAPPERS),1)
    def test_normal_candidate_excludes_laboratory_camera_input_and_legacy_network(self):
        self.select(core.BTC_1381_HASH)
        self.assertTrue({'Demo_SetupBattle','BtlCam_UpdateOverride','Port_PadRead','MainMenu_Run'}.isdisjoint(core.CALL_WRAPPER_TARGETS))
        self.assertNotIn('PortTbo_Run',core.CALL_WRAPPER_TARGETS)
        self.assertNotIn('competitive_chat.o',core.PATCH_OBJECTS)
        self.assertNotIn('battle_hud_e_d.o',core.PATCH_OBJECTS)
        self.assertIn('Battle_Load',core.CALL_WRAPPER_TARGETS)
        self.assertIn('TeamSel_Update',core.CALL_WRAPPER_TARGETS)
        # The team cap is applied around the game's own cursor input (same frame, rollback-safe).
        self.assertEqual(core.PATCH_SYMBOLS['TeamSel_Input'],'Competitive_TeamSelectInput')
        # Offline CPU practice raises CPU members to the maximum level (gated in the payload).
        self.assertEqual(core.PATCH_SYMBOLS['BattleSetup_SetMember'],'Competitive_PracticeSetMember')
        self.assertIn('BtlSeq_CheckBattleEnd',core.CALL_WRAPPER_TARGETS)
    def test_performance_backports_are_bound_only_to_reviewed_btc_engine(self):
        self.select(core.BTC_1381_HASH)
        self.assertEqual(core.PATCH_SYMBOLS['vblank_wait'],'Competitive_PaceWait')
        self.assertEqual(set(core.CALL_WRAPPERS['competitive_menu_art.o']),{'MenuLabels_Art','MenuLabels_ArtKey','MenuLabels_ArtSwap'})
        self.select('9c9b496cda2e0388581a4debc742f2a606d0646c040f3de65f6e7bac7b1809b2')
        self.assertNotIn('vblank_wait',core.CALL_WRAPPER_TARGETS)
        self.assertNotIn('competitive_menu_art.o',core.PATCH_OBJECTS)

    def test_unknown_hash_does_not_get_accepted_as_another_1381(self):
        with self.assertRaises(core.IncompatibleDecompError):self.select('0'*64)
