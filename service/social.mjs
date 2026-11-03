// BTC social service: device identities, mutual friendships and accepted invitations.
// Credentials, private messages and room tokens are never written to console output.
export class SocialError extends Error {}
const bad=message=>{throw new SocialError(message);};
const rnd=n=>[...crypto.getRandomValues(new Uint8Array(n))].map(x=>x.toString(16).padStart(2,'0')).join('');
const hash=async text=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text)))].map(x=>x.toString(16).padStart(2,'0')).join('');
const txt=(v,n)=>typeof v==='string'&&v.trim()&&v.length<=n&&!/[\x00-\x1f\x7f]/.test(v)?v.trim():bad('Texto inválido');
const identifier=v=>typeof v==='string'&&/^[a-f0-9]{32}$/.test(v)?v:bad('Identidad inválida');
function gameName(r,me) {
  const used=new Set(Object.values(r.users).map(u=>u.name.toLowerCase()));
  if(!used.has(me.name.toLowerCase()))return me.name;
  for(let number=0;number<33;number++) {
    const suffix='#'+me.code.slice(-4)+(number?String(number):'');let base=[...me.name];
    while(new TextEncoder().encode(base.join('')+suffix).length>16)base.pop();
    const name=base.join('')+suffix;if(!used.has(name.toLowerCase()))return name;
  }
  bad('No se pudo asignar el nombre de jugador en la sala');
}
const reply=v=>Response.json({protocol:1,...v},{headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
const ready=new WeakSet();
let cleanedAt=0;
async function schema(db) {
  if(ready.has(db))return;
  await db.batch([
    db.prepare('CREATE TABLE IF NOT EXISTS btc_social_users(id TEXT PRIMARY KEY,code TEXT UNIQUE NOT NULL,name TEXT NOT NULL,secret_hash TEXT NOT NULL,seen INTEGER NOT NULL,activity TEXT NOT NULL)'),
    db.prepare('CREATE TABLE IF NOT EXISTS btc_social_friends(a TEXT,b TEXT,requester TEXT,state TEXT,updated INTEGER,PRIMARY KEY(a,b))'),
    db.prepare('CREATE TABLE IF NOT EXISTS btc_social_events(id TEXT PRIMARY KEY,sender TEXT,target TEXT,kind TEXT,payload TEXT,state TEXT,created INTEGER,expires INTEGER)'),
    db.prepare('CREATE INDEX IF NOT EXISTS btc_social_inbox ON btc_social_events(target,state,created)'),
    db.prepare('CREATE INDEX IF NOT EXISTS btc_social_messages ON btc_social_events(sender,target,kind,created)')]);
  ready.add(db);
}
const pair=(a,b)=>a<b?[a,b]:[b,a];
async function relation(db,a,b) {return db.prepare('SELECT * FROM btc_social_friends WHERE a=? AND b=?').bind(...pair(a,b)).first();}
async function friend(db,a,b) {if((await relation(db,a,b))?.state!=='accepted')bad('Primero debéis aceptar la solicitud de amistad');}
async function limit(db,id,now) {
  const key='SOC:'+id+':'+Math.floor(now/3600000);
  const r=await db.prepare('INSERT INTO btc_admission(key,hits,expires) VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET hits=hits+1 WHERE hits<600').bind(key,now+3600000).run();
  if(!r.meta.changes)bad('Demasiadas acciones; espera antes de repetir');
}
async function state(db,me,now,extra={}) {
  const rows=(await db.prepare(`SELECT f.state,f.requester,u.id,u.code,u.name,u.seen,u.activity
    FROM btc_social_friends f JOIN btc_social_users u ON u.id=CASE WHEN f.a=? THEN f.b ELSE f.a END
    WHERE (f.a=? OR f.b=?) AND f.state IN ('accepted','pending') LIMIT 200`).bind(me.id,me.id,me.id).all()).results;
  const person=r=>({id:r.id,code:r.code,name:r.name,online:now-r.seen<30000,activity:now-r.seen<30000?r.activity:'offline'});
  const friends=rows.filter(r=>r.state==='accepted').map(person);
  const incoming=rows.filter(r=>r.state==='pending'&&r.requester!==me.id).map(r=>({id:r.id,code:r.code,name:r.name}));
  const outgoing=rows.filter(r=>r.state==='pending'&&r.requester===me.id).map(r=>({id:r.id,code:r.code,name:r.name}));
  const pending=(await db.prepare(`SELECT e.id,e.sender,e.kind,e.payload,e.created,u.name FROM btc_social_events e
    JOIN btc_social_users u ON u.id=e.sender WHERE e.target=? AND e.state='pending' AND e.expires>? ORDER BY e.created DESC LIMIT 64`).bind(me.id,now).all()).results;
  const allowed=new Set(friends.map(f=>f.id));
  return reply({me:{id:me.id,code:me.code,name:me.name},friends,incoming,outgoing,
    events:pending.filter(e=>allowed.has(e.sender)).map(e=>({id:e.id,sender:e.sender,name:e.name,kind:e.kind,created:e.created,...JSON.parse(e.payload)})),...extra});
}
async function event(db,sender,target,kind,payload,now,expires) {
  const id=rnd(16);
  await db.prepare('INSERT INTO btc_social_events VALUES(?,?,?,?,?,?,?,?)').bind(id,sender,target,kind,JSON.stringify(payload),'pending',now,expires).run();
  return id;
}
async function room(db,code,now) {
  const row=await db.prepare('SELECT state,revision,expires FROM btc_lobbies WHERE code=?').bind(code).first();
  if(!row||row.expires<now)bad('La sala ya no está disponible');
  const r=JSON.parse(row.state);if(r.closed)bad('La sala está cerrada');
  return {...row,r};
}
async function invitation(db,me,d,now,h) {
  const e=await db.prepare('SELECT * FROM btc_social_events WHERE id=? AND target=?').bind(identifier(d.event),me.id).first();
  if(!e||!['invite','challenge'].includes(e.kind)||e.expires<now||!['pending','accepted'].includes(e.state))bad('La invitación ya no está disponible');
  await friend(db,me.id,e.sender);
  const payload=JSON.parse(e.payload),code=h.roomCode(payload.room_code);
  for(let attempt=0;attempt<10;attempt++) {
    const {r,revision}=await room(db,code,now);
    if(d.op==='decline') {
      if(e.state!=='pending'||r.social_duel?.state==='accepted')bad('Esta invitación ya fue aceptada');
      if(e.kind==='challenge'&&r.social_duel?.to===me.id) {
        r.closed=true;
        const changed=await db.prepare('UPDATE btc_lobbies SET state=?,revision=revision+1,expires=? WHERE code=? AND revision=?').bind(JSON.stringify(r),now,code,revision).run();
        if(!changed.meta.changes)continue;
      }
      await db.prepare("UPDATE btc_social_events SET state='declined' WHERE id=? AND target=? AND state='pending'").bind(e.id,me.id).run();
      return {};
    }
    let token=Object.keys(r.users).find(t=>r.users[t].social_id===me.id);
    if(!token) {
      if(e.state!=='pending')bad('Ya no perteneces a esa sala');
      if(e.kind==='challenge'&&(r.social_duel?.to!==me.id||r.social_duel?.from!==e.sender||r.social_duel?.expires<now))bad('El desafío ha caducado');
      const result=h.apply(r,{op:'join',protocol:1,edition:'BTC',name:gameName(r,me)},now,code,true,true);
      token=result.token;r.users[token].social_id=me.id;
      if(e.kind==='challenge') {
        const host=r.users[r.host_token],guest=r.users[token];
        h.duelOp(r,host,{op:'duel_offer',target:guest.id,ft:payload.ft,characters:payload.characters,seconds:payload.seconds},now);
        h.duelOp(r,guest,{op:'duel_accept',duel_id:r.duel.id},now);r.social_duel.state='accepted';
      }
    }
    const changed=await db.prepare('UPDATE btc_lobbies SET state=?,revision=revision+1,expires=? WHERE code=? AND revision=?').bind(JSON.stringify(r),now+3600000,code,revision).run();
    if(!changed.meta.changes)continue;
    await db.prepare("UPDATE btc_social_events SET state='accepted' WHERE id=? AND target=?").bind(e.id,me.id).run();
    return {launch:h.snapshot(r,token,code)};
  }
  bad('La sala está ocupada; vuelve a aceptar la invitación');
}
export async function socialHandle(request,db,h) {
  const raw=await request.text();if(new TextEncoder().encode(raw).length>8192)bad('Petición demasiado grande');
  let d;try{d=JSON.parse(raw);}catch{bad('JSON inválido');}
  if(!d||typeof d!=='object'||Array.isArray(d))bad('Petición inválida');
  await schema(db);const now=Date.now(),id=identifier(d.id);
  if(now-cleanedAt>60000){await db.prepare('DELETE FROM btc_social_events WHERE expires<?').bind(now).run();cleanedAt=now;}
  if(typeof d.token!=='string'||!/^[a-f0-9]{64}$/.test(d.token))bad('Credencial inválida');
  const secret=await hash(d.token);
  if(d.op==='register') {
    await h.admission(db,request.headers.get('CF-Connecting-IP')||'unknown',now);
    const name=txt(d.name,24);
    for(let attempt=0;attempt<4;attempt++) {
      await db.prepare("INSERT OR IGNORE INTO btc_social_users VALUES(?,?,?,?,?,'online')").bind(id,'BTC-'+rnd(5).toUpperCase(),name,secret,now).run();
      if(await db.prepare('SELECT id FROM btc_social_users WHERE id=?').bind(id).first())break;
    }
  }
  let me=await db.prepare('SELECT * FROM btc_social_users WHERE id=? AND secret_hash=?').bind(id,secret).first();
  if(!me)bad('No se pudo autenticar el perfil local. Conserva su archivo de credenciales');
  if(d.op!=='poll'&&d.op!=='register'&&d.op!=='messages')await limit(db,id,now);
  if(d.op==='poll'||d.op==='register') {
    const name=txt(d.name??me.name,24),activity=['online','playing','room','tournament'].includes(d.activity)?d.activity:'online';
    if(now-me.seen>=8000||name!==me.name||activity!==me.activity)await db.prepare('UPDATE btc_social_users SET name=?,seen=?,activity=? WHERE id=?').bind(name,now,activity,id).run();
    me={...me,name,seen:now,activity};
  } else if(d.op==='offline') {
    await db.prepare("UPDATE btc_social_users SET seen=0,activity='offline' WHERE id=?").bind(id).run();
  } else if(d.op==='add') {
    const code=txt(d.code,20).toUpperCase();
    const other=await db.prepare('SELECT id FROM btc_social_users WHERE code=?').bind(code).first();
    if(!other||other.id===id)bad('Código de amigo inválido');
    const count=await db.prepare("SELECT COUNT(*) n FROM btc_social_friends WHERE (a=? OR b=?) AND state IN ('pending','accepted')").bind(id,id).first();
    const theirs=await db.prepare("SELECT COUNT(*) n FROM btc_social_friends WHERE (a=? OR b=?) AND state IN ('pending','accepted')").bind(other.id,other.id).first();
    if(count.n>=100||theirs.n>=100)bad('Se alcanzó el límite de amigos y solicitudes');
    const rel=await relation(db,id,other.id);
    if(!rel||rel.state==='removed')await db.prepare(`INSERT INTO btc_social_friends VALUES(?,?,?,'pending',?)
      ON CONFLICT(a,b) DO UPDATE SET requester=excluded.requester,state='pending',updated=excluded.updated WHERE state='removed'`).bind(...pair(id,other.id),id,now).run();
  } else if(['accept_friend','reject_friend','remove_friend'].includes(d.op)) {
    const target=identifier(d.target),rel=await relation(db,id,target);
    if(!rel)bad('Solicitud no disponible');
    if(d.op!=='remove_friend'&&(rel.state!=='pending'||rel.requester===id))bad('Solo el destinatario puede responder a la solicitud');
    const next=d.op==='accept_friend'?'accepted':'removed';
    await db.prepare('UPDATE btc_social_friends SET state=?,updated=? WHERE a=? AND b=? AND state=? AND requester=?').bind(next,now,...pair(id,target),rel.state,rel.requester).run();
  } else if(d.op==='messages') {
    const target=identifier(d.target);await friend(db,id,target);
    const messages=(await db.prepare(`SELECT id,sender,payload,created FROM btc_social_events WHERE kind='message' AND expires>? AND
      ((sender=? AND target=?) OR (sender=? AND target=?)) ORDER BY created DESC LIMIT 50`).bind(now,id,target,target,id).all()).results.reverse().map(e=>({id:e.id,sender:e.sender,text:JSON.parse(e.payload).text,created:e.created}));
    await db.prepare("UPDATE btc_social_events SET state='read' WHERE kind='message' AND sender=? AND target=? AND state='pending'").bind(target,id).run();
    return state(db,me,now,{conversation:{target,messages}});
  } else if(d.op==='message') {
    const target=identifier(d.target);await friend(db,id,target);
    const last=await db.prepare('SELECT created FROM btc_social_events WHERE sender=? ORDER BY created DESC LIMIT 1').bind(id).first();
    if(last&&now-last.created<500)bad('Espera antes de enviar otro mensaje');
    await event(db,id,target,'message',{text:txt(d.text,500)},now,now+7*86400000);
  } else if(d.op==='invite') {
    const target=identifier(d.target);await friend(db,id,target);
    const code=h.roomCode(d.room_code),{r}=await room(db,code,now);
    if(!r.users[d.room_token]||r.social_duel)bad('Entra en una sala normal antes de invitar');
    await event(db,id,target,'invite',{room_code:'BTC-'+code,title:r.title},now,now+120000);
  } else if(d.op==='challenge') {
    const target=identifier(d.target);await friend(db,id,target);
    if(!Number.isInteger(d.ft)||d.ft<1||d.ft>5||!Number.isInteger(d.characters)||d.characters<1||d.characters>5||![180,240,360,480].includes(d.seconds))bad('Reglas de duelo inválidas');
    const other=await db.prepare('SELECT id,name,seen FROM btc_social_users WHERE id=?').bind(target).first();
    if(now-other.seen>=30000)bad('Tu amigo está desconectado');
    const pending=await db.prepare("SELECT id FROM btc_social_events WHERE kind='challenge' AND state='pending' AND expires>? AND (sender IN (?,?) OR target IN (?,?)) LIMIT 1").bind(now,id,target,id,target).first();
    if(pending)bad('Ya hay un desafío pendiente');
    const r=h.createRoom({name:me.name,title:'Duelo: '+me.name+' vs '+other.name,capacity:2,protocol:1,edition:'BTC',kind:'casual'},now);
    r.listed=false;r.users[r.host_token].social_id=id;r.social_duel={from:id,to:target,state:'pending',expires:now+120000};
    let code;
    for(let attempt=0;attempt<6;attempt++) {
      code=[...crypto.getRandomValues(new Uint8Array(6))].map(n=>'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'[n&31]).join('');
      const inserted=await db.prepare('INSERT OR IGNORE INTO btc_lobbies(code,state,revision,expires) SELECT ?,?,0,? WHERE (SELECT COUNT(*) FROM btc_lobbies WHERE length(code)=6)<256').bind(code,JSON.stringify(r),now+3600000).run();
      if(inserted.meta.changes)break;code=null;
    }
    if(!code)bad('No se pudo preparar el duelo; inténtalo más tarde');
    await event(db,id,target,'challenge',{room_code:'BTC-'+code,title:r.title,ft:d.ft,seconds:d.seconds,characters:d.characters},now,now+120000);
    return state(db,me,now,{launch:h.snapshot(r,r.host_token,code)});
  } else if(d.op==='accept'||d.op==='decline') {
    return state(db,me,now,await invitation(db,me,d,now,h));
  } else if(!['poll','register'].includes(d.op))bad('Operación social no disponible');
  return state(db,me,now);
}
