#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <cassert>
#include <vector>
static const char *flag;
static int online,active,split,cinematic,delegated;
static std::vector<int> views,layouts;
alignas(8) static unsigned char setup[0x5A8];
static int setups,finishes,hud;
extern "C" void Hud_SetReplayMode(int mode) {hud=mode;}
extern "C" void Demo_SetupBattle() {++setups;}
extern "C" void *Battle_GetSetup() {return setup;}
extern "C" void BattleSetup_Finish() {++finishes;}
extern "C" const char *SDL_getenv(const char *) {return flag;}
extern "C" int Port_NetSession() {return online;}
extern "C" int BattleReplay_IsActive() {return active;}
extern "C" int Battle_IsSplitScreen() {return split;}
extern "C" int DemoCam_IsActive() {return cinematic;}
extern "C" int BtlCam_UpdateOverride() {++delegated;return 7;}
extern "C" void BtlCam_SelectView(int index) {views.push_back(index);}
extern "C" void BtlCam_SetLayout(int layout,int apply) {assert(apply==1);layouts.push_back(layout);}
#define ScoreLog fprintf
#include "../native/competitive_replay_view.cpp"
int main() {
    active=split=1;
    assert(Competitive_ReplayCameraOverride()==7);
    flag="1";
    assert(Competitive_ReplayCameraOverride()==0);
    assert((views==std::vector<int>{0,1}));
    assert((layouts==std::vector<int>{1,1}));
    assert(hud==1);
    online=1;assert(Competitive_ReplayCameraOverride()==7);online=0;
    active=0;assert(Competitive_ReplayCameraOverride()==7);active=1;
    split=0;assert(Competitive_ReplayCameraOverride()==7);split=1;
    cinematic=1;assert(Competitive_ReplayCameraOverride()==7);cinematic=0;
    assert(delegated==5);
    assert(views.size()==2);
    flag=nullptr;Competitive_ReplayCpuSetup();assert(setups==1 && finishes==0);
    *(int *)(setup+8)=7;
    flag="1";Competitive_ReplayCpuSetup();
    assert(*(int *)(setup+8)==0 && *(int *)(setup+0x24)==1 && finishes==1);
    online=1;Competitive_ReplayCpuSetup();assert(finishes==1);
    puts("Replay view OK");
}
