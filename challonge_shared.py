"""Participant reads of Cloudflare's shared bracket; organizer tokens stay private."""
import json
import queue
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from challonge_client import ChallongeError,tournament_identifier,NoRedirect
from rising_service import DEFAULT_ROOM_SERVICE


class SharedChallongeClient:
    def __init__(self,url=DEFAULT_ROOM_SERVICE):
        from rising_service import ServiceClient
        checked=ServiceClient(url)
        self.url=checked.url.removesuffix('/v1/rooms')+'/v1/challonge'
        self.opener=urllib.request.build_opener(NoRedirect())

    def request(self,link,binding=None):
        slug=tournament_identifier(link)
        url=self.url+('/bind' if binding else '?'+urllib.parse.urlencode(dict(slug=slug)))
        data=json.dumps(dict(binding,slug=slug)).encode() if binding else None
        req=urllib.request.Request(url,data,{'Accept':'application/json','Content-Type':'application/json','User-Agent':'RisingBattle/2.0'})
        try:
            with self.opener.open(req,timeout=60 if binding else 55) as response:raw=response.read(2_000_001)
        except urllib.error.HTTPError as exc:
            try:message=json.loads(exc.read(4096)).get('error','No se pudo consultar el bracket compartido')
            except (ValueError,OSError):message='El servicio compartido aún no está disponible.'
            finally:exc.close()
            raise ChallongeError(message) from None
        except OSError:raise ChallongeError('No se pudo conectar con el servicio de torneos BTC.') from None
        if len(raw)>2_000_000:raise ChallongeError('Bracket compartido demasiado grande.')
        try:
            value=json.loads(raw);snapshot=value['tournament']
            if value.get('protocol')!=1 or not isinstance(snapshot,dict) or not isinstance(snapshot.get('participants'),list) or not isinstance(snapshot.get('matches'),list):raise ValueError()
            return value
        except (ValueError,KeyError,TypeError):raise ChallongeError('Bracket compartido no válido.') from None


class SharedBracketManager:
    def __init__(self,store,organizer):
        self.store,self.organizer=store,organizer
        self.commands=queue.Queue(maxsize=8);self.stop=threading.Event();self.thread=None
        self.snapshot=None;self.version=0;self.status='Pega el enlace de un torneo vinculado. No necesitas estar inscrito.'
        self.link='';self.visible=False

    def submit(self,op,value='',community=''):
        if not self.thread:
            self.thread=threading.Thread(target=self._work,daemon=True);self.thread.start()
        self.commands.put_nowait((op,value,community))

    def _work(self):
        client=SharedChallongeClient();next_poll=0
        while not self.stop.is_set():
            try:
                try:op,link,community=self.commands.get(timeout=.5)
                except queue.Empty:op,link,community='',None,''
                if op=='close':
                    self.link='';self.snapshot=None;self.version+=1
                    self.status='Vista del torneo cerrada.';continue
                if op in ('import','publish'):
                    tournament_identifier(link);self.link=link;next_poll=0
                if op=='publish':
                    tokens=self.organizer._load_tokens()
                    if not tokens:raise ChallongeError('Solo el organizador debe conectar su cuenta para vincular el torneo una vez.')
                    from social_client import credentials,SocialClient
                    identity=credentials(self.store)
                    SocialClient(identity).send('register',name=self.store.profile()['name'])
                    binding=dict(identity,access_token=tokens['access_token'],refresh_token=tokens['refresh_token'],expires_at=tokens.get('expires_at',0),community=community.strip())
                    self.status='Verificando el torneo y vinculándolo al servicio BTC…'
                    value=client.request(self.link,binding)
                    self.snapshot=value['tournament'];self.version+=1;self.status=value['status'];next_poll=time.monotonic()+15
                if op=='refresh' and time.monotonic()>=next_poll:next_poll=0
                if self.link and time.monotonic()>=next_poll and (self.visible or op):
                    next_poll=time.monotonic()+15
                    value=client.request(self.link);self.snapshot=value['tournament'];self.version+=1
                    self.status=value.get('status','Bracket compartido actualizado')
            except (ChallongeError,ValueError,KeyError,OSError) as exc:
                self.status=str(exc) if isinstance(exc,(ChallongeError,ValueError)) else 'No se pudo consultar el torneo compartido.'
                next_poll=time.monotonic()+60

    def close(self):self.stop.set()
