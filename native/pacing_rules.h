#pragma once
#include <stdint.h>

// Preserve 0.1.38.1's grid, speed and network correction. Only the OS wait changes.
enum CompetitivePaceKind { PaceLate, PaceWait, PaceReset };
struct CompetitivePacePlan { CompetitivePaceKind kind; uint64_t deadline, next; };
static inline CompetitivePacePlan CompetitivePlanPace(uint64_t now, uint64_t next, unsigned shift, uint64_t period) {
    if(next) next+=shift;
    if(next && now>=next && now-next<100000000ull) return {PaceLate,next,next+period};
    if(next>now && next-now<100000000ull) return {PaceWait,next,next+period};
    return {PaceReset,now,now+period};
}
