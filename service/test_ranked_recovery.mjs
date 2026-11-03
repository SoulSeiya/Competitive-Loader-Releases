import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
import worker from './worker.mjs';
const sqlite=new DatabaseSync(':memory:');sqlite.exec(readFileSync(new URL('./schema.sql',import.meta.url),'utf8'));
class Statement{constructor(sql,args=[]){this.sql=sql;this.args=args;}bind(...args){return new Statement(this.sql,args);}async all(){return{results:sqlite.prepare(this.sql).all(...this.args)};}async first(){return sqlite.prepare(this.sql).get(...this.args)||null;}async run(){const r=sqlite.prepare(this.sql).run(...this.args);return{meta:{changes:Number(r.changes)},success:true};}}
let serial=Promise.resolve();const DB={prepare:sql=>new Statement(sql),batch:statements=>{const execute=async()=>{sqlite.exec('BEGIN');try{const out=[];for(const s of statements)out.push(await s.run());sqlite.exec('COMMIT');return out;}catch(e){sqlite.exec('ROLLBACK');throw e;}};const task=serial.then(execute);serial=task.catch(()=>{});return task;}};
let now=2000000000000;Date.now=()=>now;
const ids=[1,2].map(n=>({id:String(n).repeat(32),token:String(n).repeat(64)}));
async function send(path,data,status=200){const response=await worker.fetch(new Request('https://test'+path,{method:'POST',headers:{'Content-Type':'application/json','CF-Connecting-IP':'127.0.0.1'},body:JSON.stringify(data)}),{DB});const body=await response.json();assert.equal(response.status,status,JSON.stringify(body));return body;}
for(let i=0;i<2;i++)await send('/v1/social',{...ids[i],op:'register',name:'Recovery '+i});
const call=(i,op,args={},status=200)=>send('/v1/ranked',{...ids[i],op,...args},status),compat='a'.repeat(64);
const proof={blank:4640,local_hash:'1111111111111111',peer_hash:'2222222222222222'},mirror={...proof,local_hash:proof.peer_hash,peer_hash:proof.local_hash};
async function pair(){await call(0,'queue',{compat,recovery:1});await call(1,'queue',{compat,recovery:1});return await call(0,'poll');}
async function connected(id,attempt){await call(0,'heartbeat',{match:id,attempt,connected:true});await call(1,'heartbeat',{match:id,attempt,connected:true});}
async function fault(id,attempt){await call(0,'heartbeat',{match:id,attempt,failed:true,closed:true,desync_proof:proof});await call(1,'heartbeat',{match:id,attempt,failed:true,closed:true,desync_proof:mirror});return await call(0,'poll');}
let current=await pair(),id=current.match.id,oldLaunch=current.launch;
await connected(id,0);
await call(0,'heartbeat',{match:id,attempt:0,connected:true,score:[1,0]});
assert.deepEqual((await call(0,'poll')).match.checkpoint,[0,0],'One client cannot advance the preserved score');
await call(1,'heartbeat',{match:id,attempt:0,connected:true,score:[1,0]});
assert.deepEqual((await call(0,'poll')).match.checkpoint,[1,0]);
await call(0,'heartbeat',{match:id,attempt:0,connected:true,score:[1,1]}); // unpaired win is discarded
let interrupted=await fault(id,0);assert.equal(interrupted.match.phase,'recovering');assert.equal(interrupted.match.finished,null);
assert.deepEqual(interrupted.match.recovery.score,[1,0]);assert.equal(interrupted.me.rating,1000);assert.equal(interrupted.me.fairplay_points,0);assert(!interrupted.launch);
await call(0,'recovery_vote',{match:id,attempt:0,accept:true,compat});assert.equal((await call(0,'poll')).match.phase,'recovering');
// Lost/repeated acceptance is idempotent. Two concurrent accepts only create one attempt.
await Promise.all([call(0,'recovery_vote',{match:id,attempt:0,accept:true,compat}),call(1,'recovery_vote',{match:id,attempt:0,accept:true,compat})]);
current=await call(0,'poll');assert.equal(current.match.id,id);assert.equal(current.match.attempt,1);assert.equal(current.match.phase,'connecting');
assert.deepEqual(current.match.resume_score,[1,0]);assert.notEqual(current.launch.room_code,oldLaunch.room_code);
assert.notEqual(current.launch.token,oldLaunch.token);assert.notEqual(current.launch.combat.id,oldLaunch.combat.id);
await call(0,'heartbeat',{match:id,attempt:0,failed:true,closed:true,desync_proof:proof});
assert.equal((await call(0,'poll')).match.attempt,1);assert.equal((await call(0,'poll')).match.finished,null,'Late failure from the old process cannot settle the new attempt');
await send('/v1/rooms',{room_code:oldLaunch.room_code,token:oldLaunch.token,op:'leave'});
assert.equal((await call(0,'poll')).match.finished,null,'Leaving the old room cannot forfeit the new attempt');
await call(0,'forfeit',{match:id,attempt:0},400);
await connected(id,1);
await call(0,'heartbeat',{match:id,attempt:1,connected:true,completed:true,score:[2,1]});
assert.equal((await call(0,'poll')).me.rating,1000);
await call(1,'heartbeat',{match:id,attempt:1,connected:true,completed:true,score:[2,1]});
let a=await call(0,'poll'),b=await call(1,'poll');assert(a.match.finished);assert.equal(a.me.rating,1012);assert.equal(b.me.rating,988);
assert.equal(a.me.fairplay_points,10);assert.equal(b.me.fairplay_points,3);assert.equal(a.match.fairplay_delta,10);
await call(0,'heartbeat',{match:id,attempt:1,completed:true,score:[2,1]});a=await call(0,'poll');assert.equal(a.me.rating,1012);assert.equal(a.me.fairplay_points,10,'Repeated result cannot duplicate the bonus');
// Declining a paired desync leaves Elo/bonus unchanged, and frees both accounts.
current=await pair();id=current.match.id;await connected(id,0);await fault(id,0);
await call(1,'recovery_vote',{match:id,attempt:0,accept:false});a=await call(0,'poll');assert(a.match.finished);assert.equal(a.match.winner,null);assert.equal(a.me.rating,1012);assert.equal(a.me.fairplay_points,10);
// Unpaired/mismatched proof does not offer a score-preserving replay.
current=await pair();id=current.match.id;await connected(id,0);
await call(0,'heartbeat',{match:id,attempt:0,failed:true,desync_proof:proof});
await call(1,'heartbeat',{match:id,attempt:0,failed:true,desync_proof:{...mirror,blank:99}});
a=await call(0,'poll');assert(a.match.finished);assert.equal(a.match.recovery,null);assert.equal(a.me.fairplay_points,10);
// Expiry never awards a result or a bonus.
current=await pair();id=current.match.id;await connected(id,0);await fault(id,0);now+=120001;
a=await call(0,'poll');assert(a.match.finished);assert.equal(a.match.winner,null);assert.equal(a.me.rating,1012);assert.equal(a.me.fairplay_points,10);
// Proof can arrive after the first failure heartbeat; don't prematurely void.
current=await pair();id=current.match.id;await connected(id,0);
await call(0,'heartbeat',{match:id,attempt:0,failed:true});await call(1,'heartbeat',{match:id,attempt:0,failed:true});
assert.equal((await call(0,'poll')).match.finished,null);
await fault(id,0);assert.equal((await call(0,'poll')).match.phase,'recovering');
await call(0,'recovery_vote',{match:id,attempt:0,accept:true,compat:'b'.repeat(64)},400);
await call(0,'recovery_vote',{match:id,attempt:0,accept:false});
// Repeated desyncs keep one logical FT; stop after three resumptions with no bonus.
current=await pair();id=current.match.id;
for(let attempt=0;attempt<=3;attempt++){
 await connected(id,attempt);const response=await fault(id,attempt);
 if(attempt===3){assert(response.match.finished);assert.equal(response.match.winner,null);break;}
 await call(0,'recovery_vote',{match:id,attempt,accept:true,compat});await call(1,'recovery_vote',{match:id,attempt,accept:true,compat});
 assert.equal((await call(0,'poll')).match.attempt,attempt+1);
}
assert.equal((await call(0,'poll')).me.fairplay_points,10);
console.log('PASS: bilateral checkpoints/proofs, opt-in ranked recovery, fresh room/token, attempt fencing, concurrent acceptance, one-time Elo and 10/3 fair-play bonus, decline and expiry');
