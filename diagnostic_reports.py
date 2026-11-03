"""Opt-in structured desync reports. Never uploads raw logs, paths or save data."""
import copy
import hashlib
import json
import queue
from pathlib import Path
import re
import threading
import time
import urllib.request
import urllib.error
import uuid

HASH=re.compile(r'^[a-f0-9]{64}$')
VERSION=re.compile(r'^[A-Za-z0-9._-]{1,64}$')
FINGERPRINT=re.compile(r'gameplay data: ([a-f0-9]{8}) \(tables ([a-f0-9]{8}) characters ([a-f0-9]{8}) animations ([a-f0-9]{8}) stages ([a-f0-9]{8}) effects ([a-f0-9]{8}) scripts ([a-f0-9]{8}) menus ([a-f0-9]{8})\)')

def preference(store, value=None):
    with store.connect() as db:
        if value is not None:
            if type(value) is not bool:raise ValueError('Preferencia de diagnóstico inválida')
            db.execute("INSERT OR REPLACE INTO settings VALUES('diagnostics_opt_in',?)",(b'1' if value else b'0',))
        row=db.execute("SELECT value FROM settings WHERE key='diagnostics_opt_in'").fetchone()
        return bytes(row['value'])==b'1' if row else True

class DesyncCapture:
    """Bounded parser on the game's reader thread; no network or disk I/O here."""
    def __init__(self, summary, emit):
        self.summary=summary;self.emit=emit;self.context={};self.fingerprint={}
        self.reset()

    def reset(self):
        self.sent=False;self.divergence=None;self.connection='unknown';self.delay=None;self.rollback=None;self.metrics=[];self.combat=None;self.trace_epoch=None

    def bind(self, context):
        self.context=copy.deepcopy(context)

    def line(self, line):
        if 'btc: combat_trace ' in line and len(line)<24576:
            from combat_trace import clean_combat
            try:self.combat=clean_combat(json.loads(line.split('btc: combat_trace ',1)[1]))
            except (ValueError,TypeError):pass
        if 'connected directly;' in line or 'connected through the relay;' in line:self.reset()
        elif 'btc: session_begin online=1' in line and self.sent:self.reset()
        epoch=re.search(r'btc: session_begin online=1 trace_epoch=(\d+)',line)
        if epoch:self.trace_epoch=int(epoch[1]);self.combat=None
        m=FINGERPRINT.search(line)
        if m:self.fingerprint=dict(zip(('total','tables','characters','animations','stages','effects','scripts','menus'),m.groups()))
        if 'connected directly;' in line:self.connection='direct'
        elif 'connected through the relay;' in line:self.connection='relay'
        m=re.search(r'input delay (\d+) blanks',line)
        if m:self.delay=int(m[1])
        m=re.search(r'rollback of up to (\d+) blanks',line)
        if m:self.rollback=int(m[1])
        m=re.search(r'net: blank (\d+): (\d+) rollbacks \(([\d.]+) blanks each\), (\d+) waits',line)
        if m:
            self.metrics.append({'blank':int(m[1]),'rollbacks':int(m[2]),'average_blanks':float(m[3]),'waits':int(m[4])})
            self.metrics=self.metrics[-12:]
        m=re.search(r'the two games differ at blank (\d+) \(this copy ([a-f0-9]{16}), the other ([a-f0-9]{16})\)',line)
        if m and self.divergence is None:self.divergence={'blank':int(m[1]),'local_hash':m[2],'peer_hash':m[3]}
        if 'the two games no longer agree (desync)' in line.lower() and not self.sent:
            self.sent=True
            self.emit(self.report())

    def report(self,kind="desync"):
        versions={}
        for key in ('loader_version','decomp_release'):
            value=self.summary.get(key,'')
            if isinstance(value,str) and VERSION.fullmatch(value):versions[key]=value
        for key in ('exe_sha256','memory_sha256','dat_sha256'):
            value=self.summary.get(key,'')
            if isinstance(value,str) and HASH.fullmatch(value):versions[key]=value
        versions['payload_sha256']={k:v for k,v in self.summary.get('payload_sha256',{}).items()
            if re.fullmatch(r'[A-Za-z0-9_-]{1,80}\.o',k) and isinstance(v,str) and HASH.fullmatch(v)}
        result={'schema':1,'report_id':uuid.uuid4().hex,'kind':kind,
            'context':copy.deepcopy(self.context),'versions':versions,'fingerprint':dict(self.fingerprint),
            'divergence':copy.deepcopy(self.divergence),'network':{'connection':self.connection,
                'input_delay':self.delay,'rollback':self.rollback,'samples':list(self.metrics)},
            'character':None,'technique':None,'combat':copy.deepcopy(self.combat)}
        # Leave room for profile/room proof in the 24 KiB receiver envelope.
        combat=result.get('combat')
        while combat and len(json.dumps(result).encode('utf-8'))>22000:
            if len(combat.get('observations',[]))>1:combat['observations'].pop(0)
            elif len(combat.get('events',[]))>1:combat['events'].pop(0)
            else:break
        return result

def duel_context(room):
    combat=(room or {}).get('combat') or {}
    if combat.get('status')!='running':return {}
    match=next((m for m in combat.get('matches',[]) if m.get('id')==combat.get('current')),None)
    if not match or room.get('self_id') not in (match.get('p1'),match.get('p2')):return {}
    return {'battle_id':combat['id'],'match':match['id'],'room_code':room['room_code'],
        'side':1 if room['self_id']==match['p1'] else 2,
        'rules':{k:combat.get(k) for k in ('ft','seconds','characters')},'_room_token':room.get('token','')}

class ReportManager:
    def __init__(self,store,root):
        self.store=store;self.root=Path(root)/'diagnostic-outbox'/store.profile()['id']
        self.root.mkdir(parents=True,exist_ok=True)
        self.status='Activado: esperando un desync' if preference(store) else 'Desactivado'
        self.last_id=None;self.stopped=threading.Event();self.wake=threading.Event();self.incoming=queue.Queue(maxsize=20)
        self.lock=threading.Lock();self.thread=None
        self.history_requested=threading.Event()

    def start(self):
        if not self.thread:
            self.thread=threading.Thread(target=self._work,name='BTC diagnostics upload',daemon=True);self.thread.start()

    def accept(self,report):
        try:self.incoming.put_nowait(copy.deepcopy(report));self.wake.set()
        except queue.Full:self.status='Cola llena: conserva los registros locales'

    def _persist(self,report):
        if not preference(self.store):return
        from social_client import protect
        proof=report.get('context',{}).pop('_room_token','')
        report['_sealed_proof']=protect(proof.encode()).hex()
        with self.lock:
            if len(list(self.root.glob('*.json')))>=200:
                self.status='Cola llena: conserva los registros locales';return
            path=self.root/(report['report_id']+'.json')
            temp=path.with_suffix('.tmp');temp.write_text(json.dumps(report),encoding='utf-8');temp.replace(path)
            self.last_id=report['report_id'];self.status='Informe pendiente de envío';self.wake.set()

    def enabled(self,value):
        preference(self.store,value)
        self.status='Activado: esperando un desync' if value else 'Desactivado'
        if not value:
            self.history_requested.clear()
            with self.lock:
                for path in self.root.glob('*.json'):path.unlink()
                while True:
                    try:self.incoming.get_nowait()
                    except queue.Empty:break
        self.wake.set()

    def request_history(self):
        if not preference(self.store):raise ValueError('Activa los diagnósticos antes de enviar el historial')
        self.history_requested.set();self.status='Preparando los diagnósticos anteriores';self.wake.set()

    def _history(self):
        from diagnostic_history import history_reports
        owner=self.store.profile()['id'];queued=0
        for report in history_reports(self.root.parent.parent,owner):
            with self.store.connect() as db:
                sent=db.execute("SELECT value FROM settings WHERE key=?",('diagnostic_sent:'+report['report_id'],)).fetchone()
            if sent or (self.root/(report['report_id']+'.json')).exists():continue
            self._persist(report);queued+=1
        self.status=str(queued)+' informes históricos preparados (hasta 100 sesiones por envío)'

    def _send(self,report):
        from social_client import credentials, protect
        from rising_service import ServiceClient, DEFAULT_ROOM_SERVICE
        checked=ServiceClient(DEFAULT_ROOM_SERVICE)
        if report.get('combat'):
            # Older receivers silently drop unknown DTO fields. Retain the outbox
            # until the receiver explicitly supports combat evidence.
            probe=urllib.request.Request(checked.url.removesuffix('/v1/rooms')+'/v1/diagnostics/capabilities',
                headers={'Accept':'application/json','User-Agent':'RisingBattle-Diagnostics/1'})
            try:
                with checked.opener.open(probe,timeout=8) as response:
                    raw=response.read(8193)
                    capability=json.loads(raw) if len(raw)<=8192 else {}
                    needs_stage=any('stage' in row for row in report['combat'].get('observations',[]))
                    needs_abilities='events' in report['combat']
                    needs_costume=any('costume' in f for row in report['combat'].get('observations',[]) for f in row.get('sides',[]))
                    if capability.get('combat_trace')!=1 or (needs_stage and capability.get('stage_trace')!=1) or (needs_abilities and capability.get('ability_trace')!=1) or (needs_costume and capability.get('costume_trace')!=1):raise ValueError('Receptor sin captura de combate/escenario/habilidades/trajes')
            except Exception as exc:
                if isinstance(exc,urllib.error.HTTPError):exc.close()
                raise ValueError('Captura conservada localmente: receptor pendiente') from None
        clean=copy.deepcopy(report);proof=protect(bytes.fromhex(clean.pop('_sealed_proof')),True).decode()
        body=json.dumps(dict(credentials(self.store),room_token=proof,report=clean)).encode()
        request=urllib.request.Request(checked.url.removesuffix('/v1/rooms')+'/v1/diagnostics',body,
            {'Content-Type':'application/json','Accept':'application/json','User-Agent':'RisingBattle-Diagnostics/1'})
        with checked.opener.open(request,timeout=8) as response:
            raw=response.read(8193)
            if len(raw)>8192:raise ValueError('Respuesta demasiado grande')
            result=json.loads(raw)
            if result.get('report_id')!=report['report_id'] or result.get('accepted')is not True:raise ValueError('Respuesta incompatible')

    def _work(self):
        backoff=15
        while not self.stopped.is_set():
            failed=False
            if self.history_requested.is_set():
                self.history_requested.clear()
                try:self._history()
                except Exception:self.status='No se pudo preparar el historial; los registros siguen en tu PC'
            try:
                while True:self._persist(self.incoming.get_nowait())
            except queue.Empty:pass
            except Exception:self.status='No se pudo preparar el informe; consulta los registros locales'
            if preference(self.store):
                for path in sorted(self.root.glob('*.json')):
                    if self.stopped.is_set() or not preference(self.store):break
                    try:
                        with self.lock:
                            if not path.exists():continue
                            report=json.loads(path.read_text(encoding='utf-8'))
                        if time.time()-path.stat().st_mtime>7*86400:
                            path.unlink(missing_ok=True);continue
                        if not report.get('context',{}).get('battle_id') and report.get('context',{}).get('source')!='history':
                            self.status='Sin ID de duelo: consulta los registros locales';path.unlink(missing_ok=True);continue
                        self._send(report)
                        with self.store.connect() as db:db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('diagnostic_sent:'+report['report_id'],b'1'))
                        path.unlink(missing_ok=True);self.last_id=report['report_id'];self.status='Informe enviado · '+self.last_id[:8]
                    except urllib.error.HTTPError as exc:
                        code=exc.code;exc.close()
                        if code in (400,401,403,409,410,413):
                            self.status='Informe no enviado: '+('la sala ya expiró' if code==410 else 'requiere revisión local')
                            path.unlink(missing_ok=True);continue
                        self.status='Envío pendiente: se reintentará sin afectar la partida';failed=True;break
                    except Exception:
                        self.status='Envío pendiente: se reintentará sin afectar la partida';failed=True;break
            self.wake.wait(backoff if failed else 30);self.wake.clear()
            backoff=min(300,backoff*2) if failed else 15

    def close(self):
        self.stopped.set();self.wake.set()
        try:
            while True:self._persist(self.incoming.get_nowait())
        except queue.Empty:pass
        except Exception:self.status='Consulta los registros locales'
