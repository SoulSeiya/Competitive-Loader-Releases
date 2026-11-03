"""Provisional ranked queue, authenticated with the existing BTC device identity."""
import hashlib
import json
from pathlib import Path
import queue
import threading
import time
import urllib.error
import urllib.request
import competitive_loader as core
from social_client import credentials
from rising_service import DEFAULT_ROOM_SERVICE,ServiceClient
from rising_room import RoomError


def compatibility_key(runtime):
    runtime=Path(runtime);exe=runtime/'Tenkaichi3Decomp.exe'
    if core.sha256_file(exe)!=core.BTC_1381_HASH:raise RoomError('La ranked beta requiere el motor BTC fijo de esta versión.')
    core.validate_payload(core.PAYLOAD,exe)
    memory=core.online_memory_fingerprint(runtime)
    if not memory:raise RoomError('Importa la memory competitiva antes de entrar en rankeds.')
    marker=runtime/'gamedata'/'.competitive-v8.4.1.json'
    try:data=json.loads(marker.read_text(encoding='utf-8'))
    except (OSError,ValueError):raise RoomError('Selecciona una instalación BTC generada y revisada antes de entrar en rankeds.')
    values={'protocol':'btc-ranked-beta-1','engine':core.BTC_1381_HASH,'memory':memory,
            'edition':{k:data.get(k) for k in ('edition','slus_sha1','dbzp_sha1')},
            'payload':{n:core.sha256_file(core.PAYLOAD/n) for n in core.PATCH_OBJECTS}}
    return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()


RANKED_RULES={'ft':2,'seconds':360,'characters':2}
LEGACY_RANKED_RULES={'ft':2,'seconds':180,'characters':2}


class RankedClient:
    def __init__(self,store,url=DEFAULT_ROOM_SERVICE):
        checked=ServiceClient(url);self._opener=checked.opener
        self._url=checked.url.removesuffix('/v1/rooms')+'/v1/ranked';self._identity=credentials(store)

    def send(self,op,**values):
        request=urllib.request.Request(self._url,json.dumps(dict(self._identity,op=op,**values)).encode(),{'Content-Type':'application/json','Accept':'application/json','User-Agent':'BTC-Ranked-Beta/1'})
        try:
            with self._opener.open(request,timeout=8) as response:raw=response.read(262145)
        except urllib.error.HTTPError as exc:
            try:message=json.loads(exc.read(4096)).get('error','El servicio ranked rechazó la petición.')
            except (OSError,ValueError):message='No se pudo consultar la ranked beta.'
            finally:exc.close()
            raise RoomError(message) from None
        except OSError:raise RoomError('No se pudo conectar con el servidor ranked. No se han calculado puntos localmente.') from None
        if len(raw)>262144:raise RoomError('Respuesta ranked demasiado grande.')
        result=json.loads(raw)
        if result.get('protocol')!=1 or not isinstance(result.get('me'),dict) or result.get('rules') not in (RANKED_RULES,LEGACY_RANKED_RULES):raise RoomError('Actualiza el Loader: protocolo ranked incompatible.')
        return result


class RankedManager:
    def __init__(self,store,telemetry):
        self.store=store;self.telemetry=telemetry;self.snapshot=None;self.status='Conectando con la ranked beta…'
        self.error=None
        self.commands=queue.Queue(maxsize=8);self.launches=queue.Queue();self.stop=threading.Event();self.thread=None
        self._bound_match=None;self._bound_session=None
        self._baseline_serial=0;self._baseline_session=None
        self._bound_attempt=0

    def start(self):
        if self.thread:return
        self.thread=threading.Thread(target=self._work,name='BTC ranked beta',daemon=True);self.thread.start()

    def submit(self,op,**values):
        previous=self.status
        if op=='queue':self.status='Solicitando búsqueda ranked…'
        elif op=='cancel_queue':self.status='Cancelando búsqueda…'
        try:self.commands.put_nowait((op,values))
        except queue.Full:
            self.status=previous
            raise

    def _heartbeat(self):
        match=(self.snapshot or {}).get('match')
        if not match or match.get('finished'):return {}
        status=self.telemetry()
        if self._bound_match!=match['id']:self._bound_match=match['id'];self._bound_session=None
        connected=bool(status.get('serial',0)>self._baseline_serial or (status.get('session')!=self._baseline_session and status.get('serial',0)>0))
        if connected and self._bound_session is None:self._bound_session=status.get('session')
        closed=bool(self._bound_session and (not status.get('running') or status.get('session')!=self._bound_session or
                    (status.get('failed') and not status.get('connected'))))
        return {'match':match['id'],'connected':connected,'closed':closed,'failed':connected and bool(status.get('failed')),
                'completed':connected and bool(status.get('completed')),'score':status.get('score') if connected else None,
                'attempt':match.get('attempt',0),'desync_proof':status.get('desync_proof') if connected and status.get('failed') else None}

    def _receive(self,result):
        match=result.get('match')
        if match and (match['id']!=self._bound_match or match.get('attempt',0)!=self._bound_attempt):
            current=self.telemetry();self._baseline_serial=current.get('serial',0);self._baseline_session=current.get('session')
            self._bound_match=match['id'];self._bound_session=None
            self._bound_attempt=match.get('attempt',0)
        self.snapshot=result;self.error=None
        self.status=('Desync confirmado · elige continuar con el marcador guardado o salir sin puntos.' if match and match.get('phase')=='recovering' and not match.get('finished') else
                     'Confirmando el desync con el rival…' if match and match.get('confirming_fault') else
                     'Buscando un rival compatible…' if result.get('queued') else
                     'Rival encontrado. Preparando la partida…' if match and not match.get('finished') and match.get('phase')!='playing' else
                     'Set en curso · continúa en el juego.' if match and not match.get('finished') else
                     'Listo para buscar ranked.')
        launch=result.get('launch')
        if launch:self.launches.put(launch)

    def _work(self):
        client=None;last=0;failures=0;last_heartbeat=None
        while not self.stop.is_set():
            try:
                if client is None:client=RankedClient(self.store)
                try:op,values=self.commands.get(timeout=.25)
                except queue.Empty:op=None;values={}
                if op:
                    if op=='queue':values=dict(values,recovery=1)
                    self._receive(client.send(op,**values));last=time.monotonic();failures=0
                match=(self.snapshot or {}).get('match');active=bool(match and not match.get('finished'))
                interval=5 if active or (self.snapshot or {}).get('queued') else 25
                heartbeat=self._heartbeat() if active else {}
                urgent=bool(active and heartbeat!=last_heartbeat and time.monotonic()-last>=1)
                if time.monotonic()-last>=interval or urgent:
                    last=time.monotonic();last_heartbeat=heartbeat
                    self._receive(client.send('heartbeat' if heartbeat else 'poll',**heartbeat));failures=0
            except (OSError,RoomError,ValueError) as exc:
                self.status=str(exc);self.error=str(exc);failures+=1;self.stop.wait(min(25,2**min(failures,4)))

    def close(self):
        self.stop.set()
        if self.thread:self.thread.join(timeout=9)
