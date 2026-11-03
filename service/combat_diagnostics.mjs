// Only bounded gameplay observations. No raw logs, pointers, tokens or paths.
import {cleanActivity} from './combat_activity.mjs';
export function cleanCombat(v){
 if(v===undefined||v===null)return null;
 const int=(n,a,b)=>Number.isInteger(n)&&n>=a&&n<=b;
 const obj=x=>x&&typeof x==='object'&&!Array.isArray(x);
 const bad=()=>{throw Error('Evidencia de combate inválida');};
 if(!obj(v)||v.source!=='native_trace_v1'||v.time_basis!=='pre_tick')bad();
 for(const k of ['epoch','confirmed_through'])if(!int(v[k],0,2147483647))bad();
 for(const k of ['target_blank','nearest_distance'])if(v[k]!==null&&!int(v[k],0,2147483647))bad();
 if(!Array.isArray(v.observations)||v.observations.length<1||v.observations.length>16)bad();
 const out={source:v.source,time_basis:v.time_basis,epoch:v.epoch,confirmed_through:v.confirmed_through,target_blank:v.target_blank,nearest_distance:v.nearest_distance,observations:[]};
 let previous=-1;
 for(const r of v.observations){
  if(!obj(r)||!int(r.blank,0,2147483647)||r.blank<=previous||(r.phase!==null&&!int(r.phase,0,6))||typeof r.resimulated!=='boolean'||typeof r.input_confirmed!=='boolean'||!Array.isArray(r.sides)||r.sides.length!==2)bad();
  previous=r.blank;
  const row={blank:r.blank,phase:r.phase,resimulated:r.resimulated,input_confirmed:r.input_confirmed&&r.blank<=out.confirmed_through,sides:[]};
  if(r.stage!==undefined){
   if(r.stage===null)row.stage=null;
   else{
    const s=r.stage;if(!obj(s))bad();
    for(const k of ['id','start_id'])if(s[k]!==null&&!int(s[k],0,4095))bad();
    if(s.catalog_name!==null&&(typeof s.catalog_name!=='string'||[...s.catalog_name].length>96||/[\u0000-\u001f\u007f-\u009f\u2028\u2029]/.test(s.catalog_name)))bad();
    if(![null,'engine_catalog'].includes(s.catalog_source)||(s.catalog_name!==null&&s.catalog_source!=='engine_catalog'))bad();
    row.stage={id:s.id,start_id:s.start_id,catalog_name:s.catalog_name,catalog_source:s.catalog_source};
   }
  }
  for(let side=0;side<2;side++){
   const f=r.sides[side];if(!obj(f)||f.side!==side+1)bad();const fighter={side:side+1};
   for(const [k,lo,hi] of [['roster_id',0,160],['character_id',0,160],['member',0,4],['team_size',1,5],['variant',0,3],['action_id',0,315],['action_class',0,4]]){if(f[k]!==null&&!int(f[k],lo,hi))bad();fighter[k]=f[k];}
   for(const [k,hi] of [['ability_id',32767],['action_frame',2147483647]])if(f[k]!==undefined){if(f[k]!==null&&!int(f[k],0,hi))bad();fighter[k]=f[k];}
   if(f.costume!==undefined){if(f.costume!==null&&!int(f.costume,1,256))bad();fighter.costume=f.costume;}
   if(f.name!==null&&(typeof f.name!=='string'||[...f.name].length>128||/[\u0000-\u001f\u007f-\u009f\u2028\u2029]/.test(f.name)))bad();
   fighter.name=f.name;row.sides.push(fighter);
  }
  out.observations.push(row);
 }
 if(v.events!==undefined)out.events=cleanActivity(v.events,out.confirmed_through);
 return out;
}
