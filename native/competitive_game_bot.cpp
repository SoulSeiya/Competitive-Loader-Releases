// Programmed test inputs are sampled locally and sent through the normal netcode.
// They are not AI gameplay changes and do not run on the human's client.
extern "C" {
int Port_PadRead(int, unsigned char *);
int Port_NetMe(void);
int OriginalMainMenuRun(int) __asm__("MainMenu_Run");
extern uint32_t gProgress;
extern int gPortScreen, gPortMenuMode;
SDL_Window *GsDraw_Window(void);
}
static int risingBotIdentifier = -1;
static int risingBotId() {
    if (risingBotIdentifier < 0) {
        const char *value = SDL_getenv("BTC_TOURNAMENT_BOT");
        risingBotIdentifier = value ? SDL_atoi(value) : 0;
    }
    return risingBotIdentifier;
}
extern "C" int Competitive_BotPadRead(int socket, unsigned char *data) {
    const int result = Port_PadRead(socket, data);
    const int bot = risingBotId();
    if (!bot || !data) return result;
    unsigned buttons = 0;
    const Uint64 time = SDL_GetTicks();
    if (!Port_NetSession() || gPortMenuMode) {
        if ((time / 30) % 30 == 0) buttons = 0x4000; // Cross confirms menus.
    } else {
        const unsigned phase = (unsigned)(time / 16 + bot * 37) % 180;
        if (phase < 130) buttons |= 0x10; // Approach the opponent; different attack cadence breaks mirror ties.
        if (phase % (bot % 2 ? 20 : 8) == 0) buttons |= 0x8000;
        if (phase % 37 == 0) buttons |= 0x1000;
    }
    memset(data, 0, 18);
    data[0] = (unsigned char)~buttons; data[1] = (unsigned char)~(buttons >> 8);
    data[2] = data[3] = data[4] = data[5] = 128;
    return 1;
}

extern "C" int Competitive_RisingMainMenu(int section) {
    static bool humanDemoEntered;
    const bool bot = risingBotId() != 0;
    const bool demo = !humanDemoEntered && SDL_getenv("BTC_TOURNAMENT_DEMO_USER") != NULL;
    if ((bot || demo) && gProgress) {
        humanDemoEntered = true;
        gPortScreen = 1; // PORT_SCREEN_TBO
        *(int *)((uintptr_t)gProgress + 0x18) = 80; // Native PortScreen_Main dispatch; no menu assets are allocated here.
        if (bot) {
            SDL_Window *window = GsDraw_Window();
            if (window) {
                char title[96]; SDL_snprintf(title,sizeof(title),SDL_getenv("BTC_LOCAL_SPECTATOR") ?
                    "BTC - Espectador local P1/P2 - FT1 - 180 segundos" : "BTC Bot %d - vista local de prueba",risingBotId());
                SDL_SetWindowTitle(window,title);
            }
        }
        return 1;
    }
    return OriginalMainMenuRun(section);
}
