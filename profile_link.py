"""Optional, device-authorized Challonge identity. No tournament access or writes."""
import json
import queue
import threading
import time
import urllib.parse
import urllib.request
from challonge_client import ChallongeAPI, ChallongeError, NoRedirect


def avatar_bytes(url):
    if not url:return None
    p=urllib.parse.urlsplit(url)
    if p.scheme!='https' or p.username or p.password or p.port not in (None,443) or p.hostname not in ('user-assets.challonge.com','s3.amazonaws.com'):
        raise ChallongeError('Proveedor de imagen no compatible; se conservará tu avatar local.')
    req=urllib.request.Request(url,headers={'User-Agent':'RisingBattle/2.0'})
    with urllib.request.build_opener(NoRedirect()).open(req,timeout=10) as r:
        if r.headers.get_content_type() not in ('image/png','image/jpeg','image/bmp','image/webp'):
            raise ChallongeError('Imagen de perfil no compatible.')
        raw=r.read(4_000_001)
    if len(raw)>4_000_000:raise ChallongeError('La imagen supera el límite de descarga.')
    return raw


class ProfileLink:
    TOKEN_KEY='btc_identity_tokens'

    def __init__(self,store,client_id):
        self.store=store;self.client_id=client_id
        self.lock=threading.Lock();self.generation=0;self.events=queue.Queue()
        self.status='Challonge es opcional.';self.device=None;self.busy=False

    def snapshot(self):
        with self.lock:return {'status':self.status,'device':dict(self.device) if self.device else None,'busy':self.busy}

    def _current(self,g):return g==self.generation

    def cancel(self,forget=False):
        with self.lock:
            self.generation+=1;self.device=None;self.busy=False
            self.status='Vinculación cancelada.'
            if forget:
                with self.store.connect() as db:db.execute('DELETE FROM settings WHERE key=?',(self.TOKEN_KEY,))
        # The client discards any already delivered pending profile as well.

    def start(self):
        with self.lock:
            if self.busy:return
            self.generation+=1;g=self.generation;self.busy=True;self.device=None
            self.status='Conectando con Challonge…'
        threading.Thread(target=self._run,args=(g,),name='BTC optional identity',daemon=True).start()

    def _run(self,g):
        from social_client import protect
        api=ChallongeAPI(self.client_id)
        try:
            with self.store.connect() as db:row=db.execute('SELECT value FROM settings WHERE key=?',(self.TOKEN_KEY,)).fetchone()
            tokens=None
            if row:
                try:
                    tokens=json.loads(protect(bytes(row['value']),True))
                    if tokens.get('expires_at',0)<time.time()+60:
                        fresh=api.refresh(tokens['refresh_token']);fresh.setdefault('refresh_token',tokens['refresh_token']);tokens=fresh
                except (ValueError,OSError,KeyError,ChallongeError):tokens=None
            if not tokens:
                grant=api.device(scope='me')
                with self.lock:
                    if not self._current(g):return
                    self.device={k:grant[k] for k in ('user_code','verification_uri')}
                    self.device['url']=grant.get('verification_uri_complete') or grant['verification_uri']
                    self.status='Autoriza Rising Battle en el navegador.'
                end=time.monotonic()+min(1800,int(grant['expires_in']))
                interval=max(5,int(grant.get('interval',5)))
                while time.monotonic()<end:
                    # Bounded waits allow immediate cancellation without another request.
                    until=time.monotonic()+interval
                    while time.monotonic()<until:
                        time.sleep(.2)
                        if not self._current(g):return
                    try:tokens=api.device_token(grant['device_code']);break
                    except ChallongeError as exc:
                        if exc.code not in ('authorization_pending','slow_down'):raise
                        if exc.code=='slow_down':interval+=5
                if not tokens:raise ChallongeError('El código caducó. Vuelve a conectar.')
            identity=api.me(tokens['access_token'])
            warning=''
            try:image=avatar_bytes(identity.get('image_url',''))
            except (OSError,ValueError,ChallongeError):image=None;warning=' No se pudo importar la imagen; se conserva tu avatar.'
            with self.lock:
                if not self._current(g):return
                # DPAPI for this Windows user. Never sent to the WebView or logs.
                tokens=dict(tokens,expires_at=tokens.get('expires_at',time.time()+int(tokens.get('expires_in',604800))))
                with self.store.connect() as db:db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(self.TOKEN_KEY,protect(json.dumps(tokens).encode())))
                self.events.put((g,identity,image,warning));self.device=None
                self.status='Autorizado; esperando aplicar el perfil fuera del combate.'
        except (ChallongeError,OSError,ValueError,KeyError,TypeError):
            with self.lock:
                if self._current(g):self.status='No se pudo vincular Challonge. Puedes seguir con tu perfil local o reintentar.';self.device=None
        finally:
            with self.lock:
                if self._current(g):self.busy=False
