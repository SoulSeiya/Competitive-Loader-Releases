// Shared public bracket cache. OAuth credentials are AES-GCM sealed using a
// Worker secret and are never included in public snapshots or diagnostics.
export class ChallongeServiceError extends Error {
  constructor(message,status=400){super(message);this.status=status;}
}
const cfail=(message,status=400)=>{throw new ChallongeServiceError(message,status);};
const cid='fe3de50f505d875736b22bc6c9989747b87fcb5e3e7924fa2764966ec61f2dde';
const apiRoot='https://api.challonge.com/v2.1';
const known=new WeakSet();
const cjson=(value,status=200)=>Response.json({protocol:1,...value},{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
const chex=bytes=>[...bytes].map(n=>n.toString(16).padStart(2,'0')).join('');
const cb64=bytes=>btoa(String.fromCharCode(...bytes));
const cun64=text=>Uint8Array.from(atob(text),c=>c.charCodeAt(0));
const cslug=value=>typeof value==='string'&&/^[A-Za-z0-9_-]{1,100}$/.test(value)?value:cfail('Identificador de torneo no válido');
async function cSchema(db){
  if(known.has(db))return;
  await db.batch([
    db.prepare('CREATE TABLE IF NOT EXISTS btc_challonge_auth(owner TEXT PRIMARY KEY,cipher TEXT NOT NULL,lease TEXT,lease_until INTEGER NOT NULL DEFAULT 0)'),
    db.prepare('CREATE TABLE IF NOT EXISTS btc_challonge_brackets(slug TEXT PRIMARY KEY,owner TEXT NOT NULL,context TEXT NOT NULL,snapshot TEXT NOT NULL,updated INTEGER NOT NULL,attempt_after INTEGER NOT NULL,error TEXT NOT NULL DEFAULT \'\')'),
    db.prepare('CREATE TABLE IF NOT EXISTS btc_challonge_budget(period TEXT PRIMARY KEY,hits INTEGER NOT NULL)')]);
  known.add(db);
}
async function cKey(env){
  const secret=env.CHALLONGE_TOKEN_KEY;
  if(typeof secret!=='string'||!/^[a-f0-9]{64}$/.test(secret))cfail('La conexión compartida de Challonge aún no está configurada',503);
  return crypto.subtle.importKey('raw',Uint8Array.from(secret.match(/../g),v=>parseInt(v,16)),{name:'AES-GCM'},false,['encrypt','decrypt']);
}
async function cSeal(value,owner,key){
  const iv=crypto.getRandomValues(new Uint8Array(12));
  const data=await crypto.subtle.encrypt({name:'AES-GCM',iv,additionalData:new TextEncoder().encode(owner)},key,new TextEncoder().encode(JSON.stringify(value)));
  return JSON.stringify({iv:cb64(iv),data:cb64(new Uint8Array(data))});
}
async function cOpen(cipher,owner,key){
  const value=JSON.parse(cipher);
  return JSON.parse(new TextDecoder().decode(await crypto.subtle.decrypt({name:'AES-GCM',iv:cun64(value.iv),additionalData:new TextEncoder().encode(owner)},key,cun64(value.data))));
}
async function cBudget(db){
  // Reserve headroom for device authorization and other private previews.
  const period=new Date().toISOString().slice(0,7);
  const result=await db.prepare('INSERT INTO btc_challonge_budget VALUES(?,1) ON CONFLICT(period) DO UPDATE SET hits=hits+1 WHERE hits<300').bind(period).run();
  if(!result.meta.changes)cfail('Cupo de pruebas de Challonge agotado; se conserva el último bracket',429);
}
async function cRequest(db,url,access,form){
  await cBudget(db);
  const headers={Accept:'application/json','Content-Type':'application/vnd.api+json'};
  if(access){headers.Authorization='Bearer '+access;headers['Authorization-Type']='v2';}
  if(form)headers['Content-Type']='application/x-www-form-urlencoded';
  let response;
  try{response=await fetch(url,{method:form?'POST':'GET',headers,body:form?new URLSearchParams(form):undefined,redirect:'manual',signal:AbortSignal.timeout(12000)});}
  catch{cfail('No se pudo consultar Challonge; se conserva el último bracket',503);}
  if(response.status>=300&&response.status<400){await response.body?.cancel();cfail('Challonge devolvió una redirección inesperada',502);}
  if(!response.ok){await response.body?.cancel();cfail(response.status===404?'Esta autorización no permite consultar el torneo':response.status===429?'Challonge ha limitado las consultas':'Challonge rechazó la autorización o consulta',response.status);}
  const reader=response.body.getReader();let size=0,parts=[];
  while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>2000000){await reader.cancel();cfail('Respuesta de Challonge demasiado grande',502);}parts.push(value);}
  const raw=new Uint8Array(size);let offset=0;for(const part of parts){raw.set(part,offset);offset+=part.length;}
  try{return JSON.parse(new TextDecoder().decode(raw));}catch{cfail('Respuesta de Challonge no válida',502);}
}
async function cCollection(db,path,access){
  const result=[];
  for(let page=1;page<=10;page++){
    const data=(await cRequest(db,apiRoot+path+'?per_page=100&page='+page+'&include_community_tournaments=1',access)).data;
    if(!Array.isArray(data))cfail('Lista de Challonge no válida',502);
    result.push(...data);if(data.length<100)return result;
  }
  cfail('Torneo demasiado grande para esta prueba',422);
}
function cSnapshot(tournament,participants,matches,slug){
  const a=tournament?.attributes;
  if(!a||a.private!==false)cfail('Solo se pueden compartir torneos públicos',403);
  const people=participants.map(p=>({id:String(p.id),attributes:{name:String(p.attributes.name).slice(0,100),username:String(p.attributes.username||'').slice(0,100),seed:p.attributes.seed??null,final_rank:p.attributes.final_rank??null}}));
  const names=new Map(people.map(p=>[p.id,p.attributes.name]));
  const normalized=matches.map(m=>{
    const a=m.attributes,r=a.relationships||m.relationships||{};
    const points=a.points_by_participant||[];
    if(points.length>2)cfail('Esta prueba admite cruces de dos participantes',422);
    const p1=String(r.player1?.data?.id||points[0]?.participant_id||''),p2=String(r.player2?.data?.id||points[1]?.participant_id||'');
    return {id:String(m.id),round:Number(a.round)||0,identifier:String(a.identifier||''),state:String(a.state||'pending'),p1,p2,name1:names.get(p1)||'Por decidir',name2:names.get(p2)||'Por decidir',scores:String(a.scores||''),winner:String(a.winner_id||'')};
  });
  return {id:String(tournament.id),title:String(a.name).slice(0,200),kind:String(a.tournament_type||''),link:'https://challonge.com/'+slug,participants:people,matches:normalized,updated:Date.now()/1000};
}
async function cRead(db,slug,access,community='',savedContext){
  let context=savedContext??'',path='/tournaments/'+slug,tournament;
  if(context)path='/communities/'+cslug(context)+path;
  try{tournament=(await cRequest(db,apiRoot+path+'.json?include_community_tournaments=1',access)).data;}
  catch(error){
    if(savedContext!==undefined||!community||![403,404].includes(error.status))throw error;
    context=cslug(community);path='/communities/'+context+'/tournaments/'+slug;
    tournament=(await cRequest(db,apiRoot+path+'.json',access)).data;
  }
  // Reject private resources before downloading their participant lists.
  if(tournament?.attributes?.private!==false)cfail('Solo se pueden compartir torneos públicos',403);
  const participants=await cCollection(db,path+'/participants.json',access);
  const matches=await cCollection(db,path+'/matches.json',access);
  return {context,snapshot:cSnapshot(tournament,participants,matches,slug)};
}
async function cDevice(db,data){
  if(!/^[a-f0-9]{32}$/.test(data.id??'')||!/^[a-f0-9]{64}$/.test(data.token??''))cfail('Perfil BTC no válido',401);
  const secret=chex(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(data.token))));
  const user=await db.prepare('SELECT id FROM btc_social_users WHERE id=? AND secret_hash=?').bind(data.id,secret).first();
  if(!user)cfail('Conecta tu perfil BTC antes de vincular un torneo',401);
  const key='CHALLONGE:BIND:'+user.id+':'+Math.floor(Date.now()/3600000);
  const limited=await db.prepare('INSERT INTO btc_admission VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET hits=hits+1 WHERE hits<10').bind(key,Date.now()+3600000).run();
  if(!limited.meta.changes)cfail('Demasiados intentos de vinculación',429);
}
async function cBind(request,env){
  const raw=await request.text();if(new TextEncoder().encode(raw).length>16000)cfail('Petición demasiado grande',413);
  let d;try{d=JSON.parse(raw);}catch{cfail('Petición no válida');}
  if(!d||typeof d!=='object'||Array.isArray(d))cfail('Petición no válida');
  await cDevice(env.DB,d);const slug=cslug(d.slug),key=await cKey(env);
  if(typeof d.access_token!=='string'||d.access_token.length<10||d.access_token.length>4096||typeof d.refresh_token!=='string'||d.refresh_token.length<10||d.refresh_token.length>4096)cfail('Falta la autorización del organizador');
  const me=(await cRequest(env.DB,apiRoot+'/me.json',d.access_token)).data;
  if(me?.type!=='user'||!me.id)cfail('Organizador no válido',401);
  const owner=String(me.id),old=await env.DB.prepare('SELECT owner FROM btc_challonge_brackets WHERE slug=?').bind(slug).first();
  if(old&&old.owner!==owner)cfail('Este torneo está vinculado con otra cuenta organizadora',403);
  const result=await cRead(env.DB,slug,d.access_token,d.community||'');
  const tokens={access_token:d.access_token,refresh_token:d.refresh_token,expires_at:Math.min(Date.now()/1000+604800,Number(d.expires_at)||Date.now()/1000+3600)};
  const cipher=await cSeal(tokens,owner,key),now=Date.now();
  // Keep the first authorized owner if two devices try to claim the same URL.
  const claimed=await env.DB.prepare("INSERT INTO btc_challonge_brackets VALUES(?,?,?,?,?,?, '') ON CONFLICT(slug) DO UPDATE SET context=excluded.context,snapshot=excluded.snapshot,updated=excluded.updated,attempt_after=excluded.attempt_after,error='' WHERE owner=excluded.owner").bind(slug,owner,result.context,JSON.stringify(result.snapshot),now,now+60000).run();
  if(!claimed.meta.changes)cfail('Este torneo ya está vinculado con otro organizador',409);
  await env.DB.prepare('INSERT INTO btc_challonge_auth(owner,cipher,lease,lease_until) VALUES(?,?,NULL,0) ON CONFLICT(owner) DO UPDATE SET cipher=excluded.cipher').bind(owner,cipher).run();
  return cjson({tournament:result.snapshot,stale:false,status:'Torneo compartido. Los participantes ya pueden consultarlo sin autorización de organizador.'});
}
async function cGet(env,slug){
  const db=env.DB,now=Date.now();let row=await db.prepare('SELECT * FROM btc_challonge_brackets WHERE slug=?').bind(slug).first();
  if(!row)cfail('El organizador aún no ha vinculado este torneo con el servicio BTC',404);
  if(now>=row.attempt_after){
    const lease=chex(crypto.getRandomValues(new Uint8Array(12)));
    const locked=await db.prepare('UPDATE btc_challonge_auth SET lease=?,lease_until=? WHERE owner=? AND lease_until<?').bind(lease,now+90000,row.owner,now).run();
    if(locked.meta.changes){
      try{
        await db.prepare('UPDATE btc_challonge_brackets SET attempt_after=? WHERE slug=?').bind(now+60000,slug).run();
        const auth=await db.prepare('SELECT cipher FROM btc_challonge_auth WHERE owner=? AND lease=?').bind(row.owner,lease).first();
        const key=await cKey(env);let tokens=await cOpen(auth.cipher,row.owner,key);
        if(tokens.expires_at<Date.now()/1000+60){
          const fresh=await cRequest(db,'https://connect.challonge.com/oauth/token',null,{client_id:cid,grant_type:'refresh_token',refresh_token:tokens.refresh_token});
          if(!fresh.access_token)cfail('El organizador debe renovar su autorización',401);
          tokens={access_token:fresh.access_token,refresh_token:fresh.refresh_token||tokens.refresh_token,expires_at:Date.now()/1000+Number(fresh.expires_in||3600)};
          await db.prepare('UPDATE btc_challonge_auth SET cipher=? WHERE owner=? AND lease=?').bind(await cSeal(tokens,row.owner,key),row.owner,lease).run();
        }
        const result=await cRead(db,slug,tokens.access_token,'',row.context);
        await db.prepare("UPDATE btc_challonge_brackets SET snapshot=?,updated=?,error='' WHERE slug=?").bind(JSON.stringify(result.snapshot),Date.now(),slug).run();
      }catch(error){
        const message=error instanceof ChallongeServiceError?error.message:'No se pudo actualizar el torneo; se conserva la última copia';
        await db.prepare('UPDATE btc_challonge_brackets SET error=?,attempt_after=? WHERE slug=?').bind(message,Date.now()+300000,slug).run();
      }finally{await db.prepare('UPDATE btc_challonge_auth SET lease=NULL,lease_until=0 WHERE owner=? AND lease=?').bind(row.owner,lease).run();}
      row=await db.prepare('SELECT * FROM btc_challonge_brackets WHERE slug=?').bind(slug).first();
    }
  }
  return cjson({tournament:JSON.parse(row.snapshot),stale:!!row.error||Date.now()-row.updated>120000,status:row.error||'Bracket compartido · consulta disponible para participantes y visitantes'});
}
export async function challongeHandle(request,env){
  await cSchema(env.DB);const url=new URL(request.url);
  if(request.method==='POST'&&url.pathname==='/v1/challonge/bind')return cBind(request,env);
  if(request.method==='GET'&&url.pathname==='/v1/challonge')return cGet(env,cslug(url.searchParams.get('slug')));
  return cjson({error:'Ruta de Challonge desconocida'},404);
}
