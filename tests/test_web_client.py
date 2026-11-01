from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import competitive_loader as core
from competitive_web_client import ClientAPI
from player_profile import ProfileStore


class WebClientTests(unittest.TestCase):
    def test_identity_application_waits_for_game_and_keeps_local_uuid(self):
        identity={'id':'42','username':'Official'}
        original=self.api._store.profile()['id']
        self.api._pending_identity=(self.api._identity.generation,identity,None,'')
        with patch.object(self.api,'_running',return_value=True):self.api._identity_tick()
        self.assertEqual(self.api._store.profile()['name'],'QA')
        self.api._identity_tick()
        self.assertEqual(self.api._store.profile()['name'],'Official')
        self.assertEqual(self.api._store.profile()['id'],original)
        self.assertTrue(self.api.command('challonge_unlink')['ok'])
        self.assertEqual(self.api._store.profile()['name'],'QA')

    def test_cancelled_identity_result_cannot_relink_profile(self):
        g=self.api._identity.generation
        self.api._identity.events.put((g,{'id':'42','username':'Official'},None,''))
        self.api.command('challonge_cancel');self.api._identity_tick()
        self.assertIsNone(self.api._store.identity_state()['challonge'])

    def test_link_and_unlink_are_blocked_inside_duel(self):
        with patch.object(self.api,'_running',return_value=True):
            for command in ('challonge_connect','challonge_unlink'):
                self.assertFalse(self.api.command(command)['ok'])

    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.folder=Path(folder.name)
        for target,value in (("competitive_web_client.make_logger",None),("competitive_web_client.RoomBridge",None)):
            p=patch(target);result=p.start();self.addCleanup(p.stop)
            if target.endswith('RoomBridge'):self.bridge=result.return_value
        for name,value in (('HERE',self.folder),('CONFIG',self.folder/'config.json')):
            p=patch.object(core,name,value);p.start();self.addCleanup(p.stop)
        self.bridge.snapshot=None;self.bridge.directory=[];self.bridge.invite='';self.bridge.client=None
        self.api=ClientAPI(ProfileStore(self.folder/'profile.sqlite3','QA'));self.addCleanup(self.api._close)

    def test_fresh_setup_only_uses_paths_chosen_in_native_dialogs(self):
        from unittest.mock import MagicMock
        self.api._window=MagicMock()
        self.api._window.create_file_dialog.return_value=(str(self.folder),)
        self.assertTrue(self.api.command('setup_choose',{'field':'destination'})['ok'])
        self.assertEqual(self.api.state()['setup']['destination'],str(self.folder/'CompetitiveRuntime'))
        self.assertFalse(self.api.command('setup_choose',{'field':'arbitrary'})['ok'])
        self.assertFalse(self.api.command('setup_start',{'iso':'untrusted-ui-path'})['ok'])

    def test_fresh_setup_requires_no_running_game_room_or_ranked_reservation(self):
        self.duel_fixture()
        self.assertFalse(self.api.command('setup_start')['ok'])
        self.api._session=None;self.bridge.client=object()
        self.assertFalse(self.api.command('setup_start')['ok'])
        self.bridge.client=None;self.api._ranked.snapshot={'queued':True}
        self.assertFalse(self.api.command('setup_start')['ok'])

    def test_fresh_setup_reports_completion_and_failure_without_starting_game(self):
        self.api._setup.update(iso=str(self.folder/'btc.iso'),destination=str(self.folder/'new-runtime'),memory='')
        def install(iso,destination,memory,report):
            report('extract','Extrayendo la ISO')
            return {'runtime':destination,'memory_ready':False}
        with patch('fresh_installation.install_from_iso',side_effect=install) as prepare,patch.object(self.api,'_work',side_effect=lambda label,fn:fn()),patch.object(self.api,'_play') as play:
            self.assertTrue(self.api.command('setup_start')['ok'])
            self.assertEqual(self.api._setup['phase'],'complete')
            self.assertFalse(self.api._setup['memory_ready']);play.assert_not_called()
            prepare.side_effect=ValueError('ISO incompatible')
            self.assertFalse(self.api.command('setup_start')['ok'])
            self.assertEqual(self.api._setup['phase'],'error')
            self.assertIn('ISO incompatible',self.api._setup['error'])

    def test_installation_in_progress_blocks_mode_switches(self):
        self.api._setup['phase']='installing';self.api._busy=True
        for kind in ('play','practice','ranked_queue','create','setup_choose','setup_start'):
            self.assertFalse(self.api.command(kind)['ok'])

    def test_ranked_queue_waits_for_360_service_and_keeps_casual_modes_available(self):
        self.api._ranked.snapshot={'rules':{'ft':2,'seconds':180,'characters':2}}
        self.assertFalse(self.api._ranked_rules_ready())
        self.assertFalse(self.api.command('ranked_queue')['ok'])
        self.assertTrue(self.api._ranked.commands.empty())
        self.assertTrue(self.api.command('create',{'title':'Casual','capacity':2})['ok'])
        self.api._ranked.snapshot={'rules':{'ft':2,'seconds':360,'characters':2}}
        self.assertTrue(self.api._ranked_rules_ready())

    def test_public_room_routes_to_real_casual_service_command(self):
        self.assertTrue(self.api.command('create',{'title':'Sala de prueba','capacity':4})['ok'])
        self.assertEqual(self.bridge.submit.call_args.args,(43,))
        self.assertEqual(self.bridge.submit.call_args.kwargs['key'],'casual')
        self.assertFalse(self.api.command('create',{'title':'Mal','capacity':80})['ok'])

    def test_profile_is_persisted_and_social_messages_use_queue(self):
        self.assertTrue(self.api.command('profile',{'name':'QA2'})['ok'])
        self.assertEqual(self.api.state()['profile']['name'],'QA2')
        self.assertTrue(self.api.command('social',{'op':'message','target':'friend','text':'Hola'})['ok'])
        op,values=self.api._social.commands.get_nowait()
        self.assertEqual((op,values['text']),('message','Hola'))

    def test_future_commands_and_invalid_rules_are_unavailable(self):
        for kind in ('tournament_start','observe','arbitrary','update'):
            self.assertFalse(self.api.command(kind)['ok'])
        self.assertFalse(self.api.command('challenge',{'target':2,'ft':9,'seconds':180,'characters':2})['ok'])
        self.assertFalse(self.api.command('social',{'op':'arbitrary'})['ok'])

    def test_startup_checks_loader_only(self):
        import time
        info={'version':(1,0,0),'tag':'v1.0.0','download_url':''}
        with patch.object(core,'latest_loader_release_info',return_value=info),patch.object(core,'latest_release_info') as upstream,patch('competitive_web_client.release_history',return_value=[]):
            self.api._check()
            until=time.monotonic()+2
            while self.api._checking and time.monotonic()<until:time.sleep(.01)
            self.assertEqual(self.api.state()['update_state'],'current')
            upstream.assert_not_called()

    def duel_fixture(self):
        from types import SimpleNamespace
        self.api._session=SimpleNamespace(path='game',summary={'ranked_serial':0},running=True,dispose=lambda:None,finish=lambda *args:None)
        self.bridge.snapshot={'room_code':'BTC-TEST12','title':'Duelo','duel':{'id':'offer'},'combat':{'id':'battle','role':1,'self_enrolled':True,'ft':2,'current':1,'status':'running','matches':[]}}
        self.api._casual_duel_tick()
        self.bridge.submit.reset_mock()
        return self.api._session.summary

    def test_casual_completed_score_retries_until_server_confirmation(self):
        summary=self.duel_fixture()
        summary.update(ranked_serial=1,ranked_completed=True,ranked_score=[2,1],ranked_connected=False)
        self.api._casual_duel_tick()
        self.bridge.submit.assert_called_once_with(15,tournament_id='battle',target=1,score1=2,score2=1)
        self.api._casual_duel_tick();self.assertEqual(self.bridge.submit.call_count,1)

    def test_pause_exit_confirms_rival_winner_not_current_score(self):
        summary=self.duel_fixture()
        summary.update(ranked_serial=1,duel_exit_score=[0,2],ranked_connected=False)
        self.api._casual_duel_tick()
        self.bridge.submit.assert_called_once_with(15,tournament_id='battle',target=1,score1=0,score2=2)

    def test_previous_game_result_is_not_submitted_to_new_duel(self):
        summary=self.duel_fixture()
        summary.update(ranked_completed=True,ranked_score=[2,0])
        self.api._casual_duel_tick();self.bridge.submit.assert_not_called()

    def test_finished_direct_room_detaches_after_confirming_and_preserves_gg(self):
        self.duel_fixture();self.api._temporary_rooms.add('BTC-TEST12')
        self.bridge.snapshot['combat'].update(status='finished',current=0,role=0,champion_name='Rival')
        self.api._casual_duel_tick()
        self.bridge.submit.assert_called_once_with(46)
        self.assertEqual(self.api._last_duel['combat']['champion_name'],'Rival')
        self.assertNotIn('token',self.api._last_duel)

    def test_finished_public_room_is_kept_for_more_duels(self):
        self.duel_fixture();self.bridge.snapshot['combat'].update(status='finished',current=0,role=0)
        self.api._casual_duel_tick();self.bridge.submit.assert_not_called()
        self.assertIsNotNone(self.api._last_duel)

    def test_unclassified_session_end_cancels_without_awarding_points(self):
        summary=self.duel_fixture();summary.update(ranked_serial=1,ranked_connected=False)
        with patch('competitive_web_client.time.monotonic',return_value=100):self.api._casual_duel_tick()
        with patch('competitive_web_client.time.monotonic',return_value=104):self.api._casual_duel_tick()
        self.bridge.submit.assert_called_once_with(33,tournament_id='offer')

    def test_old_cancelled_duel_does_not_close_a_new_pending_invitation(self):
        self.api._casual_bindings['old']={'ended':10}
        self.api._temporary_rooms.add('BTC-NEW123')
        self.bridge.snapshot={'room_code':'BTC-NEW123','combat':None,'duel':None}
        self.api._casual_duel_tick();self.bridge.submit.assert_not_called()

    def finished_direct(self):
        self.duel_fixture();self.api._temporary_rooms.add('BTC-TEST12');self.api._duel_peers['BTC-TEST12']='friend-id'
        self.bridge.snapshot['combat'].update(status='finished',current=0,role=0,seconds=180,characters=2)
        self.api._casual_duel_tick();self.bridge.client=None;self.bridge.snapshot=None;self.bridge.invite=''
        return self.api._last_duel

    def test_direct_rematch_only_sends_challenge_not_a_game_session(self):
        self.finished_direct();self.bridge.submit.reset_mock()
        self.assertTrue(self.api.command('rematch',{'battle_id':'battle'})['ok'])
        self.api._client_lifecycle_tick()
        op,values=self.api._social.commands.get_nowait()
        self.assertEqual(op,'challenge');self.assertEqual(values,{'target':'friend-id','ft':2,'seconds':180,'characters':2})
        self.bridge.submit.assert_not_called()

    def test_replay_of_old_rematch_request_is_rejected(self):
        self.finished_direct()
        self.assertFalse(self.api.command('rematch',{'battle_id':'old'})['ok'])
        self.assertTrue(self.api._social.commands.empty())

    def test_public_rematch_offers_same_rules_to_actual_opponent(self):
        self.duel_fixture();room=self.bridge.snapshot;room['self_id']=1
        room['combat'].update(status='finished',current=0,role=0,seconds=180,characters=2,matches=[{'p1':1,'p2':2}])
        self.bridge.client=object();self.bridge.invite=room['room_code']
        self.api._request_rematch('battle')
        self.bridge.submit.assert_called_once_with(30,target=2,ft=2,seconds=180,characters=2)

    def test_old_finished_ranked_poll_does_not_close_current_casual_game(self):
        self.duel_fixture();self.api._auto_session='game'
        self.api._ranked.snapshot={'match':{'id':'old-ranked','room_code':'OLD123','finished':True}}
        with patch.object(self.api._closed,'wait',side_effect=[False,True]):self.api._tick()
        self.assertIsNone(self.api._pending_game_close)
        self.assertNotIn('old-ranked',self.api._auto_close_sets)
        self.assertIn('old-ranked',self.api._ranked_terminal)

    def tick_once(self):
        with patch.object(self.api._closed,'wait',side_effect=[False,True]):self.api._tick()

    def ranked_game_fixture(self, origin='duel'):
        from unittest.mock import MagicMock
        runtime=self.folder/'runtime';(runtime/'gamedata').mkdir(parents=True)
        (runtime/'Tenkaichi3Decomp.exe').write_bytes(b'MZ')
        match={'id':'current-ranked','room_code':'RANK12','finished':False}
        self.api._ranked.snapshot={'match':match}
        self.api._ranked.launches.put({'room_code':'BTC-RANK12','token':'test-token'})
        self.tick_once()
        self.bridge.invite='BTC-RANK12';self.bridge.client=object()
        self.bridge.submit.reset_mock()
        session=MagicMock(path=Path('ranked-game'),running=True)
        session.summary={'ranked_connected':False}
        image=MagicMock();image.pe.preferred_base=0
        with patch.object(self.api,'_runtime',return_value=runtime),patch('competitive_web_client.SessionDiagnostics',return_value=session),\
                patch.object(core,'validate_payload',return_value=image),patch.object(self.api,'_work',side_effect=lambda label,fn:fn()):
            self.api._play(origin=origin)
        return match,session

    def test_real_ranked_finish_closes_only_its_launched_game_once(self):
        match,session=self.ranked_game_fixture()
        self.assertEqual(self.api._ranked_game_sessions,{'current-ranked':'ranked-game'})
        match['finished']=True
        self.tick_once()
        self.assertEqual(self.api._pending_game_close['battle_id'],'current-ranked')
        self.assertEqual(self.api._pending_game_close['source'],'ranked')
        self.bridge.submit.assert_called_once_with(5)
        self.tick_once();self.assertEqual(self.bridge.submit.call_count,1)
        self.api._pending_game_close['due']=0
        self.api._client_lifecycle_tick()
        session.request_close.assert_called_once()
        self.bridge.log.info.assert_any_call('CLIENT_CLOSE_REQUESTED battle_id=%s source=%s session=%s','current-ranked','ranked','ranked-game')

    def test_late_ranked_finish_does_not_close_a_replacement_casual_game(self):
        from types import SimpleNamespace
        match,old_session=self.ranked_game_fixture()
        self.api._session=SimpleNamespace(path='new-casual-game',summary={},running=True,dispose=lambda:None,finish=lambda *a:None)
        self.api._auto_session='new-casual-game'
        match['finished']=True
        self.bridge.invite='BTC-CASUAL';self.bridge.submit.reset_mock()
        self.tick_once()
        self.assertIsNone(self.api._pending_game_close)
        self.assertNotIn('current-ranked',self.api._auto_close_sets)
        old_session.request_close.assert_not_called()
        self.bridge.submit.assert_not_called()

    def test_ranked_with_manually_opened_game_does_not_auto_close(self):
        match,session=self.ranked_game_fixture(origin='manual')
        self.assertEqual(self.api._ranked_game_sessions,{})
        match['finished']=True;self.tick_once()
        self.assertIsNone(self.api._pending_game_close)
        session.request_close.assert_not_called()
        self.bridge.submit.assert_called_once_with(5)

    def test_historical_ranked_is_consumed_before_a_new_casual_launch(self):
        self.api._ranked.snapshot={'match':{'id':'old-ranked','room_code':'OLD123','finished':True}}
        self.tick_once()
        self.duel_fixture();self.api._auto_session='game'
        self.bridge.submit.reset_mock();self.tick_once();self.tick_once()
        self.assertIsNone(self.api._pending_game_close)
        self.bridge.submit.assert_not_called()
        self.assertIn('old-ranked',self.api._ranked_terminal)

    def test_stale_ranked_launch_is_not_assigned_to_another_active_set(self):
        self.api._ranked.snapshot={'match':{'id':'new-ranked','room_code':'NEW123','finished':False}}
        self.api._ranked.launches.put({'room_code':'BTC-OLD123','token':'test-token'})
        self.tick_once()
        self.assertEqual(self.api._ranked_launches,{})
        self.assertIsNone(self.api._pending_launch)
        self.bridge.submit.assert_not_called()

    def test_confirmed_casual_duel_still_schedules_its_game_close(self):
        self.duel_fixture();self.api._auto_session='game'
        self.bridge.snapshot['combat'].update(status='finished',current=0)
        self.api._ranked.snapshot={'match':{'id':'old-ranked','room_code':'OLD123','finished':True}}
        self.tick_once()
        self.assertEqual(self.api._pending_game_close['battle_id'],'battle')
        self.assertEqual(self.api._pending_game_close['source'],'casual')
        self.assertNotIn('old-ranked',self.api._auto_close_sets)

    def test_manual_game_is_not_scheduled_for_auto_close(self):
        self.duel_fixture();self.api._schedule_duel_close('battle')
        self.assertIsNone(self.api._pending_game_close)

    def test_duel_game_close_waits_for_native_session_end(self):
        from unittest.mock import MagicMock
        summary=self.duel_fixture();self.api._auto_session='game'
        self.api._session.request_close=MagicMock(return_value=True)
        with patch('competitive_web_client.time.monotonic',return_value=10):self.api._schedule_duel_close('battle')
        summary['ranked_connected']=True
        with patch('competitive_web_client.time.monotonic',return_value=15):self.api._client_lifecycle_tick()
        self.api._session.request_close.assert_not_called()
        summary['ranked_connected']=False
        with patch('competitive_web_client.time.monotonic',return_value=16):self.api._client_lifecycle_tick()
        self.api._session.request_close.assert_called_once()

    def test_disabled_auto_close_keeps_the_duel_game_open(self):
        self.duel_fixture();self.api._auto_session='game'
        self.assertTrue(self.api.command('preferences',{'close_duel_game':False})['ok'])
        self.api._schedule_duel_close('battle');self.assertIsNone(self.api._pending_game_close)

    def test_pending_rematch_waits_until_auto_game_has_closed(self):
        from unittest.mock import MagicMock
        self.finished_direct();self.api._auto_session='game';self.api._session.request_close=MagicMock(return_value=True)
        self.api._schedule_duel_close('battle');self.api._request_rematch('battle')
        self.api._client_lifecycle_tick();self.assertTrue(self.api._social.commands.empty())
        self.api._session.running=False;self.api._client_lifecycle_tick()
        self.assertEqual(self.api._social.commands.get_nowait()[0],'challenge')

    def test_precise_timing_is_opt_in_and_independent_of_texture_filter(self):
        self.assertFalse(self.api.state()['preferences']['precise_timing'])
        self.assertTrue(self.api.state()['preferences']['fast_menu_art'])
        self.assertTrue(self.api.command('preferences',{'precise_timing':True,'fast_menu_art':False})['ok'])
        self.assertTrue(self.api.state()['preferences']['precise_timing'])
        self.assertFalse(self.api.state()['preferences']['fast_menu_art'])
        self.assertFalse(self.api.command('preferences',{'precise_timing':'yes'})['ok'])

    def test_preferences_reject_non_booleans_and_unknown_keys(self):
        self.assertFalse(self.api.command('preferences',{'close_duel_game':'false'})['ok'])
        self.assertFalse(self.api.command('preferences',{'arbitrary':True})['ok'])

    def test_new_duel_launch_waits_for_previous_auto_game_to_close(self):
        self.duel_fixture();room=self.bridge.snapshot
        room.update(users=[{'id':1,'ready':True}],self_id=1)
        self.api._pending_game_close={'session':'game','due':10**12,'requested':False}
        self.api._pending_launch=({'room_code':'BTC-NEXT12','token':'next'},10**12)
        self.bridge.invite='';self.bridge.client=None
        with patch.object(self.api._closed,'wait',side_effect=[False,True]),patch.object(self.api,'_play') as play:
            self.api._tick()
            play.assert_not_called()
        self.assertIsNotNone(self.api._pending_launch)
        self.assertEqual(self.api._auto_attempts,set())

    def test_live_view_uses_baseline_captured_before_native_connection(self):
        summary=self.duel_fixture();self.api._remember_live_duel(self.bridge.snapshot)
        summary.update(ranked_serial=1,ranked_score=[1,0],ranked_connected=True)
        self.api._bind_live_duel()
        self.assertEqual(self.api._duel_live()['score'],[1,0])
        self.assertEqual(self.api.state()['duel_view']['score'],[1,0])

    def test_previous_session_score_is_not_shown_in_new_duel(self):
        summary=self.duel_fixture();summary.update(ranked_serial=2,ranked_score=[2,0],ranked_connected=False)
        self.api._remember_live_duel(self.bridge.snapshot);self.api._bind_live_duel()
        self.assertIsNone(self.api._duel_live());self.assertEqual(self.api.state()['duel_view']['score'],[0,0])

    def test_unanswered_direct_challenge_releases_hidden_room(self):
        self.api._temporary_rooms.add('BTC-WAIT12');self.api._direct_offers['BTC-WAIT12']=100
        self.bridge.snapshot={'room_code':'BTC-WAIT12','combat':None,'duel':None}
        with patch('competitive_web_client.time.monotonic',return_value=200):self.api._casual_duel_tick()
        self.bridge.submit.assert_not_called()
        with patch('competitive_web_client.time.monotonic',return_value=231):self.api._casual_duel_tick()
        self.bridge.submit.assert_called_once_with(5)
        self.assertIn('caducó',self.api._status)
        with patch('competitive_web_client.time.monotonic',return_value=232):self.api._casual_duel_tick()
        self.assertEqual(self.bridge.submit.call_count,1)

    def test_accepted_challenge_is_never_released_by_offer_timeout(self):
        self.api._temporary_rooms.add('BTC-WAIT12');self.api._direct_offers['BTC-WAIT12']=0
        self.bridge.snapshot={'room_code':'BTC-WAIT12','title':'Duelo','duel':{'id':'offer'},'combat':{'id':'battle','role':1,'self_enrolled':True,'ft':2,'current':1,'status':'running','matches':[]}}
        with patch('competitive_web_client.time.monotonic',return_value=10**6):self.api._casual_duel_tick()
        self.assertNotIn(5,[c.args[0] for c in self.bridge.submit.call_args_list])

    def test_public_room_without_duel_is_not_left_by_offer_timeout(self):
        self.bridge.snapshot={'room_code':'BTC-PUBLIC','combat':None,'duel':None}
        with patch('competitive_web_client.time.monotonic',return_value=10**6):self.api._casual_duel_tick()
        self.bridge.submit.assert_not_called()

    def test_only_challenger_launch_starts_offer_timer(self):
        from unittest.mock import MagicMock
        self.api._social.launches.put({'room_code':'BTC-MINE12','token':'t','_direct_duel':True,'_duel_peer':'friend'})
        self.api._social.launches.put({'room_code':'BTC-THEIR1','token':'t','_direct_duel':True,'_duel_peer':'friend','combat':{'id':'b','status':'running'}})
        with patch.object(self.api._closed,'wait',side_effect=[False,False,True]),patch.object(self.api,'_play'):
            self.api._tick()
        self.assertIn('BTC-MINE12',self.api._direct_offers);self.assertNotIn('BTC-THEIR1',self.api._direct_offers)

    def test_practice_validates_rules_and_launches_with_practice_rules(self):
        with patch.object(self.api,'_play') as play:
            for bad in ({'ft':0,'seconds':180,'characters':2},{'ft':2,'seconds':200,'characters':2},{'ft':2,'seconds':180,'characters':6}):
                self.assertFalse(self.api.command('practice',bad)['ok'])
            play.assert_not_called()
            self.assertTrue(self.api.command('practice',{'ft':3,'seconds':240,'characters':2})['ok'])
            play.assert_called_once_with(origin='practice',practice={'ft':3,'seconds':240,'characters':2})

    def test_practice_needs_a_closed_game_and_no_room(self):
        from types import SimpleNamespace
        self.api._session=SimpleNamespace(running=True,dispose=lambda:None,finish=lambda *a:None,summary={})
        self.assertIn('Cierra el juego',self.api.command('practice',{'ft':2,'seconds':180,'characters':2})['error'])
        self.api._session=None;self.bridge.client=object()
        self.assertIn('Sal de la sala',self.api.command('practice',{'ft':2,'seconds':180,'characters':2})['error'])

    def test_practice_environment_reaches_the_game_and_normal_play_has_none(self):
        import time
        from unittest.mock import MagicMock
        runtime=self.folder/'runtime';(runtime/'gamedata').mkdir(parents=True);(runtime/'Tenkaichi3Decomp.exe').write_bytes(b'MZ')
        envs=[]
        class Session:
            def __init__(self,*a,**kwargs):self.path=Path('s');self.running=False;self.summary={};self.report_capture=MagicMock()
            def launch(self,exe,image,env=None):envs.append(dict(env));self.running=True;return 1
            def dispose(self):pass
            def finish(self,*a):pass
        image=MagicMock();image.pe.preferred_base=0
        with patch.object(self.api,'_runtime',return_value=runtime),patch('competitive_web_client.SessionDiagnostics',Session),\
                patch.object(core,'validate_payload',return_value=image):
            self.assertTrue(self.api.command('practice',{'ft':2,'seconds':360,'characters':3})['ok'])
            until=time.monotonic()+3
            while self.api._busy and time.monotonic()<until:time.sleep(.01)
            self.assertEqual({k:v for k,v in envs[0].items() if k.startswith('BTC_PRACTICE')},
                             {'BTC_PRACTICE_FT':'2','BTC_PRACTICE_SECONDS':'360','BTC_PRACTICE_CHARACTERS':'3'})
            self.assertEqual(self.api.state()['practice'],{'ft':2,'seconds':360,'characters':3})
            self.api._session.running=False
            self.assertTrue(self.api.command('play')['ok'])
            until=time.monotonic()+3
            while self.api._busy and time.monotonic()<until:time.sleep(.01)
            self.assertFalse(any(k.startswith('BTC_PRACTICE') for k in envs[1]))
            self.assertIsNone(self.api._practice)
            self.assertEqual(envs[0]['BTC_PRECISE_TIMING'],'0')
            self.assertEqual(envs[0]['BTC_FAST_MENU_ART'],'1')
