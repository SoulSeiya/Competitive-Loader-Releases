#pragma once
#include <stdint.h>

// Presentation state only. Never writes game memory or contributes to netplay.
// A small observer history follows native rewinds; only confirmed events count.
struct ScoreTracker {
    struct Snapshot { uint32_t tick; bool counted; } history[64];
    struct Event { uint32_t tick; unsigned winner; } pending[128];
    unsigned wins[2], draws, pendingCount;
    uint32_t lastTick;
    bool active, counted, hasTick;

    void reset() {
        wins[0] = wins[1] = draws = pendingCount = 0;
        lastTick = 0;
        active = counted = hasTick = false;
        for (unsigned i = 0; i < 64; ++i) history[i] = {UINT32_MAX, false};
    }
    void begin_tick(uint32_t tick, uint32_t confirmed, bool online, bool resim) {
        if (!online) { reset(); return; }
        if (!active) { reset(); active = true; }
        if (hasTick && tick <= lastTick) {
            const Snapshot &old = history[tick % 64];
            counted = old.tick == tick ? old.counted : false;
            unsigned n = 0;
            for (unsigned i = 0; i < pendingCount; ++i)
                if (pending[i].tick < tick) pending[n++] = pending[i];
            pendingCount = n;
        }
        history[tick % 64] = {tick, counted};
        lastTick = tick;
        hasTick = true;
        if (resim) return;
        unsigned n = 0;
        for (unsigned i = 0; i < pendingCount; ++i) {
            if (pending[i].tick < confirmed) {
                const unsigned result = pending[i].winner;
                if (result == 1) ++wins[0];
                else if (result == 2) ++wins[1];
                else if (result == 4) ++draws;
            } else pending[n++] = pending[i];
        }
        pendingCount = n;
    }
    void new_round() { counted = false; }
    bool observe(unsigned result) {
        if (!active || counted || (result & 0x18)) return false;
        const unsigned winner = result & 7;
        if (winner != 1 && winner != 2 && winner != 4) return false;
        if (pendingCount == 128) return false;
        pending[pendingCount++] = {lastTick, winner};
        counted = true;
        return true;
    }
};
