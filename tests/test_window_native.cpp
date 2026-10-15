// Integration fixture: its own hidden SDL window, never a user's game window.
#include <winsock2.h>
#include <windows.h>
#include <SDL3/SDL.h>
#include <assert.h>
#include <stdio.h>
static SDL_Window *testWindow;
extern "C" SDL_Window *GsDraw_Window(void) { return testWindow; }
extern "C" int Ui_Event(const SDL_Event *) { return 42; }
int ScoreLog(FILE *, const char *, ...) { return 0; }
#include "../native/competitive_window.cpp"

int main() {
    assert(SDL_Init(SDL_INIT_VIDEO));
    testWindow = SDL_CreateWindow("Window guard fixture", 320, 240, SDL_WINDOW_HIDDEN);
    assert(testWindow);
    HWND hwnd = (HWND)SDL_GetPointerProperty(SDL_GetWindowProperties(testWindow), SDL_PROP_WINDOW_WIN32_HWND_POINTER, NULL);
    assert(hwnd);
    competitiveWindowUpdate(false);
    LONG_PTR before = getWindowLong(hwnd, GWLP_WNDPROC);
    competitiveWindowUpdate(true);
    assert(guardedWindow == hwnd && windowOnline == 1);
    assert(getWindowLong(hwnd, GWLP_WNDPROC) == (LONG_PTR)competitiveWindowProc);
    assert(competitiveWindowProc(hwnd, WM_SYSCOMMAND, SC_MOVE | 2, 0) == 0);
    assert(competitiveWindowProc(hwnd, WM_SYSCOMMAND, SC_SIZE, 0) == 0);
    assert(competitiveWindowProc(hwnd, WM_NCLBUTTONDOWN, HTCAPTION, 0) == 0);
    SDL_Event event = {};
    event.type = SDL_EVENT_KEY_DOWN;
    event.key.key = SDLK_F11;
    assert(Competitive_WindowEvent(&event) == 1);
    event.key.key = SDLK_A;
    assert(Competitive_WindowEvent(&event) == 42);
    competitiveWindowUpdate(false);
    assert(!guardedWindow && !windowOnline);
    assert(getWindowLong(hwnd, GWLP_WNDPROC) == before);
    event.key.key = SDLK_F11;
    assert(Competitive_WindowEvent(&event) == 42);
    competitiveWindowUpdate(true);
    SDL_DestroyWindow(testWindow); // destroy while guarded must forward and clear state
    assert(!guardedWindow && !originalWindowProc);
    SDL_Quit();
    puts("Window guard OK: real HWND subclass, blocked modal commands/F11, offline restore, safe destroy.");
}
