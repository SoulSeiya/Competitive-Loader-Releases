#include <stdint.h>

extern "C" int Port_NetSession(void);
extern "C" void Battle_Load(void);
extern "C" int16_t gBattleTimeLimitTbl[8];

// The lobby transmits the original choice index. Both peers map that index to
// the same competitive duration before the official battle loader runs.
extern "C" void Competitive_TimeBattleLoad(void) {
    const int16_t original[4] = {60, 90, 180, 240};
    const int16_t competitive[4] = {180, 240, 360, 480};
    const int16_t *values = Port_NetSession() ? competitive : original;
    for (int i = 0; i < 4; ++i) gBattleTimeLimitTbl[i + 1] = values[i];
    Battle_Load();
}
