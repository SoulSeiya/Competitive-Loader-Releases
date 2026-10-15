#include "score_tracker.h"
#include <imgui.h>
#include <stdio.h>

extern "C" {
void Port_NetBeginTick(unsigned);
void Port_NetSessionBegin(int, const char *, int);
void Port_NetSessionEnd(void);
int Port_NetSession(void);
int Port_NetMe(void);
const char *Port_NetName(int);
int BtlSeq_CheckBattleEnd(void);
struct ScoreBattleResult { int winner, reason; };
ScoreBattleResult *Battle_GetResult(void);
extern unsigned sChecked;
extern int sRollMax, gPortResim;
void SDL_LockSpinlock(int *);
void SDL_UnlockSpinlock(int *);
int SDL_snprintf(char *, size_t, const char *, ...);

}

extern "C" int ScoreLog(FILE *, const char *, ...) __asm__("fprintf");
#include "competitive_window.cpp"

static ScoreTracker tracker;
static int scoreLock;
static unsigned renderedFrames;

extern "C" void Competitive_ScoreBeginTick(unsigned tick) {
    // Native rollback may restore this very stack frame. Track the tick AFTER
    // its netcode has returned, so speculative observer events get discarded.
    Port_NetBeginTick(tick);
    const bool online = Port_NetSession() != 0;
    competitiveWindowUpdate(online);
    SDL_LockSpinlock(&scoreLock);
    const unsigned before = tracker.wins[0] + tracker.wins[1] + tracker.draws;
    tracker.begin_tick(tick, sRollMax > 0 ? sChecked : tick, online, gPortResim != 0);
    // Battle_Restart is inlined in the reviewed EXE (no direct calls to hook).
    // A cleared native result reliably marks the next fight, including rematches.
    const ScoreBattleResult *result = Battle_GetResult();
    if (result && !(result->winner & 0x1f)) tracker.new_round();
    const unsigned a = tracker.wins[0], b = tracker.wins[1], draws = tracker.draws;
    SDL_UnlockSpinlock(&scoreLock);
    if (a + b + draws > before)
        ScoreLog(stderr, "net: score confirmed tick=%u P1=%u P2=%u draws=%u\n", tick, a, b, draws);
}

extern "C" void Competitive_ScoreSessionBegin(int role, const char *address, int port) {
    competitiveWindowUpdate(true);
    SDL_LockSpinlock(&scoreLock);
    tracker.reset();
    SDL_UnlockSpinlock(&scoreLock);
    Port_NetSessionBegin(role, address, port);
}

extern "C" void Competitive_ScoreSessionEnd(void) {
    competitiveWindowUpdate(false);
    SDL_LockSpinlock(&scoreLock);
    tracker.reset();
    SDL_UnlockSpinlock(&scoreLock);
    Port_NetSessionEnd();
}

extern "C" int Competitive_ScoreBattleEnd(void) {
    const int ended = BtlSeq_CheckBattleEnd();
    if (ended && Port_NetSession()) {
        ScoreBattleResult *result = Battle_GetResult();
        if (result) {
            SDL_LockSpinlock(&scoreLock);
            tracker.observe((unsigned)result->winner);
            SDL_UnlockSpinlock(&scoreLock);
        }
    }
    return ended;
}

extern "C" void OriginalImGuiRender(void) __asm__("_ZN5ImGui6RenderEv");

extern "C" void Competitive_ScoreRender(void) {
    ++renderedFrames;
    unsigned a, b, draws;
    bool show;
    SDL_LockSpinlock(&scoreLock);
    show = tracker.active;
    a = tracker.wins[0]; b = tracker.wins[1]; draws = tracker.draws;
    SDL_UnlockSpinlock(&scoreLock);
    if (show) {
        const int me = Port_NetMe() == 1 ? 1 : 0;
        const char *left = Port_NetName(me), *right = Port_NetName(1 - me);
        char text[192];
        SDL_snprintf(text, sizeof(text), "%.32s  %u - %u  %.32s",
                     left && left[0] ? left : "Tu", me ? b : a, me ? a : b,
                     right && right[0] ? right : "Rival");
        ImGui::SetNextWindowPos(ImVec2(ImGui::GetIO().DisplaySize.x * 0.5f, 8.0f), ImGuiCond_Always, ImVec2(0.5f, 0.0f));
        ImGui::SetNextWindowBgAlpha(0.7f);
        if (ImGui::Begin("##competitive-session-score", 0,
                ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoInputs |
                ImGuiWindowFlags_NoFocusOnAppearing | ImGuiWindowFlags_NoNav | ImGuiWindowFlags_NoSavedSettings)) {
            ImGui::TextUnformatted(text);
            if (draws) {
                SDL_snprintf(text, sizeof(text), "Empates: %u", draws);
                ImGui::TextUnformatted(text);
            }
        }
        ImGui::End();
    }
    OriginalImGuiRender();
}

struct SDL_GPUCommandBuffer;
struct SDL_GPUTexture;
extern "C" void Ui_Draw(SDL_GPUCommandBuffer *, SDL_GPUTexture *);
extern "C" void Ui_DrawAgain(SDL_GPUCommandBuffer *, SDL_GPUTexture *);
extern "C" void Ui_DrawGL(void);
extern bool nativeUiBuilt __asm__("_ZL6sBuilt");
void ImGui_ImplSDLGPU3_NewFrame();
void ImGui_ImplSDL3_NewFrame();
void ImGui_ImplOpenGL3_NewFrame();
void ImGui_ImplOpenGL3_RenderDrawData(ImDrawData *);

static bool needs_score_frame(unsigned before) {
    SDL_LockSpinlock(&scoreLock);
    const bool active = tracker.active;
    SDL_UnlockSpinlock(&scoreLock);
    // Native UI skips its frame when no menu, notice or meter is visible.
    // Build our own frame only in that case, after both backends are ready.
    return active && before == renderedFrames && ImGui::GetCurrentContext() &&
           ImGui::GetIO().BackendRendererUserData && ImGui::GetIO().BackendPlatformUserData;
}

extern "C" void Competitive_ScoreDraw(SDL_GPUCommandBuffer *cmd, SDL_GPUTexture *target) {
    const unsigned before = renderedFrames;
    Ui_Draw(cmd, target);
    if (needs_score_frame(before)) {
        ImGui_ImplSDLGPU3_NewFrame();
        ImGui_ImplSDL3_NewFrame();
        ImGui::NewFrame();
        Competitive_ScoreRender();
        nativeUiBuilt = true;
        Ui_DrawAgain(cmd, target);
    }
}

extern "C" void Competitive_ScoreDrawGL(void) {
    const unsigned before = renderedFrames;
    Ui_DrawGL();
    if (needs_score_frame(before)) {
        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplSDL3_NewFrame();
        ImGui::NewFrame();
        Competitive_ScoreRender();
        nativeUiBuilt = true;
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
    }
}
