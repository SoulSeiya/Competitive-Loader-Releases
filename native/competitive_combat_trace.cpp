// Reviewed BTC 0.1.38.1 ABI. Observational telemetry, outside rollback/game memory.
// One producer (simulation thread); no disk/network, locks or allocation per tick.
extern "C" {
unsigned Port_NetTick(void);
uint32_t BtlChar_FindBySide(int);
int BtlCharApi_GetChara(int);
int PortA11y_Utf8(char *, int, const uint16_t *);
extern uint32_t gBtlChars;
int Battle_GetStage(void);
int Battle_GetStartStage(void);
const char *const *MenuTranslation_StageNames(void);
uint32_t BtlObj_Get(int);
const char *Port_NetName(int);
}
enum { TraceMagic=0x54435442, TraceCapacity=4096, TraceNameCount=161 };
struct TraceFighter { int roster, character, member, count, variant, action, actionClass, abilityId, actionFrame, costume; };
struct TraceFrame { unsigned epoch, blank; int phase, resim; TraceFighter sides[2]; int stage, startStage; };
struct TraceShared {
    unsigned magic, version;
    volatile LONG sequence;
    unsigned epoch, frontier, latest, reserved[10];
    char names[TraceNameCount][128];
    char stageCatalog[35][96]; // Engine's labels, not proof of a modified BTC map name.
    char playerNames[2][96]; // Local readable journal only; never uploaded as client claims.
    TraceFrame frames[TraceCapacity];
};
static_assert(sizeof(TraceFighter)==40 && sizeof(TraceFrame)==104, "trace ABI");
static_assert(offsetof(TraceShared,names)==64 && offsetof(TraceShared,frames)==24224, "trace ABI");
static TraceShared *combatTrace;
static bool traceAttempted;
static TraceShared *competitiveTraceOpen() {
    if (traceAttempted) return combatTrace;
    traceAttempted=true;
    const char *name=SDL_getenv("BTC_DIAGNOSTIC_TRACE_MAP");
    if (!name || !*name) return 0;
    HMODULE module=GetModuleHandleW(L"kernel32.dll");
    RisingOpenMapping open=(RisingOpenMapping)GetProcAddress(module,"OpenFileMappingA");
    RisingMapView map=(RisingMapView)GetProcAddress(module,"MapViewOfFile");
    RisingCloseHandle close=(RisingCloseHandle)GetProcAddress(module,"CloseHandle");
    if (!open || !map || !close) return 0;
    HANDLE handle=open(FILE_MAP_READ|FILE_MAP_WRITE,FALSE,name);
    if (!handle) return 0;
    TraceShared *p=(TraceShared *)map(handle,FILE_MAP_READ|FILE_MAP_WRITE,0,0,sizeof(TraceShared));
    close(handle);
    if (!p) return 0;
    if (p->magic!=TraceMagic || p->version!=4) {
        typedef BOOL (WINAPI *Unmap)(LPCVOID);
        Unmap unmap=(Unmap)GetProcAddress(module,"UnmapViewOfFile");
        if (unmap) unmap(p);
        return 0;
    }
    return combatTrace=p; // OS releases this process's view at exit.
}
static void competitiveTraceReset() {
    TraceShared *p=competitiveTraceOpen(); if (!p) return;
    InterlockedIncrement(&p->sequence);
    ++p->epoch; p->frontier=p->latest=0; p->reserved[0]=0;
    InterlockedIncrement(&p->sequence);
}
static void competitiveTraceFrontier(unsigned frontier) {
    TraceShared *p=competitiveTraceOpen(); if (!p) return;
    InterlockedIncrement(&p->sequence); p->frontier=frontier;
    InterlockedIncrement(&p->sequence);
}
// Names come from the modified disc's selection text, never a vanilla roster list.
static void competitiveTraceText(char *out, uint32_t address, unsigned id) {
    out[0]=0; if (!address) return;
    const uint32_t *file=(const uint32_t *)(uintptr_t)address;
    if (id+1 >= (file[1]>>2)) return;
    const unsigned offset=file[id+1]&~3u;
    if (!offset || offset>=0x200000) return;
    const uint16_t *str=(const uint16_t *)((uintptr_t)file+offset);
    if (*str!=0xfeff) return;
    PortA11y_Utf8(out,64,str);
}
static void competitiveTraceNames(uint32_t work, unsigned nameOffset=0x28) {
    TraceShared *p=competitiveTraceOpen(); if (!p || !work) return;
    const uint32_t name=*(uint32_t *)((uintptr_t)work+nameOffset);
    const uint32_t form=*(uint32_t *)((uintptr_t)work+nameOffset+4);
    static uint32_t cachedName, cachedForm;
    if (!name || !form || (cachedName==name && cachedForm==form)) return;
    cachedName=name; cachedForm=form;
    InterlockedIncrement(&p->sequence);
    for (unsigned i=0;i<TraceNameCount;++i) {
        char base[64]={},variant[64]={};
        competitiveTraceText(base,name,i); competitiveTraceText(variant,form,i);
        if (variant[0] && strcmp(base,variant))
            SDL_snprintf(p->names[i],128,"%s / %s",base,variant);
        else SDL_snprintf(p->names[i],128,"%s",base);
    }
    InterlockedIncrement(&p->sequence);
}
static int competitiveTraceActionClass(int id) {
    if (id==0x105) return 4;
    if (id>=0xfd && id<=0x102) return (id-0xfd)%2;
    if (id>=0x106 && id<=0x13b) return (id-0x106)%3+2;
    return -1;
}
static void competitiveTraceCapture(unsigned tick=Port_NetTick(), bool practice=false) {
    TraceShared *p=competitiveTraceOpen();
    if (!p || (!Port_NetSession() && !practice) || !gBtlChars || !gBtlSeq) return;
    const unsigned mode=practice?2:1;
    if (!p->epoch || (p->reserved[0] && p->reserved[0]!=mode)) competitiveTraceReset();
    TraceFrame frame={}; frame.epoch=p->epoch;
    // Capture at the beginning of the simulation blank, after rollback restoration.
    frame.blank=tick;
    frame.phase=*(int *)(uintptr_t)gBtlSeq; frame.resim=gPortResim!=0;
    frame.stage=Battle_GetStage(); frame.startStage=Battle_GetStartStage();
    for (int side=0;side<2;++side) {
        TraceFighter &f=frame.sides[side];
        f.roster=f.character=f.member=f.count=f.variant=f.action=f.actionClass=f.abilityId=f.actionFrame=f.costume=-1;
        const uint32_t address=BtlChar_FindBySide(side);
        if (!address) continue;
        const unsigned char *chr=(const unsigned char *)(uintptr_t)address;
        const int member=*(const int *)(chr+0x994),count=*(const int *)(chr+0x998);
        if (count<1 || count>5 || member<0 || member>=count) continue;
        const unsigned char *m=chr+0x9a4+member*0xa4;
        const int roster=*(const int *)m, character=BtlCharApi_GetChara(side);
        const int action=*(const int *)(chr+0x948),variant=*(const int *)(m+0x60);
        f.member=member; f.count=count;
        const int costume=*(const int *)(m+4);
        if(costume>=0 && costume<256) f.costume=costume+1; // Human-visible number: first outfit is 1.
        if (roster>=0 && roster<TraceNameCount) f.roster=roster;
        if (character>=0 && character<TraceNameCount) f.character=character;
        if (variant>=0 && variant<=3) f.variant=variant;
        if (action>=0 && action<0x13c) {f.action=action;f.actionClass=competitiveTraceActionClass(action);}
        const int actionFrame=*(const int *)(chr+0x964);
        if (actionFrame>=0) f.actionFrame=actionFrame;
        // Skills and supers are DIFFERENT arrays: two slots at skill+0x10,
        // three at super+0x18. Never index a two-entry skill table by class 2..4.
        if (f.actionClass>=0 && (action<=0x102 || (action>=0x105 && action<=0x12f))) {
            const int objectId=*(const int *)(chr+0x0c);
            const uint32_t object=objectId>=0 && objectId<12?BtlObj_Get(objectId):0;
            if (object) {
                const bool skill=f.actionClass<2;
                const uint32_t table=*(const uint32_t *)((uintptr_t)object+(skill?0x930:0x92c));
                if (table) {
                    const int index=skill?f.actionClass:f.actionClass-2;
                    const int id=*(const int16_t *)((uintptr_t)table+(skill?0x10:0x18)+index*2);
                    if (id>=0) f.abilityId=id;
                }
            }
        }
    }
    static bool stageCatalogReady;
    if (!stageCatalogReady) {
        const char *const *names=MenuTranslation_StageNames();
        if (names) {
            InterlockedIncrement(&p->sequence);
            for (int i=0;i<35;++i) SDL_snprintf(p->stageCatalog[i],96,"%s",names[i]?names[i]:"");
            InterlockedIncrement(&p->sequence);
            stageCatalogReady=true;
        }
    }
    InterlockedIncrement(&p->sequence);
    static const char *localName;
    static bool localNameRead;
    if (!localNameRead) {localName=SDL_getenv("BT3_NET_NAME");localNameRead=true;}
    for (int side=0;side<2;++side) {
        const char *name=practice?(side==0?localName:"CPU"):Port_NetName(side);
        SDL_snprintf(p->playerNames[side],96,"%s",name&&*name?name:(side==0?"P1":"P2"));
    }
    p->frames[frame.blank%TraceCapacity]=frame; p->latest=frame.blank; p->reserved[0]=mode;
    InterlockedIncrement(&p->sequence);
}
