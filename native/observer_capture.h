#pragma once
#include "observer_shared.h"
// The source ring belongs to native netcode. Never inspect its predicted sUsed
// track: only sIn entries below the committed bound can be published.
inline bool BtcCaptureConfirmed(BtcObserverShared &out, const unsigned char source[2][4096][18],
        uint32_t confirmed, uint32_t available0, uint32_t available1) {
    if(out.header.closed || out.header.error) return false;
    uint32_t end=confirmed;
    if(available0<end)end=available0;
    if(available1<end)end=available1;
    if(end<out.header.next)return true; // A rollback cannot retract already confirmed input.
    const uint32_t read=out.header.read_serial==out.header.serial?out.header.read:out.header.first;
    if(read>end || end-out.header.next>4096 || end-read>BTC_OBSERVER_RING) {
        out.header.error=1;out.header.closed=1;return false;
    }
    for(uint32_t tick=out.header.next;tick<end;++tick) {
        BtcObserverFrame &frame=out.frames[tick%BTC_OBSERVER_RING];
        frame.tick=tick;
        for(unsigned p=0;p<2;++p)for(unsigned n=0;n<18;++n)frame.pads[p*18+n]=source[p][tick%4096][n];
    }
    return true; // The caller publishes header.next after its release barrier.
}
