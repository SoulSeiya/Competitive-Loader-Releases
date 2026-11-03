export const ADMIN_HTML=String.raw`<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Rising Battle · Diagnósticos</title>
<style>
:root{font:15px system-ui;color:#e8eef5;background:#080e17;color-scheme:dark}*{box-sizing:border-box}body{margin:0}header{height:82px;border-bottom:1px solid #263344;display:flex;align-items:center;justify-content:space-between;padding:0 4vw}h1{font-size:23px;margin:4px 0}small,.muted{color:#8ba4bb}small{font-size:11px;letter-spacing:1.6px}main{max-width:1500px;margin:auto;padding:30px 4vw}nav{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:20px 0}button,select{font:inherit;padding:10px 16px;background:#142233;border:1px solid #34475d;color:#e8eef5;cursor:pointer;border-radius:5px;transition:background .15s,border-color .15s}button:hover{background:#20364c;border-color:#ff9d53}button.primary{background:#d8813b;color:#07101b;border-color:#d8813b}button:disabled{opacity:.4;cursor:default}#workspace{display:grid;grid-template-columns:minmax(280px,1fr) minmax(400px,2fr);gap:28px}.case{width:100%;text-align:left;margin-bottom:10px;padding:16px}.case strong{display:block;margin-bottom:8px}.tag{display:inline-block;color:#6ad9ee;font-size:12px;margin-right:15px}.detail{border-top:2px solid #df914e;padding-top:18px;min-width:0}.rule{padding:10px 0;color:#a3bad0;border-bottom:1px solid #263344}#error{color:#ffb0a3;min-height:22px}table{width:100%;border-collapse:collapse;margin-top:20px}th,td{text-align:left;padding:12px 8px;border-bottom:1px solid #263344;font-size:13px;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px ui-monospace;color:#a7bed3;background:#0e1926;padding:18px;border-radius:6px;max-height:480px;overflow:auto}section:empty{display:none}#toolbar{display:flex;gap:10px;flex-wrap:wrap}h2{font-size:22px}h3{font-size:16px}.note{padding:16px;background:#101e2d;border-left:3px solid #56bbd3;line-height:1.6}footer{margin-top:25px;color:#7c96af;font-size:12px}@media(max-width:900px){#workspace{grid-template-columns:1fr}header{height:auto;min-height:82px;padding:16px 4vw}h1{font-size:19px}}
</style>
<header><div><small>RISING BATTLE / EQUIPO BTC</small><h1>Centro de diagnósticos</h1></div><span id="mode" class="tag">Acceso privado</span></header><main>
<p class="muted">Compara la evidencia de ambos jugadores. Una diferencia detectada orienta la investigación; no demuestra por sí sola la causa.</p>
<nav><select id="filter"><option value="all">Todos los casos</option><option value="pending">Pendientes</option><option value="investigating">En investigación</option><option value="resolved">Resueltos</option></select><button id="refresh">Actualizar</button><span id="local-tools" hidden><button id="import">Importar registros locales</button> <button id="online">Abrir panel en línea ↗</button></span></nav><div id="error" role="alert"></div>
<div id="workspace"><section><div id="cases">Cargando…</div><button id="more" hidden>Ver anteriores</button></section><section class="detail" id="detail"><h2>Selecciona una partida</h2><p class="muted">Aquí aparecerán las versiones, huellas, red y frame de divergencia.</p></section></div>
<footer>Solo información técnica filtrada. Los clientes con captura de combate incluyen personaje, forma y acciones recientes; los anteriores no contienen esos datos. La última acción observada no demuestra la causa. Retención: 14 días.</footer></main>
<script>
let local=false,selection=null,cursor=null,busy=false;
const $=s=>document.querySelector(s);
const element=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
async function request(path,body){
 if(local)return window.pywebview.api.call(path,body||null);
 const options={credentials:'same-origin',cache:'no-store',redirect:'error'};
 if(body)Object.assign(options,{method:'POST',headers:{'Content-Type':'application/json','X-BTC-Admin':'1'},body:JSON.stringify(body)});
 const r=await fetch('/admin/api/diagnostics'+path,options);if(!r.ok)throw Error(r.status===401||r.status===403?'La sesión privada no está autorizada. Vuelve a iniciar sesión.':'No se pudo consultar el servicio ('+r.status+').');return r.json();
}
async function load(append=false){
 if(busy)return;busy=true;$('#error').textContent='';
 try{const data=await request('?status='+$('#filter').value+(append&&cursor?'&before='+cursor:''));if(!append)$('#cases').replaceChildren();
 for(const c of data.cases){const b=element('button',undefined,'case');b.append(element('strong','Desync Match · '+(c.context.names||['Player 1','Player 2']).join(' / ')),element('span',c.sides+'/2 lados · '+c.reports+' informes','tag'),element('span',c.status,'tag'),element('p',new Date(c.received).toLocaleString()+' · '+c.battle.slice(0,8),'muted'));b.onclick=()=>detail(c);$('#cases').append(b);}
 if(!$('#cases').children.length)$('#cases').append(element('p','No hay reportes para este filtro.','muted'));cursor=data.next;$('#more').hidden=!cursor;
 }catch(e){$('#error').textContent=e.message;}finally{busy=false;}
}
async function detail(c){
 $('#error').textContent='';try{selection=c;const data=await request('?battle='+encodeURIComponent(c.battle)+'&match='+c.match_no),box=$('#detail');box.replaceChildren();
 box.append(element('small','CASO '+c.battle+' / '+c.match_no),element('h2','Desync Match · '+(c.context.names||['Player 1','Player 2']).join(' / ')));
 const rules=c.context.rules||{};box.append(element('p',c.context.source==='history'?'Histórico · relación inferida por frame y hashes. A/B no identifica al P1/P2 del juego.':'FT'+(rules.ft??'?')+' · '+(rules.seconds??'?')+' segundos · '+(rules.characters??'?')+' personajes','rule'));
 box.append(element('p',data.comparison.title,'note'));
 if(data.comparison.note)box.append(element('p',data.comparison.note,'muted'));
 if(data.comparison.differences.length){const table=element('table'),head=element('tr');for(const x of ['Dato','P1','P2'])head.append(element('th',x));table.append(head);for(const d of data.comparison.differences){const row=element('tr');for(const x of [d.group+' / '+d.key,d.p1??'No capturado',d.p2??'No capturado'])row.append(element('td',x));table.append(row);}box.append(table);}
 const tools=element('nav');for(const [s,label] of [['pending','Pendiente'],['investigating','Investigar'],['resolved','Resuelto']]){const b=element('button',label);b.onclick=async()=>{try{await request('',{battle:c.battle,match:c.match_no,status:s});await load();}catch(e){$('#error').textContent=e.message;}};tools.append(b);}box.append(tools);
 for(const r of data.reports){
  box.append(element('h3',(r.context.source==='history'?'Informe '+(r.context.side===1?'A':'B'):'P'+r.context.side)+' · '+(r.name||'Jugador')+' · '+r.report_id.slice(0,8)));
  const trace=r.combat,last=trace?.observations?.at(-1);
  if(last){
   const stage=last.stage;
   box.append(element('p',stage?'Escenario ID '+(stage.id??'?')+' · inicial '+(stage.start_id??'?')+(stage.catalog_name?' · catálogo del motor: '+stage.catalog_name+' (puede diferir en BTC modificada)':''):'Escenario no capturado en este informe.','rule'));
   box.append(element('p','Estado al inicio del tick · frame '+last.blank+' · distancia a divergencia: '+(trace.nearest_distance??'desconocida')+' · '+(last.input_confirmed?'entradas confirmadas':'observación predictiva'),'rule'));
   const table=element('table'),head=element('tr');for(const label of ['Lado','Personaje / forma','Traje','ID de acción','Clase'])head.append(element('th',label));table.append(head);
   for(const f of last.sides){const row=element('tr');for(const text of ['P'+f.side,(f.name||'Nombre no capturado')+' · ID '+(f.character_id??'?')+' / base '+(f.roster_id??'?'),f.costume??'No capturado',f.action_id??'No capturado',f.action_class??'No capturada'])row.append(element('td',String(text)));table.append(row);}box.append(table);
  }else box.append(element('p','Este informe no contiene un registro de personajes y acciones.','muted'));
  if(trace?.events?.length){
   box.append(element('h3','Habilidades y movimientos observados'));
   const table=element('table'),head=element('tr');for(const label of ['Frame','Jugador','Personaje','Evento','Entradas'])head.append(element('th',label));table.append(head);
   for(const e of trace.events){
    const player=r.context.source==='history'?'P'+e.side+' (nombre no verificado)':((r.context.names||[])[e.side-1]||'P'+e.side);
    let label='Movimiento/estado · acción '+e.action_id;
    if(e.kind==='ability')label=(e.observed_start?'Usa habilidad ':'Habilidad en curso: ')+(e.ability_class<2?'Blast 1 / '+(e.ability_class+1):e.ability_class===4?'Definitiva':'Blast 2 / '+(e.ability_class-1))+' · ID '+(e.ability_id??'no capturado')+' · acción '+e.action_id;
    if(r.divergence){const gap=r.divergence.blank-e.blank;label+=' · '+(gap>=0?gap+' blanks antes de la divergencia':Math.abs(gap)+' blanks después de la divergencia');}
    const row=element('tr');for(const text of [e.blank,player,(e.character_name||'ID '+e.character_id)+(e.costume?' · traje '+e.costume:''),label,e.input_confirmed?'Confirmadas':'Predictivas'])row.append(element('td',String(text)));table.append(row);
   }
   box.append(table,element('p','Transiciones observadas; no prueban impacto ni causa del desync. Los nombres de técnicas modificadas no se deducen del ID.','muted'));
  }
  const info={combate:trace||null,resumen:r.summary||null,divergencia:r.divergence,red:r.network,versiones:r.versions,huellas:r.fingerprint};const technical=element('details');technical.append(element('summary','Detalles técnicos'),element('pre',JSON.stringify(info,null,2)));box.append(technical);
 }
 }catch(e){$('#error').textContent=e.message;}
}
$('#refresh').onclick=()=>load();$('#filter').onchange=()=>load();$('#more').onclick=()=>load(true);
$('#import').onclick=async()=>{try{await window.pywebview.api.import_logs();await load();}catch(e){$('#error').textContent=e.message;}};
$('#online').onclick=()=>window.pywebview.api.open_online();
if(location.protocol==='https:')load();else window.addEventListener('pywebviewready',()=>{local=true;$('#mode').textContent='Vista local · sin conexión al servicio';$('#local-tools').hidden=false;load();});
</script></html>`;
