// Reuse the game's existing Tab overlay; only its data transport changes in a BTC room.
extern "C" {
int Port_NetActive(void);
unsigned PortChat_Count(void);
int PortChat_Say(const char *);
struct RisingChatLine { char text[161], sender[32]; uint64_t atMs; int mine; };
int PortChat_Line(unsigned, RisingChatLine *);
}
typedef DWORD (WINAPI *RisingThreadIdFn)(void);
static RisingThreadIdFn risingThreadId;
static volatile LONG risingUiThread, risingUiDepth;
static void risingUiEnter() {
    if (!risingThreadId) risingThreadId=(RisingThreadIdFn)GetProcAddress(GetModuleHandleW(L"kernel32.dll"),"GetCurrentThreadId");
    if (!risingThreadId) return;
    InterlockedExchange(&risingUiThread,(LONG)risingThreadId());
    InterlockedIncrement(&risingUiDepth);
}
static void risingUiLeave() { if (InterlockedCompareExchange(&risingUiDepth,0,0)) InterlockedDecrement(&risingUiDepth); }
extern "C" int Competitive_RoomNetActive() {
    // Other threads and all gameplay checks retain the real transport state.
    if (InterlockedCompareExchange(&risingUiDepth,0,0) && (DWORD)InterlockedCompareExchange(&risingUiThread,0,0)==risingThreadId() && risingState.connected) return 1;
    return Port_NetActive();
}
static RisingChatLine risingChatLines[64];
static unsigned risingChatSerial;
static void risingChatCopy(char *out, unsigned size, const char *text) {
    unsigned length=(unsigned)strlen(text), count=length<size-1?length:size-1;
    if(count<length) while(count && ((unsigned char)text[count]&0xC0)==0x80)--count;
    memcpy(out,text,count);out[count]=0;
}
static void risingChatRefresh() {
    risingRead();
    for (unsigned i = 0; i < risingState.chat_count; ++i) {
        RisingChatLine next = {};
        const char *line = risingState.chat[i], *colon = strchr(line, ':');
        const unsigned length = colon ? (unsigned)(colon-line) : 0;
        if (length && length < sizeof(next.sender)) {
            memcpy(next.sender,line,length);
            const char *text = colon+1; if (*text==' ') ++text;
            risingChatCopy(next.text,sizeof(next.text),text);
        } else risingChatCopy(next.text,sizeof(next.text),line);
        for (unsigned u = 0; u < risingState.count; ++u)
            if (risingState.users[u].id == risingState.self_id)
                next.mine = strcmp(next.sender,risingState.users[u].name)==0;
        RisingChatLine &old = risingChatLines[i];
        next.atMs = strcmp(next.text,old.text) || strcmp(next.sender,old.sender) ? SDL_GetTicks() : old.atMs;
        if(i+1==risingState.chat_count && risingChatSerial!=risingState.chat_serial) next.atMs=SDL_GetTicks();
        old = next;
    }
    risingChatSerial=risingState.chat_serial;
}
extern "C" unsigned Competitive_RoomChatCount() {
    if (!risingState.connected) return PortChat_Count();
    risingChatRefresh();
    return risingState.chat_count;
}
extern "C" int Competitive_RoomChatLine(unsigned index, RisingChatLine *out) {
    if (!risingState.connected) return PortChat_Line(index,out);
    if (!out || index >= risingState.chat_count) return 0;
    *out = risingChatLines[index];
    return 1;
}
extern "C" int Competitive_RoomChatSay(const char *text) {
    if (!risingState.connected) return PortChat_Say(text);
    if (!text || !*text || risingBusy()) return 0;
    SDL_snprintf(risingCommand.text,sizeof(risingCommand.text),"%s",text);
    return risingSend(3) ? 1 : 0;
}
extern "C" void Competitive_RoomLobbyCancel() {
    // Closing the native window does not cancel an automatically assigned fight.
    // Explicit cancellation/WO in the room pump calls the original directly.
    if(risingState.connected && risingMatchStage==1) return;
    Port_LobbyCancel();
}
static void risingSocialDraw() {
    if (!risingBracketOpen) return;
    const ImVec2 screen = ImGui::GetIO().DisplaySize;
    ImGui::SetNextWindowPos(ImVec2(12, 12),ImGuiCond_Always);
    ImGui::SetNextWindowSize(ImVec2(screen.x-24,screen.y-24),ImGuiCond_Always);
    ImGui::SetNextWindowBgAlpha(.94f);
    if (ImGui::Begin("Torneo en directo (F2 para cerrar)",NULL,
            ImGuiWindowFlags_NoInputs | ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoSavedSettings)) {
        if (!risingState.connected) ImGui::TextUnformatted("Entra en una sala BTC para ver su torneo.");
        else {
            const RisingTournament &t = risingState.tournament;
            ImGui::Text("%s | FT%u | %u inscritos",t.title,t.ft,t.enrolled);
            if (t.status==0) ImGui::TextUnformatted("Inscripciones abiertas; el anfitrion aun no ha iniciado.");
            else if (!t.mode) risingBracket(t,true);
            else for (unsigned i=0;i<t.count;++i) {
                const RisingMatch &m=t.matches[i];
                ImGui::Text("#%u  %s vs %s  |  %s  %u-%u",m.id,m.name1,m.name2,
                    m.status==2 ? "Terminado" : m.status==1 ? "En curso" : "Pendiente",m.score1,m.score2);
            }
            if (t.status==2) ImGui::Text("GG - %s",t.mode ? "Prueba completada" : t.champion_name);
        }
    }
    ImGui::End();
}
