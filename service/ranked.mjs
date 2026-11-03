// Provisional, device-identity beta. One CAS ledger keeps queue/rating settlement atomic.
import {checkpointScore,desyncProof,pairedDesync,openRecovery,recoveryView,waitingProofs} from './ranked_recovery.mjs';
export class RankedError extends Error {}
const fail=m=>{throw new RankedError(m);};
const random=n=>[...crypto.getRandomValues(new Uint8Array(n))].map(v=>v.toString(16).padStart(2,'0')).join('');
const sha=async s=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s)))].map(v=>v.toString(16).padStart(2,'0')).join('');
const season='btc-beta-publica-1';
export const rankedRules={ft:2,seconds:360,characters:2};
const fresh=(m,id,now)=>m.seen[id]!==undefined&&now-m.seen[id]<20000;
const tier=r=>r<1100?'Bronce':r<1250?'Plata':r<1450?'Oro':'Diamante';
const reply=v=>Response.json({protocol:1,...v},{headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
const ready=new WeakSet();
async function schema(db){if(ready.has(db))return;await db.batch([
  db.prepare('CREATE TABLE IF NOT EXISTS btc_ranked_beta(id TEXT PRIMARY KEY,state TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 0)'),
  db.prepare('INSERT OR IGNORE INTO btc_ranked_beta(id,state,revision) VALUES(?,?,0)').bind(season,JSON.stringify({players:{},queue:{},matches:{},mutation:''}))]);ready.add(db);}
async function auth(db,d){
  if(!/^[a-f0-9]{32}$/.test(d.id||'')||!/^[a-f0-9]{64}$/.test(d.token||''))fail('Identidad BTC no válida');
  const me=await db.prepare('SELECT id,name FROM btc_social_users WHERE id=? AND secret_hash=?').bind(d.id,await sha(d.token)).first();
  if(!me)fail('Conecta primero tu perfil BTC en Amigos');return me;
}
function player(s,me){
  if(!s.players[me.id]){if(Object.keys(s.players).length>=128)fail('La beta ha alcanzado su cupo de perfiles');s.players[me.id]={name:me.name,rating:1000,played:0,wins:0,losses:0,abandons:0,blocked_until:0};}
  s.players[me.id].name=me.name;return s.players[me.id];
}
function active(s,id){return Object.values(s.matches).find(m=>m.players.includes(id)&&!m.finished);}
export function settleRanked(s,m,winner,reason,now){
  if(m.finished)return;
  m.finished=now;m.winner=winner;m.reason=reason;
  if(!winner){m.delta={};return;}
  const loser=m.players.find(id=>id!==winner),a=s.players[winner],b=s.players[loser];
  const delta=Math.min(b.rating,Math.max(1,Math.round(24*(1-1/(1+10**((b.rating-a.rating)/400))))));
  const recovered=reason==='resultado'&&m.recovery_enabled&&(m.attempt||0)>0;
  a.rating+=delta;b.rating=recovered?b.rating+6:Math.max(0,b.rating-delta);a.played++;b.played++;a.wins++;b.losses++;
  m.delta={[winner]:delta,[loser]:recovered?6:-delta};
  if(recovered){
    a.fairplay_points=(a.fairplay_points||0)+10;
    m.fairplay_delta={[winner]:10,[loser]:0};
  }
  if(reason!=='resultado'){b.abandons++;b.blocked_until=now+Math.min(30,2*b.abandons)*60000;}
}
function finishRoom(r,m){
  const t=r.duel?.battle;if(!t||!m.finished||t.status==='finished')return;
  const winner=m.winner?m.players.indexOf(m.winner)+1:0;
  t.status='finished';t.current=0;t.champion=winner;t.revision++;
  const match=t.matches[0];Object.assign(match,{winner,score:winner===1?[2,0]:winner===2?[0,2]:null,state:'done',code:''});
  r.messages.push({id:++r.next_message,author:'Ranked BTC',text:m.winner?'GG · Set terminado: '+sName(m,m.winner)+' · '+m.reason:'Set anulado · sin puntos: '+m.reason});r.messages=r.messages.slice(-64);
}
const sName=(m,id)=>m.names[m.players.indexOf(id)];
function sweep(s,m,now){
  if(m.finished)return;
  if(m.phase==='recovering'){
    if(now>=m.recovery.expires)settleRanked(s,m,null,'revancha por desync caducada',now);
    return;
  }
  if(m.players.every(id=>m.faults?.[id])){
    if(waitingProofs(m,now))return;
    if(!openRecovery(m,now))settleRanked(s,m,null,'incompatibilidad o desincronización',now);
    return;
  }
  // A failed client may close immediately after the native desync. Give its
  // peer the existing 45 s connection margin to confirm the same fault before
  // turning that close into a loss. A single unconfirmed claim never voids a set.
  for(const [id,at] of Object.entries(m.fault_closes||{})){
    const peer=m.players.find(p=>p!==id);
    if(now-at>=45000&&fresh(m,peer,now)&&!m.faults?.[peer]){settleRanked(s,m,peer,'cierre del juego',now);return;}
  }
  // Never award a timeout when the reporting side is also stale, or before both connected.
  if(m.phase==='playing'){
    const stale=m.players.filter(id=>now-m.seen[id]>=45000),live=m.players.filter(id=>fresh(m,id,now));
    if(stale.length===1&&live.length===1)settleRanked(s,m,live[0],'desconexion',now);
    else if(stale.length===2)settleRanked(s,m,null,'ambos jugadores sin conexión',now);
  }else if(now-(m.attempt_started||m.created)>=180000)settleRanked(s,m,null,'no se pudo iniciar la conexión',now);
}
function view(s,me,now,h,r=null){
  const p=s.players[me.id],m=active(s,me.id)||Object.values(s.matches).filter(m=>m.players.includes(me.id)).at(-1);
  const current=m?{id:m.id,room_code:m.code,names:m.names,phase:m.phase,finished:m.finished||null,winner:m.winner||null,reason:m.reason||'',delta:m.delta?.[me.id]||0,created:m.created,
    attempt:m.attempt||0,checkpoint:m.checkpoint||[0,0],resume_score:m.resume_score||[0,0],recovery:recoveryView(m,me.id),fairplay_delta:m.fairplay_delta?.[me.id]||0,
    confirming_fault:!!(m.recovery_enabled&&!m.finished&&m.phase!=='recovering'&&Object.keys(m.faults||{}).length)}:null;
  return {season,provisional:true,rules:rankedRules,features:{desync_resume:1,recovery_loser_rating:6,recovery_winner_fairplay:10},me:{id:me.id,...p,fairplay_points:p.fairplay_points||0,tier:tier(p.rating)},queued:!!s.queue[me.id],match:current,
    leaderboard:Object.entries(s.players).sort((a,b)=>b[1].rating-a[1].rating).slice(0,10).map(([id,p])=>({id,name:p.name,rating:p.rating,played:p.played,tier:tier(p.rating)})),
    history:Object.values(s.matches).filter(m=>m.finished&&m.players.includes(me.id)).slice(-20).reverse().map(m=>({id:m.id,names:m.names,winner:m.winner,reason:m.reason,delta:m.delta?.[me.id]||0,fairplay_delta:m.fairplay_delta?.[me.id]||0,finished:m.finished})),
    ...(m&&!m.finished&&m.phase!=='recovering'&&r?{launch:{...h.snapshot(r,m.tokens[me.id],m.code),_ranked_attempt:m.attempt||0,_ranked_resume_score:m.resume_score||[0,0]}}:{})};
}
async function ledger(db){await schema(db);const row=await db.prepare('SELECT state,revision FROM btc_ranked_beta WHERE id=?').bind(season).first();return {...row,s:JSON.parse(row.state)};}
function writeLedger(db,row,s,nonce,condition='',args=[]){s.mutation=nonce;return db.prepare('UPDATE btc_ranked_beta SET state=?,revision=revision+1 WHERE id=? AND revision=?'+condition).bind(JSON.stringify(s),season,row.revision,...args);}
function roomWrite(db,r,code,nonce,revision=null){
  const exists='EXISTS(SELECT 1 FROM btc_ranked_beta WHERE id=? AND json_extract(state,\'$.mutation\')=?)';
  if(revision===null)return db.prepare(`INSERT INTO btc_lobbies(code,state,revision,expires) SELECT ?,?,0,? WHERE ${exists}`).bind(code,JSON.stringify(r),Date.now()+(r.duel?.battle?.status==='finished'?600000:3600000),season,nonce);
  return db.prepare(`UPDATE btc_lobbies SET state=?,revision=revision+1,expires=? WHERE code=? AND revision=? AND ${exists}`).bind(JSON.stringify(r),Date.now()+(r.duel?.battle?.status==='finished'?600000:3600000),code,revision,season,nonce);
}
export async function rankedHandle(request,db,h){
  const raw=await request.text();if(raw.length>4096)fail('Petición demasiado grande');let d;try{d=JSON.parse(raw);}catch{fail('JSON inválido');}
  if(!d||!['poll','queue','cancel_queue','heartbeat','forfeit','recovery_vote'].includes(d.op))fail('Acción ranked inválida');
  const me=await auth(db,d);const now=Date.now();
  for(let attempt=0;attempt<10;attempt++){
    const row=await ledger(db),s=row.s,p=player(s,me),nonce=random(12);let m=active(s,me.id),r=null,roomRow=null,newRoom=false,oldRoom=null;
    for(const [id,q] of Object.entries(s.queue))if(now-q.seen>30000)delete s.queue[id];
    if(m){roomRow=await db.prepare('SELECT state,revision FROM btc_lobbies WHERE code=?').bind(m.code).first();r=roomRow?JSON.parse(roomRow.state):null;sweep(s,m,now);}
    if(d.op==='queue'||(d.op==='poll'&&s.queue[me.id])){
      if(m&&!m.finished)fail('Ya tienes un set en curso');
      if(now<p.blocked_until)fail('Espera '+Math.ceil((p.blocked_until-now)/1000)+' segundos por el abandono anterior');
      const compatible=d.op==='queue'?d.compat:s.queue[me.id].compat;
      if(typeof compatible!=='string'||!/^[a-f0-9]{64}$/.test(compatible))fail('Instalación BTC no verificada');
      s.queue[me.id]={seen:now,since:s.queue[me.id]?.since||now,compat:compatible,recovery:d.op==='queue'?d.recovery===1:!!s.queue[me.id].recovery};
      const window=Math.min(1000,150+100*Math.floor((now-s.queue[me.id].since)/15000));
      const peer=Object.keys(s.queue).sort((a,b)=>s.queue[a].since-s.queue[b].since).find(id=>id!==me.id&&s.queue[id].compat===compatible&&!active(s,id)&&now>=s.players[id].blocked_until&&Math.abs(s.players[id].rating-p.rating)<=window);
      if(peer){
        const alphabet='ABCDEFGHJKLMNPQRSTUVWXYZ23456789',code=[...crypto.getRandomValues(new Uint8Array(6))].map(v=>alphabet[v&31]).join('');
        r=h.createRoom({protocol:1,edition:'BTC',name:s.players[peer].name,title:'Ranked BTC · beta',capacity:2,kind:'legacy'},now);
        const a=r.host_token;const guest=h.apply(r,{op:'join',protocol:1,edition:'BTC',name:s.players[me.id].name===s.players[peer].name?s.players[me.id].name.slice(0,10)+'#2':s.players[me.id].name},now,code,true,true),b=guest.token;
        h.duelOp(r,r.users[a],{op:'duel_offer',target:r.users[b].id,...rankedRules},now);h.duelOp(r,r.users[b],{op:'duel_accept',duel_id:r.duel.id},now);
        m={id:random(16),code,players:[peer,me.id],names:[s.players[peer].name,s.players[me.id].name],tokens:{[peer]:a,[me.id]:b},seen:{[peer]:now,[me.id]:now},connected:{},created:now,phase:'connecting',finished:null,
           recovery_enabled:!!(s.queue[peer].recovery&&s.queue[me.id].recovery),compat:compatible,attempt:0,checkpoint:[0,0],score_reports:{}};
        r.ranked_id=m.id;s.matches[m.id]=m;delete s.queue[peer];delete s.queue[me.id];newRoom=true;
      }
    }else if(d.op==='cancel_queue')delete s.queue[me.id];
    else if(s.queue[me.id])s.queue[me.id].seen=now;
    if(m&&!m.finished){
      const correctAttempt=!m.recovery_enabled||d.attempt===(m.attempt||0);
      if(d.op==='recovery_vote'){
        if(d.match!==m.id||!correctAttempt||m.phase!=='recovering')fail('La solicitud de revancha ya cambió');
        if(typeof d.accept!=='boolean')fail('Respuesta de revancha inválida');
        m.seen[me.id]=now;
        if(!d.accept)settleRanked(s,m,null,'revancha por desync rechazada',now);
        else{
          if(d.compat!==m.compat)fail('La instalación cambió; vuelve a verificarla antes de continuar');
          m.recovery.votes[me.id]=true;
          if(m.players.every(id=>m.recovery.votes[id])){
            oldRoom={r,code:m.code,revision:roomRow.revision};
            const oldBattle=oldRoom.r.duel.battle;oldBattle.status='finished';oldBattle.current=0;oldBattle.champion=0;oldBattle.revision++;
            Object.assign(oldBattle.matches[0],{winner:0,score:null,state:'done',code:''});
            const alphabet='ABCDEFGHJKLMNPQRSTUVWXYZ23456789',code=[...crypto.getRandomValues(new Uint8Array(6))].map(v=>alphabet[v&31]).join('');
            r=h.createRoom({protocol:1,edition:'BTC',name:m.names[0],title:'Ranked BTC · reanudación',capacity:2,kind:'legacy'},now);
            const a=r.host_token,guest=h.apply(r,{op:'join',protocol:1,edition:'BTC',name:m.names[1]===m.names[0]?m.names[1].slice(0,10)+'#2':m.names[1]},now,code,true,true),b=guest.token;
            h.duelOp(r,r.users[a],{op:'duel_offer',target:r.users[b].id,...rankedRules},now);h.duelOp(r,r.users[b],{op:'duel_accept',duel_id:r.duel.id},now);
            m.resume_score=m.recovery.score.slice();m.checkpoint=m.resume_score.slice();m.code=code;m.tokens={[m.players[0]]:a,[m.players[1]]:b};
            m.attempt=(m.attempt||0)+1;m.attempt_started=now;m.phase='connecting';m.connected={};m.seen={[m.players[0]]:now,[m.players[1]]:now};
            m.faults={};m.fault_closes={};m.desync_proofs={};m.score_reports={};delete m.recovery;delete m.proof_deadline;r.ranked_id=m.id;newRoom=true;
          }
        }
      }else if(d.op==='heartbeat'&&correctAttempt){
        if(d.match!==m.id)fail('El set ya no está activo');m.seen[me.id]=now;
        if(m.phase!=='recovering'){
        if(d.connected===true)m.connected[me.id]=true;
        if(m.players.every(id=>m.connected[id]))m.phase='playing';
        checkpointScore(m,me.id,d.score);
        if(d.failed===true){m.faults??={};m.faults[me.id]=true;const proof=desyncProof(d.desync_proof);if(proof){m.desync_proofs??={};m.desync_proofs[me.id]=proof;}}
        if(d.completed===true&&Array.isArray(d.score)&&!m.finished&&!(m.recovery_enabled&&Object.keys(m.faults||{}).length)){
          h.apply(r,{op:'tournament_report',token:m.tokens[me.id],tournament_id:r.duel.battle.id,match:1,score:d.score},now,m.code);
          const t=r.duel.battle;if(t.status==='finished')settleRanked(s,m,m.players[t.matches[0].winner-1]||null,'resultado',now);
          else if(Object.keys(t.matches[0].reports).length===2)settleRanked(s,m,null,'resultados distintos',now);
        }
        if(d.failed===true&&m.phase!=='playing'&&!(m.recovery_enabled&&desyncProof(d.desync_proof)))settleRanked(s,m,null,'incompatibilidad o desincronización',now);
        if(!m.finished&&d.closed===true&&!(d.completed===true&&Array.isArray(d.score)&&d.score.length===2)&&m.phase==='playing'){
          if(m.faults?.[me.id]){m.fault_closes??={};m.fault_closes[me.id]??=now;}
          else settleRanked(s,m,m.players.find(id=>id!==me.id),'cierre del juego',now);
        }
        }
      }else if(d.op==='forfeit'){
        if(d.match!==m.id||!correctAttempt)fail('El set ya no está activo');settleRanked(s,m,m.phase==='recovering'?null:m.players.find(id=>id!==me.id),m.phase==='recovering'?'revancha por desync rechazada':'abandono voluntario',now);
      }
      sweep(s,m,now);
    }
    if(r&&m)finishRoom(r,m);
    // Keep the beta row bounded. Finished records have already settled exactly once.
    const done=Object.values(s.matches).filter(m=>m.finished);for(const old of done.slice(0,Math.max(0,done.length-120)))delete s.matches[old.id];
    const condition=(newRoom?' AND NOT EXISTS(SELECT 1 FROM btc_lobbies WHERE code=?)':'')+(roomRow?' AND EXISTS(SELECT 1 FROM btc_lobbies WHERE code=? AND revision=?)':'');
    const params=[...(newRoom?[m.code]:[]),...(roomRow?[oldRoom?.code||m.code,roomRow.revision]:[])];
    if(!newRoom&&JSON.stringify(s)===row.state&&(!r||JSON.stringify(r)===roomRow.state))return reply(view(s,me,now,h,r));
    const writes=[writeLedger(db,row,s,nonce,condition,params)];if(r&&m&&(newRoom||JSON.stringify(r)!==roomRow.state))writes.push(roomWrite(db,r,m.code,nonce,newRoom?null:roomRow.revision));
    if(oldRoom)writes.push(roomWrite(db,oldRoom.r,oldRoom.code,nonce,oldRoom.revision));
    const result=await db.batch(writes);if(result[0].meta.changes)return reply(view(s,me,now,h,r));
  }
  fail('La cola está ocupada. Vuelve a intentarlo.');
}
// Ranked room traffic never reaches unrestricted host operations in the casual handler.
export async function rankedRoom(db,d,h,now){
  const code=h.roomCode(d.room_code??d.code);
  for(let attempt=0;attempt<10;attempt++){
    const roomRow=await db.prepare('SELECT state,revision FROM btc_lobbies WHERE code=?').bind(code).first();
    if(!roomRow)return null;const r=JSON.parse(roomRow.state);if(!r.ranked_id)return null;
    const row=await ledger(db),s=row.s,m=s.matches[r.ranked_id];if(!m)fail('El set ranked ha caducado');
    if(code!==m.code){if(!r.users[d.token])fail('No perteneces a ese intento');if(!['poll','chat','leave'].includes(d.op))fail('Ese intento ya terminó');return reply(h.snapshot(r,d.token,code));}
    const id=m.players.find(id=>m.tokens[id]===d.token);if(!id)fail('No perteneces a este set');
    if(!['poll','chat','tournament_code','tournament_report','leave'].includes(d.op))fail('Esta operación no está disponible en rankeds');
    sweep(s,m,now);
    let result;
    if(d.op==='leave'){
      if(!m.finished&&m.phase!=='recovering')settleRanked(s,m,m.players.find(p=>p!==id),'abandono voluntario',now);
      finishRoom(r,m);result=h.snapshot(r,d.token,code);
    }else{
      if(m.phase==='recovering'&&d.op!=='poll'&&d.op!=='chat')fail('Responde a la revancha por desync en el Loader');
      if(m.finished&&d.op!=='poll'&&d.op!=='chat')fail('El set ya terminó');
      result=h.apply(r,d,now,code);
      const t=r.duel?.battle;
      if(t?.status==='finished'&&!m.finished){const index=t.matches[0].winner-1;settleRanked(s,m,m.players[index]||null,'resultado',now);}
      else if(t&&Object.keys(t.matches[0].reports).length===2&&!m.finished)settleRanked(s,m,null,'resultados distintos',now);
    }
    finishRoom(r,m);result=h.snapshot(r,d.token,code);
    if(JSON.stringify(s)===row.state&&JSON.stringify(r)===roomRow.state)return reply(result);
    const nonce=random(12),writes=[writeLedger(db,row,s,nonce,' AND EXISTS(SELECT 1 FROM btc_lobbies WHERE code=? AND revision=?)',[code,roomRow.revision]),roomWrite(db,r,code,nonce,roomRow.revision)];
    const written=await db.batch(writes);if(written[0].meta.changes)return reply(result);
  }
  fail('El set está ocupado. Repite la operación.');
}
