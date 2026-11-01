// Included by competitive_room.cpp. Replace only the PC's TBO screen entry.
// The original Dragon Net Battle and the global disc-data checks are untouched.
extern "C" {
int Job_Run(void);
void Gfx_BeginFrame(void);
void Gfx_EndFrame(int);
void Pad_Update(void);
void Snd_Update(void);
void ColorFade_Update(void);
void ColorFade_StartIn(int, int, int, int);
void ColorFade_Draw(void);
void File_Stub264D90(void);
void Dma_Flush(void);
void Dma_ResetBuffers(void);
int sceGsSyncPath(int, unsigned short);
int Port_NetSession(void);
}

extern "C" int Competitive_TournamentMode(void) {
    risingModeActive = 1;
    risingRoomRequested = false;
    risingSelectTournament = true;
    gPortNetMenuRequest = 1;
    ColorFade_StartIn(0, 0, 0, 0x14);
    fprintf(stderr, "bt3: Rising Battle: TBO tournament mode entered\n");
    while (risingModeActive) {
        Job_Run();
        Gfx_BeginFrame();
        Pad_Update();
        Snd_Update();
        ColorFade_Update();
        ColorFade_Draw();
        File_Stub264D90();
        Gfx_EndFrame(1);
        Dma_Flush();
    }
    if (nativeNetOpen) Ui_Toggle();
    risingRoomRequested = false;
    if (!Port_NetSession()) Port_LobbyCancel();
    sceGsSyncPath(0, 0);
    Dma_ResetBuffers();
    return 0; // PortScreen_Main returns to the native main menu.
}
