"""Official Challonge v2.1 device login and read-only bracket synchronization.

No client secret is distributed. Tokens are sealed by Windows DPAPI and are
never placed in game arguments, room messages, diagnostics or image requests.
"""
import json
import queue
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

API='https://api.challonge.com/v2.1'
CONNECT='https://connect.challonge.com'
SCOPES='me tournaments:read matches:read participants:read'


class ChallongeError(RuntimeError):
    def __init__(self,message,code=''):
        super().__init__(message);self.code=code


def tournament_identifier(value):
    """Accept tournament links, not arbitrary API URLs or redirect parameters."""
    p=urllib.parse.urlsplit(value.strip())
    if p.scheme!='https' or p.username or p.password or p.port not in (None,443):
        raise ValueError('Pega un enlace HTTPS de un torneo de Challonge.')
    host=(p.hostname or '').lower()
    if host not in ('challonge.com','www.challonge.com'):
        raise ValueError('Usa el enlace principal challonge.com del torneo.')
    parts=p.path.strip('/').split('/')
    if len(parts)>1 and re.fullmatch('[a-z]{2}(?:-[A-Z]{2})?',parts[0]):parts.pop(0)
    if len(parts)!=1 or not re.fullmatch('[A-Za-z0-9_-]{1,100}',parts[0]):
        raise ValueError('Usa el enlace del bracket, sin /participants ni /settings.')
    if parts[0] in ('users','settings','tournaments','communities','user_session'):
        raise ValueError('El enlace debe corresponder a un torneo.')
    return parts[0]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ChallongeError('Challonge devolvió una redirección inesperada.')


class ChallongeAPI:
    def __init__(self,client_id,opener=None):
        self.client_id=client_id.strip()
        self.opener=opener or urllib.request.build_opener(NoRedirect())

    def request(self,url,token=None,form=None):
        headers={'Accept':'application/json','Content-Type':'application/vnd.api+json','User-Agent':'RisingBattle/2.0'}
        if token:headers.update(Authorization='Bearer '+token,**{'Authorization-Type':'v2'})
        body=None
        if form is not None:
            headers['Content-Type']='application/x-www-form-urlencoded'
            body=urllib.parse.urlencode(form).encode()
        req=urllib.request.Request(url,body,headers)
        try:
            with self.opener.open(req,timeout=12) as response:raw=response.read(2_000_001)
        except urllib.error.HTTPError as exc:
            try:error=json.loads(exc.read(4096)).get('error','')
            except (ValueError,OSError):error=''
            finally:exc.close()
            code=error if isinstance(error,str) else ''
            raise ChallongeError({401:'La sesión de Challonge ha caducado. Vuelve a conectar.',403:'Challonge no permite acceder a este recurso.',404:'No se encontró el torneo.',429:'Challonge limita las consultas. Reintentaremos más tarde.'}.get(exc.code,'Challonge rechazó la solicitud.'),code) from None
        except OSError:raise ChallongeError('No se pudo conectar con Challonge.') from None
        if len(raw)>2_000_000:raise ChallongeError('La respuesta de Challonge supera el límite admitido.')
        try:return json.loads(raw)
        except ValueError:raise ChallongeError('Respuesta no válida de Challonge.') from None

    def device(self,community=False,scope=None):
        if not re.fullmatch('[A-Za-z0-9_-]{8,200}',self.client_id):
            raise ChallongeError('Falta registrar y configurar la aplicación OAuth Rising Battle en Challonge.')
        scopes=scope or SCOPES+(' communities:manage' if community else '')
        result=self.request(CONNECT+'/oauth/authorize_device',form=dict(client_id=self.client_id,scope=scopes))
        if not all(result.get(k) for k in ('device_code','user_code','verification_uri','expires_in')):raise ChallongeError('Autorización incompleta de Challonge.')
        uri=result.get('verification_uri_complete') or result['verification_uri']
        if urllib.parse.urlsplit(uri).hostname not in ('auth.challonge.com','connect.challonge.com') or not uri.startswith('https://'):raise ChallongeError('Destino de autorización inesperado.')
        return result

    def device_token(self,device_code):
        return self.request(CONNECT+'/oauth/token',form=dict(client_id=self.client_id,device_code=device_code,grant_type='urn:ietf:params:oauth:grant-type:device_code'))

    def refresh(self,refresh_token):
        return self.request(CONNECT+'/oauth/token',form=dict(client_id=self.client_id,refresh_token=refresh_token,grant_type='refresh_token'))

    def me(self,token):
        data=self.request(API+'/me.json',token)['data'];a=data['attributes']
        if data.get('type')!='user' or not a.get('username'):raise ChallongeError('Perfil de Challonge no válido.')
        return dict(id=str(data['id']),username=a['username'],image_url=a.get('image_url') or '')

    def collection(self,path,token):
        result=[]
        for page in range(1,101):
            response=self.request(API+path+'?'+urllib.parse.urlencode(dict(page=page,per_page=100,include_community_tournaments=1)),token)
            rows=response.get('data')
            if not isinstance(rows,list):raise ChallongeError('Lista de Challonge no válida.')
            result.extend(rows)
            if len(rows)<100:return result
        raise ChallongeError('El torneo supera el tamaño admitido por esta prueba.')

    def bracket(self,link,token,community=''):
        key=tournament_identifier(link);path='/tournaments/'+urllib.parse.quote(key,safe='')
        if community:
            if not re.fullmatch('[A-Za-z0-9_-]{1,100}',community):raise ValueError('Usa el identificador de la comunidad, por ejemplo universotenkaichi.')
            path='/communities/'+urllib.parse.quote(community,safe='')+path
        tournament=self.request(API+path+'.json?include_community_tournaments=1',token)['data']
        participants=self.collection(path+'/participants.json',token)
        matches=self.collection(path+'/matches.json',token)
        names={str(p['id']):p['attributes']['name'] for p in participants}
        normalized=[]
        for m in matches:
            a=m['attributes'];relationships=a.get('relationships',m.get('relationships',{}))
            def player(k):
                related=(relationships.get(k,{}).get('data') or {}).get('id')
                points=a.get('points_by_participant') or []
                side=0 if k=='player1' else 1
                fallback=points[side].get('participant_id') if len(points)>side else None
                return str(related or fallback or '')
            p1,p2=player('player1'),player('player2')
            normalized.append(dict(id=str(m['id']),round=int(a.get('round',0)),identifier=a.get('identifier',''),state=a.get('state','pending'),p1=p1,p2=p2,name1=names.get(p1,'Por decidir'),name2=names.get(p2,'Por decidir'),scores=a.get('scores',''),winner=str(a.get('winner_id') or '')))
        return dict(id=str(tournament['id']),title=tournament['attributes']['name'],kind=tournament['attributes'].get('tournament_type',''),link='https://challonge.com/'+key,participants=participants,matches=normalized,updated=time.time())


class ChallongeManager:
    def __init__(self,store,organizer=False):
        self.organizer=organizer;self.prefix='challonge_organizer_' if organizer else 'challonge_'
        self.store=store;self.commands=queue.Queue(maxsize=8);self.events=queue.Queue();self.stop=threading.Event()
        self.thread=None;self.snapshot=None;self.identity=None;self.device=None;self.link='';self.gaming=False
        self.status='Conecta tu cuenta de Challonge';self.version=0
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value BLOB)')
            row=db.execute("SELECT value FROM settings WHERE key='challonge_client_id'").fetchone()
        import competitive_loader as core
        config=json.loads((core.RESOURCE_ROOT/'assets'/'challonge_config.json').read_text(encoding='utf-8'))
        self.client_id=bytes(row['value']).decode() if row else config.get('client_id','')
        self.sync_interval=max(60,int(config.get('sync_interval_seconds',60)))
        self.sync_until=0
        with store.connect() as db:row=db.execute('SELECT value FROM settings WHERE key=?',(self.prefix+'community',)).fetchone()
        self.community=bytes(row['value']).decode() if row else ''

    def submit(self,op,value=''):
        if not self.thread:
            self.thread=threading.Thread(target=self._work,daemon=True);self.thread.start()
        self.commands.put_nowait((op,value))

    def _save_tokens(self,tokens):
        from social_client import protect
        tokens=dict(tokens,expires_at=time.time()+int(tokens.get('expires_in',604800)))
        with self.store.connect() as db:db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(self.prefix+'tokens',protect(json.dumps(tokens).encode())))
        return tokens

    def _load_tokens(self):
        from social_client import protect
        with self.store.connect() as db:row=db.execute('SELECT value FROM settings WHERE key=?',(self.prefix+'tokens',)).fetchone()
        if row:
            try:return json.loads(protect(bytes(row['value']),True))
            except (ValueError,OSError):self.status='Vuelve a conectar tu cuenta de Challonge.'
        return None

    def _profile(self,api,tokens):
        identity=api.me(tokens['access_token'])
        if self.organizer:
            self.identity=identity
            self.events.put(('organizer',identity))
            return
        # Preserve the local UUID/history when linking the first official account.
        with self.store.connect() as db:
            previous=db.execute("SELECT value FROM settings WHERE key='challonge_identity'").fetchone()
            if previous and json.loads(bytes(previous['value']))['id']!=identity['id']:
                raise ChallongeError('Este perfil ya está vinculado a otra cuenta de Challonge.')
            db.execute("INSERT OR REPLACE INTO settings VALUES('challonge_identity',?)",(json.dumps(identity).encode(),))
        name=identity['username'].encode()[:16].decode('utf-8','ignore')
        self.store.rename(name);self.identity=identity
        if identity['image_url']:
            try:self._avatar(identity['image_url'])
            except (OSError,ValueError,ChallongeError):self.status='Cuenta conectada; no se pudo descargar su avatar.'
        self.events.put(('profile',identity))

    def _avatar(self,url):
        import tempfile
        from pathlib import Path
        parsed=urllib.parse.urlsplit(url)
        # Only official avatar storage; never forward OAuth headers to media URLs.
        if parsed.scheme!='https' or parsed.username or parsed.password or parsed.port not in (None,443) or parsed.hostname not in ('user-assets.challonge.com','s3.amazonaws.com'):
            raise ChallongeError('El proveedor del avatar todavía no es compatible.')
        opener=urllib.request.build_opener(NoRedirect())
        with opener.open(urllib.request.Request(url,headers={'User-Agent':'RisingBattle/2.0'}),timeout=10) as response:
            if response.headers.get_content_type() not in ('image/png','image/jpeg','image/bmp'):raise ChallongeError('Formato de avatar no compatible.')
            raw=response.read(4_000_001)
        if len(raw)>4_000_000:raise ChallongeError('El avatar supera el límite de descarga.')
        with tempfile.TemporaryDirectory(prefix='btc-avatar-') as temp:
            path=Path(temp)/'image';path.write_bytes(raw);self.store.set_avatar(path)

    def _work(self):
        api=ChallongeAPI(self.client_id);tokens=self._load_tokens();next_sync=0;grant=None;grant_end=0;next_grant=0
        while not self.stop.is_set():
            try:
                try:op,value=self.commands.get(timeout=.5)
                except queue.Empty:op,value='',None
                now=time.monotonic()
                if op=='config':
                    api=ChallongeAPI(value);self.client_id=value
                    with self.store.connect() as db:db.execute("INSERT OR REPLACE INTO settings VALUES('challonge_client_id',?)",(value.encode(),))
                    self.status='Aplicación configurada. Conecta tu cuenta.'
                if op=='community':
                    value=value.strip()
                    if value and not re.fullmatch('[A-Za-z0-9_-]{1,100}',value):raise ValueError('Identificador de comunidad no válido.')
                    self.community=value
                    with self.store.connect() as db:db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(self.prefix+'community',value.encode()))
                if op=='login':
                    grant=api.device(community=bool(self.organizer and self.community));self.device=grant;grant_end=now+min(1800,int(grant['expires_in']));next_grant=now+max(5,int(grant.get('interval',5)))
                    self.status='Autoriza Rising Battle en Challonge.';self.events.put(('device',grant))
                if op=='import':
                    tournament_identifier(value)
                    if not tokens:raise ChallongeError('Conecta tu cuenta de Challonge antes de importar el torneo.')
                    self.link=value;next_sync=0;self.sync_until=now+300
                if op=='refresh' and now>=next_sync:self.sync_until=now+300
                if grant and now>=grant_end:
                    grant=None;self.device=None;self.status='El código ha caducado. Vuelve a conectar.'
                if grant and now>=next_grant:
                    next_grant=now+max(5,int(grant.get('interval',5)))
                    try:new=api.device_token(grant['device_code'])
                    except ChallongeError as exc:
                        if exc.code not in ('authorization_pending','slow_down'):grant=None;self.device=None;raise
                        if exc.code=='slow_down':grant['interval']=int(grant.get('interval',5))+5
                    else:
                        if not new.get('access_token'):raise ChallongeError('Challonge no devolvió un token de acceso.')
                        self._profile(api,new);tokens=self._save_tokens(new);grant=None;self.device=None;self.status='Cuenta de Challonge conectada.'
                if tokens and not self.identity:
                    if tokens.get('expires_at',0)<time.time()+60:
                        fresh=api.refresh(tokens['refresh_token']);fresh.setdefault('refresh_token',tokens['refresh_token']);tokens=self._save_tokens(fresh)
                    self._profile(api,tokens);self.status='Cuenta de Challonge conectada.'
                if self.link and tokens and now>=self.sync_until:
                    self.status='Prueba de sincronización pausada tras 5 minutos para cuidar la cuota Sandbox.'
                if self.link and tokens and now>=next_sync and now<self.sync_until:
                    next_sync=now+self.sync_interval
                    if tokens.get('expires_at',0)<time.time()+60:
                        fresh=api.refresh(tokens['refresh_token']);fresh.setdefault('refresh_token',tokens['refresh_token']);tokens=self._save_tokens(fresh)
                    try:snapshot=api.bracket(self.link,tokens['access_token'],self.community if self.organizer else '')
                    except ChallongeError as exc:
                        if str(exc) in ('No se encontró el torneo.','Challonge no permite acceder a este recurso.'):
                            raise ChallongeError('Esta cuenta no tiene acceso por API al torneo. Conecta al organizador y, si es de comunidad, autoriza esa comunidad en Challonge.') from None
                        raise
                    self.snapshot=snapshot;self.version+=1
                    self.status=f'Sincronizado con Challonge · cada {self.sync_interval} s · prueba de 5 minutos'
            except (ChallongeError,ValueError,KeyError,TypeError,OSError) as exc:
                # Never expose provider response bodies or tokens in diagnostics.
                self.status=str(exc) if isinstance(exc,(ChallongeError,ValueError)) else 'No se pudo leer el torneo o perfil de Challonge.'
                next_sync=time.monotonic()+60
                if tokens and not self.identity:tokens=None

    def close(self):
        self.stop.set()
