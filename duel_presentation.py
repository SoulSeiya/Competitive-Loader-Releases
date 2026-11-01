"""Presentation of native confirmed wins. Never awards results or changes game state."""
def valid_score(score,ft):
    return type(ft)is int and 1<=ft<=5 and isinstance(score,list) and len(score)==2 and all(type(n)is int and 0<=n<=ft for n in score)


def present_duel(room=None,last=None,live=None,profile=None,peer_name=None,running=False,busy=False,pending_rules=None):
    room=room or {};profile=profile or {};live=live or {};pending_rules=pending_rules or {}
    # A new pending challenge must not show the previous duel's GG screen.
    source=room if room else (last or {})
    combat=source.get('combat') or {};duel=source.get('duel') or {}
    matches=combat.get('matches') or []
    match=next((m for m in matches if m.get('id')==combat.get('current')),matches[0] if matches else {})
    ft=combat.get('ft',duel.get('ft',pending_rules.get('ft')));seconds=combat.get('seconds',duel.get('seconds',pending_rules.get('seconds')));characters=combat.get('characters',duel.get('characters',pending_rules.get('characters')))
    score=[0,0];score_source='none';done=combat.get('status')=='finished'
    if combat and valid_score(match.get('score'),ft):score=list(match['score']);score_source='server'
    elif combat and live.get('combat_id')==combat.get('id') and valid_score(live.get('score'),ft) and not done:
        score=list(live['score']);score_source='native_confirmed'
    names=[match.get('name1') or duel.get('name1') or profile.get('name') or 'Jugador 1',match.get('name2') or duel.get('name2') or peer_name or 'Esperando rival']
    ids=[match.get('p1',duel.get('from')),match.get('p2',duel.get('to'))]
    phase='idle'
    if done:phase='finished'
    elif combat:
        if live.get('combat_id')==combat.get('id') and live.get('completed'):phase='confirming'
        elif live.get('combat_id')==combat.get('id') and live.get('online'):phase='active'
        elif running:phase='connecting'
        else:phase='launching'
    elif duel or peer_name:phase='pending'
    winner=combat.get('champion_name') if done else None
    if done and not winner and match.get('winner') is not None and match.get('winner') in ids:
        winner=names[ids.index(match['winner'])]
    labels={'idle':'Crea un desafío para empezar.','pending':'Esperando la aceptación del rival.','launching':'Abriendo el juego para los dos jugadores.','connecting':'Preparando la conexión del duelo.','active':'Juego conectado · victorias confirmadas.','confirming':'Confirmando el resultado con el rival…','finished':'Resultado confirmado · GG'}
    return {'id':combat.get('id'),'phase':phase,'ft':ft,'seconds':seconds,'characters':characters,'score':score,'score_source':score_source,
            'players':[{'id':ids[i],'name':names[i],'wins':score[i],'remaining':max(0,ft-score[i]) if ft else None,
                        'is_self':ids[i] is not None and ids[i]==source.get('self_id'),'winner':bool(done and ids[i] is not None and ids[i]==match.get('winner'))} for i in range(2)],
            'winner_name':winner,'status':labels[phase],'temporary':bool(source.get('temporary',False)),
            'can_accept':bool(duel.get('status')=='pending' and duel.get('to')==source.get('self_id')),
            'can_rematch':bool(done and (last or {}).get('can_rematch',True)),
            'room_code':source.get('room_code')}
