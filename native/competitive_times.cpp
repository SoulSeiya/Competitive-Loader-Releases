#include <stdint.h>

extern "C" int Port_NetSession(void);
extern "C" void Battle_Load(void);
extern "C" int16_t gBattleTimeLimitTbl[8];
extern "C" void Port_NetRules(int *, int *, int *);
extern "C" void *Battle_GetSetup(void);
extern "C" unsigned char gBattleReplay[];

// The lobby transmits the original choice index. Both peers map that index to
// the same competitive duration before the official battle loader runs.
extern "C" void Competitive_TimeBattleLoad(void) {
    const int16_t original[4] = {60, 90, 180, 240};
    const int16_t competitive[4] = {180, 240, 360, 480};
    const int16_t *values = Port_NetSession() ? competitive : original;
    for (int i = 0; i < 4; ++i) gBattleTimeLimitTbl[i + 1] = values[i];
    if(Port_NetSession()) {
        int type,dp,time;
        Port_NetRules(&type,&dp,&time);
        if(time>=0 && time<=4) {
            // The menu can restore its save default after the session's initial setup.
            // Apply the negotiated choice to the actual battle and its replay copy.
            const int index=time==4 ? 0 : time+1;
            unsigned char *setup=(unsigned char *)Battle_GetSetup();
            if(setup) *(int *)(setup+0x10)=index;
            *(int *)(gBattleReplay+0x10)=index;
        }
    }
    Battle_Load();
}
