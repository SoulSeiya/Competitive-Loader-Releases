export function cleanActivity(events,frontier){
 const int=(n,a,b)=>Number.isInteger(n)&&n>=a&&n<=b;
 const obj=x=>x&&typeof x==='object'&&!Array.isArray(x);
 const bad=()=>{throw Error('Eventos inválidos');};
 if(!Array.isArray(events)||events.length>24)bad();
 const out=[];let previous=[-1,0];
 for(const e of events){
  if(!obj(e))bad();const r={};
  for(const [k,lo,hi,nullable] of [['blank',0,2147483647,false],['side',1,2,false],['character_id',0,160,false],['ability_class',0,4,true],['ability_id',0,32767,true],['action_id',0,315,false],['stage_id',0,4095,true]]){if(!(nullable&&e[k]===null)&&!int(e[k],lo,hi))bad();r[k]=e[k];}
  if(r.blank<previous[0]||(r.blank===previous[0]&&r.side<=previous[1]))bad();previous=[r.blank,r.side];
  if(e.character_name!==null&&(typeof e.character_name!=='string'||[...e.character_name].length>128||/[\u0000-\u001f\u007f-\u009f\u2028\u2029]/.test(e.character_name)))bad();
  if(e.costume!==undefined){if(e.costume!==null&&!int(e.costume,1,256))bad();r.costume=e.costume;}
  if(!['ability','action'].includes(e.kind)||typeof e.observed_start!=='boolean'||typeof e.input_confirmed!=='boolean'||(e.kind==='ability')!==(r.ability_class!==null))bad();
  Object.assign(r,{character_name:e.character_name,kind:e.kind,observed_start:e.observed_start,input_confirmed:e.input_confirmed&&r.blank<=frontier});out.push(r);
 }
 return out;
}
