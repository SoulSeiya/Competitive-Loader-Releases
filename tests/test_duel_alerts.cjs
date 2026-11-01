const assert=require('node:assert/strict');
const {incomingDuelOffers,createDuelAlertController}=require('../web_client/duel_alerts.js');
const event={kind:'challenge',id:'offer1',name:'Rival',ft:2,seconds:360,characters:2};
const social=(events)=>({social:{events}});
(async()=>{
    let shown=[],hidden=0,replyResolve,replies=[];
    const controller=createDuelAlertController({show:o=>shown.push(o),hide:()=>hidden++,pending:()=>{},reply:(o,a)=>{replies.push([o,a]);return new Promise(r=>replyResolve=r);}});
    // Old inbox-only behavior missed these offers entirely. Repeated polling
    // must not reopen or submit the same offer twice.
    controller.update(social([event,{kind:'message',id:'dm'}]));
    assert.equal(shown.length,1);assert.equal(shown[0].seconds,360);
    controller.update(social([event]));assert.equal(shown.length,1);
    // Use the actual response callback supplied to the host.
    let respond,now=1000,opened=0;
    const c=createDuelAlertController({now:()=>now,show:(o,fn)=>{respond=fn;opened++;},hide:()=>hidden++,pending:()=>{},reply:(o,a)=>{replies.push([o,a]);return new Promise(r=>replyResolve=r);}});
    c.update(social([event]));const first=respond(true);respond(true);
    assert.equal(replies.length,1);replyResolve(null);await first;
    const retry=respond(false);assert.equal(replies.length,2);replyResolve(true);await retry;
    c.update(social([event]));assert.equal(replies.length,2);
    assert.equal(opened,1);
    now+=21000;c.update(social([event]));assert.equal(opened,2);
    // Cancelled offers disappear, with the next offer surfaced automatically.
    controller.update(social([{...event,id:'offer2'}]));
    assert.equal(shown.at(-1).id,'offer2');assert.ok(hidden>0);
    const room={room_code:'BTC-X',self_id:2,duel:{id:'d',status:'pending',to:2,name1:'Host',ft:3,seconds:180,characters:1}};
    assert.equal(incomingDuelOffers({room})[0].kind,'room');
    assert.equal(incomingDuelOffers({room:{...room,self_id:1}}).length,0);
    assert.equal(incomingDuelOffers({room:{...room,duel:{...room.duel,status:'accepted'}}}).length,0);
    console.log('Duel alerts: social/room, repeat polls, double click, retry, cancellation OK');
})().catch(e=>{console.error(e);process.exitCode=1;});
