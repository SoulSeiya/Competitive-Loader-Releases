// Offline replay viewer only: render the game's existing local P1/P2 cameras.
// It neither advances the simulation twice nor changes replay input consumption.
extern "C" {
int BtlCam_UpdateOverride(void);
int BattleReplay_IsActive(void);
int Battle_IsSplitScreen(void);
int DemoCam_IsActive(void);
void BtlCam_SelectView(int);
void BtlCam_SetLayout(int,int);
void Demo_SetupBattle(void);
void *Battle_GetSetup(void);
void BattleSetup_Finish(void);
void Hud_SetReplayMode(int);
}

extern "C" void Competitive_ReplayCpuSetup(void) {
    Demo_SetupBattle();
    const char *record=SDL_getenv("BTC_REPLAY_RECORD_CPU");
    if(record && !strcmp(record,"1") && !Port_NetSession()) {
        unsigned char *setup=(unsigned char *)Battle_GetSetup();
        if(setup) {
            *(int *)(setup+8)=0; // Versus CPU/CPU, with the ordinary battle HUD (not the attract demo).
            *(int *)(setup+0x24)=1;
            BattleSetup_Finish(); // Keep the recorded setup identical to the fight being recorded.
        }
    }
}

extern "C" int Competitive_ReplayCameraOverride(void) {
    const char *enabled=SDL_getenv("BTC_REPLAY_SPLIT");
    if(!enabled || strcmp(enabled,"1") || Port_NetSession() ||
       !BattleReplay_IsActive() || !Battle_IsSplitScreen() || DemoCam_IsActive())
        return BtlCam_UpdateOverride();
    BtlCam_SelectView(0);
    BtlCam_SetLayout(1,1);
    BtlCam_SelectView(1);
    BtlCam_SetLayout(1,1);
    static bool logged;
    if(!logged) {
        logged=true;
        Hud_SetReplayMode(1); // The replay's normal full HUD; its initial mode hides the gauges.
        ScoreLog(stderr,"bt3: replay spectator: native P1/P2 split view active; offline playback\n");
    }
    return 0; // Battle_Update / BtlScene draw both views from this one simulation.
}
