'use strict';
function socialSignals(social){
    const unread={};
    for(const event of social?.events||[])if(event.kind==='message')unread[event.sender]=(unread[event.sender]||0)+1;
    const actions=[...(social?.incoming||[]).map(r=>({...r,actionKind:'friend'})),
        ...(social?.events||[]).filter(r=>r.kind==='invite').map(r=>({...r,actionKind:'invite'}))];
    return {unread,actions,total:(social?.incoming?.length||0)+(social?.events?.length||0)};
}
function newSocialSignals(events,seen){
    const fresh=(events||[]).filter(e=>e.kind==='message'&&!seen.has(e.id));
    for(const e of events||[])seen.add(e.id);
    if(seen.size>2048){const keep=Array.from(seen).slice(-1024);seen.clear();keep.forEach(id=>seen.add(id));}
    return fresh;
}
if(typeof module!=='undefined')module.exports={socialSignals,newSocialSignals};
