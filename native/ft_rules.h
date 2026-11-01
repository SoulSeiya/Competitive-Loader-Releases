#pragma once
#include <stdint.h>

// Native rules use 0..11 for battle/DP/time, 12 for legacy speed, 16..23
// for speed percent. Bits 13..15 travel intact in HELLO_ACK and CONFIG.
inline unsigned CompetitiveFt(uint32_t rules) {
    const unsigned ft = (rules >> 13) & 7;
    return ft <= 5 ? ft : 0;
}
inline uint32_t CompetitiveFtRules(uint32_t rules, unsigned ft) {
    return (rules & ~(7u << 13)) | ((ft <= 5 ? ft : 0) << 13);
}
// Private tournament cap, negotiated in the same rules word as FT/time.
// Zero means ordinary five-member teams. Bits 24..26 are unused upstream.
inline unsigned CompetitiveTeamLimit(uint32_t rules) {
    unsigned n=(rules>>24)&7u;
    return n>=1 && n<=5?n:5;
}
inline uint32_t CompetitiveTeamLimitRules(uint32_t rules,unsigned limit) {
    return (rules&~(7u<<24))|((limit>=1 && limit<=5?limit:0)<<24);
}
inline int CompetitiveTournamentTime(unsigned seconds) {
    switch(seconds) {case 180:return 0;case 240:return 1;case 360:return 2;case 480:return 3;default:return -1;}
}
