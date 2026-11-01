"""Private confirmed-input transport. All disk/HTTP work stays outside the game.

One mapping per Loader: publish as P1, or consume as a room observer. Never join
the two-player combat socket and never send an observer's controller inputs.
"""
import hashlib
import json
import os
from pathlib import Path
import threading
import time
import uuid
from observer_lab import ObserverMapping,Header
from spectator_protocol import compatible,encode_chunk,decode_chunk
from rising_service import ServiceClient

LIMIT=36000

def payload_fingerprint(folder):
    digest=hashlib.sha256()
    for path in sorted(Path(folder).glob('*.o')):
        digest.update(path.name.encode());digest.update(b'\0');digest.update(path.read_bytes())
    return digest.hexdigest()

def game_fingerprint(runtime):
    """Hash actual generated game/mod contents; ignore installer timestamps."""
    runtime=Path(runtime);files=[]
    for label in ('gamedata','mods'):
        root=runtime/label
        if not root.is_dir():continue
        for folder,dirs,names in os.walk(root):
            dirs[:]=sorted(d for d in dirs if not d.startswith('.'))
            for name in sorted(names):
                if name.startswith('.'):continue
                path=Path(folder)/name;files.append((label+'/'+path.relative_to(root).as_posix().lower(),path))
    if not files:raise ValueError('La instalación no contiene datos generados')
    for filename in ('Tenkaichi3Decomp.dat','Tenkaichi3Decomp.exe.mem'):
        if (runtime/filename).is_file():files.append((filename,runtime/filename))
    digest=hashlib.sha256()
    for name,path in sorted(files):
        digest.update(name.encode());digest.update(b'\0');digest.update(path.stat().st_size.to_bytes(8,'little'))
        with path.open('rb') as source:
            while block:=source.read(1024*1024):digest.update(block)
    return digest.hexdigest()

class LiveSpectator:
    def __init__(self,bridge):
        import competitive_loader as core
        self.bridge=bridge;self.mapping=ObserverMapping();self.lock=threading.Lock()
        self.stop=threading.Event();self.watch_request=None;self.fingerprints=None
        self.serial=0;self.capture=None;self.pads=bytearray();self.status='Espectador experimental: abre tu juego antes de observar.'
        self.root=core.HERE/'logs'/'spectator'/uuid.uuid4().hex;self.root.mkdir(parents=True)
        self.closed=False;self.runtime=None;self.binding=False
        self.collector=threading.Thread(target=self._collect,daemon=True);self.network=threading.Thread(target=self._network,daemon=True)
        self.collector.start();self.network.start()

    def configure(self,runtime):
        if self.binding:
            if self.runtime!=Path(runtime):raise ValueError('Reinicia este Loader para cambiar la instalación del espectador')
            return
        self.binding=True;self.runtime=Path(runtime);self.status='Espectador: calculando huellas de los datos y memory…'
        def hash_files():
            import competitive_loader as core
            try:
                result=dict(exe_sha256=core.sha256_file(self.runtime/'Tenkaichi3Decomp.exe'),
                    payload_sha256=payload_fingerprint(core.PAYLOAD),
                    data_sha256=game_fingerprint(self.runtime),memory_sha256=core.online_memory_fingerprint(self.runtime))
                if not result['memory_sha256']:raise ValueError('Falta la memory competitiva para observar')
                self.fingerprints=result;self.status='Espectador experimental preparado; esperando transmisión de P1.'
                self._log('COMPATIBILITY_READY')
            except Exception as exc:self.status='No se preparó el espectador: '+str(exc);self._log('COMPATIBILITY_FAILED',error=str(exc))
        threading.Thread(target=hash_files,daemon=True).start()

    def _log(self,event,**values):
        with (self.root/'transport.jsonl').open('a',encoding='utf-8') as out:out.write(json.dumps(dict(time=time.time(),event=event,**values),ensure_ascii=False)+'\n')

    def _session_fingerprints(self):
        import competitive_loader as core
        result=dict(self.fingerprints)
        # launch_patched stages and protects this actual online save. The
        # personal offline save may change while the long data hash runs.
        actual=self.runtime/'net_session'/'card1'/core.SAVE_NAME/core.SAVE_NAME
        if not actual.is_file():raise ValueError('Falta la memory preparada de la sesión')
        result['memory_sha256']=core.sha256_file(actual)
        return result

    def watch(self,tid,match):
        if not isinstance(self.bridge.client,ServiceClient):raise ValueError('Esta prueba requiere una sala Cloudflare')
        self.cancel()
        self.watch_request=dict(tournament_id=tid,match=match,request=uuid.uuid4().hex)
        self.status='Espectador: esperando las entradas confirmadas de P1…'
        self._log('WATCH_REQUESTED',match=match)

    def cancel(self):
        self.watch_request=None
        if self.mapping.shared.header.mode in (2,3):self.mapping.stop()

    def _collect(self):
        while not self.stop.wait(.02):
            try:
                data=self.mapping.drain()
                if not data:continue
                h,start,pads=data
                with self.lock:
                    if h.serial!=self.serial:
                        s=self.bridge.snapshot or {};t=s.get('combat') or s.get('tournament',{})
                        if t.get('role')!=1 or t.get('status')!='running':continue
                        self.serial=h.serial;self.pads=bytearray()
                        self.capture=dict(native=h,serial=h.serial,generation=uuid.uuid4().hex,
                            tournament_id=t['id'],match=t['current'],closed=False)
                        self._log('CAPTURE_STARTED',match=t['current'])
                    if start!=h.first+len(self.pads)//36:raise ValueError('Hueco en las entradas capturadas')
                    if len(self.pads)+len(pads)>LIMIT*36:raise ValueError('Se alcanzó el límite de 10 minutos de esta prueba')
                    self.pads.extend(pads);self.capture['closed']=bool(h.closed)
                if pads:
                    with (self.root/(self.capture['generation']+'.pads')).open('ab') as out:out.write(pads)
            except Exception as exc:
                self._log('CAPTURE_FAILED',error=str(exc));self.status='Captura de espectador detenida: '+str(exc)
                # Capture errors never interrupt or disconnect the players.
                return

    def _network(self):
        client=None;identity=None;published=None;sent=1;finished=False
        watching=None;view_generation=None;read=1;played=False;view_finished=False;failures=0
        while not self.stop.wait(.08):
            original=self.bridge.client
            if not isinstance(original,ServiceClient):continue
            current=(original.url,original.code,original.token)
            if identity!=current:
                client=ServiceClient(original.url.removesuffix('/v1/rooms'),original.code,original.token);identity=current
            try:
                with self.lock:cap=self.capture.copy() if self.capture else None
                if cap and self.fingerprints and published!=cap['generation']:
                    h=cap['native']
                    meta=dict(version=1,tournament_id=cap['tournament_id'],match=cap['match'],generation=cap['generation'],
                        first_tick=h.first,seed=h.seed,rules=h.rules,options=list(h.options),
                        names=[bytes(h.names[i]).split(b'\0')[0].decode('utf-8','replace') for i in (0,1)],**self._session_fingerprints())
                    client.send('observer_begin',tournament_id=cap['tournament_id'],match=cap['match'],header=meta)
                    (self.root/(cap['generation']+'.json')).write_text(json.dumps(meta,indent=2),encoding='utf-8')
                    published=cap['generation'];sent=h.first;finished=False
                    self._log('PUBLISH_STARTED',match=cap['match'])
                if cap and published==cap['generation'] and not finished:
                    with self.lock:
                        offset=(sent-cap['native'].first)*36;raw=bytes(self.pads[offset:offset+48*36]);closed=cap['closed']
                    if len(raw)==48*36 or raw and closed:
                        client.send('observer_append',tournament_id=cap['tournament_id'],match=cap['match'],generation=published,chunk=encode_chunk(sent,raw));sent+=len(raw)//36
                        self.status=f'Publicando entradas confirmadas para el espectador · enviadas {sent-1}'
                    elif closed and not raw:
                        client.send('observer_end',tournament_id=cap['tournament_id'],match=cap['match'],generation=published,tick=sent);finished=True
                        self._log('PUBLISH_ENDED',next=sent)
                request=self.watch_request
                if request and self.fingerprints:
                    if self.mapping.shared.header.mode in (3,4) and watching!=request['request']:
                        continue # Wait for the previous observer session to restore its own game.
                    if watching!=request['request']:
                        watching=request['request'];view_generation=None;read=1;played=False;view_finished=False
                    mode=self.mapping.shared.header.mode
                    if mode==3:played=True
                    if played and mode==0:
                        self.watch_request=None;self.status='Has vuelto a tu juego; la sala sigue abierta.';self._log('WATCH_RETURNED');continue
                    state=self.bridge.snapshot or {};t=state.get('combat') or state.get('tournament',{})
                    if t.get('id')!=request['tournament_id'] or t.get('role') in (1,2):
                        self.cancel();self.status='Observación cancelada: cambió el combate o ahora te toca jugar.';continue
                    if self.mapping.shared.header.next-self.mapping.shared.header.read>6500:continue
                    response=client.send('observer_pull',tournament_id=request['tournament_id'],match=request['match'],tick=read)['stream']
                    if not response.get('ready'):continue
                    meta=compatible(response['header'],self._session_fingerprints())
                    if view_generation is None:
                        h=Header();h.seed=meta['seed'];h.rules=meta['rules'];h.options[:]=meta['options'];h.first=meta['first_tick']
                        for p in (0,1):h.names[p].value=meta['names'][p].encode()
                        self.mapping.prepare_view(h);view_generation=meta['generation'];read=h.first
                        (self.root/'watch-header.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
                        self._log('WATCH_COMPATIBLE',match=request['match'])
                    if view_generation!=meta['generation']:raise ValueError('Cambió la transmisión; vuelve a pulsar Observar')
                    for chunk in response['chunks']:
                        raw=decode_chunk(chunk)
                        if chunk['start']!=read:raise ValueError('Faltan entradas del espectador')
                        if not self.mapping.feed(read,raw):raise ValueError('El búfer del espectador se llenó')
                        with (self.root/'watch.pads').open('ab') as out:out.write(raw)
                        read+=chunk['count']
                    if response['finished'] and read==response['next']:
                        self.mapping.finish();view_finished=True
                    self.status=f"Espectador experimental · recibidas {read-1} entradas · reproducidas {self.mapping.shared.header.read}"
                    if view_finished:self.status+=' · transmisión terminada'
                failures=0
            except Exception as exc:
                failures+=1;self.status='Espectador: '+str(exc);self._log('TRANSPORT_ERROR',error=str(exc),attempt=failures)
                if self.watch_request and (isinstance(exc,ValueError) or failures>=4):self.cancel()
                if failures>=4 and cap:published=cap['generation'];finished=True
                self.stop.wait(1)

    def close(self):
        if self.closed:return
        self.closed=True;self.cancel();self.stop.set()
        self.collector.join(timeout=2);self.network.join(timeout=8)
        if not self.collector.is_alive() and not self.network.is_alive():self.mapping.close()
