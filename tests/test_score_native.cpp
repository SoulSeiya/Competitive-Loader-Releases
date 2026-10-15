#include <assert.h>
#include <stdio.h>
#include "../native/score_tracker.h"
#include "../native/window_policy.h"

int main() {
    assert(CompetitiveWindowBlocks(0x112, 0xf012, true));
    assert(CompetitiveWindowBlocks(0x112, 0xf008, true));
    assert(CompetitiveWindowBlocks(0xa1, 2, true));
    assert(CompetitiveWindowBlocks(0xa1, 10, true));
    assert(CompetitiveWindowBlocks(0xa4, 2, true));
    assert(CompetitiveWindowBlocks(0x112, 0xf100, true));
    assert(!CompetitiveWindowBlocks(0x112, 0xf010, false));
    assert(!CompetitiveWindowBlocks(0xa1, 2, false));
    assert(!CompetitiveWindowBlocks(0x112, 0xf060, true)); // close stays available
    assert(!CompetitiveWindowBlocks(0xa1, 20, true));   // close button
    assert(!CompetitiveWindowBlocks(0x100, 0x41, true)); // game input
    ScoreTracker s = {};
    s.reset();
    assert(!s.observe(1));
    s.begin_tick(0, 0, true, false);
    assert(s.observe(1));
    assert(!s.observe(1));
    s.begin_tick(1, 0, true, false);
    assert(s.wins[0] == 0); // speculative result is not displayed
    s.begin_tick(0, 0, true, true); // rollback removes the wrong winner
    assert(s.observe(2));
    s.begin_tick(1, 1, true, true);
    assert(s.wins[1] == 0); // never commit during resimulation
    s.begin_tick(2, 2, true, false);
    assert(s.wins[0] == 0 && s.wins[1] == 1);
    assert(!s.observe(2));
    s.new_round();
    s.begin_tick(3, 3, true, false);
    assert(s.observe(1));
    s.begin_tick(4, 4, true, false);
    assert(s.wins[0] == 1 && s.wins[1] == 1);
    s.new_round();
    s.begin_tick(5, 5, true, false);
    assert(!s.observe(8) && !s.observe(16) && !s.observe(0));
    assert(s.observe(4));
    s.begin_tick(6, 6, true, false);
    assert(s.draws == 1 && s.wins[0] == 1);
    // Rewind across the boundary of a new round. The previous round's
    // counted latch must be restored without recounting its confirmed win.
    s.new_round();
    s.begin_tick(7, 7, true, false);
    assert(s.observe(1));
    s.begin_tick(6, 6, true, true);
    assert(!s.observe(4));
    s.new_round();
    s.begin_tick(7, 7, true, true);
    assert(s.observe(2));
    s.begin_tick(8, 8, true, false);
    assert(s.wins[0] == 1 && s.wins[1] == 2 && s.draws == 1);
    for (unsigned tick = 9; tick < 2000; ++tick) {
        s.new_round();
        s.begin_tick(tick, tick, true, false);
        assert(s.observe(1));
    }
    s.begin_tick(2000, 2000, true, false);
    assert(s.wins[0] == 1992 && s.wins[1] == 2 && s.pendingCount == 0);
    s.begin_tick(2001, 2001, false, false);
    assert(!s.active && s.wins[0] == 0 && s.draws == 0);
    s.begin_tick(0, 0, true, false);
    assert(s.active && s.wins[1] == 0 && !s.counted);
    puts("Score OK: rematches, confirmation, corrected winners, rollback, draws, aborts, session reset.");
}
