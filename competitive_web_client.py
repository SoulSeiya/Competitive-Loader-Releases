"""Approved HTML client over the existing native Loader and BTC services."""
import base64
import ctypes
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time
import webbrowser

import competitive_loader as core
from client_updates import classify_release, release_history
from player_profile import ProfileStore
from duel_presentation import present_duel
from rising_room_bridge import RoomBridge
from rising_service import DEFAULT_ROOM_SERVICE
from session_diagnostics import SessionDiagnostics, make_logger
from social_client import SocialManager

core.RELEASE_PROFILE=True
DIRECT_OFFER_TIMEOUT=130 # Service-side challenge lifetime is 120 s.


class ClientAPI:
    def __init__(self, store=None):
        (core.HERE/'logs').mkdir(parents=True,exist_ok=True)
        self._store=store or ProfileStore(initial_name=core.load_config().get('btc_player_name','Jugador'))
        from profile_link import ProfileLink
        oauth=json.loads((core.RESOURCE_ROOT/'assets'/'challonge_config.json').read_text(encoding='utf-8'))
        self._identity=ProfileLink(self._store,oauth.get('client_id',''))
        self._pending_identity=None
        self._social=SocialManager(self._store)
        self._bridge=RoomBridge(make_logger('competitive.web.room',core.HERE/'logs'/'rising-battle.log'),profile_store=self._store)
        self._session=None;self._window=None;self._busy=False;self._status='Listo para jugar.'
        self._lock=threading.Lock();self._closed=threading.Event();self._force_close=False
        self._release=None;self._releases=[];self._release_error='';self._checking=False
        self._auto_attempts=set();self._pending_launch=None;self._last_launch=0
        self._last_notice='';self._avatar_stamp=None;self._avatar=''
        self._started=False
        from ranked_client import RankedManager
        self._ranked=RankedManager(self._store,self._ranked_telemetry)
        self._ranked_terminal=set()
        self._ranked_launches={};self._ranked_game_sessions={}
        self._temporary_rooms=set();self._casual_cancelled_rooms=set();self._casual_bindings={};self._last_duel=None
        self._pending_duel_rules={};self._room_live_baselines={};self._live_duels={};self._duel_peers={};self._dismissed_duels=set();self._auto_session=None
        self._pending_game_close=None;self._auto_close_sets=set();self._pending_rematch=None
        self._direct_offers={}
        self._practice=None # rules of the offline CPU practice launched by this client
        self._setup={"iso":"","destination":str(core.HERE/"CompetitiveRuntime"),"memory":"","phase":"choose","step":"","message":"","error":""}

    def _ranked_telemetry(self):
        summary=self._session.summary if self._session else {}
        return {'session':str(self._session.path) if self._session else None,'running':self._running(),
                'connected':summary.get('ranked_connected',False),'failed':summary.get('ranked_failed',False),
                'score':summary.get('ranked_score'),'completed':summary.get('ranked_completed',False),'serial':summary.get('ranked_serial',0)}

    def _ranked_active(self):
        match=(self._ranked.snapshot or {}).get('match')
        return bool(match and not match.get('finished'))

    def _ranked_rules_ready(self):
        from ranked_client import RANKED_RULES
        return (self._ranked.snapshot or {}).get('rules')==RANKED_RULES

    def _ranked_reserved(self):
        return self._ranked_active() or bool((self._ranked.snapshot or {}).get('queued'))

    def _runtime(self):
        return Path(core.load_config().get('runtime',core.DEFAULT_RUNTIME))

    def _running(self):
        return bool(self._session and self._session.running)

    def _work(self, label, fn, allow_game=False):
        with self._lock:
            if self._busy:raise ValueError('Espera a que termine la operación actual.')
            if self._running() and not allow_game:raise ValueError('Cierra el juego antes de realizar esta operación.')
            self._busy=True;self._status=label
        def worker():
            try:fn()
            except Exception as exc:
                self._status=str(exc)
                self._bridge.log.exception('CLIENT_OPERATION_FAILED %s',label)
            finally:self._busy=False
        threading.Thread(target=worker,name='BTC client operation',daemon=True).start()

    def _play(self, origin='manual', practice=None):
        if self._running():return
        runtime=self._runtime();exe=runtime/'Tenkaichi3Decomp.exe'
        if not exe.is_file() or not (runtime/'gamedata').is_dir():raise ValueError('Selecciona una instalación generada en Ajustes.')
        # Capture ownership before the asynchronous launch: an unrelated ranked poll
        # must never close this process, including after it has been replaced.
        ranked=(self._ranked.snapshot or {}).get('match') or {}
        ranked_id=ranked.get('id') if (origin=='duel' and ranked and not ranked.get('finished') and
            self._ranked_launches.get(ranked.get('id'))==self._bridge.invite) else None
        def launch():
            if self._session:self._session.dispose()
            self._session=SessionDiagnostics(core.HERE/'logs',runtime)
            self._auto_session=str(self._session.path) if origin=='duel' else None
            if ranked_id:self._ranked_game_sessions[ranked_id]=self._auto_session
            self._pending_game_close=None;self._practice=dict(practice) if practice else None
            try:
                image=core.validate_payload(core.PAYLOAD,exe)
                image.build(0x60000000,image.pe.preferred_base)
                self._bridge.runtime=runtime
                launch_env={'BTC_ROOM_BRIDGE':self._bridge.name,'BT3_NET_NAME':self._store.profile()['name']}
                if core.load_config().get('fast_start',True):launch_env['BTC_FAST_START']='1'
                launch_env['BTC_PRECISE_TIMING']='1' if core.load_config().get('precise_timing',False) else '0'
                launch_env['BTC_FAST_MENU_ART']='1' if core.load_config().get('fast_menu_art',True) else '0'
                if practice:
                    # Offline only: the game ignores these rules in any online session.
                    launch_env.update(BTC_PRACTICE_FT=str(practice['ft']),BTC_PRACTICE_SECONDS=str(practice['seconds']),
                                      BTC_PRACTICE_CHARACTERS=str(practice['characters']))
                pid=self._session.launch(exe,image,env=launch_env)
                self._bridge.game_pid=pid;self._status='Juego iniciado. Mantén el cliente abierto.'
            except Exception:
                self._practice=None
                self._session.finish('launch_failed');core._release_online_memory_handles();raise
            if practice:self._status=f"Práctica FT{practice['ft']} contra la CPU en dificultad máxima. Elige Duelo o Team Battle contra la CPU."
        self._work('Comprobando compatibilidad e iniciando el juego…',launch)

    def _check(self):
        with self._lock:
            if self._checking:return
            self._checking=True;self._release_error=''
        def worker():
            try:
                info=core.latest_loader_release_info()
                self._release=info;self._releases=release_history(info)
            except Exception as exc:self._release_error=str(exc)
            finally:self._checking=False
        threading.Thread(target=worker,name='BTC loader versions',daemon=True).start()

    def _remember_live_duel(self, snapshot):
        summary=self._session.summary if self._session else {}
        baseline={'serial':summary.get('ranked_serial',0),'session':str(self._session.path) if self._session else None}
        if snapshot.get('room_code'):self._room_live_baselines[snapshot['room_code']]=baseline
        combat=snapshot.get('combat') or {}
        if combat.get('id') and combat.get('status')=='running':self._live_duels.setdefault(combat['id'],baseline)

    def _bind_live_duel(self):
        combat=(self._bridge.snapshot or {}).get('combat') or {}
        if not combat or combat.get('status')!='running':return
        summary=self._session.summary if self._session else {}
        baseline=self._room_live_baselines.get((self._bridge.snapshot or {}).get('room_code')) or {'serial':summary.get('ranked_serial',0),'session':str(self._session.path) if self._session else None}
        self._live_duels.setdefault(combat['id'],dict(baseline))

    def _duel_live(self):
        combat=(self._bridge.snapshot or {}).get('combat') or {}
        binding=self._live_duels.get(combat.get('id'))
        if not binding or not self._session:return None
        summary=self._session.summary
        began=summary.get('ranked_serial',0)>binding['serial'] or (str(self._session.path)!=binding['session'] and summary.get('ranked_serial',0)>0)
        if not began:return None
        return {'combat_id':combat['id'],'score':summary.get('ranked_score'),'online':summary.get('ranked_connected',False),
                'completed':summary.get('ranked_completed',False) or bool(summary.get('duel_exit_score'))}

    def _schedule_duel_close(self, battle_id, source='casual', session=None):
        if session is not None and session!=self._auto_session:
            self._bridge.log.info('CLIENT_CLOSE_IGNORED battle_id=%s source=%s reason=replaced_session',battle_id,source)
            return
        if not self._session or not self._running() or str(self._session.path)!=self._auto_session:return
        if not core.load_config().get('close_duel_game',True) or battle_id in self._auto_close_sets:return
        self._auto_close_sets.add(battle_id)
        self._pending_game_close={'session':self._auto_session,'due':time.monotonic()+2,'requested':False,
                                  'battle_id':battle_id,'source':source}
        self._bridge.log.info('CLIENT_CLOSE_SCHEDULED battle_id=%s source=%s session=%s',battle_id,source,self._auto_session)

    def _client_lifecycle_tick(self):
        close=self._pending_game_close
        if close:
            if not self._session or str(self._session.path)!=close['session'] or not self._running():
                self._pending_game_close=None
            elif not core.load_config().get('close_duel_game',True):self._pending_game_close=None
            elif not close['requested'] and time.monotonic()>=close['due'] and not self._session.summary.get('ranked_connected'):
                close['requested']=self._session.request_close()
                if close['requested']:
                    self._status='Cerrando el juego al terminar el set…'
                    self._bridge.log.info('CLIENT_CLOSE_REQUESTED battle_id=%s source=%s session=%s',close.get('battle_id'),close.get('source'),close['session'])
            elif close['requested'] and time.monotonic()-close['due']>15:
                self._pending_game_close=None;self._status='El juego sigue abierto; puedes cerrarlo manualmente.'
        pending=self._pending_rematch
        if pending and not self._bridge.client and not self._pending_game_close and not self._busy:
            self._social.submit('challenge',**pending);self._pending_rematch=None
            self._status='Revancha enviada. El rival debe aceptarla.'

    def _request_rematch(self, battle_id):
        room=self._bridge.snapshot or {}
        result=room if (room.get('combat') or {}).get('id')==battle_id else self._last_duel
        combat=(result or {}).get('combat') or {}
        if combat.get('id')!=battle_id or combat.get('status')!='finished':raise ValueError('La revancha está disponible al terminar el FT.')
        if self._ranked_reserved():raise ValueError('Termina o cancela la ranked antes de pedir una revancha casual.')
        if self._pending_rematch:raise ValueError('Ya se está preparando una revancha.')
        rules={k:combat[k] for k in ('ft','seconds','characters')}
        code=result.get('room_code')
        if code in self._temporary_rooms:
            peer=self._duel_peers.get(code)
            if not peer:raise ValueError('Vuelve a desafiar a tu amigo desde Amigos.')
            if self._bridge.client and self._bridge.invite!=code:raise ValueError('Sal de la otra sala antes de pedir la revancha.')
            self._pending_rematch=dict(target=peer,**rules)
            if self._bridge.client:self._bridge.submit(46)
        else:
            if not self._bridge.client or self._bridge.invite!=code:raise ValueError('Vuelve a la sala para desafiar a este rival.')
            match=combat.get('matches',[{}])[0];me=result.get('self_id')
            target=match.get('p2') if match.get('p1')==me else match.get('p1')
            if target is None:raise ValueError('El rival ya no está disponible.')
            self._remember_live_duel(room)
            self._bridge.submit(30,target=target,**rules)
        self._status='Preparando revancha con las mismas reglas…'

    def _casual_duel_tick(self):
        room=self._bridge.snapshot or {};combat=room.get('combat') or {}
        if not combat or (combat.get('role') not in (1,2) and not (combat.get('status')=='finished' and combat.get('self_enrolled'))):
            code=room.get('room_code')
            if code in self._casual_cancelled_rooms and not room.get('duel'):
                self._pending_launch=None;self._bridge.submit(5)
            elif (code in self._temporary_rooms and not room.get('duel') and not combat and
                    time.monotonic()-self._direct_offers.get(code,float('inf'))>=DIRECT_OFFER_TIMEOUT):
                # The social challenge expires after 120 s; do not leave the challenger in a hidden empty room.
                self._direct_offers.pop(code,None);self._pending_launch=None;self._bridge.submit(5)
                self._status='El desafío caducó sin respuesta. Puedes volver a desafiar.'
            return
        ranked=(self._ranked.snapshot or {}).get('match')
        code=room.get('room_code')
        if ranked and code=='BTC-'+ranked['room_code']:return
        summary=self._session.summary if self._session else {}
        session=str(self._session.path) if self._session else None
        key=combat['id'];now=time.monotonic()
        binding=self._casual_bindings.setdefault(key,dict(self._live_duels.get(key) or {'session':session,'serial':summary.get('ranked_serial',0)},sent=0,ended=None))
        if combat.get('status')=='finished':
            import copy
            if key not in self._dismissed_duels:
                self._last_duel=copy.deepcopy({k:room[k] for k in ('combat','duel','room_code','title','self_id') if k in room})
                self._last_duel['temporary']=code in self._temporary_rooms
                self._last_duel['can_rematch']=bool(self._duel_peers.get(code)) or code not in self._temporary_rooms
            self._schedule_duel_close(key)
            if code in self._temporary_rooms and now-binding['sent']>=1.5:
                if self._pending_launch and self._pending_launch[0]['room_code']==code:self._pending_launch=None
                self._bridge.submit(46);binding['sent']=now
            return
        began=summary.get('ranked_serial',0)>binding['serial'] or (session!=binding['session'] and summary.get('ranked_serial',0)>0)
        if not began:return
        score=summary.get('duel_exit_score') or (summary.get('ranked_score') if summary.get('ranked_completed') else None)
        ft=combat.get('ft',0)
        valid=isinstance(score,list) and len(score)==2 and all(type(v)is int and 0<=v<=ft for v in score) and ((score[0]==ft)!=(score[1]==ft))
        if valid:
            if now-binding['sent']>=1.5:
                self._bridge.submit(15,tournament_id=key,target=1,score1=score[0],score2=score[1]);binding['sent']=now
                self._status='Confirmando el resultado del duelo con el rival…'
            return
        ended=not summary.get('ranked_connected') or not self._running()
        if ended:
            if binding['ended'] is None:binding['ended']=now
            if now-binding['ended']>=3 and now-binding['sent']>=1.5 and room.get('duel'):
                # An unclassified network/session failure cannot award a winner.
                self._casual_cancelled_rooms.add(code)
                self._bridge.submit(33,tournament_id=room['duel']['id']);binding['sent']=now
                self._status='Duelo interrumpido sin resultado confirmado.'
        if room.get('duel') is None and code in self._temporary_rooms:self._bridge.submit(5)

    def _identity_tick(self):
        try:
            while True:self._pending_identity=self._identity.events.get_nowait()
        except queue.Empty:pass
        pending=self._pending_identity
        if not pending:return
        if pending[0]!=self._identity.generation:self._pending_identity=None;return
        if self._busy or self._running() or self._bridge.client or self._ranked_reserved():return
        self._pending_identity=None
        self._store.link_identity(pending[1],pending[2])
        config=core.load_config();config['btc_player_name']=self._store.profile()['name'];core.save_config(config)
        self._identity.status='Cuenta de Challonge vinculada.'+pending[3]
        self._status=self._identity.status

    def _tick(self):
        while not self._closed.wait(.5):
            try:
                self._identity_tick()
                self._social.activity='playing' if self._running() else 'room' if self._bridge.snapshot else 'online'
                try:
                    while True:self._status=self._social.notices.get_nowait()
                except queue.Empty:pass
                try:
                    launch=self._social.launches.get_nowait()
                    self._remember_live_duel(launch)
                    if launch.get('_direct_duel'):
                        self._temporary_rooms.add(launch['room_code'])
                        if launch.get('_duel_peer'):self._duel_peers[launch['room_code']]=launch['_duel_peer']
                        if launch.get('_duel_rules'):self._pending_duel_rules[launch['room_code']]=launch['_duel_rules']
                        # Only the challenger joins before the rival answers; the accepter's launch already has the combat.
                        if not launch.get('combat'):self._direct_offers[launch['room_code']]=time.monotonic()
                    self._pending_launch=(launch,time.monotonic()+120)
                except queue.Empty:pass
                try:
                    launch=self._ranked.launches.get_nowait()
                    match=(self._ranked.snapshot or {}).get('match') or {}
                    if match and not match.get('finished') and launch['room_code']=='BTC-'+match['room_code']:
                        self._ranked_launches[match['id']]=launch['room_code']
                        self._remember_live_duel(launch);self._pending_launch=(launch,time.monotonic()+120)
                except queue.Empty:pass
                match=(self._ranked.snapshot or {}).get('match')
                if (match and match.get('finished') and match['id'] not in self._ranked_terminal and
                        not (match['id'] in self._ranked_launches and self._busy and match['id'] not in self._ranked_game_sessions)):
                    # Poll also returns historical sets. Consume them once, but only
                    # the exact process opened for this ranked set may be closed.
                    self._ranked_terminal.add(match['id'])
                    session=self._ranked_game_sessions.pop(match['id'],None)
                    if session:self._schedule_duel_close(match['id'],source='ranked',session=session)
                    else:self._bridge.log.info('RANKED_TERMINAL_NO_AUTO_GAME battle_id=%s',match['id'])
                    code=self._ranked_launches.pop(match['id'],None)
                    if code:
                        if self._pending_launch and self._pending_launch[0]['room_code']==code:self._pending_launch=None
                        if self._bridge.invite==code and self._bridge.client:self._bridge.submit(5)
                if self._pending_launch:
                    value,until=self._pending_launch
                    if time.monotonic()>until or self._bridge.invite==value['room_code']:self._pending_launch=None
                    elif not self._bridge.client and not self._pending_game_close and time.monotonic()-self._last_launch>5:
                        self._bridge.submit(45,address=DEFAULT_ROOM_SERVICE,key=value['room_code'],text=value['token']);self._last_launch=time.monotonic()
                self._bind_live_duel()
                self._casual_duel_tick()
                self._client_lifecycle_tick()
                snapshot=self._bridge.snapshot or {};combat=snapshot.get('combat') or {}
                key=(combat.get('id'),combat.get('current'))
                me=next((u for u in snapshot.get('users',[]) if u['id']==snapshot.get('self_id')), {})
                if combat.get('status')=='running' and combat.get('role') in (1,2) and combat.get('current') and key not in self._auto_attempts and me.get('ready') and not self._busy and not self._pending_game_close:
                    self._auto_attempts.add(key);self._play(origin='duel')
                if self._bridge.notice!=self._last_notice:
                    self._last_notice=self._bridge.notice;self._status=self._last_notice
            except Exception as exc:self._status=str(exc)

    def _start(self):
        if self._started:return
        self._started=True
        self._social.start();self._ranked.start();self._check()
        threading.Thread(target=self._tick,name='BTC client state',daemon=True).start()

    def state(self):
        avatar=self._store.avatar_path()
        stamp=avatar.stat().st_mtime_ns if avatar.is_file() else None
        if stamp!=self._avatar_stamp:
            self._avatar='data:image/png;base64,'+base64.b64encode(avatar.read_bytes()).decode() if stamp else ''
            self._avatar_stamp=stamp
        peer=self._duel_peers.get(self._bridge.invite)
        peer_name=next((f.get('name') for f in (self._social.snapshot or {}).get('friends',[]) if f.get('id')==peer),None)
        duel=present_duel(self._bridge.snapshot,self._last_duel,self._duel_live(),self._store.profile(),peer_name,self._running(),self._busy,self._pending_duel_rules.get(self._bridge.invite))
        return {'duel_view':duel,'profile':self._store.profile(),'identity':dict(self._store.identity_state(),**self._identity.snapshot()),'avatar':self._avatar,'social':self._social.snapshot,
                'social_status':self._social.status,'conversation':self._social.conversation,
                'room':self._bridge.snapshot,'rooms':self._bridge.directory,'room_code':self._bridge.invite,
                'status':self._status,'busy':self._busy,'running':self._running(),
                'installed':(self._runtime()/'Tenkaichi3Decomp.exe').is_file() and (self._runtime()/'gamedata'/'.competitive-v8.4.1.json').is_file(),'runtime':str(self._runtime()),
                'setup':dict(self._setup),
                'version':core.APP_VERSION_TEXT,'highlights':core.VERSION_HIGHLIGHTS,
                'release':self._release,'releases':self._releases,'checking':self._checking,
                'release_error':self._release_error,
                'ranked':self._ranked.snapshot,'ranked_status':self._ranked.status,'ranked_rules_ready':self._ranked_rules_ready(),'last_duel':self._last_duel,
                'preferences':{'fast_start':bool(core.load_config().get('fast_start',True)), 'close_duel_game':bool(core.load_config().get('close_duel_game',True)), 'precise_timing':bool(core.load_config().get('precise_timing',False)), 'fast_menu_art':bool(core.load_config().get('fast_menu_art',True))},
                'rematch_pending':bool(self._pending_rematch),
                'practice':self._practice if self._running() else None,
                'update_state':classify_release(self._release) if self._release and not self._release_error else 'error' if self._release_error else 'checking'}

    def command(self, kind, values=None):
        """Explicit allowlist: no arbitrary Python, paths or tournament opcodes."""
        values=values or {}
        try:
            if not isinstance(values,dict):raise ValueError('Solicitud no válida.')
            if self._ranked_reserved() and kind in ('create','join','challenge','installation','memory','iso','profile','practice','setup_choose','setup_start','setup_clear_memory'):
                raise ValueError('Cancela la búsqueda o termina tu set ranked antes de cambiar de modo.')
            if self._ranked_active() and kind=='leave':raise ValueError('Usa Abandonar ranked para confirmar la derrota.')
            if self._setup['phase']=='installing' and kind not in ('logs','check_updates'):
                raise ValueError('Espera a que termine la instalación antes de cambiar de modo.')
            if not self._store.identity_state()['ready'] and kind in ('play','practice','create','join','challenge','ranked_queue'):
                raise ValueError('Primero crea tu perfil BTC desde Mi perfil.')
            name=self._store.profile()['name']
            if kind=='play':self._play()
            elif kind=='practice':
                ft=int(values['ft']);seconds=int(values['seconds']);characters=int(values['characters'])
                if not 1<=ft<=5 or seconds not in (180,240,360,480) or not 1<=characters<=5:raise ValueError('Reglas de práctica no válidas.')
                if self._running():raise ValueError('Cierra el juego para iniciar la práctica: sus reglas se aplican al abrirlo.')
                if self._bridge.client:raise ValueError('Sal de la sala antes de practicar contra la CPU.')
                self._play(origin='practice',practice={'ft':ft,'seconds':seconds,'characters':characters})
            elif kind=='rooms':
                if '--smoke-web-client' not in sys.argv:self._bridge.submit(42,address=DEFAULT_ROOM_SERVICE,key='casual')
            elif kind=='create':
                capacity=int(values.get('capacity',8));title=str(values.get('title','')).strip();password=str(values.get('password',''))
                if not title or len(title.encode())>96 or not 2<=capacity<=32 or len(password.encode())>128:raise ValueError('Revisa el nombre, las plazas (2–32) y la contraseña.')
                self._bridge.submit(43,address=DEFAULT_ROOM_SERVICE,name=name,title=title,capacity=capacity,key='casual',text=password)
            elif kind=='join':self._bridge.submit(44,address=DEFAULT_ROOM_SERVICE,name=name,key=str(values['code']),text=str(values.get('password','')))
            elif kind in ('leave','ready','chat','kick'):
                if not self._bridge.client:raise ValueError('Entra en una sala primero.')
                if kind=='chat':
                    text=str(values.get('text','')).strip()
                    if not text or len(text.encode())>384:raise ValueError('El mensaje admite hasta 384 bytes UTF-8.')
                    self._bridge.submit(3,text=text)
                elif kind=='kick':self._bridge.submit(4,target=int(values['target']))
                else:
                    if kind=='leave':self._pending_launch=None
                    self._bridge.submit({'leave':5,'ready':6}[kind])
            elif kind=='challenge':
                ft=int(values['ft']);seconds=int(values['seconds']);characters=int(values['characters'])
                if not 1<=ft<=5 or seconds not in (180,240,360,480) or not 1<=characters<=5:raise ValueError('Reglas de combate no válidas.')
                if values.get('friend'):
                    if self._bridge.client:raise ValueError('Sal de tu sala antes de iniciar un duelo directo.')
                    self._social.submit('challenge',target=str(values['target']),ft=ft,seconds=seconds,characters=characters)
                else:
                    self._remember_live_duel(self._bridge.snapshot or {})
                    self._bridge.submit(30,target=int(values['target']),ft=ft,seconds=seconds,characters=characters)
            elif kind in ('accept_duel','decline_duel','cancel_duel'):
                duel=(self._bridge.snapshot or {}).get('duel')
                if kind=='accept_duel':self._remember_live_duel(self._bridge.snapshot or {})
                if not duel:raise ValueError('El desafío ya no está disponible.')
                self._bridge.submit({'accept_duel':31,'decline_duel':32,'cancel_duel':33}[kind],tournament_id=duel['id'])
            elif kind=='social':
                op=values.get('op');target=str(values.get('target',''))
                if self._ranked_reserved() and op in ('accept','invite'):raise ValueError('Termina la ranked o cancela la búsqueda antes de aceptar otra sala.')
                if op not in ('add','accept_friend','reject_friend','remove_friend','messages','message','invite','accept','decline'):raise ValueError('Acción social no disponible.')
                args={}
                if op=='add':args={'code':str(values.get('code','')).strip().upper()}
                elif op in ('accept','decline'):
                    if op=='accept' and self._bridge.client:raise ValueError('Sal de la sala actual antes de aceptar.')
                    args={'event':str(values['event'])}
                elif op=='invite':
                    if not self._bridge.client:raise ValueError('Primero entra en una sala.')
                    args={'target':target,'room_code':self._bridge.invite,'room_token':self._bridge.client.token}
                else:
                    args={'target':target}
                    if op=='messages':self._social.chat_target=target
                    if op=='message':args['text']=str(values.get('text','')).strip()
                self._social.submit(op,**args)
            elif kind in ('challonge_connect','challonge_cancel','challonge_unlink','challonge_open'):
                if kind=='challonge_open':
                    device=self._identity.snapshot()['device']
                    if not device:raise ValueError('Primero solicita un código de vinculación.')
                    webbrowser.open(device['url'])
                else:
                    if self._busy or self._running() or self._bridge.client or self._ranked_reserved():raise ValueError('Termina el duelo, cierra el juego y sal de la sala para cambiar la vinculación.')
                    if kind=='challonge_connect':self._identity.start()
                    else:
                        self._identity.cancel(forget=kind=='challonge_unlink');self._pending_identity=None
                        if kind=='challonge_unlink':
                            self._store.unlink_identity()
                            config=core.load_config();config['btc_player_name']=self._store.profile()['name'];core.save_config(config)
                            self._identity.status='Perfil local restaurado.'
            elif kind=='profile':
                if self._busy or self._running() or self._bridge.client:raise ValueError('Cierra el juego y sal de la sala antes de cambiar el nombre.')
                self._store.complete_profile(str(values['name']));config=core.load_config();config['btc_player_name']=self._store.profile()['name'];core.save_config(config)
            elif kind in ('setup_choose','setup_clear_memory','setup_start'):
                if self._busy or self._running():raise ValueError('Cierra el juego y espera a que terminen las operaciones antes de instalar.')
                if self._bridge.client:raise ValueError('Sal de la sala antes de preparar una instalación.')
                if kind=='setup_clear_memory':
                    self._setup.update(memory='',phase='choose',error='')
                elif kind=='setup_choose':
                    import webview
                    field=values.get('field')
                    if field not in ('iso','destination','memory'):raise ValueError('Selección de instalación no válida.')
                    types={'iso':('ISO (*.iso)',),'memory':('Memory PS2 (*.ps2)',)}
                    chosen=self._window.create_file_dialog(webview.FileDialog.FOLDER if field=='destination' else webview.FileDialog.OPEN,file_types=types.get(field,()))
                    if chosen:
                        value=Path(chosen[0]).resolve()
                        self._setup.update({field:str(value/'CompetitiveRuntime') if field=='destination' else str(value)},phase='choose',error='')
                else:
                    if not self._setup['iso']:raise ValueError('Selecciona primero tu ISO competitiva.')
                    selection=dict(self._setup)
                    def install():
                        from fresh_installation import install_from_iso
                        self._setup.update(phase='installing',step='engine',message='Preparando la instalación...',error='')
                        def report(step,message):
                            self._setup.update(step=step,message=message);self._status=message
                        try:
                            result=install_from_iso(selection['iso'],selection['destination'],selection['memory'] or None,report)
                            self._bridge.runtime=Path(result['runtime'])
                            self._setup.update(phase='complete',step='complete',message='Instalación lista. Ya puedes iniciar el juego.',memory_ready=result['memory_ready'])
                            self._status='BTC instalado. Ya puedes jugar.'
                        except Exception as exc:
                            self._setup.update(phase='error',error=str(exc),message='No se completó la instalación. Revisa el error y vuelve a intentarlo.')
                            raise
                    self._work('Instalando BTC desde tu ISO…',install)
            elif kind in ('installation','avatar','memory','iso'):
                if kind=='avatar' and self._store.identity_state()['challonge']:raise ValueError('Desvincula Challonge antes de cambiar tu imagen local.')
                if self._busy or self._running():raise ValueError('Cierra el juego antes de cambiar estos datos.')
                import webview
                types={'avatar':('Imágenes (*.png;*.jpg;*.jpeg;*.webp)',),'memory':('Memory PS2 (*.ps2)',),'iso':('ISO (*.iso)',)}
                chosen=self._window.create_file_dialog(webview.FileDialog.FOLDER if kind=='installation' else webview.FileDialog.OPEN,file_types=types.get(kind,()))
                if chosen:
                    path=Path(chosen[0])
                    def apply():
                        if kind=='installation':
                            from candidate_installation import prepare_existing
                            runtime=prepare_existing(path);cfg=core.load_config();cfg['runtime']=str(runtime);core.save_config(cfg);self._bridge.runtime=runtime
                        elif kind=='avatar':self._store.set_avatar(path)
                        elif kind=='memory':core.import_ps2_card(path,self._runtime())
                        else:core.replace_competitive_iso(path,self._runtime())
                        self._status='Cambios guardados.'
                    self._work('Preparando cambios…',apply)
            elif kind=='rematch':self._request_rematch(str(values.get('battle_id','')))
            elif kind=='duel_done':
                if self._last_duel:self._dismissed_duels.add(self._last_duel['combat']['id'])
                self._last_duel=None;self._pending_rematch=None
                if self._bridge.invite in self._temporary_rooms and (self._bridge.snapshot or {}).get('combat',{}).get('status')=='finished':self._bridge.submit(46)
            elif kind=='preferences':
                if any(k not in ('fast_start','close_duel_game','precise_timing','fast_menu_art') or type(v)is not bool for k,v in values.items()):raise ValueError('Preferencias no válidas.')
                config=core.load_config();config.update(values);core.save_config(config)
                self._status='Preferencias guardadas. Los cambios se aplican al próximo arranque del juego.'
            elif kind=='history':return {'ok':True,'rows':self._store.history()}
            elif kind=='ranked_queue':
                if not self._ranked_rules_ready():raise ValueError('El formato FT2 / 360 s / 2 personajes aún no está activo en el servicio. Puedes seguir usando duelos casuales.')
                if self._bridge.client:raise ValueError('Sal de tu sala casual antes de buscar ranked.')
                if not self._social.snapshot:raise ValueError('Espera a que el perfil BTC se conecte.')
                if self._ranked_telemetry().get('connected'):raise ValueError('Termina tu combate online antes de buscar ranked.')
                from ranked_client import compatibility_key
                self._work('Comprobando la instalación para ranked…',lambda:self._ranked.submit('queue',compat=compatibility_key(self._runtime())),allow_game=True)
            elif kind=='ranked_cancel':self._ranked.submit('cancel_queue')
            elif kind=='ranked_refresh':self._ranked.submit('poll')
            elif kind=='ranked_forfeit':
                match=(self._ranked.snapshot or {}).get('match')
                if not match or match.get('finished'):raise ValueError('No hay un set ranked activo.')
                self._ranked.submit('forfeit',match=match['id'])
            elif kind=='close_chat':self._social.chat_target=None
            elif kind=='check_updates':self._check()
            elif kind=='update':
                if self._checking or self._release_error or not self._release or classify_release(self._release)!='available':raise ValueError('No hay una actualización disponible y verificada.')
                if core.online_memory_guard_active() or core._is_game_running():raise ValueError('Cierra el juego antes de actualizar el Loader.')
                release=dict(self._release)
                def update():
                    staged=core.stage_loader_update(release);core.schedule_loader_update(staged)
                    self._force_close=True;self._window.destroy()
                self._work('Descargando y verificando el Loader…',update)
            elif kind=='release_page':webbrowser.open('https://github.com/SoulSeiya/Competitive-Loader-Releases/releases')
            elif kind=='logs':
                path=core.HERE/'logs';path.mkdir(exist_ok=True);os.startfile(path)
            elif kind=='exit':
                if self._ranked_active():
                    from ranked_client import RankedClient
                    match=self._ranked.snapshot['match']
                    self._ranked._receive(RankedClient(self._store).send('forfeit',match=match['id']))
                self._force_close=True;self._window.destroy()
            else:raise ValueError('Acción no disponible.')
            return {'ok':True}
        except Exception as exc:return {'ok':False,'error':str(exc)}

    def _closing(self):
        if self._busy and not self._force_close:
            self._window.evaluate_js("toast('Espera a que termine la operación antes de cerrar.')")
            return False
        if (self._running() or self._ranked_active()) and not self._force_close:
            self._window.evaluate_js('confirmExit()');return False
        return True

    def _close(self):
        self._closed.set()
        self._identity.cancel()
        self._ranked.close();self._social.close();self._bridge.close()
        if self._session:
            if self._running():self._session.finish('loader_closed_while_game_running')
            else:self._session.dispose()


def main():
    if '--apply-loader-update' in sys.argv:
        i=sys.argv.index('--apply-loader-update');core.apply_loader_update(int(sys.argv[i+1]),Path(sys.argv[i+2]),Path(sys.argv[i+3]));return
    if '--finish-loader-update' in sys.argv:
        i=sys.argv.index('--finish-loader-update');core.finish_loader_update(int(sys.argv[i+1]),Path(sys.argv[i+2]))
    try:ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:pass
    import webview
    api=ClientAPI()
    smoke='--smoke-web-client' in sys.argv
    window=webview.create_window('Rising Battle · Competitive Client',str(core.RESOURCE_ROOT/'web_client'/'index.html'),js_api=api,width=1380,height=820,min_size=(820,600),background_color='#080d16',hidden=smoke)
    api._window=window;window.events.closing+=api._closing
    def start():
        from window_chrome import apply_dark_titlebar
        chrome=apply_dark_titlebar(window)
        if smoke:
            try:
                time.sleep(.6)
                window.evaluate_js('window.btcClosing=true;')
                result=window.evaluate_js("({title:document.title,logo:document.querySelector('.hero-copy .logo').naturalWidth>0,brand:!!document.querySelector('.brand-text'),simulations:document.body.innerText.includes('SIMULAR'),ready:window.btcReady===true,backendLoaded:state!==null,renderErrors:window.btcRenderErrors,styles:document.querySelector('style').textContent,fonts:getComputedStyle(document.body).fontFamily})")
                result['window_chrome']=chrome
                result['public_branding']=window.evaluate_js("({label:document.querySelector('.preview b').textContent,version:document.querySelector('.version').textContent,privateVisible:document.body.innerText.includes('CLIENTE PRIVADO'),internalVersionVisible:document.body.innerText.includes('ranked-beta'),footerFits:document.querySelector('.bottom-bar').scrollWidth<=document.querySelector('.bottom-bar').clientWidth})")
                branding=result['public_branding']
                if branding['label']!='BETA PÚBLICA' or branding['version']!='RISING BATTLE · 2.0.0' or branding['privateVisible'] or branding['internalVersionVisible']:raise RuntimeError('El paquete público conserva etiquetas internas.')
                window.evaluate_js("showView('duel')")
                result['duel_view']=window.evaluate_js("({players:document.querySelectorAll('.duel-player').length,status:document.querySelector('#duel-status').textContent,errors:window.btcRenderErrors.slice()})")
                if result['duel_view']['players']!=2 or result['duel_view']['errors']:raise RuntimeError('Falló la vista de duelo integrada.')
                window.resize(820,600)
                time.sleep(.2)
                window.evaluate_js("setupDialog()")
                result['setup_view']=window.evaluate_js("({pickers:document.querySelectorAll('.setup-pick').length,startDisabled:document.querySelector('#setup-start').disabled,errors:window.btcRenderErrors.slice(),fits:(()=>{const r=document.querySelector('#dialog').getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight&&r.left>=0&&r.right<=innerWidth})(),overflowX:document.querySelector('#dialog').scrollWidth>document.querySelector('#dialog').clientWidth,overflowY:document.querySelector('#dialog').scrollHeight>document.querySelector('#dialog').clientHeight,buttonsInside:(()=>{const r=document.querySelector('#dialog').getBoundingClientRect();return Array.from(document.querySelectorAll('.setup-pick')).every(b=>{const q=b.getBoundingClientRect();return q.right<=r.right&&q.left>=r.left})})()})")
                (core.HERE/'setup-layout-check.json').write_text(json.dumps(result['setup_view']),encoding='utf-8')
                if result['setup_view']['pickers']!=3 or not result['setup_view']['startDisabled'] or not result['setup_view']['fits'] or result['setup_view']['errors'] or result['setup_view']['overflowX'] or result['setup_view']['overflowY'] or not result['setup_view']['buttonsInside']:raise RuntimeError('Falló el asistente de primera instalación: contenido desbordado o controles fuera del cuadro.')
                # Regression: long file paths must clip inside their column, not
                # push the native-picker buttons outside the dialog.
                window.evaluate_js("window.btcSetupBackup={...state.setup};state.setup.iso='C:/'+('ISO-'.repeat(120))+'.iso';state.setup.destination='C:/'+('Carpeta-'.repeat(100));state.setup.memory='C:/'+('Memory-'.repeat(100))+'.ps2';renderSetup()")
                result['setup_long_paths']=window.evaluate_js("({overflowX:document.querySelector('#dialog').scrollWidth>document.querySelector('#dialog').clientWidth,overflowY:document.querySelector('#dialog').scrollHeight>document.querySelector('#dialog').clientHeight,buttonsInside:(()=>{const r=document.querySelector('#dialog').getBoundingClientRect();return Array.from(document.querySelectorAll('.setup-pick')).every(b=>{const q=b.getBoundingClientRect();return q.right<=r.right&&q.left>=r.left})})(),pathsClipped:Array.from(document.querySelectorAll('.setup-path')).every(el=>el.scrollWidth>el.clientWidth)})")
                if result['setup_long_paths']['overflowX'] or result['setup_long_paths']['overflowY'] or not result['setup_long_paths']['buttonsInside'] or not result['setup_long_paths']['pathsClipped']:raise RuntimeError('Las rutas largas desbordan el asistente.')
                window.evaluate_js("state.setup=window.btcSetupBackup;closeDialog();showView('home')")
                window.evaluate_js("performanceDialog()")
                result['performance_view']=window.evaluate_js("({fastArt:document.querySelector('#art-performance').checked,preciseTiming:document.querySelector('#timer-performance').checked,overflowX:document.querySelector('#dialog').scrollWidth>document.querySelector('#dialog').clientWidth,overflowY:document.querySelector('#dialog').scrollHeight>document.querySelector('#dialog').clientHeight,errors:window.btcRenderErrors.slice()})")
                if not result['performance_view']['fastArt'] or result['performance_view']['preciseTiming'] or result['performance_view']['overflowX'] or result['performance_view']['overflowY'] or result['performance_view']['errors']:raise RuntimeError('Falló la presentación de opciones de fluidez.')
                window.evaluate_js("closeDialog();showView('home')")
                # Social notification fixtures. Commands are intercepted, never sent.
                window.evaluate_js("window.btcSocialBackup=state.social;window.btcApiBackup=api;window.btcSocialCommands=[];api=async(kind,values)=>{window.btcSocialCommands.push({kind,values});return {ok:true};};state.social={friends:[{id:'fixture-friend',name:'Amigo de prueba',online:true,activity:'online'}],incoming:[{id:'fixture-new',name:'Nuevo amigo'}],events:[{id:'fixture-message',kind:'message',sender:'fixture-friend',name:'Amigo de prueba'},{id:'fixture-invite',kind:'invite',name:'Invitador',title:'Sala de prueba'}]};openFriends();renderFriends()")
                result['social_signals_fixture']=window.evaluate_js("({badge:document.querySelector('.friend-unread').textContent,passiveSummary:document.querySelector('#inbox-summary').tagName==='SPAN',visibleRequest:!socialNotices.hidden,requestButtons:socialNotices.querySelectorAll('.social-request-actions button').length,noticeVisible:!messageNotice.hidden,overflow:document.querySelector('#social').scrollHeight>document.querySelector('#social').clientHeight,errors:window.btcRenderErrors.slice()})")
                window.evaluate_js("document.querySelector('#friends-list .friend').click()")
                result['social_signals_fixture']['clickOpensChat']=window.evaluate_js("!dm.hidden&&dmPeer==='fixture-friend'&&window.btcSocialCommands.some(c=>c.kind==='social'&&c.values.op==='messages'&&c.values.target==='fixture-friend')")
                window.evaluate_js("closeDm();state.social={friends:state.social.friends,incoming:[],events:[]};renderFriends()")
                result['social_signals_fixture']['readClearsBadge']=window.evaluate_js("!document.querySelector('.friend-unread')")
                window.evaluate_js("state.social=window.btcSocialBackup;api=window.btcApiBackup;renderFriends();$('#social').hidden=true")
                social_result=result['social_signals_fixture']
                if not social_result['passiveSummary'] or not social_result['visibleRequest'] or social_result['requestButtons']!=2 or not social_result['clickOpensChat'] or not social_result['readClearsBadge'] or social_result['overflow'] or social_result['errors']:raise RuntimeError('Falló la interfaz de avisos sociales: '+json.dumps(social_result))
                # Local onboarding and OAuth-device layouts only. No authorization request.
                window.evaluate_js("window.btcIdentityBackup=state.identity;state.identity={ready:false,challonge:null,status:'Challonge es opcional.',busy:false};profile()")
                result['profile_fixture']=window.evaluate_js("({emptyName:document.querySelector('#profile-form input').value==='',localAvatar:!!document.querySelector('#profile-avatar'),connect:!!document.querySelector('#identity-connect'),fits:(()=>{const r=document.querySelector('#dialog').getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight})(),overflow:document.querySelector('#dialog').scrollHeight>document.querySelector('#dialog').clientHeight})")
                window.evaluate_js("state.identity={...state.identity,busy:true,device:{user_code:'ABCDEF'},status:'Autoriza Rising Battle en el navegador.'};renderProfileLink()")
                result['profile_device_fixture']=window.evaluate_js("({code:document.querySelector('.identity-code strong').textContent,disabled:document.querySelector('#identity-connect').disabled,cancel:!!document.querySelector('#identity-cancel'),overflow:document.querySelector('#dialog').scrollHeight>document.querySelector('#dialog').clientHeight,errors:window.btcRenderErrors.slice()})")
                window.evaluate_js("state.identity={ready:true,challonge:{id:'fixture',username:'Cuenta de prueba'},busy:false,status:'Cuenta vinculada.'};renderProfileLink()")
                result['profile_linked_fixture']=window.evaluate_js("({nameLocked:document.querySelector('#profile-form input').disabled,unlink:!!document.querySelector('#identity-unlink'),localAvatar:!!document.querySelector('#profile-avatar'),overflow:document.querySelector('#dialog').scrollHeight>document.querySelector('#dialog').clientHeight})")
                window.evaluate_js("state.identity=window.btcIdentityBackup;closeDialog()")
                if not result['profile_fixture']['emptyName'] or not result['profile_fixture']['fits'] or result['profile_fixture']['overflow'] or result['profile_device_fixture']['overflow'] or result['profile_device_fixture']['errors'] or not result['profile_linked_fixture']['nameLocked'] or result['profile_linked_fixture']['overflow']:raise RuntimeError('Falló la interfaz de perfil local/Challonge: '+json.dumps({k:v for k,v in result.items() if k.startswith('profile_')}))
                # UI-only incoming offer fixture; no reply is sent to a service.
                window.evaluate_js("window.btcOfferBackup=state.social;state.social={events:[{kind:'challenge',id:'smoke-offer',name:'Rival de prueba',ft:2,seconds:360,characters:2}]};duelAlerts.update(state)")
                result['duel_alert_fixture']=window.evaluate_js("({open:duelAlert.open,name:document.querySelector('#duel-alert-title').textContent,rules:document.querySelector('.duel-offer-rules').textContent,buttons:duelAlert.querySelectorAll('button').length,focusedReject:document.activeElement.id==='duel-alert-decline',fits:(()=>{const r=duelAlert.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight})(),errors:window.btcRenderErrors.slice()})")
                window.evaluate_js("state.social=window.btcOfferBackup;duelAlerts.update(state)")
                result['duel_alert_fixture']['removed']=window.evaluate_js("!duelAlert.open")
                offer=result['duel_alert_fixture']
                if not offer['open'] or not offer['fits'] or not offer['removed'] or not offer['focusedReject'] or offer['buttons']!=2 or offer['errors']:raise RuntimeError('Falló el aviso automático de duelo.')
                import hashlib
                result['css_sha256']=hashlib.sha256(result.pop('styles').encode()).hexdigest()
                manifest=json.loads((core.RESOURCE_ROOT/'web_client'/'design-integrity.json').read_text(encoding='utf-8'))
                result['approved_css_identical']=result['css_sha256']==manifest['original_css_sha256']
                (core.HERE/'web-client-smoke.json').write_text(json.dumps(result),encoding='utf-8')
                if not all(result[k] for k in ('ready','backendLoaded','logo','brand','approved_css_identical')) or result['renderErrors']:
                    raise RuntimeError('Falló la verificación de la interfaz HTML integrada.')
            finally:api._force_close=True;window.destroy()
        else:api._start()
    window.events.loaded+=start
    try:webview.start(gui='edgechromium',private_mode=True)
    finally:api._close()


if __name__=='__main__':
    try:
        if '--check-services' in sys.argv:
            check=ClientAPI()
            try:
                check._social.start();check._ranked.start()
                check._bridge.submit(42,address=DEFAULT_ROOM_SERVICE,key='casual')
                until=time.monotonic()+30
                while time.monotonic()<until:
                    if check._social.snapshot and check._ranked.snapshot and check._bridge.directory_version:break
                    time.sleep(.25)
                result={'social':bool(check._social.snapshot),'ranked':bool(check._ranked.snapshot),
                        'rooms':bool(check._bridge.directory_version),'social_status':check._social.status,
                        'ranked_status':check._ranked.status,'rooms_status':check._bridge.notice}
                (core.HERE/'services-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            finally:check._close()
        else:main()
    except Exception as exc:
        import traceback
        (core.HERE/'logs').mkdir(parents=True,exist_ok=True)
        (core.HERE/'logs'/'web-client-error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        if '--smoke-web-client' not in sys.argv:
            ctypes.windll.user32.MessageBoxW(None,'No se pudo iniciar el cliente.\n'+str(exc)+'\n\nDetalle: logs/web-client-error.txt\nLa interfaz necesita Microsoft Edge WebView2 Runtime.','Rising Battle',0x10)
        raise
