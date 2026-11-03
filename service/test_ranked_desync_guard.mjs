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
const ids=[1,2].map(n=>({id:String(n).repeat(32),token:String(n).repeat(64)}));
for(let i=0;i<2;i++)await send('/v1/social',{...ids[i],op:'register',name:'Guard '+i});
const call=(i,op,args={})=>send('/v1/ranked',{...ids[i],op,...args});
await call(0,'queue',{compat:'a'.repeat(64)});await call(1,'queue',{compat:'a'.repeat(64)});
const mid=(await call(0,'poll')).match.id;
await call(0,'heartbeat',{match:mid,connected:true});await call(1,'heartbeat',{match:mid,connected:true});
await call(0,'heartbeat',{match:mid,failed:true,closed:true});
assert.equal((await call(0,'poll')).match.finished,null,'A desync plus immediate game close must wait for the other side before awarding a loss');
await call(1,'heartbeat',{match:mid,failed:true,closed:true});
const result=await call(0,'poll');assert(result.match.finished);assert.equal(result.match.winner,null);assert.equal(result.me.rating,1000);assert.equal(result.me.played,0);assert.equal(result.me.abandons,0);
console.log('PASS: two confirmed desync reports void the set, including an immediate game close, with no points or abandonment penalty');
