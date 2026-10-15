// Integration fixture: real ImGui, Windows mapping and Loader room bridge.
// Run with mapping name and a free loopback room port; it creates no visible window.
#include <winsock2.h>
#include <windows.h>
#include <SDL3/SDL.h>
#include <imgui.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../native/ft_rules.h"
extern "C" { uint32_t sRules; }
#include "../native/competitive_room.cpp"
bool nativeNetOpen = true;
static int originalMenuCalls;
extern "C" void OriginalNetMenu(void) { ++originalMenuCalls; }
extern "C" void Ui_Toggle(void) { nativeNetOpen = false; }
extern "C" void Port_LobbyCancel(void) {}
extern "C" int Competitive_WindowEvent(const SDL_Event *) { nativeNetOpen = false; return 1; }
extern "C" { volatile int gPortNetMenuRequest; }
extern "C" { uint32_t gProgress; int gPortScreen, gPortMenuMode; }
extern "C" int OriginalMainMenuRun(int) { return 7; }
extern "C" int Port_PadRead(int, unsigned char *data) { data[0]=0xab; return 1; }
extern "C" int Port_NetMe(void) { return 0; }
extern "C" SDL_Window *GsDraw_Window(void) { return NULL; }
static int modeFrames, resets, online, lobbyState, starts, startHost, launches;
static char startCode[16];
extern "C" {
int Job_Run(void) { return 0; }
void Gfx_BeginFrame(void) {}
void Gfx_EndFrame(int n) { assert(n == 1); if (++modeFrames == 2) risingModeActive = 0; }
void Pad_Update(void) {}
void Snd_Update(void) {}
void ColorFade_Update(void) {}
void ColorFade_StartIn(int, int, int, int) {}
void ColorFade_Draw(void) {}
void File_Stub264D90(void) {}
void Dma_Flush(void) {}
void Dma_ResetBuffers(void) { ++resets; }
int sceGsSyncPath(int, unsigned short) { return 0; }
int Port_NetSession(void) { return online; }
void Port_NetRulesSet(int type, int, int) { sRules = (114u << 16) | (unsigned)type; }
void Port_NetOptions(int roll, int delay) { assert(roll == 8 && delay == -2); }
void Port_NetNameSet(const char *) {}
int Port_LobbyStartCode(int host, const char *code) { ++starts; startHost = host; strcpy(startCode, code); return 3; }
const char *Port_LobbyCode(void) { return "ABCDEF"; }
const char *Port_LobbyError(void) { return "fixture failure"; }
int Port_LobbyPoll(void) { return lobbyState; }
void Port_LobbyLaunch(void) { ++launches; }
}

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
    risingRoomRequested = true;
    assert(Competitive_RisingEvent(NULL) == 1 && !risingRoomRequested); // Escape/native close cannot change the next normal entry.
    nativeNetOpen = true;
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
    assert(risingState.tournament.enrolled == 3);
    assert(risingSend(12)); waitCommand();
    assert(risingState.tournament.status == 1 && risingState.tournament.count == 3);
    for (int i = 0; i < 2; ++i) { assert(risingSend(13)); waitCommand(); frame(); }
    assert(risingState.tournament.status == 2 && risingState.tournament.champion);
    assert(risingSend(8)); waitCommand();
    assert(risingState.count == 1);
    frame();
    // Closing the panel must not close the room: it persists during combat.
    nativeNetOpen = false;
    assert(risingState.connected);
    assert(risingSend(5)); waitCommand();
    assert(!risingState.connected);
    unsigned char pad[18] = {};
    risingBotIdentifier = 0;
    assert(Competitive_BotPadRead(0,pad)==1 && pad[0]==0xab);
    risingBotIdentifier = 2;
    assert(Competitive_BotPadRead(0,pad)==1 && pad[2]==128 && pad[17]==0);
    void *progress=VirtualAlloc((void*)0x35000000,0x1000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
    assert(progress && (uintptr_t)progress<0x100000000ULL);
    gProgress=(uint32_t)(uintptr_t)progress;
    assert(Competitive_RisingMainMenu(0)==1 && gPortScreen==1 && *(int*)((char*)progress+0x18)==80);
    risingBotIdentifier=0;gProgress=0;VirtualFree(progress,0,MEM_RELEASE);
    assert(Competitive_RisingMainMenu(0)==7);
    assert(Competitive_TournamentMode() == 0 && modeFrames == 2 && resets == 1);
    RisingShared *real = risingShared;
    RisingShared fake = {};
    risingShared = &fake;
    fake.state.connected = 1; fake.state.self_id = 1;
    strcpy(fake.state.users[0].name, "Host"); fake.state.users[0].id = 1; fake.state.count = 1;
    RisingTournament &t = fake.state.tournament;
    strcpy(t.id, "fixture"); t.status = 1; t.current = 1; t.count = 1; t.ft = 2; t.characters = 1;
    t.matches[0].id = 1; t.matches[0].round = 1; t.matches[0].p1 = 1; t.matches[0].p2 = 2;
    risingTournamentPump(0, 0, 0, 0);
    assert(starts == 0); // Room host waiting for a turn does not join as a third player.
    t.role = 1;
    risingTournamentPump(0, 0, 0, 0);
    assert(starts == 1 && startHost == 1 && CompetitiveFt(sRules) == 2);
    assert(fake.command.op == 17 && strcmp(fake.command.text, "ABCDEF") == 0);
    fake.ack_seq = fake.command_seq;
    strcpy(t.matches[0].code,"ABCDEF"); // The room acknowledged and published the native code.
    lobbyState = 2; nativeNetOpen = true;
    risingTournamentPump(0, 0, 0, 0);
    assert(launches == 1 && risingMatchStage == 2);
    online = 1;
    risingResultSentAt = SDL_GetTicks() - 1001;
    risingTournamentPump(2, 1, 1, 2);
    // First result starts a retry timer at zero; run after the minimum interval if needed.
    if (fake.command.op != 15) { risingResultSentAt = SDL_GetTicks()-1001; risingTournamentPump(2,1,1,2); }
    assert(fake.command.op == 15 && fake.command.score1 == 2 && fake.command.score2 == 1);
    t.current = 0;
    risingTournamentPump(0, 0, 0, 0);
    assert(risingLeaveRequested == 1);
    online = 0; risingLeaveRequested = 0;
    fake.ack_seq = fake.command_seq;
    strcpy(t.id, "fixture2"); t.current = 1; t.role = 2; strcpy(t.matches[0].code, "ABCDEF");
    lobbyState = 3;
    risingTournamentPump(0,0,0,0);
    assert(starts == 2 && startHost == 0 && strcmp(startCode,"ABCDEF") == 0);
    risingShared = real;
    ImGui::DestroyContext();
    puts("Room native UI OK: bracket, bots, TBO mode loop, native code handoff and FT result reporting.");
}
