'use strict';
// Incoming offers only; accepting still goes through the existing backend.
function incomingDuelOffers(snapshot) {
    const room=snapshot?.room, duel=room?.duel, offers=[];
    if(duel?.id && duel.status==='pending' && duel.to===room.self_id) {
        offers.push({key:'room:'+room.room_code+':'+duel.id,name:duel.name1,
            ft:duel.ft,seconds:duel.seconds,characters:duel.characters,
            kind:'room',id:duel.id});
    }
    for(const event of snapshot?.social?.events||[]) {
        if(event.kind==='challenge' && event.id) offers.push({
            key:'social:'+event.id,name:event.name,ft:event.ft,
            seconds:event.seconds,characters:event.characters,kind:'social',id:event.id});
    }
    return offers;
}

function createDuelAlertController(host) {
    const handled=new Map(),clock=host.now||Date.now;
    let active=null,busy=false,available=[];
    function update(snapshot) {
        available=incomingDuelOffers(snapshot);
        // The backend command is queued, not a server acknowledgement. If an
        // offer remains pending after two social polls, let the user retry.
        for(const [key,until] of handled) if(clock()>=until || !available.some(o=>o.key===key)) handled.delete(key);
        if(active && !available.some(o=>o.key===active.key)) {
            host.hide();active=null;
        }
        if(busy || active) return;
        const next=available.find(o=>!handled.has(o.key));
        if(next) { active=next;host.show(next,respond); }
    }
    async function respond(accept) {
        if(busy || !active) return;
        const offer=active;
        busy=true;host.pending(true);
        try {
            const ok=await host.reply(offer,accept);
            if(ok) {
                handled.set(offer.key,clock()+20000);
                if(active?.key===offer.key) {host.hide();active=null;}
            }
        } finally {
            busy=false;host.pending(false);
            // Only show offers still present in the latest poll.
            if(!active) {
                const next=available.find(o=>!handled.has(o.key));
                if(next) {active=next;host.show(next,respond);}
            }
        }
    }
    return {update};
}

if(typeof module!=='undefined') module.exports={incomingDuelOffers,createDuelAlertController};
