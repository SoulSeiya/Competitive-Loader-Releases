#include <assert.h>
#include "../native/pacing_rules.h"
int main() {
    const uint64_t p=16683350ull;
    auto q=CompetitivePlanPace(1000000000,0,1000,p);
    assert(q.kind==PaceReset&&q.next==1000000000+p);
    q=CompetitivePlanPace(1000,2000,500,p);
    assert(q.kind==PaceWait&&q.deadline==2500&&q.next==2500+p);
    q=CompetitivePlanPace(2200,2000,0,p);
    assert(q.kind==PaceLate&&q.next==2000+p);
    q=CompetitivePlanPace(102000000,2000,0,p);
    assert(q.kind==PaceReset&&q.next==102000000+p);
    q=CompetitivePlanPace(1000,200000000,0,p);
    assert(q.kind==PaceReset);
    // The exact period is kept at every supported offline/online speed.
    for(unsigned speed=500;speed<=2000;speed+=10) {
        uint64_t period=p*1000/speed;
        uint64_t next=1000000000;
        for(unsigned tick=0;tick<600;tick++) {
            auto r=CompetitivePlanPace(next-1000,next,0,period);
            assert(r.kind==PaceWait&&r.next==next+period);next=r.next;
        }
    }
}
