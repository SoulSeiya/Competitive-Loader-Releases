// Included by competitive_score.cpp: presentation hooks share one COFF object.
#include <winsock2.h>
#include <windows.h>
#include <SDL3/SDL.h>
#include "window_policy.h"

extern "C" SDL_Window *GsDraw_Window(void);
extern "C" int Ui_Event(const SDL_Event *);
typedef LONG_PTR (WINAPI *GetWindowLongFn)(HWND, int);
typedef LONG_PTR (WINAPI *SetWindowLongFn)(HWND, int, LONG_PTR);
typedef LRESULT (WINAPI *CallWindowFn)(WNDPROC, HWND, UINT, WPARAM, LPARAM);
static HWND guardedWindow;
static WNDPROC originalWindowProc;
static GetWindowLongFn getWindowLong;
static SetWindowLongFn setWindowLong;
static CallWindowFn callWindow;
static volatile LONG windowOnline;

static LRESULT CALLBACK competitiveWindowProc(HWND hwnd, UINT message, WPARAM wp, LPARAM lp) {
    // No network calls here: a window message must never start a connection.
    if (CompetitiveWindowBlocks(message, (uintptr_t)wp, windowOnline != 0)) return 0;
    WNDPROC original = originalWindowProc;
    if (message == WM_NCDESTROY && hwnd == guardedWindow) {
        guardedWindow = NULL;
        originalWindowProc = NULL;
    }
    return original && callWindow ? callWindow(original, hwnd, message, wp, lp) : 0;
}

static void competitiveWindowUpdate(bool online) {
    InterlockedExchange(&windowOnline, online ? 1 : 0);
    if (!getWindowLong || !setWindowLong || !callWindow) {
        HMODULE module = GetModuleHandleW(L"user32.dll");
        if (!module) return;
        getWindowLong = (GetWindowLongFn)GetProcAddress(module, "GetWindowLongPtrW");
        setWindowLong = (SetWindowLongFn)GetProcAddress(module, "SetWindowLongPtrW");
        callWindow = (CallWindowFn)GetProcAddress(module, "CallWindowProcW");
        if (!getWindowLong || !setWindowLong || !callWindow) return;
    }
    if (online && !guardedWindow) {
        SDL_Window *window = GsDraw_Window();
        if (!window) return;
        HWND hwnd = (HWND)SDL_GetPointerProperty(SDL_GetWindowProperties(window), SDL_PROP_WINDOW_WIN32_HWND_POINTER, NULL);
        if (!hwnd) return;
        WNDPROC old = (WNDPROC)getWindowLong(hwnd, GWLP_WNDPROC);
        if (!old) return;
        // Assign before subclassing so the new procedure can always forward.
        originalWindowProc = old;
        LONG_PTR previous = setWindowLong(hwnd, GWLP_WNDPROC, (LONG_PTR)competitiveWindowProc);
        if (previous) {
            originalWindowProc = (WNDPROC)previous;
            guardedWindow = hwnd;
            ScoreLog(stderr, "net: window guard active (move/resize/system menu/F11 blocked)\n");
        } else originalWindowProc = NULL;
    } else if (!online && guardedWindow) {
        if (getWindowLong(guardedWindow, GWLP_WNDPROC) == (LONG_PTR)competitiveWindowProc)
            setWindowLong(guardedWindow, GWLP_WNDPROC, (LONG_PTR)originalWindowProc);
        guardedWindow = NULL;
        originalWindowProc = NULL;
        ScoreLog(stderr, "net: window guard released\n");
    }
}

extern "C" int Competitive_WindowEvent(const SDL_Event *event) {
    if (windowOnline && event && event->type == SDL_EVENT_KEY_DOWN && event->key.key == SDLK_F11) return 1;
    return Ui_Event(event);
}
