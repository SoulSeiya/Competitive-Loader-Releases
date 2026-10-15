#include <assert.h>
#include <stdio.h>
#include "../native/score_tracker.h"
#include "../native/window_policy.h"
#include "../native/ft_rules.h"

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
    for (unsigned ft = 1; ft <= 5; ++ft) {
        const uint32_t base = (114u << 16) | 0x1321u;
        const uint32_t encoded = CompetitiveFtRules(base, ft);
        assert(CompetitiveFt(encoded) == ft);
        assert((encoded & ~(7u << 13)) == (base & ~(7u << 13)));
        s.reset();
        uint32_t tick = 100;
        s.begin_tick(tick, tick, true, false, ft);
        assert(s.observe(4)); // draws do not advance the FT
        ++tick; s.begin_tick(tick, tick, true, false, ft);
        assert(s.draws == 1 && !s.setWinner);
        for (unsigned round = 0; round < ft; ++round) {
            s.new_round();
            ++tick; s.begin_tick(tick, tick, true, false, ft);
            assert(s.observe(2));
            ++tick; s.begin_tick(tick, tick, true, false, ft);
        }
        assert(s.wins[1] == ft && s.wins[0] == 0 && s.setWinner == 2);
        assert(!s.observe(1));
        assert(!s.should_leave(s.completedTick + 299, false));
        assert(!s.should_leave(s.completedTick + 300, true));
        assert(s.should_leave(s.completedTick + 300, false));
        ++tick; s.begin_tick(tick, tick, false, false, ft);
        assert(!s.active && !s.setWinner && !s.target);
    }
    assert(CompetitiveFtRules(0xffffffffu, 8) == (0xffffffffu & ~(7u << 13)));
    assert(CompetitiveFt(7u << 13) == 0);
    // An apparent match point must disappear when rollback changes the winner.
    s.reset();
    s.begin_tick(10, 10, true, false, 1);
    assert(s.observe(1));
    s.begin_tick(10, 10, true, true, 1);
    assert(s.observe(2));
    s.begin_tick(11, 11, true, false, 1);
    assert(s.setWinner == 2 && s.wins[0] == 0);
    puts("Score OK: rematches, confirmation, corrected winners, rollback, draws, aborts, session reset.");
}
