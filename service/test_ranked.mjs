import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
import worker from './worker.mjs';
const sqlite=new DatabaseSync(':memory:');sqlite.exec(readFileSync(new URL('./schema.sql',import.meta.url),'utf8'));
class Statement{
 constructor(sql,args=[]){this.sql=sql;this.args=args;}bind(...args){return new Statement(this.sql,args);}
 async all(){return{results:sqlite.prepare(this.sql).all(...this.args)};}async first(){return sqlite.prepare(this.sql).get(...this.args)||null;}
 async run(){const r=sqlite.prepare(this.sql).run(...this.args);return{meta:{changes:Number(r.changes)},success:true};}
}
let serial=Promise.resolve();
const DB={prepare:sql=>new Statement(sql),batch:statements=>{const execute=async()=>{sqlite.exec('BEGIN');try{const out=[];for(const st of statements)out.push(await st.run());sqlite.exec('COMMIT');return out;}catch(e){sqlite.exec('ROLLBACK');throw e;}};const result=serial.then(execute);serial=result.catch(()=>{});return result;}};
let now=2000000000000;Date.now=()=>now;
async function send(path,data,status=200){const r=await worker.fetch(new Request('https://test'+path,{method:'POST',headers:{'Content-Type':'application/json','CF-Connecting-IP':'127.0.0.1'},body:JSON.stringify(data)}),{DB});const value=await r.json();assert.equal(r.status,status,JSON.stringify(value));return value;}
const ids=[1,2,3,4].map(n=>({id:String(n).repeat(32),token:String(n).repeat(64)}));
for(let i=0;i<ids.length;i++)await send('/v1/social',{...ids[i],op:'register',name:'Jugador '+(i+1)});
const ranked=(i,op,args={},status=200)=>send('/v1/ranked',{...ids[i],op,...args},status);
// A fresh season starts at 1000 without deleting the testing season.
sqlite.exec('CREATE TABLE IF NOT EXISTS btc_ranked_beta(id TEXT PRIMARY KEY,state TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 0)');
const oldState=JSON.stringify({players:{[ids[0].id]:{name:'Tester',rating:1700,played:40,wins:35,losses:5}},queue:{},matches:{},mutation:'archive'});
sqlite.prepare('INSERT INTO btc_ranked_beta VALUES(?,?,0)').run('btc-beta-1',oldState);
const fresh=await ranked(0,'poll',{},200);
assert.equal(fresh.season,'btc-beta-publica-1');assert.equal(fresh.me.rating,1000);assert.equal(fresh.me.played,0);assert.equal(fresh.me.wins,0);assert.equal(fresh.me.losses,0);
assert.equal(sqlite.prepare('SELECT state FROM btc_ranked_beta WHERE id=?').get('btc-beta-1').state,oldState);
await send('/v1/ranked',{...ids[0],token:'0'.repeat(64),op:'poll'},400);
const compat='a'.repeat(64);
assert((await ranked(0,'queue',{compat})).queued);
const paired=await ranked(1,'queue',{compat});assert(paired.launch);assert.equal(paired.rules.characters,2);assert.deepEqual(paired.rules,{ft:2,seconds:360,characters:2});assert.equal(paired.launch.combat.seconds,360);
const first=await ranked(0,'poll'),mid=first.match.id;const p1=first.launch,p2=paired.launch;
assert.notEqual(p1.token,p2.token);assert.equal(p1.combat.role,1);assert.equal(p2.combat.role,2);
await ranked(0,'heartbeat',{match:mid,connected:true});await ranked(1,'heartbeat',{match:mid,connected:true});
const call=(p,op,values={},status=200)=>send('/v1/rooms',{room_code:p.room_code,token:p.token,op,...values},status);
await call(p1,'duel_cancel',{duel_id:p1.duel.id},400);
await call(p1,'tournament_wo',{target:2,tournament_id:p1.combat.id},400);
await call(p1,'tournament_report',{tournament_id:p1.combat.id,match:1,score:[2,1]});
assert.equal((await ranked(0,'poll')).me.rating,1000);
await call(p2,'tournament_report',{tournament_id:p2.combat.id,match:1,score:[2,1]});
assert.equal((await ranked(0,'poll')).me.rating,1012);assert.equal((await ranked(1,'poll')).me.rating,988);
await ranked(0,'forfeit',{match:mid});assert.equal((await ranked(0,'poll')).me.rating,1012);
// Queue races cannot assign either account twice.
await Promise.all([ranked(0,'queue',{compat}),ranked(1,'queue',{compat})]);
const next=await ranked(0,'poll'),nextId=next.match.id;assert.notEqual(nextId,mid);
await ranked(0,'heartbeat',{match:nextId,connected:true});await ranked(1,'heartbeat',{match:nextId,connected:true});
await ranked(0,'heartbeat',{match:nextId,failed:true});assert.equal((await ranked(0,'poll')).match.finished,null);
await ranked(0,'heartbeat',{match:nextId,closed:true});assert.equal((await ranked(0,'poll')).match.finished,null);
for(let tick=0;tick<3;tick++){now+=15000;await ranked(1,'heartbeat',{match:nextId,connected:true});}
const loss=await ranked(0,'poll');assert.equal(loss.me.losses,1);assert.equal(loss.me.abandons,1);
await ranked(0,'queue',{compat},400); // Cooldown survives restarting the Loader.
const before=(await ranked(1,'poll')).me.rating;
await ranked(0,'heartbeat',{match:nextId,closed:true});assert.equal((await ranked(1,'poll')).me.rating,before);
now+=180000;
await ranked(2,'queue',{compat:'b'.repeat(64)});assert((await ranked(3,'queue',{compat})).queued); // Different editions never pair.
await ranked(2,'cancel_queue');await ranked(3,'cancel_queue');
await ranked(0,'queue',{compat});let t=await ranked(1,'queue',{compat});const timeout=t.match.id;
await ranked(0,'heartbeat',{match:timeout,connected:true});await ranked(1,'heartbeat',{match:timeout,connected:true});
for(let i=0;i<3;i++){now+=10000;await ranked(1,'heartbeat',{match:timeout,connected:true});}
now+=16000;await ranked(1,'heartbeat',{match:timeout,connected:true});
const win=await ranked(1,'poll');assert.equal(win.match.reason,'desconexion');assert.equal(win.match.winner,ids[1].id);
now+=300000;await ranked(0,'queue',{compat});t=await ranked(1,'queue',{compat});
await ranked(0,'heartbeat',{match:t.match.id,connected:true});await ranked(1,'heartbeat',{match:t.match.id,connected:true});
const rating=(await ranked(1,'poll')).me.rating;now+=46000;
const voided=await ranked(1,'poll');assert.equal(voided.match.winner,null);assert.equal(voided.me.rating,rating);
const ledger=JSON.parse(sqlite.prepare('SELECT state FROM btc_ranked_beta').get().state);
assert.equal(Object.values(ledger.matches).filter(m=>!m.finished).length,0);
console.log('PASS: fixed FT2/360/2, authentication, compatible queue, concurrent matching, paired results, exact-once Elo, restricted host actions, self-close loss, cooldown, one-sided timeout and both-offline void.');
