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
