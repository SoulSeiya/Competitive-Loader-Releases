// Integration fixture: real ImGui, Windows mapping and Loader room bridge.
// Run with mapping name and a free loopback room port; it creates no visible window.
#include <winsock2.h>
#include <windows.h>
#include <SDL3/SDL.h>
#include <imgui.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../native/competitive_room.cpp"
bool nativeNetOpen = true;
static int originalMenuCalls;
extern "C" void OriginalNetMenu(void) { ++originalMenuCalls; }
extern "C" void Ui_Toggle(void) { nativeNetOpen = false; }
extern "C" void Port_LobbyCancel(void) {}
extern "C" { volatile int gPortNetMenuRequest; }

static void frame() {
    ImGui::NewFrame();
    Competitive_RisingMenu();
    ImGui::Render();
}
static void waitCommand() {
    for (int i = 0; i < 120 && risingBusy(); ++i) SDL_Delay(25);
    assert(!risingBusy());
    risingRead();
}
int main(int argc, char **argv) {
    assert(argc == 3);
    SDL_setenv_unsafe("BTC_ROOM_BRIDGE", argv[1], 1);
    ImGui::CreateContext();
    ImGuiIO &io = ImGui::GetIO();
    io.IniFilename = NULL;
    io.DisplaySize = ImVec2(1280, 720);
    io.DeltaTime = 1.0f / 60.0f;
    unsigned char *pixels; int width, height;
    io.Fonts->GetTexDataAsRGBA32(&pixels, &width, &height);
    frame();
    assert(originalMenuCalls == 1 && !risingRoomRequested); // Native entry is never replaced by default.
    risingRoomRequested = true; // Explicit development panel entry, pending the TBO integration.
    frame(); frame();
    assert(risingShared && !risingState.connected);
    assert(ImGui::GetDrawData()->CmdListsCount > 0);
    strcpy(risingCommand.name, "Native Host");
    strcpy(risingCommand.title, "Rising Native UI");
    strcpy(risingCommand.address, "127.0.0.1");
    risingCommand.port = (uint32_t)atoi(argv[2]);
    assert(risingSend(1)); waitCommand();
    assert(risingState.connected && risingState.count == 1);
    assert(strncmp(risingState.invite, "BTC1-", 5) == 0);
    frame(); frame();
    assert(ImGui::GetDrawData()->CmdListsCount > 0);
    strcpy(risingCommand.text, "Anuncio desde el menu nativo");
    assert(risingSend(3)); waitCommand();
    assert(risingState.chat_count == 2);
    assert(strstr(risingState.chat[1], "Anuncio desde el menu nativo"));
    assert(risingSend(6)); waitCommand();
    assert(risingState.users[0].flags == 1);
    assert(risingSend(7, 3)); waitCommand();
    assert(risingState.count == 4);
    assert(risingState.users[1].flags & 2);
    frame(); frame();
    assert(risingSend(8)); waitCommand();
    assert(risingState.count == 1);
    frame();
    // Closing the panel must not close the room: it persists during combat.
    nativeNetOpen = false;
    assert(risingState.connected);
    assert(risingSend(5)); waitCommand();
    assert(!risingState.connected);
    ImGui::DestroyContext();
    puts("Room native UI OK: real ImGui frames, mapping, host, chat, ready and close.");
}
