import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
import worker from './worker.mjs';
import {adminAuth,cleanReport,compare,purgeDiagnostics} from './diagnostics.mjs';
const sqlite=new DatabaseSync(':memory:');sqlite.exec(readFileSync(new URL('./schema.sql',import.meta.url),'utf8'));
class Statement{constructor(sql,args=[]){this.sql=sql;this.args=args;}bind(...args){return new Statement(this.sql,args);}async all(){return{results:sqlite.prepare(this.sql).all(...this.args)};}async first(){return sqlite.prepare(this.sql).get(...this.args)||null;}async run(){const r=sqlite.prepare(this.sql).run(...this.args);return{meta:{changes:Number(r.changes)},success:true};}}
const DB={prepare:sql=>new Statement(sql),batch:async list=>{sqlite.exec('BEGIN');try{const out=[];for(const st of list)out.push(await st.run());sqlite.exec('COMMIT');return out;}catch(e){sqlite.exec('ROLLBACK');throw e;}}};
const env={DB,DIAGNOSTICS_ENABLED:'true',DIAGNOSTICS_ACCESS_ISSUER:'https://btc-test.cloudflareaccess.com',DIAGNOSTICS_ACCESS_AUD:'private-audience',DIAGNOSTICS_ADMIN_EMAIL:'owner@example.test'};
const ids=[1,2,3].map(n=>({id:String(n).repeat(32),token:String(n).repeat(64)}));
async function send(path,data,expected=200,headers={}){
 const r=await worker.fetch(new Request('https://test'+path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json','CF-Connecting-IP':'127.0.0.1',...headers},...(data?{body:JSON.stringify(data)}:{})}),env);
 const value=await r.json();assert.equal(r.status,expected,JSON.stringify(value));return value;
}
for(let i=0;i<ids.length;i++)await send('/v1/social',{...ids[i],op:'register',name:'Player '+i});
assert.equal((await send('/v1/diagnostics/capabilities')).combat_trace,1);
assert.equal((await send('/v1/diagnostics/capabilities')).stage_trace,1);
assert.equal((await send('/v1/diagnostics/capabilities')).ability_trace,1);
const first=await send('/v1/ranked',{...ids[0],op:'queue',compat:'a'.repeat(64)});
const joined=await send('/v1/ranked',{...ids[1],op:'queue',compat:'a'.repeat(64)});
const host=(await send('/v1/ranked',{...ids[0],op:'poll'})).launch,guest=joined.launch;
function report(p,id){return {schema:1,report_id:id,kind:'desync',context:{battle_id:p.combat.id,match:1,side:p.combat.role,room_code:p.room_code,rules:{seconds:1}},versions:{loader_version:'2.0.1',decomp_release:'v0.1.38.1',exe_sha256:'a'.repeat(64),memory_sha256:'b'.repeat(64),dat_sha256:'c'.repeat(64),payload_sha256:{'test.o':'d'.repeat(64)}},fingerprint:Object.fromEntries(['total','tables','characters','animations','stages','effects','scripts','menus'].map(k=>[k,'02dfd69d'])),divergence:{blank:3648,local_hash:'f3491de612a8250d',peer_hash:'9cc9bd601e60b2af'},network:{connection:'direct',input_delay:1,rollback:8,samples:[]},character:null,technique:null};}
const a=report(host,'a'.repeat(32)),b=report(guest,'b'.repeat(32));b.divergence={blank:3648,local_hash:a.divergence.peer_hash,peer_hash:a.divergence.local_hash};b.fingerprint.characters='07a727a9';
const fighter={side:1,roster_id:8,character_id:8,name:'Bardock / SSJ',member:0,team_size:2,variant:1,action_id:253,action_class:0};
a.combat={source:'native_trace_v1',time_basis:'pre_tick',epoch:1,confirmed_through:3648,target_blank:3648,nearest_distance:0,observations:[{blank:3648,phase:3,resimulated:false,input_confirmed:true,sides:[fighter,{...fighter,side:2}]}]};
a.raw_log='SECRET CHAT';a.context._room_token='SECRET';a.versions.path='C:/Users/secret';
a.combat.observations[0].stage={id:3,start_id:2,catalog_name:'Dying Namek',catalog_source:'engine_catalog'};
a.combat.events=[{blank:3648,side:1,character_id:8,character_name:'Bardock / SSJ',kind:'ability',ability_class:2,ability_id:500,action_id:262,observed_start:true,input_confirmed:true,stage_id:3,player:'fake alias'}];
assert(!JSON.stringify(cleanReport(a)).includes('SECRET'));assert(!JSON.stringify(cleanReport(a)).includes('Users'));
await send('/v1/diagnostics',{...ids[0],room_token:host.token,report:a});
await send('/v1/diagnostics',{...ids[1],room_token:guest.token,report:b});
await send('/v1/diagnostics',{...ids[0],room_token:host.token,report:a}); // Idempotent retry.
assert.equal(sqlite.prepare('SELECT COUNT(*) AS n FROM btc_diagnostic_reports').get().n,2);
const stored=sqlite.prepare('SELECT body FROM btc_diagnostic_reports').all().map(r=>JSON.parse(r.body));
assert.equal(stored[0].combat.observations[0].sides[0].name,'Bardock / SSJ');assert.equal(stored[1].combat,null);assert.equal(stored[0].context.rules.seconds,360);assert(!JSON.stringify(stored).includes('SECRET'));
assert.equal(stored[0].combat.observations[0].stage.id,3);assert.equal(stored[0].combat.observations[0].stage.start_id,2);
assert.equal(stored[0].combat.events[0].ability_id,500);assert(!JSON.stringify(stored[0]).includes('fake alias'));
assert.equal(stored[0].context.names[0],'Player 0');
assert(!JSON.stringify(stored).includes(host.token));assert(!JSON.stringify(stored).includes(host.room_code));assert(!JSON.stringify(stored).includes(ids[0].token));
assert.equal(compare(stored).kind,'mismatch');assert(compare(stored).differences.some(d=>d.key==='characters'));
assert.equal(compare([stored[0]]).kind,'waiting');
const different=structuredClone(stored[1]);different.divergence.blank=100;assert.equal(compare([stored[0],different]).kind,'waiting');
const same=structuredClone(stored[1]);same.fingerprint=structuredClone(stored[0].fingerprint);assert.equal(compare([stored[0],same]).kind,'investigate');
await send('/v1/diagnostics',{...ids[0],token:'0'.repeat(64),room_token:host.token,report:{...a,report_id:'c'.repeat(32)}},401);
await send('/v1/diagnostics',{...ids[2],room_token:'wrong',report:{...a,report_id:'c'.repeat(32)}},403);
await send('/v1/diagnostics',{...ids[0],room_token:host.token,report:{...a,report_id:'c'.repeat(32),context:{...a.context,side:2}}},403);
await send('/v1/diagnostics',{...ids[0],room_token:host.token,report:{...a,report_id:'c'.repeat(32),context:{...a.context,battle_id:'f'.repeat(24)}}},403);
await send('/v1/diagnostics',{...ids[0],room_token:host.token,report:{...a,extra:'x'.repeat(30000)}},413);
await send('/admin/api/diagnostics',null,401,{'Cf-Access-Authenticated-User-Email':env.DIAGNOSTICS_ADMIN_EMAIL});
// Real cryptographic signature verification, not trusting a header or an unsigned payload.
const key=await crypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
const jwk=await crypto.subtle.exportKey('jwk',key.publicKey);jwk.kid='test-key';
globalThis.fetch=async url=>{assert.equal(url,env.DIAGNOSTICS_ACCESS_ISSUER+'/cdn-cgi/access/certs');return Response.json({keys:[jwk]});};
const enc=v=>Buffer.from(JSON.stringify(v)).toString('base64url');
async function token(changes={}){const now=Math.floor(Date.now()/1000),parts=[enc({alg:'RS256',kid:'test-key'}),enc({iss:env.DIAGNOSTICS_ACCESS_ISSUER,aud:[env.DIAGNOSTICS_ACCESS_AUD],email:env.DIAGNOSTICS_ADMIN_EMAIL,iat:now,exp:now+300,...changes})];return parts.join('.')+'.'+Buffer.from(await crypto.subtle.sign('RSASSA-PKCS1-v1_5',key.privateKey,Buffer.from(parts.join('.')))).toString('base64url');}
const valid=await token(),headers={'Cf-Access-Jwt-Assertion':valid};
await adminAuth(new Request('https://test'),env,undefined,{access:{aud:env.DIAGNOSTICS_ACCESS_AUD,getIdentity:async()=>({email:env.DIAGNOSTICS_ADMIN_EMAIL})}});
await assert.rejects(adminAuth(new Request('https://test'),env,undefined,{access:{aud:'wrong',getIdentity:async()=>({email:env.DIAGNOSTICS_ADMIN_EMAIL})}}));
await assert.rejects(adminAuth(new Request('https://test'),env,undefined,{access:{aud:env.DIAGNOSTICS_ACCESS_AUD,getIdentity:async()=>({email:'other@example.test'})}}));
await adminAuth(new Request('https://test',{headers}),env);
for(const change of [{aud:['wrong']},{iss:'https://evil.example'},{exp:0},{iat:9999999999},{email:'another@example.test'}])await assert.rejects(adminAuth(new Request('https://test',{headers:{'Cf-Access-Jwt-Assertion':await token(change)}}),env));
await assert.rejects(adminAuth(new Request('https://test',{headers:{'Cf-Access-Jwt-Assertion':valid.slice(0,-10)+'AAAAAAAAAA'}}),env));
const list=await send('/admin/api/diagnostics',null,200,headers);assert.equal(list.cases.length,1);assert.equal(list.cases[0].sides,2);
const details=await send('/admin/api/diagnostics?battle='+a.context.battle_id+'&match=1',null,200,headers);assert.equal(details.comparison.kind,'mismatch');
await send('/admin/api/diagnostics',{battle:a.context.battle_id,match:1,status:'resolved'},403,headers);
await send('/admin/api/diagnostics',{battle:a.context.battle_id,match:1,status:'resolved'},200,{...headers,Origin:'https://test','X-BTC-Admin':'1'});
assert.equal((await send('/admin/api/diagnostics?status=resolved',null,200,headers)).cases.length,1);
// Backfill requires profile auth, never claims room membership, and pairs mirrored hashes rather than clocks.
const ha={...a,report_id:'d'.repeat(32),context:{source:'history'},summary:{status:'desync',exit_code:'0x00000000',online:true}},hb={...b,report_id:'e'.repeat(32),context:{source:'history'},summary:{status:'desync',exit_code:'0x00000000',online:true}};
await send('/v1/diagnostics',{...ids[0],report:ha});await send('/v1/diagnostics',{...ids[1],report:hb});
const history=sqlite.prepare("SELECT body FROM btc_diagnostic_reports WHERE json_extract(body,'$.context.source')='history'").all().map(r=>JSON.parse(r.body));
assert.equal(history.length,2);assert.equal(history[0].context.battle_id,history[1].context.battle_id);assert.notEqual(history[0].context.side,history[1].context.side);assert.equal(compare(history).kind,'mismatch');
await send('/v1/diagnostics',{...ids[0],report:{schema:1,report_id:'9'.repeat(32),kind:'session',context:{source:'history'},versions:{payload_sha256:{}},fingerprint:{},divergence:null,network:{connection:'unknown',input_delay:null,rollback:null,samples:[]},summary:{status:'closed',exit_code:'0x00000000',online:false,raw_log:'SECRET'}}});
const closed=JSON.parse(sqlite.prepare('SELECT body FROM btc_diagnostic_reports WHERE id=?').get('9'.repeat(32)).body);
assert.equal(closed.kind,'session');assert.equal(compare([closed]).kind,'session');assert(!JSON.stringify(closed).includes('SECRET'));
// Atomic rate limit: only 12 rows per profile per hour, not counting idempotent retries.
for(let i=0;i<11;i++)await send('/v1/diagnostics',{...ids[0],room_token:host.token,report:{...a,report_id:(100+i).toString(16).padStart(32,'0')}});
await send('/v1/diagnostics',{...ids[0],room_token:host.token,report:{...a,report_id:'f'.repeat(32)}},429);
sqlite.exec('UPDATE btc_diagnostic_reports SET expires=0');await purgeDiagnostics(env);
assert.equal(sqlite.prepare('SELECT COUNT(*) AS n FROM btc_diagnostic_reports').get().n,0);
assert.equal(sqlite.prepare('SELECT COUNT(*) AS n FROM btc_diagnostic_cases').get().n,0);
env.DIAGNOSTICS_ENABLED='false';await send('/admin/api/diagnostics',null,503,headers);
console.log('PASS: uploads, pairing, privacy allowlist, room authorization, idempotency, size/rate limits, signed Access JWT, CSRF and case status');
