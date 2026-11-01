// Private opt-in spectator lab. Shared-memory IO only; no game-thread networking.
// Session entry/return uses the engine's existing same-process state exchange.
#include "observer_capture.h"
extern "C" {
extern unsigned char sIn[2][4096][18];
extern unsigned sHave[2], sSeed, sOpts[2], sTick;
extern int sMode, sSession, sConnected, sMe, sResim, sArrived;
extern char sNames[2][20];
extern uint32_t gBootCard,gLogo,gMcFlow;
int Port_SessionCan(void);
void Port_SessionRequest(int,const char *,int);
void Port_SessionReturn(void);
void Port_NetInput(int,unsigned char *);
int Port_NetView(void);
int Port_NetWarp(void);
void Port_NetArrived(void);
}
static BtcObserverShared *observerShared;
static volatile LONG observerActive;
static bool observerRequested, observerOldSaveSet;
static char observerOldSave[1024];
static unsigned char observerPads[36];
static const unsigned char observerIdle[18]={255,255,128,128,128,128};
static bool observerSaveEnvironment(const char *value) {
    // The reviewed engine imports getenv/_putenv_s from msvcrt.dll. SDL3 uses
    // another CRT: setting only SDL's environment leaves the engine unchanged.
    typedef int (*Set)(const char *,const char *);
    Set set=(Set)GetProcAddress(GetModuleHandleW(L"msvcrt.dll"),"_putenv_s");
    return set && SetEnvironmentVariableA("BT3_SAVES",value) && set("BT3_SAVES",value?value:"")==0;
}

static bool observerMap() {
    if(observerShared)return true;
    const char *enabled=SDL_getenv("BTC_OBSERVER_LAB");
    const char *name=SDL_getenv("BTC_OBSERVER_BRIDGE");
    if(!enabled || strcmp(enabled,"1") || !name || !*name)return false;
    HMODULE kernel=GetModuleHandleW(L"kernel32.dll");
    RisingOpenMapping open=(RisingOpenMapping)GetProcAddress(kernel,"OpenFileMappingA");
    RisingMapView map=(RisingMapView)GetProcAddress(kernel,"MapViewOfFile");
    RisingCloseHandle close=(RisingCloseHandle)GetProcAddress(kernel,"CloseHandle");
    if(!open || !map || !close)return false;
    HANDLE handle=open(FILE_MAP_READ|FILE_MAP_WRITE,FALSE,name);
    if(!handle)return false;
    observerShared=(BtcObserverShared *)map(handle,FILE_MAP_READ|FILE_MAP_WRITE,0,0,sizeof(BtcObserverShared));
    close(handle);
    if(!observerShared || observerShared->header.magic!=BTC_OBSERVER_MAGIC || observerShared->header.version!=1) {
        observerShared=NULL;return false;
    }
    return true;
}
static bool observerIsActive() { return InterlockedCompareExchange(&observerActive,0,0)!=0; }
static void observerCaptureBegin(int role) {
    if(role!=1 || !observerMap())return;
    const char *labCapture=SDL_getenv("BTC_OBSERVER_CAPTURE");
    if((!risingState.connected || risingState.tournament.role!=1) && (!labCapture || strcmp(labCapture,"1")))return;
    BtcObserverHeader &h=observerShared->header;
    const unsigned serial=(h.serial&~1u)+1;
    InterlockedExchange((volatile LONG *)&h.serial,(LONG)serial);
    h.mode=1;h.error=h.closed=0;
    h.seed=sSeed;h.rules=sRules;h.options[0]=sOpts[0];h.options[1]=sOpts[1];
    h.first=h.next=1;h.scores[0]=h.scores[1]=0;
    SDL_snprintf(h.names[0],sizeof(h.names[0]),"%s",sNames[0]);
    SDL_snprintf(h.names[1],sizeof(h.names[1]),"%s",sNames[1]);
    MemoryBarrier();InterlockedExchange((volatile LONG *)&h.serial,(LONG)(serial+1));
    fprintf(stderr,"bt3: spectator lab: confirmed input publisher started\n");
}
static void observerCaptureTick(unsigned tick,unsigned checked,unsigned a,unsigned b) {
    if(!observerShared || observerShared->header.mode!=1)return;
    BtcObserverHeader &h=observerShared->header;
    if(tick%1200==0 && gProgress)fprintf(stderr,"bt3: spectator lab: tick=%u mode=%d flags=%x menu=%d arrived=%d\n",tick,*(int *)((uintptr_t)gProgress+0x18),*(unsigned *)((uintptr_t)gProgress+0x14),gPortMenuMode,sArrived);
    if(tick%1200==0)fprintf(stderr,"bt3: spectator lab: boot=%x logo=%x flow=%x state=%d\n",gBootCard,gLogo,gMcFlow,gMcFlow?*(int *)((uintptr_t)gMcFlow+0x24):-1);
    const unsigned end=checked<tick?checked:tick;
    if(BtcCaptureConfirmed(*observerShared,sIn,end,sHave[0],sHave[1])) {
        unsigned limit=end;if(sHave[0]<limit)limit=sHave[0];if(sHave[1]<limit)limit=sHave[1];
        if(limit>=h.next) {MemoryBarrier();InterlockedExchange((volatile LONG *)&h.next,(LONG)limit);}
    }
    h.scores[0]=a;h.scores[1]=b;
}
static bool observerBegin(int role) {
    if(role!=3 || !observerMap() || observerShared->header.mode!=2)return false;
    BtcObserverHeader &h=observerShared->header;
    typedef DWORD (WINAPI *GetEnv)(LPCSTR,LPSTR,DWORD);
    GetEnv get=(GetEnv)GetProcAddress(GetModuleHandleW(L"kernel32.dll"),"GetEnvironmentVariableA");
    if(!get)return false;
    const DWORD oldSize=get("BT3_SAVES",observerOldSave,sizeof(observerOldSave));
    observerOldSaveSet=oldSize>0;
    if(oldSize>=sizeof(observerOldSave) || !observerSaveEnvironment("net_session"))return false;
    sMode=1;sSession=sConnected=1;sMe=0;sResim=0;gPortResim=0;sArrived=0;
    sTick=0;sSeed=h.seed;sRules=h.rules;sRollMax=0;
    sOpts[0]=h.options[0];sOpts[1]=h.options[1];
    SDL_snprintf(sNames[0],20,"%s",h.names[0]);SDL_snprintf(sNames[1],20,"%s",h.names[1]);
    memcpy(observerPads,observerIdle,18);memcpy(observerPads+18,observerIdle,18);
    InterlockedExchange(&observerActive,1);h.mode=3;
    fprintf(stderr,"bt3: spectator lab: same-process observer session started; no combat socket\n");
    return true;
}
static void observerCaptureEnd() {
    if(observerShared && observerShared->header.mode==1) {
        MemoryBarrier();InterlockedExchange((volatile LONG *)&observerShared->header.closed,1);
    }
}
static void observerEnd() {
    observerRequested=false;
    if(!observerIsActive()) {
        if(observerShared && observerShared->header.mode==4)observerShared->header.mode=0;
        return;
    }
    observerSaveEnvironment(observerOldSaveSet?observerOldSave:NULL);
    InterlockedExchange(&observerActive,0);observerRequested=false;
    if(observerShared)observerShared->header.mode=0;
    fprintf(stderr,"bt3: spectator lab: returned to own game and room\n");
}
static void observerRequest() {
    if(observerIsActive() || observerRequested || !observerMap())return;
    BtcObserverHeader &h=observerShared->header;
    if(h.mode==4){h.mode=0;return;}
    if(h.mode!=2 || (h.serial&1) || h.next<h.first || h.next-h.first<120 || !Port_SessionCan())return;
    if(Port_NetSession())return; // Never interrupt a player's own fight.
    observerRequested=true;Port_SessionRequest(3,"",0);
}
static bool observerTick(unsigned tick) {
    if(!observerIsActive()) {observerRequest();return false;}
    sTick=tick;
    BtcObserverHeader &h=observerShared->header;
    if(tick<h.first) {memcpy(observerPads,observerIdle,18);memcpy(observerPads+18,observerIdle,18);return true;}
    const Uint64 waiting=SDL_GetTicks();
    while(tick>=h.next && !h.closed && !h.error && h.mode==3 && SDL_GetTicks()-waiting<15000)SDL_Delay(5);
    MemoryBarrier();
    if(tick>=h.next || h.error || h.mode!=3) {Port_SessionReturn();return true;}
    const BtcObserverFrame &frame=observerShared->frames[tick%BTC_OBSERVER_RING];
    if(frame.tick!=tick) {h.error=2;Port_SessionReturn();return true;}
    memcpy(observerPads,frame.pads,36);
    MemoryBarrier();h.read_serial=h.serial;InterlockedExchange((volatile LONG *)&h.read,(LONG)(tick+1));
    return true;
}
extern "C" void Competitive_ObserverNetInput(int player,unsigned char *data) {
    if(!observerIsActive()) {Port_NetInput(player,data);return;}
    memcpy(data,player>=0&&player<2?observerPads+18*player:observerIdle,18);
}
extern "C" int Competitive_ObserverNetView() {return observerIsActive()?-1:Port_NetView();}
extern "C" int Competitive_ObserverNetWarp() {
    if(!observerIsActive())return Port_NetWarp();
    const BtcObserverHeader &h=observerShared->header;
    return !sArrived || (!h.closed && h.next>h.read && h.next-h.read>240);
}
extern "C" void Competitive_ObserverNetArrived() {
    if(observerIsActive() && sArrived)return;
    Port_NetArrived();
}
extern "C" void Competitive_ObserverNetLeave() {
    if(observerIsActive()) {Port_SessionReturn();return;}
    Port_NetLeave();
}
