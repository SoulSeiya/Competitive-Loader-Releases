#include "menu_startup_policy.h"
extern "C" void Port_LobbyHelloAsk(void);
static CompetitiveMenuHelloCache menuHelloCache;
static int menuHelloLock;
extern "C" void Competitive_MenuHello(void) {
    // This is still the native signed hello, including server clock learning.
    // The main menu prepares it before the player opens the online panel.
    SDL_LockSpinlock(&menuHelloLock);
    const bool request = menuHelloCache.request(SDL_GetTicks());
    SDL_UnlockSpinlock(&menuHelloLock);
    if (request) Port_LobbyHelloAsk();
}
