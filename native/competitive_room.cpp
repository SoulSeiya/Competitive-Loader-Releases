// Included by competitive_score.cpp. Only shared memory is touched on the UI thread.
#include "rising_room_shared.h"
extern "C" void OriginalNetMenu(void) __asm__("_ZL9build_netv");
extern bool nativeNetOpen __asm__("_ZL4sNet");
extern "C" void Ui_Toggle(void);
extern "C" void Port_SettingTextSave(const char *,const char *);
extern "C" void Port_LobbyCancel(void);
extern "C" volatile int gPortNetMenuRequest;
extern "C" int gPortChatTyping;
extern "C" bool OriginalRoomBegin(const char *, bool *, ImGuiWindowFlags) __asm__("_ZN5ImGui5BeginEPKcPbi");
typedef HANDLE (WINAPI *RisingOpenMapping)(DWORD, BOOL, LPCSTR);
typedef LPVOID (WINAPI *RisingMapView)(HANDLE, DWORD, DWORD, DWORD, SIZE_T);
typedef BOOL (WINAPI *RisingCloseHandle)(HANDLE);
static RisingShared *risingShared;
// Development room panel is opt-in. The normal Dragon Net Battle path stays native.
static bool risingRoomRequested;
static volatile LONG risingModeActive;
static volatile LONG risingLeaveRequested;
static RisingState risingState;
static RisingCommand risingCommand;
static bool risingBracketOpen;
static void risingRoomContent();
static bool risingNetTab;
static bool risingSelectTournament;
static void risingUiEnter();
static void risingUiLeave();
extern "C" int Competitive_WindowEvent(const SDL_Event *);
extern "C" int Competitive_RisingEvent(const SDL_Event *event) {
    if(event && risingState.connected && nativeNetOpen && event->type==SDL_EVENT_KEY_DOWN &&
            event->key.scancode==SDL_SCANCODE_TAB && !event->key.repeat) Ui_Toggle();
    const bool wasOnlineMenu = nativeNetOpen;
    risingUiEnter();
    const int result = Competitive_WindowEvent(event);
    risingUiLeave();
    if (wasOnlineMenu && !nativeNetOpen) {
        risingRoomRequested = false;
        risingModeActive = 0;
    }
    return result;
}

static bool risingConnectBridge() {
    if (risingShared) return true;
    const char *name = SDL_getenv("BTC_ROOM_BRIDGE");
    if (!name || !*name) return false;
    HMODULE module = GetModuleHandleW(L"kernel32.dll");
    RisingOpenMapping open = (RisingOpenMapping)GetProcAddress(module, "OpenFileMappingA");
    RisingMapView map = (RisingMapView)GetProcAddress(module, "MapViewOfFile");
    RisingCloseHandle close = (RisingCloseHandle)GetProcAddress(module, "CloseHandle");
    if (!open || !map || !close) return false;
    HANDLE handle = open(FILE_MAP_READ | FILE_MAP_WRITE, FALSE, name);
    if (!handle) return false;
    RisingShared *shared = (RisingShared *)map(handle, FILE_MAP_READ | FILE_MAP_WRITE, 0, 0, sizeof(RisingShared));
    close(handle);
    if (!shared) return false;
    if (shared->magic != 0x52435442 || shared->version != 6) {
        typedef BOOL (WINAPI *Unmap)(LPCVOID);
        Unmap unmap = (Unmap)GetProcAddress(module, "UnmapViewOfFile");
        if (unmap) unmap(shared);
        return false;
    }
    risingShared = shared; // The process owns the view until it exits.
    fprintf(stderr, "bt3: Rising Battle: Loader room bridge connected\n");
    return true;
}

static void risingRead() {
    if (!risingConnectBridge()) return;
    static uint32_t lastSequence;
    static bool haveState;
    const uint32_t before = risingShared->state_seq;
    if ((before & 1) || (haveState && before == lastSequence)) return;
    MemoryBarrier();
    RisingState copy;
    memcpy(&copy, &risingShared->state, sizeof(copy));
    MemoryBarrier();
    if (before != risingShared->state_seq) return;
    if (copy.count > 32 || copy.chat_count > 64 || copy.tournament.count > 31 || copy.tournament.current > 31) return;
    // Bound every string independently, even for an invalid local bridge.
    copy.title[96] = copy.address[128] = copy.notice[256] = copy.key[64] = 0;
    copy.invite[384] = 0;
    copy.tournament.id[64] = copy.tournament.title[96] = copy.tournament.champion_name[64] = copy.tournament.roster[256] = 0;
    for (unsigned i = 0; i < copy.tournament.count; ++i) {
        if (copy.tournament.matches[i].id != i+1 || copy.tournament.matches[i].round < 1 || copy.tournament.matches[i].round > 5) return;
        copy.tournament.matches[i].name1[64] = copy.tournament.matches[i].name2[64] = copy.tournament.matches[i].code[7] = 0;
    }
    for (unsigned i = 0; i < copy.count; ++i) copy.users[i].name[64] = 0;
    for (unsigned i = 0; i < copy.chat_count; ++i) copy.chat[i][384] = 0;
    risingState = copy;
    lastSequence = before;
    haveState = true;
}

static bool risingRankedSession() {
    // Shared header ABI is unchanged: bit 0 is connected, bit 1 is ranked.
    // Capture once when the net session begins, including an already-open game.
    if (!risingConnectBridge()) return false;
    for (int attempt = 0; attempt < 3; ++attempt) {
        const uint32_t before = risingShared->state_seq;
        if (before & 1) continue;
        MemoryBarrier();
        const uint32_t flags = risingShared->state.connected;
        MemoryBarrier();
        if (before == risingShared->state_seq) return (flags & 3) == 3;
    }
    // A freshly auto-launched ranked game also carries its session provenance.
    const char *ranked = SDL_getenv("BTC_RANKED_SESSION");
    return ranked && strcmp(ranked, "1") == 0;
}

static bool risingBusy() {
    return !risingShared || risingShared->command_seq != risingShared->ack_seq;
}

static bool risingSend(unsigned op, unsigned target = 0) {
    if (risingBusy()) return false;
    risingCommand.op = op;
    risingCommand.target = target;
    memcpy(&risingShared->command, &risingCommand, sizeof(risingCommand));
    MemoryBarrier();
    ++risingShared->command_seq;
    return true;
}

#include "competitive_tournament_match.cpp"
#include "competitive_room_social.cpp"

extern "C" int Port_Setting(const char *, int);
extern "C" int Competitive_ClientSetting(const char *key, int fallback) {
    if (key && strcmp(key,"update_check")==0) return 0; // pinned motor; Loader owns updates
    if (key && SDL_getenv("BTC_FAST_START") &&
            (!strcmp(key,"skip_logos") || !strcmp(key,"skip_intro") || !strcmp(key,"skip_copyright"))) return 1;
    return Port_Setting(key,fallback);
}
extern "C" bool OriginalClientCheckbox(const char *,bool *) __asm__("_ZN5ImGui8CheckboxEPKcPb");
extern "C" bool Competitive_ClientCheckbox(const char *label,bool *value) {
    if(label && !strcmp(label,"Check for updates")) return false;
    return OriginalClientCheckbox(label,value);
}
extern "C" bool Competitive_RisingBegin(const char *name, bool *open, ImGuiWindowFlags flags) {
    const bool net=name && !strcmp(name,"Dragon Net Battle");
    const bool settings=name && !strcmp(name,"Settings");
    if(net || settings) {
        const ImVec2 size=ImGui::GetIO().DisplaySize;
        ImGui::SetNextWindowSizeConstraints(ImVec2(300,200),ImVec2(size.x*.96f,size.y*.94f));
    }
    const char *title=net?"Dragon Net Battle / BTC###Dragon Net Battle":settings?"Rising Battle / UT###Settings":name;
    const bool visible=OriginalRoomBegin(title,open,flags);
    if(visible && (net || settings)) {
        ImGui::TextColored(ImVec4(1,.54f,.23f,1),"UNIVERSO TENKAICHI");
        ImGui::SameLine();ImGui::TextDisabled(net?"BTC / ONLINE":"RISING BATTLE / AJUSTES");
        if(net) {
            risingRead();
            if(risingState.connected) {
                ImGui::TextWrapped("%s",risingState.notice);
                const RisingTournament &duel=risingState.tournament;
                if(duel.status==1) ImGui::Text("FT%u  /  %u s  /  %u personajes",duel.ft,duel.seconds,duel.characters);
            }
            ImGui::TextDisabled("Salas, desafios y revanchas: desde el cliente Rising Battle.");
        } else {
            ImGui::TextDisabled(SDL_getenv("BTC_FAST_START")?"Inicio agil activo / motor BTC fijo":"Motor BTC fijo / actualizaciones desde el Loader");
        }
        ImGui::Separator();
    }
    return visible;
}

extern "C" void Competitive_RisingMenu(void) {
    static bool profileApplied;
    if(!profileApplied) {
        const char *profile=SDL_getenv("BT3_NET_NAME");
        if(profile && *profile)Port_SettingTextSave("net_name",profile);
        profileApplied=true;
    }
    risingRoomRequested=false;risingSelectTournament=false;risingNetTab=false;
    OriginalNetMenu(); // Native Host/Join/Quick Match transport; no tournament panel.
}
