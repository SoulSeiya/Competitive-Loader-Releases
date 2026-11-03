"""Read-only evidence from the reviewed native trace. No game writes.

The native producer overwrites a frame on rollback. A snapshot is copied only
when a desync is reported. CPU practice additionally journals identity changes
on a Loader background thread; unconfirmed online observations are labelled.
"""
import mmap
import struct
import uuid

MAGIC=0x54435442
CAPACITY=4096
NAMES=64
STAGE_NAMES=NAMES+161*128
PLAYER_NAMES=STAGE_NAMES+35*96
FRAMES=PLAYER_NAMES+2*96
FRAME=struct.Struct('<IIii22i')
SIZE=FRAMES+CAPACITY*FRAME.size

def clean_stage(stage):
    if stage is None:return None
    if not isinstance(stage,dict):raise ValueError('Escenario inválido')
    result={}
    for key in ('id','start_id'):
        value=stage.get(key)
        if value is not None and not (type(value) is int and 0<=value<=4095):raise ValueError('Escenario inválido')
        result[key]=value
    name=stage.get('catalog_name');source=stage.get('catalog_source')
    if name is not None and (not isinstance(name,str) or len(name)>96 or any(not c.isprintable() for c in name)):raise ValueError('Escenario inválido')
    if source not in (None,'engine_catalog') or (name is not None and source!='engine_catalog'):raise ValueError('Catálogo inválido')
    result.update(catalog_name=name,catalog_source=source)
    return result

def clean_combat(value):
    """Strict bounded DTO, also used when reconstructing older local logs."""
    integer=lambda v,lo,hi:type(v) is int and lo<=v<=hi
    if not isinstance(value,dict) or value.get('source')!='native_trace_v1' or value.get('time_basis')!='pre_tick':return None
    for key in ('epoch','confirmed_through'):
        if not integer(value.get(key),0,2147483647):return None
    for key in ('target_blank','nearest_distance'):
        if value.get(key) is not None and not integer(value.get(key),0,2147483647):return None
    observations=value.get('observations')
    if not isinstance(observations,list) or not 1<=len(observations)<=16:return None
    result={k:value.get(k) for k in ('source','time_basis','epoch','confirmed_through','target_blank','nearest_distance')}
    result['observations']=[]
    previous=-1
    for row in observations:
        if not isinstance(row,dict) or not integer(row.get('blank'),0,2147483647) or row['blank']<=previous:return None
        previous=row['blank']
        if row.get('phase') is not None and not integer(row.get('phase'),0,6):return None
        if type(row.get('resimulated')) is not bool or type(row.get('input_confirmed')) is not bool:return None
        sides=row.get('sides')
        if not isinstance(sides,list) or len(sides)!=2:return None
        r={k:row[k] for k in ('blank','phase','resimulated','input_confirmed')};r['sides']=[]
        if 'stage' in row:
            try:r['stage']=clean_stage(row['stage'])
            except ValueError:return None
        # An observation cannot declare itself confirmed beyond the recorded frontier.
        r['input_confirmed']=row['input_confirmed'] and row['blank']<=result['confirmed_through']
        for index,f in enumerate(sides):
            if not isinstance(f,dict) or f.get('side')!=index+1:return None
            out={'side':index+1}
            fields=[('roster_id',0,160),('character_id',0,160),('member',0,4),('team_size',1,5),('variant',0,3),('action_id',0,315),('action_class',0,4)]
            fields += [(key,0,hi) for key,hi in [('ability_id',32767),('action_frame',2147483647)] if key in f]
            for key,lo,hi in fields:
                v=f.get(key)
                if v is not None and not integer(v,lo,hi):return None
                out[key]=v
            if 'costume' in f:
                costume=f['costume']
                if costume is not None and not integer(costume,1,256):return None
                out['costume']=costume
            name=f.get('name')
            if name is not None and (not isinstance(name,str) or len(name)>128 or any(not c.isprintable() for c in name)):return None
            out['name']=name;r['sides'].append(out)
        result['observations'].append(r)
    if 'events' in value:
        from combat_activity import clean_events
        try:result['events']=clean_events(value['events'],result['confirmed_through'])
        except ValueError:return None
    return result

def _name(raw, ident):
    if ident is None:return None
    text=raw[NAMES+ident*128:NAMES+(ident+1)*128].split(b'\0',1)[0].decode('utf-8','replace')
    return ''.join(c for c in text if c.isprintable())[:128] or None

def decode_snapshot(raw,target,identities_only=False,journal=False):
    if len(raw)!=SIZE or struct.unpack_from('<II',raw)!=(MAGIC,4):return None
    if identities_only and struct.unpack_from('<I',raw,24)[0]!=2:return None
    seq,epoch,frontier,latest=struct.unpack_from('<4I',raw,8)
    if seq&1 or not epoch or not latest:return None
    frames=[]
    for offset in range(FRAMES,SIZE,FRAME.size):
        values=FRAME.unpack_from(raw,offset); e,blank,phase,resim=values[:4]
        if e!=epoch or not 0<blank<=latest or latest-blank>=CAPACITY:continue
        if journal and latest-blank>600:continue
        if target is not None and (blank>target or target-blank>600):continue
        sides=[]
        for side in range(2):
            roster,chara,member,count,variant,action,action_class,ability_id,action_frame,costume=values[4+side*10:14+side*10]
            valid=lambda n,hi:n if 0<=n<=hi else None
            chara=valid(chara,160);roster=valid(roster,160)
            sides.append({'side':side+1,'roster_id':roster,'character_id':chara,
                'name':_name(raw,chara),'member':valid(member,4),'team_size':count if 1<=count<=5 else None,
                'variant':valid(variant,3),'action_id':valid(action,315),'action_class':valid(action_class,4),
                'ability_id':valid(ability_id,32767),'action_frame':valid(action_frame,2147483647),'costume':costume if 1<=costume<=256 else None})
        stage,start=values[-2:]
        valid=lambda n:n if 0<=n<=4095 else None
        catalog=None
        if 0<=stage<35:
            catalog=raw[STAGE_NAMES+stage*96:STAGE_NAMES+(stage+1)*96].split(b'\0',1)[0].decode('utf-8','replace')
            catalog=''.join(c for c in catalog if c.isprintable())[:96] or None
        frames.append({'blank':blank,'phase':phase if 0<=phase<=6 else None,
                       'resimulated':bool(resim),'input_confirmed':blank<=frontier,'sides':sides,
                       'stage':{'id':valid(stage),'start_id':valid(start),'catalog_name':catalog,'catalog_source':'engine_catalog' if catalog else None}})
    frames.sort(key=lambda f:f['blank'])
    if not frames:return None
    # Keep transitions and the last state. Cap output independently of fight length.
    changes=[];previous=None
    for frame in frames:
        if target is not None and target-frame['blank']>180:continue
        fighters=tuple(tuple(f[k] for k in ('roster_id','character_id','name','member','team_size','variant','costume')) for f in frame['sides'])
        states=[{k:v for k,v in f.items() if k!='action_frame'} for f in frame['sides']]
        key=(fighters,frame['stage']) if identities_only or journal else (frame['phase'],states,frame['stage'])
        if key!=previous:changes.append(frame);previous=key
    if not changes:return None
    if not identities_only and changes[-1]['blank']!=frames[-1]['blank']:changes.append(frames[-1])
    from combat_activity import action_events
    result={'source':'native_trace_v1','time_basis':'pre_tick','epoch':epoch,
            'confirmed_through':frontier,'target_blank':target,
            'nearest_distance':None if target is None else target-frames[-1]['blank'],
            'observations':changes[-8:],'events':action_events(frames,512 if journal else 24)}
    if journal:
        result['_mode']=struct.unpack_from('<I',raw,24)[0]
        result['_latest']=latest
        result['_players']=[raw[PLAYER_NAMES+i*96:PLAYER_NAMES+(i+1)*96].split(b'\0',1)[0].decode('utf-8','replace') for i in range(2)]
    return result

class CombatTrace:
    def __init__(self):
        self.name='Local\\BTC-Trace-'+uuid.uuid4().hex
        self.mapping=mmap.mmap(-1,SIZE,tagname=self.name)
        struct.pack_into('<II',self.mapping,0,MAGIC,4)

    def snapshot(self,target=None,identities_only=False,journal=False):
        # Bounded retries: never waits for the game thread or holds its locks.
        for _ in range(3):
            before=struct.unpack_from('<I',self.mapping,8)[0]
            if before&1:continue
            raw=self.mapping[:]
            after=struct.unpack_from('<I',self.mapping,8)[0]
            if before==after:return decode_snapshot(raw,target,identities_only,journal)
        return None

    def close(self):self.mapping.close()

class PracticeCharacterJournal:
    """Local combat activity; CPU identity journal retained for compatibility."""
    def __init__(self,trace,folder,cpu=True):
        import threading
        from pathlib import Path
        self.trace=trace;self.path=Path(folder)/'personajes-ft-cpu.jsonl'
        self.text_path=Path(folder)/'personajes-ft-cpu.txt'
        self.stop=threading.Event();self.thread=None;self.cursor=(-1,-1);self.identity=None;self.cpu=cpu
        self.action_cursor=(-1,-1,0)
        self.last_sample=None
        self.actions_path=Path(folder)/'acciones-combate.jsonl'
        self.actions_text=Path(folder)/'acciones-combate.txt'
        self.actions_text.write_text('Eventos observados del combate · no prueban impacto ni causa de desync\n',encoding='utf-8')
        if cpu:self.text_path.write_text('FT contra CPU · detecciones leídas del juego\nEsperando el inicio del combate.\n',encoding='utf-8')

    def _append(self,path,line):
        # Fixed disk bound per file; only these generated journal files rotate.
        if path.exists() and path.stat().st_size>=2*1024*1024:
            path.replace(path.with_name(path.name+'.previous'))
        with path.open('a',encoding='utf-8') as file:file.write(line+'\n')

    def sample(self):
        import json
        snapshot=self.trace.snapshot(journal=True)
        if not snapshot:return
        epoch=snapshot['epoch']
        latest=snapshot.get('_latest')
        if self.last_sample and latest is not None and self.last_sample[0]==epoch and latest-self.last_sample[1]>600:
            self._append(self.actions_text,'AVISO: hubo un intervalo sin lectura; el historial local puede estar incompleto.')
        if latest is not None:self.last_sample=(epoch,latest)
        from combat_activity import describe_event
        players=snapshot.get('_players',['P1','CPU' if self.cpu else 'P2'])
        event_json=[];event_text=[];cpu_text=[]
        for event in snapshot.get('events',[]):
            cursor=(epoch,event['blank'],event['side'])
            if cursor<=self.action_cursor:continue
            self.action_cursor=cursor
            player=''.join(c for c in players[event['side']-1] if c.isprintable())[:96]
            event_json.append(json.dumps({'epoch':epoch,**event,'player':player},ensure_ascii=False))
            event_text.append('Frame %s · %s · %s'%(event['blank'],describe_event(event,player),
                'entradas confirmadas' if event['input_confirmed'] else 'observación predictiva'))
            if snapshot.get('_mode',2 if self.cpu else 1)==2 and event['kind']=='ability':
                cpu_text.append((event['blank'],'Frame %s · %s'%(event['blank'],describe_event(event,player))))
        if event_json:self._append(self.actions_path,'\n'.join(event_json))
        if event_text:self._append(self.actions_text,'\n'.join(event_text))
        if snapshot.get('_mode',2 if self.cpu else 1)!=2:return
        for row in snapshot['observations']:
            cursor=(epoch,row['blank'])
            if cursor<=self.cursor:continue
            self.cursor=cursor
            sides=[{k:f[k] for k in ('side','roster_id','character_id','name','member','team_size','variant','costume')} for f in row['sides']]
            identity=(sides,row['stage'])
            if identity==self.identity:continue
            self.identity=identity
            record={'mode':'cpu_ft','epoch':epoch,'blank':row['blank'],'sides':sides,'stage':row['stage']}
            self._append(self.path,json.dumps(record,ensure_ascii=False))
            label=' | '.join('P%d: %s [ID %s, traje %s, base %s, miembro %s]'%(f['side'],f['name'] or 'Nombre no capturado',f['character_id'],f['costume'],f['roster_id'],f['member']) for f in sides)
            stage=row['stage'];stage_label='Mapa ID %s (inicial %s)'%(stage['id'],stage['start_id'])
            if stage['catalog_name']:stage_label+=' · catálogo del motor: '+stage['catalog_name']
            cpu_text.append((row['blank'],'Frame %d · %s | %s'%(row['blank'],stage_label,label)))
        if cpu_text:self._append(self.text_path,'\n'.join(text for _,text in sorted(cpu_text,key=lambda x:x[0])))

    def start(self):
        import threading
        def work():
            while not self.stop.wait(.5):
                try:self.sample()
                except (OSError,ValueError):pass # Telemetry must not interrupt a fight.
        self.thread=threading.Thread(target=work,name='BTC CPU character journal',daemon=True);self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread:self.thread.join(timeout=2)
        self.sample()
