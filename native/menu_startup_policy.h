#pragma once
#include <stdint.h>
struct CompetitiveMenuHelloCache {
    uint64_t last = 0;
    bool requested = false;
    bool request(uint64_t now) {
        if (requested && now - last < 60000) return false;
        requested = true;
        last = now;
        return true;
    }
};
