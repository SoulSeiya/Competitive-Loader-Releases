// Structured diagnostics only. No raw logs or credentials are persisted.
import {ADMIN_HTML} from './diagnostics_admin.mjs';
import {cleanCombat} from './combat_diagnostics.mjs';
const DAY=86400000,MAX_BODY=24576,RETENTION=14*DAY;
const hash=async s=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s)))].map(x=>x.toString(16).padStart(2,'0')).join('');
const hex=(v,n)=>typeof v==='string'&&new RegExp('^[a-f0-9]{'+n+'}$').test(v);
const integer=(n,lo,hi)=>Number.isInteger(n)&&n>=lo&&n<=hi;
const obj=v=>v&&typeof v==='object'&&!Array.isArray(v);
const reply=(body,status=200)=>Response.json(body,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
export class DiagnosticError extends Error {constructor(message,status=400){super(message);this.status=status;}}
const fail=(message,status=400)=>{throw new DiagnosticError(message,status);};
let jwksCache=null;
function decode(value){return Uint8Array.from(atob(value.replace(/-/g,'+').replace(/_/g,'/')),c=>c.charCodeAt(0));}
export async function adminAuth(request,env,fetcher=(input,init)=>fetch(input,init),ctx){
  const issuer=env.DIAGNOSTICS_ACCESS_ISSUER,audience=env.DIAGNOSTICS_ACCESS_AUD,email=env.DIAGNOSTICS_ADMIN_EMAIL;
  if(!/^https:\/\/[a-z0-9-]+\.cloudflareaccess\.com$/.test(issuer||'')||!audience||!email)fail('El acceso privado aún no está configurado',503);
  // Prefer Cloudflare's verified runtime context on direct Worker invocations.
  // This object is supplied by the platform, never by a request header/body.
  if(ctx?.access){
    if(ctx.access.aud!==audience)fail('Acceso no autorizado',403);
    let identity;try{identity=await ctx.access.getIdentity();}catch{fail('No se pudo comprobar la identidad privada',503);}
    if(identity?.email!==email)fail('Acceso no autorizado',403);
    return;
  }
  const token=request.headers.get('Cf-Access-Jwt-Assertion')||'';
  if(token.length>12000)fail('Acceso no válido',403);
  let header,claims,parts;
  try{parts=token.split('.');if(parts.length!==3)throw 0;header=JSON.parse(new TextDecoder().decode(decode(parts[0])));claims=JSON.parse(new TextDecoder().decode(decode(parts[1])));}catch{fail('Inicia sesión con tu cuenta autorizada',401);}
  const now=Math.floor(Date.now()/1000);
  if(header.alg!=='RS256'||typeof header.kid!=='string'||claims.iss!==issuer||!Array.isArray(claims.aud)||!claims.aud.includes(audience)||!Number.isFinite(claims.exp)||claims.exp<=now||!Number.isFinite(claims.iat)||claims.iat>now+30||(claims.nbf!==undefined&&(!Number.isFinite(claims.nbf)||claims.nbf>now+30))||claims.email!==email)fail('Acceso no autorizado',403);
  if(!jwksCache||jwksCache.issuer!==issuer||jwksCache.until<Date.now()||!jwksCache.keys.some(k=>k.kid===header.kid)){
    let response;
    try{response=await fetcher(issuer+'/cdn-cgi/access/certs',{redirect:'error'});}catch{fail('No se pudieron obtener los certificados de Access',503);}
    if(!response.ok)fail('No se pudo validar el acceso',503);
    const text=await response.text();if(text.length>65536)fail('Certificados no válidos',503);
    let data;try{data=JSON.parse(text);}catch{fail('Respuesta de certificados no válida',503);}if(!Array.isArray(data.keys)||data.keys.length>20)fail('Certificados no válidos',503);
    jwksCache={issuer,keys:data.keys,until:Date.now()+300000};
  }
  const jwk=jwksCache.keys.find(k=>k.kid===header.kid&&k.kty==='RSA');if(!jwk)fail('Acceso no autorizado',403);
  let valid=false;
  try{const key=await crypto.subtle.importKey('jwk',jwk,{name:'RSASSA-PKCS1-v1_5',hash:'SHA-256'},false,['verify']);valid=await crypto.subtle.verify('RSASSA-PKCS1-v1_5',key,decode(parts[2]),new TextEncoder().encode(parts[0]+'.'+parts[1]));}catch{}
  if(!valid)fail('Acceso no autorizado',403);
}
export async function schema(db){
  await db.batch([
    db.prepare('CREATE TABLE IF NOT EXISTS btc_diagnostic_reports(id TEXT PRIMARY KEY,battle TEXT NOT NULL,match_no INTEGER NOT NULL,side INTEGER NOT NULL,reporter TEXT NOT NULL,name TEXT NOT NULL,received INTEGER NOT NULL,expires INTEGER NOT NULL,body TEXT NOT NULL,UNIQUE(battle,match_no,side,reporter,body))'),
    db.prepare('CREATE INDEX IF NOT EXISTS btc_diagnostics_battle ON btc_diagnostic_reports(battle,match_no)'),
    db.prepare('CREATE INDEX IF NOT EXISTS btc_diagnostics_expiry ON btc_diagnostic_reports(expires)'),
    db.prepare('CREATE INDEX IF NOT EXISTS btc_diagnostics_rate ON btc_diagnostic_reports(reporter,received)'),
    db.prepare("CREATE TABLE IF NOT EXISTS btc_diagnostic_cases(case_id TEXT PRIMARY KEY,status TEXT NOT NULL DEFAULT 'pending')")]);
}
export async function purgeDiagnostics(env){
  if(env.DIAGNOSTICS_ENABLED!=='true')return;
  await schema(env.DB);
  await env.DB.prepare('DELETE FROM btc_diagnostic_reports WHERE expires<?').bind(Date.now()).run();
  await env.DB.prepare("DELETE FROM btc_diagnostic_cases WHERE NOT EXISTS(SELECT 1 FROM btc_diagnostic_reports r WHERE btc_diagnostic_cases.case_id=r.battle||':'||r.match_no)").run();
}
export function cleanReport(r,historical=false){
  if(!obj(r)||r.schema!==1||!(historical?['desync','session']:['desync']).includes(r.kind)||!hex(r.report_id,32))fail('Informe inválido');
  const c=r.context,v=r.versions,d=r.divergence,n=r.network;
  if(!obj(c)||!historical&&(!hex(c.battle_id,24)||!integer(c.match,1,128)||![1,2].includes(c.side)||!/^BTC-[A-Z2-9]{6}$/.test(c.room_code||'')))fail('Duelo inválido');
  if(!obj(v)||!historical&&!['exe_sha256','memory_sha256','dat_sha256'].every(k=>hex(v[k],64))||!obj(v.payload_sha256))fail('Versiones incompletas');
  const versions={};for(const k of ['loader_version','decomp_release']){if(historical&&v[k]===undefined)continue;if(typeof v[k]!=='string'||!/^[A-Za-z0-9._-]{1,64}$/.test(v[k]))fail('Versión inválida');versions[k]=v[k];}
  for(const k of ['exe_sha256','memory_sha256','dat_sha256']){if(historical&&v[k]===undefined)continue;if(!hex(v[k],64))fail('Huella inválida');versions[k]=v[k];}
  if(Object.keys(v.payload_sha256).length>32)fail('Demasiados parches');
  versions.payload_sha256={};for(const [k,value] of Object.entries(v.payload_sha256)){if(!/^[A-Za-z0-9_-]{1,80}\.o$/.test(k)||!hex(value,64))fail('Parche inválido');versions.payload_sha256[k]=value;}
  const fingerprint={};if(!obj(r.fingerprint))fail('Huella inválida');
  for(const k of ['total','tables','characters','animations','stages','effects','scripts','menus'])if(r.fingerprint[k]!==undefined){if(!hex(r.fingerprint[k],8))fail('Huella inválida');fingerprint[k]=r.fingerprint[k];}
  let divergence=null;if(d!==null){if(!obj(d)||!integer(d.blank,0,2147483647)||!hex(d.local_hash,16)||!hex(d.peer_hash,16))fail('Divergencia inválida');divergence={blank:d.blank,local_hash:d.local_hash,peer_hash:d.peer_hash};}
  if(!obj(n)||!['unknown','direct','relay'].includes(n.connection)||!Array.isArray(n.samples)||n.samples.length>12||![n.input_delay,n.rollback].every(v=>v===null||integer(v,0,120)))fail('Red inválida');
  const samples=n.samples.map(s=>{if(!obj(s)||!integer(s.blank,0,2147483647)||!integer(s.rollbacks,0,1000000)||!integer(s.waits,0,1000000)||!Number.isFinite(s.average_blanks)||s.average_blanks<0||s.average_blanks>1000000)fail('Muestra inválida');return{blank:s.blank,rollbacks:s.rollbacks,waits:s.waits,average_blanks:s.average_blanks};});
  // Reconstruct every field. Unknown fields, local paths, arbitrary text, tokens and chats never reach storage.
  /** @type {any} Server-verified membership/rules are added after sanitization. */
  const result={schema:1,report_id:r.report_id,kind:r.kind,context:historical?{source:'history'}:{battle_id:c.battle_id,match:c.match,side:c.side},versions,fingerprint,divergence,network:{connection:n.connection,input_delay:n.input_delay,rollback:n.rollback,samples},character:null,technique:null};
  try{result.combat=cleanCombat(r.combat);}catch{fail('Evidencia de combate inválida');}
  if(historical){
    if(r.kind==='session')result.divergence=null;
    const s=r.summary||{},statuses=['unknown','preparing','running','closed','desync','crash','abnormal_exit','exit_unavailable','monitor_error','loader_closed_while_game_running'];
    result.summary={status:statuses.includes(s.status)?s.status:'unknown',exit_code:typeof s.exit_code==='string'&&/^0x[0-9a-fA-F]{8}$/.test(s.exit_code)?s.exit_code:null,online:s.online===true,desync:r.kind==='desync'};
  }
  return result;
}
export function compare(reports){
  if(reports.length&&reports.every(r=>r.kind==='session'))return {kind:'session',title:'Sesión histórica: no hay un desync confirmado en estos registros',differences:[]};
  const p1=reports.filter(r=>r.context.side===1),p2=reports.filter(r=>r.context.side===2);
  if(!p1.length||!p2.length)return {kind:'waiting',title:'Falta el informe del otro jugador',differences:[]};
  // Pair the same divergence, rather than mixing different games in an FT set.
  const a=p1.at(-1),b=p2.findLast(r=>r.divergence?.blank===a.divergence?.blank);
  if(!a.divergence)return {kind:'incomplete',title:'Falta el primer frame de divergencia; no se pueden emparejar los eventos',differences:[]};
  if(!b)return {kind:'waiting',title:'Los informes pertenecen a puntos distintos del set',differences:[]};
  const differences=[];
  for(const key of ['loader_version','decomp_release','exe_sha256','memory_sha256','dat_sha256'])if(a.versions[key]!==b.versions[key])differences.push({group:'versions',key,p1:a.versions[key],p2:b.versions[key]});
  for(const key of new Set([...Object.keys(a.versions.payload_sha256),...Object.keys(b.versions.payload_sha256)]))if(a.versions.payload_sha256[key]!==b.versions.payload_sha256[key])differences.push({group:'patches',key,p1:a.versions.payload_sha256[key]??null,p2:b.versions.payload_sha256[key]??null});
  for(const key of ['total','tables','characters','animations','stages','effects','scripts','menus'])if(a.fingerprint[key]&&b.fingerprint[key]&&a.fingerprint[key]!==b.fingerprint[key])differences.push({group:'data',key,p1:a.fingerprint[key],p2:b.fingerprint[key]});
  if(differences.length)return {kind:'mismatch',title:'Diferencias comprobadas entre los clientes; causa exacta pendiente',differences};
  const complete=['total','tables','characters','animations','stages','effects','scripts','menus'].every(k=>a.fingerprint[k]&&b.fingerprint[k]);
  return {kind:complete?'investigate':'incomplete',title:complete?'Sin diferencias en los metadatos capturados: requiere reproducción':'Faltan huellas para descartar diferencias de datos',differences:[],note:'La igualdad de hashes no identifica por sí sola la causa. La conexión o el rollback no prueban un fallo de red.'};
}
async function upload(request,env){
  const advertised=Number(request.headers.get('Content-Length')||0);if(advertised>MAX_BODY)fail('Informe demasiado grande',413);
  const reader=request.body?.getReader();if(!reader)fail('Falta el informe');let size=0,chunks=[];
  while(true){const{done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>MAX_BODY){await reader.cancel();fail('Informe demasiado grande',413);}chunks.push(value);}
  let d;try{const bytes=new Uint8Array(size);let offset=0;for(const value of chunks){bytes.set(value,offset);offset+=value.length;}d=JSON.parse(new TextDecoder().decode(bytes));}catch{fail('JSON inválido');}
  if(!hex(d.id,32)||!hex(d.token,64))fail('Identidad no válida',401);
  const me=await env.DB.prepare('SELECT id,name FROM btc_social_users WHERE id=? AND secret_hash=?').bind(d.id,await hash(d.token)).first();if(!me)fail('Perfil no autorizado',401);
  const historical=d.report?.context?.source==='history';
  const report=cleanReport(d.report,historical),now=Date.now();
  await schema(env.DB);
  const existing=await env.DB.prepare('SELECT reporter,body FROM btc_diagnostic_reports WHERE id=?').bind(report.report_id).first();
  if(existing){if(existing.reporter!==me.id)fail('ID de informe ocupado',409);return reply({accepted:true,report_id:report.report_id});}
  let name=me.name;
  if(historical){
    const v=report.divergence;
    const event=v?[v.blank,...[v.local_hash,v.peer_hash].sort()].join(':'):me.id+':'+report.report_id;
    report.context={source:'history',battle_id:(await hash('history-v1:'+event)).slice(0,24),match:1,side:v&&v.local_hash>v.peer_hash?2:1,names:['Informe A','Informe B'],rules:{}};
  }else{
    const code=d.report.context.room_code.slice(4),row=await env.DB.prepare('SELECT state,expires FROM btc_lobbies WHERE code=?').bind(code).first();
    if(!row||row.expires<now)fail('La sala del informe ya expiró',410);
    const room=JSON.parse(row.state),member=room.users[d.room_token],battle=room.duel?.battle,match=battle?.matches.find(m=>m.id===report.context.match);
    if(!member||member.social_id&&member.social_id!==me.id||!battle||battle.id!==report.context.battle_id||!match||member.id!==(report.context.side===1?match.p1:match.p2))fail('El perfil no pertenece a ese lado del duelo',403);
    report.context.rules={ft:battle.ft,seconds:battle.seconds,characters:battle.characters};report.context.names=[battle.entrants[match.p1]?.name||'P1',battle.entrants[match.p2]?.name||'P2'];name=member.name;
  }
  // Atomic per-player hourly and global retention caps, bounded storage even under concurrent requests.
  await env.DB.prepare('DELETE FROM btc_diagnostic_reports WHERE expires<?').bind(now).run();
  const inserted=await env.DB.prepare("INSERT OR IGNORE INTO btc_diagnostic_reports(id,battle,match_no,side,reporter,name,received,expires,body) SELECT ?,?,?,?,?,?,?,?,? WHERE (SELECT COUNT(*) FROM btc_diagnostic_reports WHERE reporter=? AND received>? AND COALESCE(json_extract(body,'$.context.source'),'live')=?)<? AND (SELECT COUNT(*) FROM btc_diagnostic_reports)<2000").bind(report.report_id,report.context.battle_id,report.context.match,report.context.side,me.id,name,now,now+RETENTION,JSON.stringify(report),me.id,now-(historical?DAY:3600000),historical?'history':'live',historical?100:12).run();
  if(!inserted.meta.changes)fail('Límite de informes alcanzado; inténtalo más tarde',429);
  return reply({accepted:true,report_id:report.report_id});
}
async function admin(request,env,ctx){
  await adminAuth(request,env,undefined,ctx);
  const url=new URL(request.url);
  if(url.pathname==='/admin/diagnostics')return new Response(ADMIN_HTML,{headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store','Content-Security-Policy':"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'}});
  await schema(env.DB);
  if(request.method==='GET'){
    const battle=url.searchParams.get('battle'),match=Number(url.searchParams.get('match')||1);
    if(battle){
      if(!hex(battle,24)||!integer(match,1,128))fail('Caso inválido');
      const rows=(await env.DB.prepare('SELECT name,received,body FROM btc_diagnostic_reports WHERE battle=? AND match_no=? AND expires>? ORDER BY received LIMIT 24').bind(battle,match,Date.now()).all()).results;
      const reports=rows.map(r=>({...JSON.parse(r.body),received:r.received,name:r.name}));
      return reply({reports,comparison:compare(reports)});
    }
    const status=url.searchParams.get('status')||'all';if(!['all','pending','investigating','resolved'].includes(status))fail('Filtro inválido');
    const cursor=Number(url.searchParams.get('before')||Date.now()+1);if(!Number.isSafeInteger(cursor)||cursor<0)fail('Cursor inválido');
    const rows=(await env.DB.prepare(`SELECT r.battle,r.match_no,MAX(r.received) AS received,COUNT(*) AS reports,COUNT(DISTINCT r.side) AS sides,MIN(r.body) AS sample,COALESCE(c.status,'pending') AS status FROM btc_diagnostic_reports r LEFT JOIN btc_diagnostic_cases c ON c.case_id=r.battle||':'||r.match_no WHERE r.expires>? GROUP BY r.battle,r.match_no HAVING MAX(r.received)<? AND (?='all' OR COALESCE(c.status,'pending')=?) ORDER BY received DESC LIMIT 30`).bind(Date.now(),cursor,status,status).all()).results;
    return reply({cases:rows.map(({sample,...r})=>({...r,context:JSON.parse(sample).context})),next:rows.length===30?rows.at(-1).received:null});
  }
  if(request.method==='POST'){
    if(request.headers.get('Origin')!==url.origin||request.headers.get('X-BTC-Admin')!=='1')fail('Origen no autorizado',403);
    const raw=await request.text();if(raw.length>1024)fail('Petición demasiado grande',413);
    let d;try{d=JSON.parse(raw);}catch{fail('JSON inválido');}
    if(!hex(d.battle,24)||!integer(d.match,1,128)||!['pending','investigating','resolved'].includes(d.status))fail('Estado inválido');
    await env.DB.prepare('INSERT INTO btc_diagnostic_cases VALUES(?,?) ON CONFLICT(case_id) DO UPDATE SET status=excluded.status').bind(d.battle+':'+d.match,d.status).run();return reply({ok:true});
  }
  fail('Método no disponible',405);
}
export async function diagnosticsHandle(request,env,ctx){
  try{
    if(env.DIAGNOSTICS_ENABLED!=='true')return reply({error:'Diagnósticos pendientes de activación'},503);
    const path=new URL(request.url).pathname;
    if(path.startsWith('/admin/'))return await admin(request,env,ctx);
    if(request.method!=='POST')return reply({error:'Método no disponible'},405);
    return await upload(request,env);
  }catch(e){return reply({error:e instanceof DiagnosticError?e.message:'No se pudo procesar el informe'},e instanceof DiagnosticError?e.status:503);}
}
