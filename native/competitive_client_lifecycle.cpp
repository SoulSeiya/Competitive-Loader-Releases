// A per-launch local event asks the game to use its own normal exit dialog flow.
// No remote room message and no other process can be selected by this path.
extern "C" {
void PortQuit_Request(void);
int PortQuit_Active(void);
int PortQuit_Failed(void);
int PortQuit_Ready(void);
int PortQuit_Cursor(void);
void PortQuit_Action(int);
}
static void competitiveClientCloseTick() {
    typedef HANDLE (WINAPI *OpenEventFn)(DWORD,BOOL,LPCSTR);
    typedef DWORD (WINAPI *WaitFn)(HANDLE,DWORD);
    static bool initialized,closing;
    static HANDLE event;
    static WaitFn wait;
    if(!initialized) {
        initialized=true;
        const char *name=SDL_getenv("BTC_CLIENT_CLOSE_EVENT");
        if(name && *name) {
            HMODULE module=GetModuleHandleW(L"kernel32.dll");
            OpenEventFn open=(OpenEventFn)GetProcAddress(module,"OpenEventA");
            wait=(WaitFn)GetProcAddress(module,"WaitForSingleObject");
            if(open && wait)event=open(SYNCHRONIZE,FALSE,name);
        }
    }
    if(event && wait(event,0)==WAIT_OBJECT_0)closing=true;
    if(!closing)return;
    if(Port_NetSession()) {closing=false;return;} // never interrupt a new combat
    if(PortQuit_Failed()) {closing=false;ScoreLog(stderr,"btc: auto_close unavailable; game left open\n");return;}
    if(!PortQuit_Active())PortQuit_Request();
    if(PortQuit_Ready())PortQuit_Action(PortQuit_Cursor()==0?2:1);
}
