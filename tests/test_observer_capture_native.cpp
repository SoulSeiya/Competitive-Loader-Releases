#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../native/observer_capture.h"
static BtcObserverShared capture;
static unsigned char pads[2][4096][18];
int main() {
    capture.header.first=capture.header.next=capture.header.read=1;
    memset(pads[0],17,sizeof(pads[0]));memset(pads[1],29,sizeof(pads[1]));
    assert(BtcCaptureConfirmed(capture,pads,4,12,5));
    assert(capture.frames[3].tick==3 && capture.frames[3].pads[0]==17 && capture.frames[3].pads[18]==29);
    assert(capture.frames[4].tick==0); // Speculative frame 4 never escapes.
    capture.header.next=4;
    assert(BtcCaptureConfirmed(capture,pads,2,12,5)); // Re-running old ticks emits nothing.
    assert(capture.frames[4].tick==0);
    assert(BtcCaptureConfirmed(capture,pads,8,12,5)); // Unknown remote frames remain private too.
    assert(capture.frames[4].tick==4 && capture.frames[5].tick==0);
    capture.header.next=5;
    assert(!BtcCaptureConfirmed(capture,pads,5000,6000,6000));
    assert(capture.header.error && capture.header.closed); // Lost source history stops streaming, never the match.
    capture={};capture.header.next=9000;capture.header.read=1;
    assert(!BtcCaptureConfirmed(capture,pads,9001,10000,10000)); // Slow consumer cannot overwrite data silently.
    puts("Observer capture OK: confirmed inputs only, rollback safe, bounded nonblocking source and consumer rings.");
}
