// Included by competitive_score.cpp. Only shared memory is touched on the UI thread.
#include "rising_room_shared.h"
extern "C" void OriginalNetMenu(void) __asm__("_ZL9build_netv");
extern bool nativeNetOpen __asm__("_ZL4sNet");
extern "C" void Ui_Toggle(void);
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
    if (event && (event->type == SDL_EVENT_KEY_DOWN || event->type == SDL_EVENT_KEY_UP) && event->key.scancode == SDL_SCANCODE_F2) {
        if (event->type == SDL_EVENT_KEY_DOWN && !event->key.repeat) risingBracketOpen = !risingBracketOpen;
        return 1;
    }
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
    if (shared->magic != 0x52435442 || shared->version != 5) {
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
    const uint32_t before = risingShared->state_seq;
    if (before & 1) return;
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

#include "competitive_tournament_mode.cpp"
#include "competitive_game_bot.cpp"
#include "competitive_tournament_match.cpp"
#include "competitive_tournament.cpp"
#include "competitive_room_social.cpp"

extern "C" bool Competitive_RisingBegin(const char *name, bool *open, ImGuiWindowFlags flags) {
    if (name && strcmp(name, "Dragon Net Battle") == 0 && risingNetTab) flags &= ~ImGuiWindowFlags_AlwaysAutoResize;
    const bool visible = OriginalRoomBegin(name, open, flags);
    if (visible && name && strcmp(name, "Settings") == 0) {
        if (ImGui::Button("Pruebas de sala BTC (desarrollo)")) {
            risingRoomRequested = true;
            gPortNetMenuRequest = 1;
        }
        ImGui::Separator();
    }
    if (visible && name && strcmp(name, "Dragon Net Battle") == 0) {
        if(SDL_getenv("BTC_MATCH_UNCONFIGURED"))
            ImGui::TextWrapped("Matchmaking BTC pendiente: configura nuestro Worker en el Loader. Los codigos de pelea no conectan sin ese servicio. Offline y conexion por IP siguen disponibles.");
        risingRead();
        const bool tournamentRunning = risingState.connected && risingState.tournament.status == 1;
        if(tournamentRunning) risingSelectTournament=true;
        bool direct = true;
        if (ImGui::BeginTabBar("btc-online-sections")) {
            ImGui::BeginDisabled(tournamentRunning);
            if (ImGui::BeginTabItem("Partidas")) {
                risingNetTab = false;
                ImGui::EndTabItem();
            }
            ImGui::EndDisabled();
            if (ImGui::BeginTabItem("Torneos BTC",NULL,risingSelectTournament ? ImGuiTabItemFlags_SetSelected : 0)) {
                risingNetTab = true;
                ImGui::EndTabItem();
            }
            ImGui::EndTabBar();
            risingSelectTournament = false;
        }
        direct = !risingNetTab;
        if (!direct) {
            if(tournamentRunning) ImGui::TextWrapped("Torneo en curso: el bracket gestiona las conexiones de combate.");
            ImGui::SetWindowSize(ImVec2(760, 650), ImGuiCond_Always);
            if (ImGui::BeginChild("btc-tournament-tab", ImVec2(0, 550), ImGuiChildFlags_None)) risingRoomContent();
            ImGui::EndChild();
            if(risingModeActive && ImGui::Button("Volver al menu principal")) { risingModeActive=0;Ui_Toggle(); }
        }
        // The original caller still pairs its Begin with End. Returning false skips
        // only its direct-match body while the tournament pane occupies this window.
        return direct;
    }
    return visible;
}

extern "C" void Competitive_RisingMenu(void) {
    if (!risingRoomRequested) {
        static bool loggedOriginal;
        if (!loggedOriginal) {
            loggedOriginal = true;
            fprintf(stderr, "bt3: Dragon Net Battle: native menu preserved\n");
        }
        OriginalNetMenu(); // Preserve its Host/Join room codes, controls and window title.
        return;
    }
    static bool logged;
    if (!logged) {
        logged = true;
        fprintf(stderr, "bt3: Rising Battle: native room menu opened\n");
    }
    bool open = true;
    if (risingModeActive) {
        ImGui::SetNextWindowPos(ImVec2(0, 0), ImGuiCond_Always);
        ImGui::SetNextWindowSize(ImGui::GetIO().DisplaySize, ImGuiCond_Always);
    } else {
    ImGui::SetNextWindowPos(ImVec2(ImGui::GetIO().DisplaySize.x * .5f, ImGui::GetIO().DisplaySize.y * .5f),
                            ImGuiCond_Appearing, ImVec2(.5f, .5f));
    ImGui::SetNextWindowSize(ImVec2(720, 570), ImGuiCond_Appearing);
    }
    if (ImGui::Begin("Rising Battle", &open, risingModeActive ?
            ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoSavedSettings : ImGuiWindowFlags_NoCollapse)) {
        if (risingModeActive && ImGui::Button("Volver al menu principal")) open = false;
        risingRoomContent();
    }
    ImGui::End();
    if (!open) {
        risingRoomRequested = false;
        risingModeActive = 0;
        Ui_Toggle(); // Native close also restores input ownership; membership stays alive.
    }
}

static void risingRoomContent() {
    risingRead();
    static bool initialized;
    if (!initialized) {
        initialized = true;
        memcpy(risingCommand.name, "Jugador", 8);
        memcpy(risingCommand.title, "Sala BTC", 9);
        SDL_snprintf(risingCommand.address, sizeof(risingCommand.address), "%s", risingState.address[0] ? risingState.address : "127.0.0.1");
        risingCommand.port = 7001;
        risingCommand.capacity = 8;
    }
        ImGui::TextUnformatted("BTC - Sala de jugadores");
        ImGui::TextWrapped("F2: bracket en directo | Tab: chat de la sala. Los cruces conectan automaticamente a sus dos jugadores.");
        ImGui::Separator();
        if (!risingShared) {
            ImGui::TextWrapped("Abre el juego desde el Loader actualizado para activar las salas.");
        } else {
            ImGui::TextWrapped("%s", risingState.notice);
            ImGui::BeginDisabled(risingBusy());
            if (!risingState.connected) {
                ImGui::InputText("Tu nombre", risingCommand.name, sizeof(risingCommand.name));
                static char service[129] = "http://127.0.0.1:7010", serviceCode[16];
                static bool serviceInitialized = false;
                if(!serviceInitialized) {
                    const char *configured=SDL_getenv("BTC_ROOM_SERVICE");
                    if(configured && configured[0]) SDL_snprintf(service,sizeof(service),"%s",configured);
                    serviceInitialized=true;
                }
                ImGui::InputText("Servicio de salas BTC",service,sizeof(service));
                ImGui::TextWrapped("Un mismo servicio para todos los miembros. El local sirve solo para pruebas en este equipo; Internet requiere nuestro servidor HTTPS publicado.");
                if(SDL_getenv("BTC_DEV_TOOLS") && ImGui::Button("Iniciar servicio local de prueba")) risingSend(23);
                ImGui::InputText("Nombre de sala BTC",risingCommand.title,sizeof(risingCommand.title));
                int serviceCapacity=(int)risingCommand.capacity;
                if(ImGui::SliderInt("Plazas de sala",&serviceCapacity,2,32))risingCommand.capacity=(unsigned)serviceCapacity;
                if(ImGui::Button("Crear sala con room code")) {
                    SDL_snprintf(risingCommand.address,sizeof(risingCommand.address),"%s",service);
                    risingSend(21);
                }
                ImGui::InputText("Room code BTC",serviceCode,sizeof(serviceCode),ImGuiInputTextFlags_CharsUppercase);
                if(ImGui::Button("Unirse con room code")) {
                    SDL_snprintf(risingCommand.address,sizeof(risingCommand.address),"%s",service);
                    SDL_snprintf(risingCommand.text,sizeof(risingCommand.text),"%s",serviceCode);
                    risingSend(22);
                }
                if(SDL_getenv("BTC_DEV_TOOLS")) {
                ImGui::SeparatorText("Laboratorio");
                if (ImGui::Button("Crear prueba: tu + 3 bots, todos contra mi")) risingSend(19);
                ImGui::TextWrapped("Prueba local FT1. Cada bot abre su propio juego cuando le toca. Revisa primero las opciones de control.");
                }
                if(ImGui::CollapsingHeader("Conexion directa avanzada (IP / VPN)")) {
                int port = (int)risingCommand.port;
                if (ImGui::InputInt("Puerto de sala", &port)) risingCommand.port = port > 0 && port <= 65535 ? (unsigned)port : 7001;
                if (ImGui::BeginTabBar("rising-room-tabs")) {
                    if (ImGui::BeginTabItem("Crear sala")) {
                        ImGui::InputText("Nombre de sala", risingCommand.title, sizeof(risingCommand.title));
                        ImGui::InputText("IP / equipo para la invitacion", risingCommand.address, sizeof(risingCommand.address));
                        ImGui::TextWrapped("Revisa la direccion de tu red local o VPN. 127.0.0.1 sirve solo en este equipo.");
                        int capacity = (int)risingCommand.capacity;
                        if (ImGui::SliderInt("Maximo de usuarios", &capacity, 2, 32)) risingCommand.capacity = (unsigned)capacity;
                        ImGui::TextWrapped("Alojas la sala en tu equipo. Comparte tu IP, puerto y la clave generada. Usa una red local, VPN o un puerto accesible.");
                        if (ImGui::Button("Crear sala BTC")) risingSend(1);
                        ImGui::EndTabItem();
                    }
                    if (ImGui::BeginTabItem("Unirse a sala")) {
                        ImGui::InputText("Codigo BTC1", risingCommand.text, sizeof(risingCommand.text));
                        if (ImGui::Button("Entrar con codigo")) risingSend(9);
                        ImGui::SeparatorText("O entrar por IP y clave");
                        ImGui::InputText("IP / equipo del anfitrion", risingCommand.address, sizeof(risingCommand.address));
                        ImGui::InputText("Clave de sala", risingCommand.key, sizeof(risingCommand.key));
                        if (ImGui::Button("Entrar en la sala")) risingSend(2);
                        ImGui::EndTabItem();
                    }
                    ImGui::EndTabBar();
                }
                }
            } else {
                ImGui::Text("%s  |  %u / %u usuarios", risingState.title, risingState.count, risingState.capacity);
                ImGui::TextUnformatted(risingState.address);
                const bool host = risingState.self_id == risingState.host_id;
                if (host) {
                    ImGui::TextWrapped("Codigo: %s", risingState.invite);
                    if (ImGui::Button("Copiar codigo de sala")) SDL_SetClipboardText(risingState.invite);
                    if(risingState.key[0]) {
                    ImGui::Text("Clave: %s", risingState.key);
                    ImGui::SameLine();
                    if (ImGui::Button("Copiar clave")) SDL_SetClipboardText(risingState.key);
                    }
                    if(SDL_getenv("BTC_DEV_TOOLS")) {
                    if (ImGui::Button("Anadir 1 bot de prueba")) risingSend(7, 1);
                    ImGui::SameLine();
                    if (ImGui::Button("Llenar con bots")) risingSend(7, risingState.capacity > risingState.count ? risingState.capacity - risingState.count : 0);
                    ImGui::SameLine();
                    if (ImGui::Button("Retirar bots")) risingSend(8);
                    ImGui::TextWrapped("Los bots prueban usuarios, chat, listo y expulsiones; no juegan combates.");
                    }
                }
                if (ImGui::Button("Cambiar listo / esperando")) risingSend(6);
                ImGui::SameLine();
                if (ImGui::Button(host ? "Cerrar sala" : "Salir de sala")) risingSend(5);
                risingTournamentPanel(host);
                if (ImGui::BeginTable("rising-users", 3, ImGuiTableFlags_Borders | ImGuiTableFlags_RowBg)) {
                    ImGui::TableSetupColumn("Usuario"); ImGui::TableSetupColumn("Estado"); ImGui::TableSetupColumn("Anfitrion");
                    ImGui::TableHeadersRow();
                    for (unsigned i = 0; i < risingState.count; ++i) {
                        const RisingUser &user = risingState.users[i];
                        ImGui::PushID((int)user.id);
                        ImGui::TableNextRow(); ImGui::TableNextColumn();
                        ImGui::Text("%s%s%s%s", user.name, user.id == risingState.host_id ? " [Host]" : "", user.id == risingState.self_id ? " (tu)" : "", user.flags & 2 ? " [BOT]" : "");
                        ImGui::TableNextColumn(); ImGui::TextUnformatted(user.flags & 1 ? "Listo" : "Esperando");
                        ImGui::TableNextColumn();
                        if (host && user.id != risingState.self_id && ImGui::Button("Expulsar")) risingSend(4, user.id);
                        ImGui::PopID();
                    }
                    ImGui::EndTable();
                }
                ImGui::TextWrapped("Tab abre el chat del juego para todos los miembros de esta sala, tambien durante los combates.");
            }
            ImGui::EndDisabled();
        }
}
