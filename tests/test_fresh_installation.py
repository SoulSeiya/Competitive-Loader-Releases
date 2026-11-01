from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,MagicMock
import competitive_loader as core
from fresh_installation import install_from_iso


class FreshInstallationTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name);self.iso=self.root/'btc.iso';self.iso.write_bytes(b'ISO')
        self.card=self.root/'btc.ps2';self.card.write_bytes(b'card')
        self.target=self.root/'CompetitiveRuntime'
        engine=self.root/'resources'/'engine';engine.mkdir(parents=True)
        (engine/'Tenkaichi3Decomp.exe').write_bytes(b'engine')
        (engine/'Tenkaichi3Decomp.dat').write_bytes(b'dat')
        (engine/'SDL3.dll').write_bytes(b'dll')
        config=self.root/'config.json';config.write_text('{"btc_player_name":"QA","runtime":"old-runtime","online_memory_sha256":"old"}')
        self.config=config;self.old_config=config.read_bytes()
        for name,value in (('RESOURCE_ROOT',engine.parent),('CONFIG',config)):
            p=patch.object(core,name,value);p.start();self.addCleanup(p.stop)
        for name,kwargs in (
            ('_is_game_running',{'return_value':False}),('sha256_file',{'return_value':core.BTC_1381_HASH}),
            ('ensure_intro_compatible',{}),('patch_dat',{}),('validate_payload',{}),
            ('_extract_competitive_iso',{'side_effect':self.extract}),('import_ps2_card',{'side_effect':self.memory})):
            p=patch.object(core,name,**kwargs);m=p.start();self.addCleanup(p.stop);setattr(self,name,m)

    def extract(self,iso,game,report=None):
        disc=game/'disc';(disc/'BIN').mkdir(parents=True)
        (disc/'SLUS_216.78').write_bytes(b'slus');(disc/'BIN/DBZP.BIN').write_bytes(b'dbzp')
        (game/'.competitive-v8.4.1.json').write_text('{}')
        return disc/'SLUS_216.78',disc/'BIN/DBZP.BIN'

    def memory(self,card,runtime,persist_config=True):
        self.assertFalse(persist_config)
        (runtime/'saves').mkdir();(runtime/'saves/test-save').write_bytes(card.read_bytes())
        return 'new-fingerprint'

    def assert_rollback(self):
        self.assertEqual(self.config.read_bytes(),self.old_config)
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.root.glob('.btc-install-*')),[])
        self.assertEqual(list(self.root.glob('.btc-config-*')),[])
        self.assertEqual(self.iso.read_bytes(),b'ISO');self.assertEqual(self.card.read_bytes(),b'card')

    def test_first_install_publishes_only_after_validation_and_preserves_preferences(self):
        steps=[]
        result=install_from_iso(self.iso,self.target,self.card,lambda step,text:steps.append(step))
        self.assertTrue((self.target/'gamedata/disc/SLUS_216.78').is_file())
        self.assertEqual((self.target/'saves/test-save').read_bytes(),b'card')
        cfg=core.load_config();self.assertEqual(cfg['btc_player_name'],'QA')
        self.assertEqual(cfg['runtime'],str(self.target));self.assertEqual(cfg['online_memory_sha256'],'new-fingerprint')
        self.assertTrue(result['memory_ready']);self.assertEqual(steps[-1],'publish')
        self.validate_payload.return_value.build.assert_called_once()

    def test_without_memory_does_not_inherit_previous_install_fingerprint(self):
        result=install_from_iso(self.iso,self.target)
        self.assertFalse(result['memory_ready']);self.assertNotIn('online_memory_sha256',core.load_config())
        self.import_ps2_card.assert_not_called()

    def test_existing_installation_is_never_merged_or_deleted(self):
        self.target.mkdir();(self.target/'keep').write_text('old')
        with self.assertRaisesRegex(core.LoaderError,'ya existe'):install_from_iso(self.iso,self.target,self.card)
        self.assertEqual((self.target/'keep').read_text(),'old');self._extract_competitive_iso.assert_not_called()

    def test_rejected_iso_keeps_config_and_sources_untouched(self):
        self._extract_competitive_iso.side_effect=core.LoaderError('ISO incompatible')
        with self.assertRaises(core.LoaderError):install_from_iso(self.iso,self.target,self.card)
        self.assert_rollback()

    def test_invalid_memory_does_not_leave_a_partially_installed_runtime(self):
        self.import_ps2_card.side_effect=core.LoaderError('Memory inválida')
        with self.assertRaises(core.LoaderError):install_from_iso(self.iso,self.target,self.card)
        self.assert_rollback()

    def test_failed_payload_validation_rolls_back_before_publication(self):
        self.validate_payload.return_value.build.side_effect=core.LoaderError('Hook incompatible')
        with self.assertRaises(core.LoaderError):install_from_iso(self.iso,self.target,self.card)
        self.assert_rollback()

    def test_failed_config_commit_removes_only_new_installation(self):
        with patch('fresh_installation.os.replace',side_effect=OSError('config locked')):
            with self.assertRaises(OSError):install_from_iso(self.iso,self.target,self.card)
        self.assert_rollback()

    def test_wrong_engine_and_insufficient_space_fail_before_extraction(self):
        self.sha256_file.return_value='wrong'
        with self.assertRaisesRegex(core.LoaderError,'motor incluido'):install_from_iso(self.iso,self.target)
        self.sha256_file.return_value=core.BTC_1381_HASH
        with patch('fresh_installation.shutil.disk_usage',return_value=MagicMock(free=0)):
            with self.assertRaisesRegex(core.LoaderError,'GB libres'):install_from_iso(self.iso,self.target)
        self._extract_competitive_iso.assert_not_called();self.assert_rollback()

    def test_running_game_blocks_installation(self):
        self._is_game_running.return_value=True
        with self.assertRaisesRegex(core.LoaderError,'Cierra'):install_from_iso(self.iso,self.target)
        self.assert_rollback()
