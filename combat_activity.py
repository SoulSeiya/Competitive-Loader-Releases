"""Derive observed action/ability entries from the rollback-corrected trace.

This is evidence of simulated state, not proof of a player's button press,
successful hit, or the cause of a desync. Player aliases are local/display data.
"""
def action_events(frames,limit=24):
    events=[];previous={}
    for frame in frames:
        if frame['phase']!=3:
            previous.clear();continue
        for f in frame['sides']:
            side=f['side'];old=previous.get(side)
            if f['character_id'] is None or f['action_id'] is None:
                previous.pop(side,None);continue
            # 0x133..0x13B are the victim's rush/catch actions; 0x130..132
            # are clash states. Their class must not attribute a cast to the victim.
            ability=f['action_class'] is not None and (0xfd<=f['action_id']<=0x102 or 0x105<=f['action_id']<=0x12f)
            key=(f['character_id'],f['member'],'ability',f['action_class'],f.get('ability_id')) if ability else (f['character_id'],f['member'],'action',f['action_id'])
            counter=f.get('action_frame')
            restarted=bool(old and old[0]==key and old[1]==f['action_id'] and
                           counter is not None and old[2] is not None and counter<old[2])
            previous[side]=(key,f['action_id'],counter)
            # Different native phases of the same skill are one observed use.
            if old and old[0]==key and not restarted:continue
            if f['action_id'] in (0,11) and not ability:continue # null / neutral
            events.append({'blank':frame['blank'],'side':side,'character_id':f['character_id'],
                'character_name':f['name'],'costume':f.get('costume'),'kind':'ability' if ability else 'action',
                'ability_class':f['action_class'] if ability else None,'ability_id':f.get('ability_id') if ability else None,
                'action_id':f['action_id'],'observed_start':old is not None,
                'input_confirmed':frame['input_confirmed'],'stage_id':(frame.get('stage') or {}).get('id')})
    selected=events[-limit:]
    if limit==24:
        # Retain recent abilities even when rapid movement-state changes follow.
        for ability in [e for e in events if e['kind']=='ability'][-8:]:
            if ability in selected:continue
            replace=next((i for i,e in enumerate(selected) if e['kind']=='action'),None)
            if replace is not None:selected[replace]=ability
        selected.sort(key=lambda e:(e['blank'],e['side']))
    return selected

def clean_events(events,frontier):
    if not isinstance(events,list) or len(events)>24:raise ValueError('Demasiados eventos')
    out=[];previous=(-1,0)
    for e in events:
        if not isinstance(e,dict):raise ValueError('Evento inválido')
        result={}
        for k,lo,hi,nullable in [('blank',0,2147483647,False),('side',1,2,False),('character_id',0,160,False),
                ('ability_class',0,4,True),('ability_id',0,32767,True),('action_id',0,315,False),('stage_id',0,4095,True)]:
            v=e.get(k)
            if not (v is None and nullable) and not (type(v) is int and lo<=v<=hi):raise ValueError('Evento inválido')
            result[k]=v
        position=(result['blank'],result['side'])
        if position<=previous:raise ValueError('Eventos desordenados')
        previous=position
        if 'costume' in e:
            costume=e['costume']
            if costume is not None and not (type(costume) is int and 1<=costume<=256):raise ValueError('Traje inválido')
            result['costume']=costume
        name=e.get('character_name')
        if name is not None and (not isinstance(name,str) or len(name)>128 or any(not c.isprintable() for c in name)):raise ValueError('Nombre inválido')
        if e.get('kind') not in ('action','ability') or any(type(e.get(k)) is not bool for k in ('observed_start','input_confirmed')):raise ValueError('Evento inválido')
        if (e['kind']=='ability')!=(result['ability_class'] is not None):raise ValueError('Habilidad inválida')
        result.update(character_name=name,kind=e['kind'],observed_start=e['observed_start'],
                      input_confirmed=e['input_confirmed'] and result['blank']<=frontier)
        out.append(result)
    return out

def describe_event(event,player=None):
    character=event['character_name'] or 'Personaje ID '+str(event['character_id'])
    if event.get('costume') is not None:character+=' (traje '+str(event['costume'])+')'
    actor='%s, P%d'%(player,event['side']) if player else 'P%d'%event['side']
    if event['kind']=='ability':
        slot=event['ability_class']
        label=('Blast 1, ranura '+str(slot+1)) if slot<2 else ('definitiva' if slot==4 else 'Blast 2, ranura '+str(slot-1))
        verb='usa habilidad' if event['observed_start'] else 'tiene una habilidad en curso:'
        return '%s %s %s [ID %s, acción %s] (%s)'%(character,verb,label,event['ability_id'] if event['ability_id'] is not None else 'no capturado',event['action_id'],actor)
    return '%s entra en movimiento/estado de acción %s (%s)'%(character,event['action_id'],actor)
