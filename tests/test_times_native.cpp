#include <assert.h>
#include <stdio.h>
#include "../native/competitive_times.cpp"
static bool online;
static int loads;
extern "C" {
int16_t gBattleTimeLimitTbl[8] = {-1,60,90,180,240,111,222,333};
int Port_NetSession(void) { return online; }
void Battle_Load(void) {
    const int16_t *expected;
    const int16_t comp[4] = {180,240,360,480};
    const int16_t orig[4] = {60,90,180,240};
    expected = online ? comp : orig;
    for (int i=0; i<4; ++i) assert(gBattleTimeLimitTbl[i+1] == expected[i]);
    ++loads;
}
}
int main() {
    online = true;
    Competitive_TimeBattleLoad();
    Competitive_TimeBattleLoad(); // repeated load/rematch preparation
    online = false;
    Competitive_TimeBattleLoad();
    assert(loads == 3);
    assert(gBattleTimeLimitTbl[0] == -1);
    assert(gBattleTimeLimitTbl[5] == 111 && gBattleTimeLimitTbl[7] == 333);
    puts("Timers OK: all online choices before Battle_Load, offline restore, untouched unlimited/other entries.");
}
