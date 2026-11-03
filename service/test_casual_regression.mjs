// Run the production Worker against actual SQLite, with D1's promise API.
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
import worker from './worker.mjs';
const sqlite=new DatabaseSync(':memory:');
sqlite.exec(readFileSync(new URL('./schema.sql',import.meta.url),'utf8'));
class Statement {
  constructor(sql,args=[]){this.sql=sql;this.args=args;}
  bind(...args){return new Statement(this.sql,args);}
  async all(){return {results:sqlite.prepare(this.sql).all(...this.args)};}
  async first(){return sqlite.prepare(this.sql).get(...this.args)||null;}
  async run(){const r=sqlite.prepare(this.sql).run(...this.args);return {success:true,meta:{changes:Number(r.changes)}};}
}
const env={DB:{prepare:sql=>new Statement(sql),batch:async statements=>{
  sqlite.exec('BEGIN');try{const results=[];for(const s of statements)results.push(await s.run());sqlite.exec('COMMIT');return results;}catch(e){sqlite.exec('ROLLBACK');throw e;}
}}};
async function send(d,expected=200) {
  const response=await worker.fetch(new Request('https://rooms.test/v1/rooms',{method:'POST',headers:{'Content-Type':'application/json','CF-Connecting-IP':'127.0.0.1'},body:JSON.stringify(d)}),env);
  const r=await response.json();assert.equal(response.status,expected,JSON.stringify(r));return r;
}
const create=name=>send({op:'create',name,title:'Test BTC',capacity:32,protocol:1,edition:'BTC'});
let host=await create('Host');const code=host.room_code;
const call=(who,op,values={},status=200)=>send({op,token:who.token,room_code:code,...values},status);
const members=[host];
for(let i=1;i<8;i++)members.push(await send({op:'join',room_code:code,name:'Guest '+i,protocol:1,edition:'BTC',bot:true,token:host.token}));
assert.equal(members[1].users[1].bot,false);
assert.notEqual(members[1].token,host.token);
let offer=await call(members[1],'duel_offer',{target:members[2].self_id,ft:2,characters:2,seconds:360});
const duel_id=offer.duel.id;
await call(host,'duel_accept',{duel_id},400);
const accepted=await Promise.all([call(members[2],'duel_accept',{duel_id}),call(members[2],'duel_accept',{duel_id})]);
assert.equal(accepted[0].combat.id,accepted[1].combat.id);
assert.equal(accepted[0].combat.mode,'duel');assert.equal(accepted[0].combat.seconds,360);
assert.equal((await call(host,'poll')).combat.role,0); // Host stays in the room.
await call(members[3],'duel_cancel',{duel_id},400);
const duelTid=accepted[0].combat.id;
const observerHeader={version:1,tournament_id:duelTid,match:1,generation:'a'.repeat(32),first_tick:1,seed:12,rules:0,options:[0,0],names:['P1','P2'],exe_sha256:'1'.repeat(64),payload_sha256:'2'.repeat(64),data_sha256:'3'.repeat(64),memory_sha256:'4'.repeat(64)};
await call(host,'observer_begin',{tournament_id:duelTid,match:1,header:observerHeader},400);
await call(members[1],'observer_begin',{tournament_id:duelTid,match:1,header:observerHeader});
const pads=Buffer.alloc(48*36,255),chunk={start:1,count:48,pads:pads.toString('base64'),sha256:Buffer.from(await crypto.subtle.digest('SHA-256',pads)).toString('hex')};
await call(members[1],'observer_append',{tournament_id:duelTid,match:1,generation:observerHeader.generation,chunk});
await call(members[1],'observer_append',{tournament_id:duelTid,match:1,generation:observerHeader.generation,chunk}); // retry
await call(host,'observer_append',{tournament_id:duelTid,match:1,generation:observerHeader.generation,chunk},400);
await call(members[2],'observer_pull',{tournament_id:duelTid,match:1,tick:1},400);
const observed=await call(host,'observer_pull',{tournament_id:duelTid,match:1,tick:1});
assert.deepEqual(observed.stream.chunks,[chunk]);assert.equal(observed.stream.next,49);
await call(members[1],'observer_append',{tournament_id:duelTid,match:1,generation:observerHeader.generation,chunk:{...chunk,start:97}},400);
await call(members[1],'observer_end',{tournament_id:duelTid,match:1,generation:observerHeader.generation,tick:49});
assert((await call(host,'observer_pull',{tournament_id:duelTid,match:1,tick:49})).stream.finished);
await call(members[2],'tournament_code',{tournament_id:duelTid,match:1,code:'ABCDEF'},400);
await call(members[1],'tournament_code',{tournament_id:duelTid,match:1,code:'ABCDEF'});
await call(members[1],'tournament_report',{tournament_id:duelTid,match:1,score:[2,0]});
offer=await call(members[2],'tournament_report',{tournament_id:duelTid,match:1,score:[2,0]});
assert.equal(offer.combat.status,'finished');assert.equal(offer.tournament.enrolled,0);
offer=await call(members[1],'duel_offer',{target:members[2].self_id,ft:1,characters:1,seconds:180});
await call(members[2],'duel_decline',{duel_id:offer.duel.id});
await call(members[2],'duel_accept',{duel_id},400); // Stale challenge must never join a new duel.
await call(members[1],'kick',{target:host.self_id},400);
await call(members[1],'tournament_config',{title:'Bad',ft:1,characters:1},400);
await call(host,'poll',{token:'__proto__'},400);
await call(host,'tournament_config',{title:'Copa BTC',ft:1,characters:1,seconds:181},400);
host=await call(host,'tournament_config',{title:'Copa BTC',ft:1,characters:1,seconds:240});
assert.equal(host.tournament.seconds,240);
// Competing writes must survive CAS retries without lost messages or entrants.
await Promise.all(members.map((u,i)=>call(u,'chat',{text:'Hola '+i})));
host=await call(host,'poll');assert.equal(host.messages.filter(m=>m.text.startsWith('Hola ')).length,8);
await Promise.all(members.map(u=>call(u,'tournament_register',{roster:['Androide 16']})));
host=await call(host,'tournament_start');assert.equal(host.tournament.enrolled,8);assert.equal(host.tournament.matches.length,7);
while(host.tournament.status==='running') {
  const t=host.tournament,m=t.matches[t.current-1],p1=members.find(u=>u.self_id===m.p1),p2=members.find(u=>u.self_id===m.p2);
  await call(p2,'tournament_code',{tournament_id:t.id,match:m.id,code:'ABCDEF'},400);
  await call(p1,'tournament_code',{tournament_id:t.id,match:m.id,code:'ABCDEF'});
  await call(p2,'tournament_report',{tournament_id:t.id,match:m.id,score:[1,0]});
  const after=await call(p1,'tournament_report',{tournament_id:t.id,match:m.id,score:[1,0]});
  const revision=after.tournament.revision;
  const duplicate=await call(p1,'tournament_report',{tournament_id:t.id,match:m.id,score:[1,0]});
  assert.equal(duplicate.tournament.revision,revision);host=await call(host,'poll');
}
assert.equal(host.tournament.podium.length,2);
await call(host,'tournament_reset');
await call(host,'kick',{target:members[1].self_id});await call(members[1],'poll',{},400);
const stored=JSON.parse(sqlite.prepare('SELECT state FROM btc_lobbies WHERE code=?').get(code.slice(4)).state);
for(const u of Object.values(stored.users))if(u.id===members[2].self_id)u.seen=Date.now()-100000;
sqlite.prepare('UPDATE btc_lobbies SET state=? WHERE code=?').run(JSON.stringify(stored),code.slice(4));
host=await call(host,'poll');assert(!host.users.some(u=>u.id===members[2].self_id));
await call(host,'leave');await call(members[3],'poll',{},400);
assert.equal((await worker.fetch(new Request('https://rooms.test/health'),env)).status,200);
const open=await send({op:'create',kind:'casual',name:'Free host',title:'Sala libre',capacity:4,protocol:1,edition:'BTC'});
const locked=await send({op:'create',kind:'casual',password:'clave-prueba',name:'Locked host',title:'Sala privada',capacity:4,protocol:1,edition:'BTC'});
const cup=await send({op:'create',kind:'tournament',name:'Cup host',title:'Torneo separado',capacity:4,protocol:1,edition:'BTC'});
const freeList=await send({op:'list',kind:'casual'}),cupList=await send({op:'list',kind:'tournament'});
assert.equal(freeList.rooms.length,2);assert.equal(cupList.rooms.length,1);
assert.deepEqual(Object.keys(freeList.rooms[0]).sort(),['capacity','count','host','kind','locked','room_code','status','title']);
assert(freeList.rooms.find(r=>r.room_code===locked.room_code).locked);
assert(!JSON.stringify(freeList).includes('clave-prueba'));
await send({op:'join',room_code:locked.room_code,name:'No password',protocol:1,edition:'BTC'},400);
await send({op:'join',room_code:locked.room_code,name:'Wrong password',password:'wrong',passwordVerified:true,protocol:1,edition:'BTC'},400);
const guest=await send({op:'join',room_code:locked.room_code,name:'Friend',password:'clave-prueba',protocol:1,edition:'BTC'});
assert.equal(guest.users.length,2);assert(!('access' in guest));
const storedLocked=JSON.parse(sqlite.prepare('SELECT state FROM btc_lobbies WHERE code=?').get(locked.room_code.slice(4)).state);
assert(!JSON.stringify(storedLocked).includes('clave-prueba'));assert.equal(storedLocked.access.hash.length,64);
await send({op:'tournament_config',room_code:open.room_code,token:open.token,title:'No',ft:1,characters:1},400);
await send({op:'duel_offer',room_code:cup.room_code,token:cup.token,target:2,ft:1,characters:1,seconds:180},400);
await send({op:'list',kind:'legacy'},400);
await send({op:'leave',room_code:open.room_code,token:open.token});
assert.equal((await send({op:'list',kind:'casual'})).rooms.length,1);
const stale=JSON.parse(sqlite.prepare('SELECT state FROM btc_lobbies WHERE code=?').get(cup.room_code.slice(4)).state);
for(const u of Object.values(stale.users))u.seen=Date.now()-91000;
sqlite.prepare('UPDATE btc_lobbies SET state=? WHERE code=?').run(JSON.stringify(stale),cup.room_code.slice(4));
assert.equal((await send({op:'list',kind:'tournament'})).rooms.length,0);
console.log('PASS: directory separation, passwords, no secret exposure, wrong password rejection, stale hosts and closure.');
console.log('PASS: SQLite persistence, concurrent chat/registration, host authority, code routing, 8-player FT1 bracket, dual results, idempotence, kick, expiry and closure.');
