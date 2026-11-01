"""BTC social transport on a separate worker, with device credentials protected by Windows."""
import ctypes as C
from ctypes import wintypes as W
import json
import queue
import secrets
import threading
import time
import urllib.request
import urllib.error
from rising_service import DEFAULT_ROOM_SERVICE
from rising_room import RoomError


def protect(data,decrypt=False):
    class Blob(C.Structure):
        _fields_=[('size',W.DWORD),('data',C.POINTER(C.c_ubyte))]
    buffer=C.create_string_buffer(data);source=Blob(len(data),C.cast(buffer,C.POINTER(C.c_ubyte)));out=Blob()
    fn=getattr(C.WinDLL('crypt32',use_last_error=True),'CryptUnprotectData' if decrypt else 'CryptProtectData')
    fn.argtypes=[C.POINTER(Blob),C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p,W.DWORD,C.POINTER(Blob)];fn.restype=W.BOOL
    if not fn(C.byref(source),None,None,None,None,1,C.byref(out)):raise C.WinError(C.get_last_error())
    free=C.WinDLL('kernel32').LocalFree;free.argtypes=[C.c_void_p];free.restype=C.c_void_p
    try:return C.string_at(out.data,out.size)
    finally:free(out.data)


def credentials(store):
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value BLOB)')
        row=db.execute("SELECT value FROM settings WHERE key='social_credential'").fetchone()
        if not row:
            sealed=protect(secrets.token_hex(32).encode())
            db.execute("INSERT OR IGNORE INTO settings VALUES('social_credential',?)",(sealed,))
            row=db.execute("SELECT value FROM settings WHERE key='social_credential'").fetchone()
    return dict(id=store.profile()['id'],token=protect(bytes(row['value']),True).decode())


class SocialClient:
    def __init__(self,identity,url=DEFAULT_ROOM_SERVICE):
        from rising_service import ServiceClient
        checked=ServiceClient(url)
        self.url=checked.url.removesuffix('/v1/rooms')+'/v1/social';self.opener=checked.opener;self.identity=identity

    def send(self,op,**values):
        request=urllib.request.Request(self.url,json.dumps(dict(self.identity,op=op,**values)).encode(),
            {'Content-Type':'application/json','User-Agent':'CompetitiveLoader-BTC/2.0','Accept':'application/json'})
        try:
            with self.opener.open(request,timeout=6) as response:raw=response.read(262145)
        except urllib.error.HTTPError as exc:
            try:detail=json.loads(exc.read(4096)).get('error','Petición social rechazada')
            except (ValueError,OSError):detail='Petición social rechazada'
            finally:exc.close()
            raise RoomError(detail) from None
        except OSError:raise RoomError('No se pudo conectar con el servicio social BTC') from None
        if len(raw)>262144:raise RoomError('Respuesta social demasiado grande')
        try:
            result=json.loads(raw)
            if result.get('protocol')!=1 or not isinstance(result.get('me'),dict):raise ValueError()
            for key,limit in (('friends',200),('incoming',200),('outgoing',200),('events',64)):
                if not isinstance(result.get(key),list) or len(result[key])>limit:raise ValueError()
            return result
        except (ValueError,TypeError,AttributeError):raise RoomError('Respuesta social incompatible') from None


class SocialManager:
    def __init__(self,store):
        self.store=store;self.commands=queue.Queue(maxsize=32);self.launches=queue.Queue();self.notices=queue.Queue()
        self.snapshot=None;self.conversation=None;self.chat_target=None;self.activity='online'
        self.status='Conectando el perfil…';self.version=0;self.stopped=threading.Event();self.thread=None

    def start(self):
        if self.thread:return
        self.thread=threading.Thread(target=self._work,daemon=True);self.thread.start()

    def submit(self,op,**values):
        self.commands.put_nowait((op,values))

    def _receive(self,result,direct_duel=False,duel_peer=None,duel_rules=None):
        if 'launch' in result:self.launches.put(dict(result['launch'],_direct_duel=direct_duel,_duel_peer=duel_peer,_duel_rules=duel_rules))
        if 'conversation' in result:self.conversation=result['conversation']
        self.snapshot=result;self.version+=1

    def _work(self):
        client=None;registered=False;last_poll=0;failures=0
        try:
            client=SocialClient(credentials(self.store))
            while not self.stopped.is_set():
                try:
                    if not registered:
                        self._receive(client.send('register',name=self.store.profile()['name']));registered=True;failures=0;self.status='Social conectado'
                    try:op,values=self.commands.get(timeout=.15)
                    except queue.Empty:op=None;values={}
                    if op:
                        direct=op=='challenge' or (op=='accept' and any(e.get('id')==values.get('event') and e.get('kind')=='challenge' for e in (self.snapshot or {}).get('events',[])))
                        peer=values.get('target') if op=='challenge' else next((e.get('sender') for e in (self.snapshot or {}).get('events',[]) if e.get('id')==values.get('event')),None)
                        self._receive(client.send(op,**values),direct_duel=direct,duel_peer=peer,duel_rules={k:values[k] for k in ('ft','seconds','characters') if k in values} if direct else None);self.status='Social conectado' 
                        self.notices.put({'add':'Solicitud de amistad procesada. Revisa Social.','accept_friend':'Amigo agregado.','reject_friend':'Solicitud rechazada.','remove_friend':'Amistad eliminada.','message':'Mensaje enviado.','invite':'Invitación enviada.','challenge':'Desafío enviado; esperando aceptación.','accept':'Invitación aceptada.','decline':'Invitación rechazada.','messages':'Conversación abierta.'}.get(op,'Acción completada.'))
                    now=time.monotonic()
                    if now-last_poll>=8 or op:
                        last_poll=now
                        self._receive(client.send('poll',name=self.store.profile()['name'],activity=self.activity))
                        if self.chat_target and any(f['id']==self.chat_target for f in self.snapshot['friends']):
                            self._receive(client.send('messages',target=self.chat_target))
                except (RoomError,OSError,ValueError) as exc:
                    failures+=1;self.status=str(exc);self.notices.put(str(exc));self.stopped.wait(2 if registered else min(30,2**min(failures,5)))
        except Exception:
            self.status='No se pudo preparar el perfil social de este PC'
        finally:
            if client and registered:
                try:client.send('offline')
                except (RoomError,OSError):pass

    def close(self):
        self.stopped.set()
        if self.thread:self.thread.join(timeout=8)
