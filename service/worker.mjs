import {diagnosticsHandle,purgeDiagnostics} from './diagnostics.mjs';
import {rankedHandle,rankedRoom,RankedError} from './ranked.mjs';
import {socialHandle,SocialError} from './social.mjs';
import {challongeHandle,ChallongeServiceError} from './challonge.mjs';
// Private BTC lobby protocol v1. No game data, replay, credentials or chat logging.
// D1 stores membership and brackets; revision CAS serializes concurrent clients.
const ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
export class RoomError extends Error {}
const fail = message => { throw new RoomError(message); };
const integer = (v, lo, hi) => Number.isInteger(v) && v >= lo && v <= hi;
const clean = (v, n) => typeof v === 'string' ? [...v].filter(c => c >= ' ' && c !== '\x7f').join('').trim().slice(0,n) : fail('Texto inválido');
const random = n => [...crypto.getRandomValues(new Uint8Array(n))].map(x => x.toString(16).padStart(2,'0')).join('');
const code6 = () => [...crypto.getRandomValues(new Uint8Array(6))].map(x => ALPHABET[x & 31]).join('');
export function roomCode(v) {
  if (typeof v !== 'string') fail('Código de sala inválido');
  v = v.trim().toUpperCase().replace(/^BTC-/, '');
  if (v.length !== 6 || [...v].some(c => !ALPHABET.includes(c))) fail('Usa el código BTC de seis letras/números');
  return v;
}
function announce(r, message, author='Sala') {
  r.messages.push({id:++r.next_message, author, text:message});
  r.messages = r.messages.slice(-64);
}
function tournament() {
  return {id:random(12), title:'Torneo BTC', ft:2, characters:1, seconds:180, status:'registration', entrants:{}, matches:[],
    disqualified:[], current:0, champion:0, revision:0, mode:'elimination'};
}
function add(r, name, now) {
  name = clean(name,24);
  if (!name) fail('Escribe tu nombre');
  if (Object.values(r.users).some(u => u.name.toLowerCase() === name.toLowerCase())) fail('Ese nombre ya está en la sala');
  const token = random(32);
  r.users[token] = {id:++r.next_id, name, ready:false, bot:false, game_bot:false, seen:now};
  return token;
}
export function createRoom(d, now) {
  if (d.protocol !== 1 || d.edition !== 'BTC') fail('Versión del servicio BTC incompatible');
  if (!integer(d.capacity ?? 8,2,32)) fail('La capacidad debe estar entre 2 y 32');
  if(!['legacy','casual','tournament'].includes(d.kind??'legacy'))fail('Tipo de sala inválido');
  const r = {title:clean(d.title,64)||'Sala BTC',capacity:d.capacity??8,users:{},messages:[],next_id:0,next_message:0,
    kind:d.kind??'legacy',closed:false,last_chat:{},tournament:tournament()};
  r.host_token = add(r,d.name,now); r.host_id = r.users[r.host_token].id;
  announce(r,'Sala creada');
  return r;
}
const nameOf = (t,id) => id ? t.entrants[id].name : 'Pase libre';
function finish(r,m,winner,score=null,reason='resultado') {
  Object.assign(m,{winner,score,state:'done',code:''}); r.tournament.revision++;
  if (winner) announce(r,`Cruce #${m.id}: avanza ${nameOf(r.tournament,winner)} (${score?score.join('–'):reason}).`);
}
function podium(t) {
  if (t.status !== 'finished' || !t.champion) return [];
  const f=t.matches.at(-1), second=[f.p1,f.p2].find(p=>p&&p!==t.champion);
  const ids=[t.champion,...(second?[second]:[])];
  if (Object.keys(t.entrants).length===3) ids.push(...Object.keys(t.entrants).map(Number).filter(p=>!ids.includes(p)));
  return ids;
}
function advance(r) {
  const t=r.tournament, before=t.current; t.current=0;
  for (const m of t.matches) {
    if (m.winner !== null) continue;
    if (m.sources.length) {
      const [a,b]=m.sources.map(i=>t.matches[i-1].winner);
      if (a===null||b===null) continue;
      m.p1=a; m.p2=b;
    }
    if (m.p1===null||m.p2===null) continue;
    const available=[m.p1,m.p2].filter(p=>p&&!t.disqualified.includes(p));
    if (available.length<2) finish(r,m,available[0]||0,null,!m.p1||!m.p2?'pase libre':'WO');
    else if (!t.current) {t.current=m.id;m.state='active';}
    else m.state='pending';
  }
  if (t.matches.length && t.matches.every(m=>m.winner!==null)) {
    t.status='finished';t.champion=t.matches.at(-1).winner;t.current=0;
    announce(r,'Torneo terminado. '+(t.champion?'Campeón: '+nameOf(t,t.champion):'Sin campeón.'));
    podium(t).forEach((p,i)=>announce(r,`Podio ${i+1}: ${nameOf(t,p)}`));
  } else if (t.current && t.current!==before) {
    const m=t.matches[t.current-1];
    announce(r,`Próxima pelea #${m.id}: ${nameOf(t,m.p1)} vs ${nameOf(t,m.p2)} — FT${t.ft}.`);
  }
}
function withdraw(r,uid) {
  const t=r.tournament;
  if (t.entrants[uid]) {const n=t.entrants[uid].name;delete t.entrants[uid];t.revision++;announce(r,n+' retiró su inscripción');}
}
function disqualify(r,uid) {
  const t=r.tournament;
  if (!t.entrants[uid]) return;
  if (t.status==='registration') withdraw(r,uid);
  else if (t.status==='running') {if (!t.disqualified.includes(uid)) t.disqualified.push(uid);t.revision++;advance(r);}
}
function remove(r,token,reason) {
  const u=r.users[token];delete r.users[token];delete r.last_chat[token];
  announce(r,u.name+' '+reason);disqualify(r,u.id);
  if(r.duel && [r.duel.from,r.duel.to].includes(u.id)) {r.duel=null;announce(r,'Duelo cancelado: un jugador salió de la sala.');}
  if (u.id===r.host_id) r.closed=true;
}
function start(r) {
  const t=r.tournament, players=Object.keys(t.entrants).map(Number);
  if (t.status!=='registration') fail('El torneo ya empezó');
  if (players.length<2||players.length>32) fail('Se necesitan entre 2 y 32 inscritos');
  // Rejection sampling avoids modulo bias in the bracket shuffle.
  for (let i=players.length-1;i>0;i--) {
    const bound=Math.floor(0x100000000/(i+1))*(i+1);let n;
    do {n=crypto.getRandomValues(new Uint32Array(1))[0];} while(n>=bound);
    const j=n%(i+1);[players[i],players[j]]=[players[j],players[i]];
  }
  let size=2;while(size<players.length)size*=2;
  let seeds=[1,2];while(seeds.length<size) {const total=seeds.length*2+1;seeds=seeds.flatMap(s=>[s,total-s]);}
  const slots=seeds.map(s=>players[s-1]||0);let previous=[],round=1;
  while(size>1) {
    const row=[];
    for(let i=0;i<size/2;i++) {
      const id=t.matches.length+1;
      t.matches.push({id,round,sources:round===1?[]:[previous[2*i],previous[2*i+1]],
        p1:round===1?slots[2*i]:null,p2:round===1?slots[2*i+1]:null,winner:null,score:null,reports:{},code:'',state:'pending'});
      row.push(id);
    }
    previous=row;size/=2;round++;
  }
  t.status='running';t.revision++;
  announce(r,`Inicia ${t.title}: ${players.length} inscritos, FT${t.ft}.`);advance(r);
}
function tournamentOp(r,u,d) {
  const t=r.tournament, op=d.op;
  if (['tournament_config','tournament_start','tournament_reset','tournament_wo'].includes(op)&&u.id!==r.host_id) fail('Solo el anfitrión puede organizar el torneo');
  if (op==='tournament_config') {
    if(t.status!=='registration')fail('El torneo ya empezó');
    if(typeof d.title!=='string'||!d.title.trim()||d.title.length>64)fail('Escribe un nombre de torneo de hasta 64 caracteres');
    if(!integer(d.ft,1,5)||!integer(d.characters,1,5))fail('El FT y el máximo de personajes deben estar entre 1 y 5');
    const seconds=d.seconds??180;
    if(![180,240,360,480].includes(seconds))fail('El tiempo debe ser 180, 240, 360 o 480 segundos');
    const title=clean(d.title,64);if(!title)fail('El nombre del torneo está vacío');
    if(d.characters!==t.characters&&Object.keys(t.entrants).length) {t.entrants={};announce(r,'Cambio de límite de personajes: vuelve a inscribirte.');}
    Object.assign(t,{title,ft:d.ft,characters:d.characters,seconds,revision:t.revision+1});
  } else if(op==='tournament_register') {
    if(t.status!=='registration')fail('Las inscripciones están cerradas');
    if(!Array.isArray(d.roster)||d.roster.length<1||d.roster.length>t.characters||d.roster.some(c=>typeof c!=='string'||!c.trim()||c.length>32||/[\x00-\x1f]/.test(c)))fail('Personajes declarados inválidos');
    const roster=d.roster.map(c=>c.trim());if(new Set(roster.map(c=>c.toLowerCase())).size!==roster.length)fail('No repitas un personaje en tu inscripción');
    t.entrants[u.id]={id:u.id,name:u.name,bot:false,game_bot:false,roster};t.revision++;announce(r,u.name+' se inscribió en '+t.title);
  } else if(op==='tournament_withdraw') {
    if(t.status!=='registration')fail('El torneo ya empezó; el anfitrión puede resolver una baja por WO');withdraw(r,u.id);
  } else if(op==='tournament_start') start(r);
  else if(op==='tournament_reset') {announce(r,'El anfitrión cerró el torneo anterior. Se abren nuevas inscripciones.');r.tournament=tournament();}
  else if(op==='tournament_wo') {
    if(!integer(d.target,1,0xffffffff)||!t.entrants[d.target]||t.status!=='running')fail('Selecciona un participante del torneo activo para dar WO');
    announce(r,t.entrants[d.target].name+': baja por decisión del anfitrión (WO).');disqualify(r,d.target);
  } else if(op==='tournament_report'||op==='tournament_code') {
    if(d.tournament_id!==t.id||!integer(d.match,1,t.matches.length))fail('El resultado no corresponde a este torneo/cruce');
    const m=t.matches[d.match-1];
    if(op==='tournament_code') {
      if(t.status!=='running'||t.current!==m.id||u.id!==m.p1)fail('Solo P1 del cruce activo puede publicar su código de combate');
      if(typeof d.code!=='string'||!/^[A-Z0-9]{1,7}$/.test(d.code))fail('Código de combate inválido');
      if(!m.code){m.code=d.code;t.revision++;}else if(m.code!==d.code)fail('El cruce ya tiene un código');
    } else {
      if(![m.p1,m.p2].includes(u.id))fail('Solo los jugadores del cruce pueden confirmar el resultado');
      const s=d.score;
      if(!Array.isArray(s)||s.length!==2||s.some(v=>!integer(v,0,t.ft))||((s[0]===t.ft)===(s[1]===t.ft)))fail('Marcador inválido');
      if(m.state==='done') {if(JSON.stringify(m.score)===JSON.stringify(s))return;fail('El cruce ya terminó con otro resultado');}
      if(t.status!=='running'||t.current!==m.id)fail('Este cruce todavía no está activo');
      m.reports[u.id]=s;t.revision++;
      const reports=Object.values(m.reports);
      if(reports.length===2&&JSON.stringify(reports[0])===JSON.stringify(reports[1])) {finish(r,m,s[0]===t.ft?m.p1:m.p2,s);advance(r);}
      else if(reports.length===2)announce(r,`Cruce #${m.id}: resultados distintos; ambos jugadores deben revisarlos.`);
    }
  } else fail('Operación no disponible en el servicio de salas');
}
function duelOp(r,u,d,now) {
  let duel=r.duel;
  if(d.op==='duel_offer') {
    if(r.tournament.status==='running'||duel?.battle?.status==='running'||duel?.status==='pending')fail('Ya hay un desafío o combate en curso');
    const other=Object.values(r.users).find(p=>p.id===d.target);
    if(!other||other.id===u.id)fail('Selecciona otro luchador de la sala');
    if(!integer(d.ft,1,5)||!integer(d.characters,1,5)||![180,240,360,480].includes(d.seconds))fail('Reglas de duelo inválidas');
    r.duel={id:random(12),status:'pending',from:u.id,to:other.id,name1:u.name,name2:other.name,ft:d.ft,characters:d.characters,seconds:d.seconds,expires:now+120000};
    announce(r,`${u.name} desafía a ${other.name}: FT${d.ft}, ${d.seconds}s, máximo ${d.characters} personajes.`);return;
  }
  if(!duel||d.duel_id!==duel.id)fail('El desafío ya no está disponible');
  if(d.op==='duel_accept') {
    if(u.id!==duel.to)fail('Solo el rival desafiado puede aceptar');
    if(duel.status==='accepted')return; // Lost response retry cannot start a second session.
    if(duel.status!=='pending'||now>=duel.expires)fail('El desafío caducó');
    const a=Object.values(r.users).find(p=>p.id===duel.from),b=Object.values(r.users).find(p=>p.id===duel.to);
    if(!a||!b||r.tournament.status==='running')fail('Los jugadores ya no están disponibles');
    const t=tournament();Object.assign(t,{title:'Duelo libre BTC',ft:duel.ft,characters:duel.characters,seconds:duel.seconds,status:'running',current:1});
    for(const p of [a,b])t.entrants[p.id]={id:p.id,name:p.name,bot:false,game_bot:false,roster:['Libre']};
    t.matches=[{id:1,round:1,sources:[],p1:a.id,p2:b.id,winner:null,score:null,reports:{},code:'',state:'active'}];
    duel.battle=t;duel.status='accepted';a.ready=b.ready=true;
    announce(r,`${b.name} aceptó: ${a.name} vs ${b.name}. Preparando código de combate.`);
  } else if(d.op==='duel_decline') {
    if(u.id!==duel.to||duel.status!=='pending')fail('Solo el rival puede rechazar un desafío pendiente');
    r.duel=null;announce(r,u.name+' rechazó el desafío.');
  } else if(d.op==='duel_cancel') {
    if(![duel.from,duel.to,r.host_id].includes(u.id))fail('No puedes cancelar este duelo');
    r.duel=null;announce(r,u.name+' canceló el duelo.');
  } else fail('Operación de duelo desconocida');
}
export function snapshot(r, token, code) {
  const u=r.users[token],t=r.tournament,m=t.current?t.matches[t.current-1]:null;
  const result={protocol:1,room_kind:r.kind??'legacy',title:r.title,capacity:r.capacity,self_id:u.id,host_id:r.host_id,token,room_code:'BTC-'+code,
    users:Object.values(r.users).map(({id,name,ready,bot,game_bot})=>({id,name,ready,bot,game_bot})),messages:r.messages,
    tournament:{id:t.id,title:t.title,ft:t.ft,characters:t.characters,seconds:t.seconds??180,mode:t.mode,status:t.status,enrolled:Object.keys(t.entrants).length,
      self_enrolled:!!t.entrants[u.id],self_roster:t.entrants[u.id]?.roster||[],role:m?.p1===u.id?1:m?.p2===u.id?2:0,
      revision:t.revision,current:t.current,champion:t.champion,champion_name:t.champion?nameOf(t,t.champion):'',
      podium:podium(t).map((p,i)=>({place:i+1,id:p,name:nameOf(t,p)})),participants:Object.values(t.entrants),
      matches:t.matches.map(m=>({id:m.id,round:m.round,p1:m.p1,p2:m.p2,winner:m.winner,score:m.score,state:m.state,code:m.code,
        name1:m.p1===null?'Por definir':nameOf(t,m.p1),name2:m.p2===null?'Por definir':nameOf(t,m.p2),bots:false,playable:true,confirmations:Object.keys(m.reports).length}))}};
  if(r.duel) {
    const {battle,...publicDuel}=r.duel;result.duel=publicDuel;
    if(battle){result.combat=snapshot({...r,tournament:battle,duel:null},token,code).tournament;result.combat.mode='duel';}
  }
  return result;
}
export function apply(r, d, now, code, passwordVerified=false,socialVerified=false) {
  for(const [token,u] of Object.entries(r.users)) if(now-u.seen>90000)remove(r,token,'perdió la conexión');
  if(r.closed)fail('El anfitrión cerró la sala');
  let token=d.token;
  if(d.op==='join') {
    if(r.social_duel&&!socialVerified)fail('Este duelo solo admite al amigo que recibió el desafío');
    if(r.access&&!passwordVerified)fail('Contraseña incorrecta');
    if(d.protocol!==1||d.edition!=='BTC')fail('Esta sala requiere Rising Battle BTC compatible');
    if(Object.keys(r.users).length>=r.capacity)fail('La sala está llena');
    // Public admission never grants bots or host identity, even if flags are supplied.
    token=add(r,d.name,now);announce(r,r.users[token].name+' entró en la sala');
  } else if(typeof token!=='string'||!Object.hasOwn(r.users,token))fail('Ya no perteneces a esta sala (expulsión o desconexión)');
  const u=r.users[token];
  if(r.duel?.status==='pending'&&now>=r.duel.expires){r.duel=null;announce(r,'El desafío caducó sin respuesta.');}
  // A poll reads only; persist a heartbeat every 15 seconds to limit D1 writes.
  if(now-u.seen>=15000)u.seen=now;
  if(d.op==='chat') {
    const msg=clean(d.text,240);if(!msg)fail('El mensaje está vacío');
    if(now-(r.last_chat[token]??-100000)<500)fail('Espera antes de enviar otro mensaje');
    r.last_chat[token]=now;announce(r,msg,u.name);
  } else if(d.op==='ready')u.ready=!u.ready;
  else if(d.op==='kick') {
    if(u.id!==r.host_id)fail('Solo el anfitrión puede expulsar usuarios');
    const other=Object.keys(r.users).find(t=>r.users[t].id===d.target);
    if(!other||other===token)fail('Selecciona otro usuario de la sala');remove(r,other,'fue expulsado por el anfitrión');
  } else if(d.op==='leave') {remove(r,token,'salió de la sala');return {left:true,room_code:'BTC-'+code};}
  else if(typeof d.op==='string'&&d.op.startsWith('duel_')) {
    if(r.kind==='tournament')fail('Los duelos libres se crean en Salas, fuera del torneo');
    duelOp(r,u,d,now);
  }
  else if(typeof d.op==='string'&&d.op.startsWith('tournament_')) {
    if(r.duel?.battle && d.tournament_id===r.duel.battle.id && ['tournament_code','tournament_report'].includes(d.op)) {
      const original=r.tournament;r.tournament=r.duel.battle;
      try{tournamentOp(r,u,d);}finally{r.duel.battle=r.tournament;r.tournament=original;}
    } else {
      if(r.kind==='casual')fail('Esta es una sala libre; crea un torneo independiente');
      if(d.op==='tournament_start'&&(r.duel?.status==='pending'||r.duel?.battle?.status==='running'))fail('Termina o cancela el duelo antes del torneo');
      if(d.op==='tournament_start')r.duel=null;
      tournamentOp(r,u,d);
    }
  }
  else if(!['join','poll'].includes(d.op))fail('Operación no disponible en el servicio de salas');
  return snapshot(r,token,code);
}
const json=(v,status=200)=>Response.json(v,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
const STREAM_LIMIT=36000, STREAM_CHUNK=48;
const streamKey=(code,generation,tick)=>`OBS:${code}:${generation}:${tick}`;
const hex=bytes=>[...new Uint8Array(bytes)].map(n=>n.toString(16).padStart(2,'0')).join('');
async function streamOp(db,r,d,code,now) {
  // Poll authenticates membership and expires kicked/absent users first.
  apply(r,{op:'poll',token:d.token},now,code);
  const u=r.users[d.token],t=r.duel?.battle??r.tournament;
  if(d.tournament_id!==t.id)fail('La transmisión pertenece a otro duelo');
  const m=t.matches[(d.match??1)-1];
  if(!m)fail('No existe ese combate');
  const response=stream=>({result:{...snapshot(r,d.token,code),stream}});
  if(d.op==='observer_begin') {
    if(t.status!=='running'||m.id!==t.current||u.id!==m.p1)fail('Solo P1 del combate activo puede publicar entradas');
    const h=d.header;
    if(!h||h.version!==1||h.tournament_id!==t.id||h.match!==m.id||h.first_tick!==1||!/^[a-f0-9]{32}$/.test(h.generation??''))fail('Cabecera de espectador inválida');
    for(const k of ['seed','rules'])if(!integer(h[k],0,0xffffffff))fail('Reglas de espectador inválidas');
    for(const k of ['exe_sha256','payload_sha256','data_sha256','memory_sha256'])if(!/^[a-f0-9]{64}$/.test(h[k]??''))fail('Huella de compatibilidad inválida');
    if(!Array.isArray(h.options)||h.options.length!==2||h.options.some(n=>!integer(n,0,0xffffffff))||!Array.isArray(h.names)||h.names.length!==2||h.names.some(n=>typeof n!=='string'||!n||new TextEncoder().encode(n).length>64||/[\x00-\x1f]/.test(n)))fail('Opciones de espectador inválidas');
    if(new TextEncoder().encode(JSON.stringify(h)).length>2048)fail('Cabecera demasiado grande');
    if(r.stream?.header.tournament_id===t.id && r.stream.header.match===m.id) {
      if(JSON.stringify(r.stream.header)!==JSON.stringify(h))fail('El combate ya tiene otra transmisión');
    } else r.stream={header:h,next:1,finished:false,writer:u.id};
    return response({ready:true,next:r.stream.next});
  }
  const s=r.stream;
  if(!s||s.header.tournament_id!==t.id||s.header.match!==m.id)return response({ready:false});
  if(d.op==='observer_pull') {
    if([m.p1,m.p2].includes(u.id))fail('Un jugador no puede observar su propio combate');
    if(!integer(d.tick,1,s.next)||d.tick>STREAM_LIMIT)fail('Posición de reproducción inválida');
    const chunks=[];let tick=d.tick;
    for(let i=0;i<8&&tick<s.next;i++) {
      const row=await db.prepare('SELECT state FROM btc_lobbies WHERE code=?').bind(streamKey(code,s.header.generation,tick)).first();
      if(!row)fail('Faltan entradas confirmadas; reinicia la observación');
      const chunk=JSON.parse(row.state);chunks.push(chunk);tick+=chunk.count;
    }
    return response({ready:true,header:s.header,chunks,next:s.next,finished:s.finished});
  }
  if(u.id!==s.writer||u.id!==m.p1||d.generation!==s.header.generation)fail('No puedes modificar esta transmisión');
  if(d.op==='observer_end') {
    if(d.tick!==s.next)fail('Final de transmisión incompleto');
    s.finished=true;return response({ready:true,next:s.next});
  }
  if(d.op!=='observer_append')fail('Operación de espectador desconocida');
  const c=d.chunk;
  if(!c||!integer(c.start,1,STREAM_LIMIT)||!integer(c.count,1,STREAM_CHUNK)||c.start+c.count>STREAM_LIMIT||typeof c.pads!=='string'||c.pads.length>2304||!/^[a-f0-9]{64}$/.test(c.sha256??''))fail('Bloque de entradas inválido');
  let bytes;try{bytes=Uint8Array.from(atob(c.pads),c=>c.charCodeAt(0));}catch{fail('Entradas inválidas');}
  if(bytes.length!==c.count*36||hex(await crypto.subtle.digest('SHA-256',bytes))!==c.sha256)fail('Entradas corruptas');
  const key=streamKey(code,s.header.generation,c.start);
  const old=await db.prepare('SELECT state FROM btc_lobbies WHERE code=?').bind(key).first();
  if(old&&old.state!==JSON.stringify(c))fail('Las entradas confirmadas no pueden cambiar');
  if(c.start<s.next) {if(!old||c.start+c.count>s.next)fail('Reintento inválido');return response({ready:true,next:s.next});}
  if(c.start!==s.next||s.finished)fail('Faltan entradas anteriores o la transmisión terminó');
  s.next+=c.count;
  return {...response({ready:true,next:s.next}),extra:db.prepare('INSERT OR IGNORE INTO btc_lobbies(code,state,revision,expires) VALUES(?,?,0,?)').bind(key,JSON.stringify(c),now+3600000)};
}
function passwordText(value) {
  if(value===undefined)return '';
  if(typeof value!=='string'||new TextEncoder().encode(value).length>128||/[\x00-\x1f]/.test(value))fail('Contraseña inválida (máximo 128 bytes)');
  return value;
}
async function passwordHash(password,salt) {
  const key=await crypto.subtle.importKey('raw',new TextEncoder().encode(password),'PBKDF2',false,['deriveBits']);
  return hex(await crypto.subtle.deriveBits({name:'PBKDF2',salt:Uint8Array.from(salt.match(/../g),x=>parseInt(x,16)),iterations:100000,hash:'SHA-256'},key,256));
}
async function passwordMatches(access,password) {
  const actual=await passwordHash(password,access.salt);let diff=0;
  for(let i=0;i<actual.length;i++)diff|=actual.charCodeAt(i)^access.hash.charCodeAt(i);
  return diff===0;
}
async function directory(db,kind,now) {
  if(!['casual','tournament'].includes(kind))fail('Selecciona Salas o Torneos');
  const rows=await db.prepare('SELECT code,state FROM btc_lobbies WHERE length(code)=6 AND expires>? LIMIT 256').bind(now).all();
  const rooms=[];
  for(const row of rows.results) {
    const r=JSON.parse(row.state),host=Object.values(r.users).find(u=>u.id===r.host_id);
    if(r.listed===false||r.kind!==kind||r.closed||!host||now-host.seen>90000)continue;
    rooms.push({room_code:'BTC-'+row.code,title:r.title,host:host.name,
      count:Object.values(r.users).filter(u=>now-u.seen<=90000).length,capacity:r.capacity,
      locked:!!r.access,kind,status:kind==='tournament'?r.tournament.status:(r.duel?.battle?.status==='running'?'playing':'waiting')});
  }
  return json({protocol:1,rooms});
}
async function admission(db,ip,now) {
  const key=[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(`${Math.floor(now/3600000)}:${ip}`)))].map(v=>v.toString(16).padStart(2,'0')).join('');
  const result=await db.prepare('INSERT INTO btc_admission(key,hits,expires) VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET hits=hits+1 WHERE hits<60').bind(key,now+3600000).run();
  if(!result.meta.changes)fail('Demasiados intentos de crear/entrar; espera antes de repetir');
}
export async function handle(request, env, ctx) {
  const path=new URL(request.url).pathname;
  if(request.method==='GET'&&path==='/v1/diagnostics/capabilities')return json({combat_trace:env.DIAGNOSTICS_ENABLED==='true'?1:0,stage_trace:env.DIAGNOSTICS_ENABLED==='true'?1:0,ability_trace:env.DIAGNOSTICS_ENABLED==='true'?1:0,costume_trace:env.DIAGNOSTICS_ENABLED==='true'?1:0});
  if(path==='/v1/diagnostics'||path==='/admin/diagnostics'||path==='/admin/api/diagnostics')return diagnosticsHandle(request,env,ctx);
  if(path==='/v1/challonge'||path==='/v1/challonge/bind')return challongeHandle(request,env);
  if(request.method==='GET'&&path==='/health') {
    await env.DB.prepare('SELECT code FROM btc_lobbies LIMIT 1').first();
    return json({service:'BTC Rising Battle rooms',protocol:1,status:'ok',features:['duels','tournament_rules','observer_experimental','room_directory','room_passwords','separate_tournaments','social_friends','social_messages','social_challenges','ranked_beta']});
  }
  if(request.method==='POST'&&path==='/v1/ranked')return rankedHandle(request,env.DB,{createRoom,apply,snapshot,duelOp,roomCode});
  if(request.method==='POST'&&path==='/v1/social')return socialHandle(request,env.DB,{createRoom,apply,snapshot,duelOp,roomCode,admission});
  if(request.method!=='POST'||path!=='/v1/rooms')return json({error:'Ruta desconocida'},404);
  if(Number(request.headers.get('Content-Length')||0)>4096)fail('Petición demasiado grande');
  const raw=await request.text();if(new TextEncoder().encode(raw).length>4096)fail('Petición demasiado grande');
  let d;try{d=JSON.parse(raw);}catch{fail('JSON inválido');}
  if(!d||typeof d!=='object'||Array.isArray(d))fail('Petición inválida');
  const now=Date.now(),db=env.DB;
  if(!['create','list'].includes(d.op)){const ranked=await rankedRoom(db,d,{createRoom,apply,snapshot,duelOp,roomCode},now);if(ranked)return ranked;}
  if(d.op==='create'||d.op==='join')await admission(db,request.headers.get('CF-Connecting-IP')||'unknown',now);
  if(d.op==='list')return directory(db,d.kind,now);
  if(d.op==='create') {
    const r=createRoom(d,now),password=passwordText(d.password);
    if(password){const salt=random(16);r.access={salt,hash:await passwordHash(password,salt)};}
    await db.batch([db.prepare('DELETE FROM btc_lobbies WHERE expires<?').bind(now),db.prepare('DELETE FROM btc_admission WHERE expires<?').bind(now)]);
    for(let i=0;i<6;i++) {
      const code=code6();
      const inserted=await db.prepare('INSERT OR IGNORE INTO btc_lobbies(code,state,revision,expires) SELECT ?,?,0,? WHERE (SELECT COUNT(*) FROM btc_lobbies WHERE length(code)=6)<256').bind(code,JSON.stringify(r),now+3600000).run();
      if(inserted.meta.changes)return json(snapshot(r,r.host_token,code));
    }
    fail('Servicio de salas lleno; vuelve a intentarlo más tarde');
  }
  const code=roomCode(d.room_code??d.code);
  for(let attempt=0;attempt<10;attempt++) {
    const row=await db.prepare('SELECT state,revision,expires FROM btc_lobbies WHERE code=?').bind(code).first();
    if(!row||row.expires<now)fail('La sala no existe o ha caducado');
    const r=JSON.parse(row.state);
    const verified=d.op==='join'&&r.access?await passwordMatches(r.access,passwordText(d.password)):false;
    const streamed=typeof d.op==='string'&&d.op.startsWith('observer_')?await streamOp(db,r,d,code,now):null;
    const result=streamed?streamed.result:apply(r,d,now,code,verified),state=JSON.stringify(r);
    if(state===row.state)return json(result);
    const update=db.prepare('UPDATE btc_lobbies SET state=?,revision=revision+1,expires=? WHERE code=? AND revision=?').bind(state,r.closed?now:now+3600000,code,row.revision);
    const write=streamed?.extra?(await db.batch([streamed.extra,update])).at(-1):await update.run();
    if(write.meta.changes)return json(result);
  }
  return json({error:'La sala está ocupada; repite la operación'},409);
}
export default {async scheduled(event,env,ctx){ctx.waitUntil(purgeDiagnostics(env));},async fetch(request,env,ctx) {
  try{return await handle(request,env,ctx);}
  catch(e){return json({error:e instanceof RankedError||e instanceof RoomError||e instanceof SocialError||e instanceof ChallongeServiceError?e.message:'El servicio de salas no está disponible temporalmente'},e instanceof ChallongeServiceError?e.status:e instanceof RankedError||e instanceof RoomError||e instanceof SocialError?400:503);}
}};
