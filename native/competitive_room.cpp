// Included by competitive_score.cpp. Only shared memory is touched on the UI thread.
#include "rising_room_shared.h"
extern "C" void OriginalNetMenu(void) __asm__("_ZL9build_netv");
extern bool nativeNetOpen __asm__("_ZL4sNet");
extern "C" void Ui_Toggle(void);
extern "C" void Port_LobbyCancel(void);
extern "C" volatile int gPortNetMenuRequest;
extern "C" bool OriginalRoomBegin(const char *, bool *, ImGuiWindowFlags) __asm__("_ZN5ImGui5BeginEPKcPbi");
typedef HANDLE (WINAPI *RisingOpenMapping)(DWORD, BOOL, LPCSTR);
typedef LPVOID (WINAPI *RisingMapView)(HANDLE, DWORD, DWORD, DWORD, SIZE_T);
typedef BOOL (WINAPI *RisingCloseHandle)(HANDLE);
static RisingShared *risingShared;
// Development room panel is opt-in. The normal Dragon Net Battle path stays native.
static bool risingRoomRequested;
static RisingState risingState;
static RisingCommand risingCommand;
extern "C" int Competitive_WindowEvent(const SDL_Event *);
extern "C" int Competitive_RisingEvent(const SDL_Event *event) {
    const bool wasOnlineMenu = nativeNetOpen;
    const int result = Competitive_WindowEvent(event);
    if (wasOnlineMenu && !nativeNetOpen) risingRoomRequested = false;
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
    if (shared->magic != 0x52435442 || shared->version != 2) {
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
    if (copy.count > 32 || copy.chat_count > 64) return;
    // Bound every string independently, even for an invalid local bridge.
    copy.title[96] = copy.address[128] = copy.notice[256] = copy.key[64] = 0;
    copy.invite[384] = 0;
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

extern "C" bool Competitive_RisingBegin(const char *name, bool *open, ImGuiWindowFlags flags) {
    const bool visible = OriginalRoomBegin(name, open, flags);
    if (visible && name && strcmp(name, "Settings") == 0) {
        if (ImGui::Button("Pruebas de sala BTC (desarrollo)")) {
            risingRoomRequested = true;
            gPortNetMenuRequest = 1;
        }
        ImGui::Separator();
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
    bool open = true;
    ImGui::SetNextWindowPos(ImVec2(ImGui::GetIO().DisplaySize.x * .5f, ImGui::GetIO().DisplaySize.y * .5f),
                            ImGuiCond_Appearing, ImVec2(.5f, .5f));
    ImGui::SetNextWindowSize(ImVec2(720, 570), ImGuiCond_Appearing);
    if (ImGui::Begin("Rising Battle", &open, ImGuiWindowFlags_NoCollapse)) {
        ImGui::TextUnformatted("BTC - Sala de jugadores");
        if (ImGui::Button("Abrir Dragon Net Battle")) risingRoomRequested = false;
        ImGui::TextWrapped("La sala sigue conectada durante el combate. Usa el chat para compartir el codigo de partida.");
        ImGui::Separator();
        if (!risingShared) {
            ImGui::TextWrapped("Abre el juego desde el Loader actualizado para activar las salas.");
        } else {
            ImGui::TextWrapped("%s", risingState.notice);
            ImGui::BeginDisabled(risingBusy());
            if (!risingState.connected) {
                ImGui::InputText("Tu nombre", risingCommand.name, sizeof(risingCommand.name));
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
            } else {
                ImGui::Text("%s  |  %u / %u usuarios", risingState.title, risingState.count, risingState.capacity);
                ImGui::TextUnformatted(risingState.address);
                const bool host = risingState.self_id == risingState.host_id;
                if (host) {
                    ImGui::TextWrapped("Codigo: %s", risingState.invite);
                    if (ImGui::Button("Copiar codigo de sala")) SDL_SetClipboardText(risingState.invite);
                    ImGui::Text("Clave: %s", risingState.key);
                    ImGui::SameLine();
                    if (ImGui::Button("Copiar clave")) SDL_SetClipboardText(risingState.key);
                    if (ImGui::Button("Anadir 1 bot de prueba")) risingSend(7, 1);
                    ImGui::SameLine();
                    if (ImGui::Button("Llenar con bots")) risingSend(7, risingState.capacity > risingState.count ? risingState.capacity - risingState.count : 0);
                    ImGui::SameLine();
                    if (ImGui::Button("Retirar bots")) risingSend(8);
                    ImGui::TextWrapped("Los bots prueban usuarios, chat, listo y expulsiones; no juegan combates.");
                }
                if (ImGui::Button("Cambiar listo / esperando")) risingSend(6);
                ImGui::SameLine();
                if (ImGui::Button(host ? "Cerrar sala" : "Salir de sala")) risingSend(5);
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
                ImGui::SeparatorText("Chat de la sala");
                static char message[385];
                bool send = ImGui::InputText("Mensaje", message, sizeof(message), ImGuiInputTextFlags_EnterReturnsTrue);
                ImGui::SameLine(); send = ImGui::Button("Enviar") || send;
                if (send && message[0]) {
                    memcpy(risingCommand.text, message, sizeof(message));
                    if (risingSend(3)) message[0] = 0;
                }
                if (ImGui::BeginChild("rising-chat", ImVec2(0, 0), ImGuiChildFlags_Borders)) {
                    const bool bottom = ImGui::GetScrollY() >= ImGui::GetScrollMaxY() - 4;
                    for (unsigned i = 0; i < risingState.chat_count; ++i) ImGui::TextWrapped("%s", risingState.chat[i]);
                    if (bottom) ImGui::SetScrollHereY(1);
                }
                ImGui::EndChild();
            }
            ImGui::EndDisabled();
        }
    }
    ImGui::End();
    if (!open) {
        risingRoomRequested = false;
        Ui_Toggle(); // Native close also restores input ownership; membership stays alive.
    }
}
