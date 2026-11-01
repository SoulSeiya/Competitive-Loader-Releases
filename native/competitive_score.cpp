#include "score_tracker.h"
#include <imgui.h>
#include <stdio.h>

extern "C" {
void Port_NetBeginTick(unsigned);
void Port_NetSessionBegin(int, const char *, int);
void Port_NetSessionEnd(void);
void Port_NetLeave(void);
void Port_SessionReturn(void);
int Port_NetSession(void);
int Port_NetMe(void);
const char *Port_NetName(int);
int BtlSeq_CheckBattleEnd(void);
struct ScoreBattleResult { int winner, reason; };
ScoreBattleResult *Battle_GetResult(void);
extern unsigned sChecked;
extern int sRollMax, gPortResim;
extern int gPortMenuMode;
void SDL_LockSpinlock(int *);
void SDL_UnlockSpinlock(int *);
int SDL_snprintf(char *, size_t, const char *, ...);

}

extern "C" int ScoreLog(FILE *, const char *, ...) __asm__("fprintf");
#include "competitive_performance.cpp"
#include "competitive_window.cpp"
#include "competitive_ft.cpp"
#include "competitive_room.cpp"

static ScoreTracker tracker;
static int scoreLock;
static unsigned renderedFrames;
static unsigned drawnWinner;
// Presentation hints written by the game thread, read by the renderer only.
static bool fightLive, battleSeen;
static uint32_t battleSeenTick;
static int pendingExitPad = -1;
static unsigned pendingExitTick;
// ---- offline practice against the CPU (rules from the Loader, read once) ----
#include "competitive_practice.h"
static CompetitivePracticeRules practiceRules;
static volatile LONG practiceState = -1; // -1 not read yet, 0 off, 1 on
static bool practiceWasLive;
static bool competitivePracticeEnabled() {
    if (practiceState < 0) {
        CompetitivePracticeRules rules = {};
        const bool on = CompetitivePracticeParse(SDL_getenv("BTC_PRACTICE_FT"), SDL_getenv("BTC_PRACTICE_SECONDS"),
                                                 SDL_getenv("BTC_PRACTICE_CHARACTERS"), rules);
        if (on) practiceRules = rules;
        if (InterlockedCompareExchange(&practiceState, on ? 1 : 0, -1) == -1 && on)
            ScoreLog(stderr, "btc: practice ft=%u seconds=%u characters=%u cpu=max (offline only)\n",
                     rules.ft, rules.seconds, rules.characters);
    }
    return practiceState == 1;
}
// Practice never applies to an online session, whatever the launch environment says.
static bool competitivePractice() { return !Port_NetSession() && competitivePracticeEnabled(); }
static unsigned competitiveTeamCap() {
    if (Port_NetSession()) return CompetitiveTeamLimit(sRules);
    return competitivePractice() ? practiceRules.characters : 5;
}
extern "C" void BattleSetup_SetMember(int, int, int, int, int, int, float, void *);
// Raises the CPU of every member to the game's maximum difficulty, offline practice only.
extern "C" void Competitive_PracticeSetMember(int side, int index, int chara, int costume, int variant, int cpuLevel,
                                              float health, void *items) {
    if (competitivePractice()) cpuLevel = CompetitivePracticeCpu(cpuLevel);
    BattleSetup_SetMember(side, index, chara, costume, variant, cpuLevel, health, items);
}
static bool exitReported;
extern "C" int PauseMenu_Update(int, int);
// Observe only an explicit exit selected by this pad. Opening/resuming pause and
// rematches are not abandonments. Publish after the rollback confirmation frontier.
extern "C" int Competitive_PauseMenuUpdate(int pad, int which) {
    const int result = PauseMenu_Update(pad, which);
    const ScoreBattleResult *battle = Battle_GetResult();
    if (Port_NetSession() && !gPortResim && pad >= 0 && pad < 2 && battle &&
            (battle->winner & 8) && (battle->reason & 0x68)) {
        SDL_LockSpinlock(&scoreLock);
        if (!tracker.setWinner && pendingExitPad < 0 && !exitReported) {
            pendingExitPad = pad; pendingExitTick = tracker.lastTick;
        }
        SDL_UnlockSpinlock(&scoreLock);
    }
    return result;
}
#include "competitive_team_limit.cpp"
#include "competitive_menu_startup.cpp"
#include "competitive_main_menu.cpp"

extern "C" void Competitive_ScoreBeginTick(unsigned tick) {
    // Update the score only after the original rollback step has returned.
    Port_NetBeginTick(tick);
    const bool online = Port_NetSession() != 0;
    const bool practice = !online && competitivePracticeEnabled();
    competitiveWindowUpdate(online);
    SDL_LockSpinlock(&scoreLock);
    bool newPracticeSet = false;
    if (practice) {
        // After a completed practice set, the next fight that starts opens a new set.
        const ScoreBattleResult *current = Battle_GetResult();
        const bool live = current && !(current->winner & 0x1f);
        if (live && !practiceWasLive && tracker.setWinner) { tracker.reset(); newPracticeSet = true; }
        practiceWasLive = live;
    }
    const unsigned before = tracker.wins[0] + tracker.wins[1] + tracker.draws;
    tracker.begin_tick(tick, sRollMax > 0 ? sChecked : tick, online || practice, gPortResim != 0,
                       online ? CompetitiveFt(sRules) : practice ? practiceRules.ft : 0);
    // Battle_Restart is inlined in the reviewed EXE (no direct calls to hook).
    // A cleared native result reliably marks the next fight, including rematches.
    const ScoreBattleResult *result = Battle_GetResult();
    if (result && !(result->winner & 0x1f)) tracker.new_round();
    fightLive = (online || practice) && result && !(result->winner & 0x1f);
    const unsigned a = tracker.wins[0], b = tracker.wins[1], draws = tracker.draws;
    const bool leave = online && tracker.should_leave(tick, gPortResim != 0);
    int exitPad = -1;
    if (online && !gPortResim && pendingExitPad >= 0 && !exitReported &&
            pendingExitTick < (sRollMax > 0 ? sChecked : tick)) {
        exitPad = pendingExitPad; exitReported = true;
    }
    const unsigned exitTarget = tracker.target;
    SDL_UnlockSpinlock(&scoreLock);
    if (exitPad >= 0 && exitTarget >= 1 && exitTarget <= 5)
        ScoreLog(stderr, "btc: pause_exit loser=P%d P1=%u P2=%u target=%u\n", exitPad+1,
                 exitPad == 0 ? a : exitTarget, exitPad == 1 ? b : exitTarget, exitTarget);
    if (newPracticeSet) ScoreLog(stderr, "btc: practice new_set\n");
    // Practice uses its own log line: the Loader only reads "net:" lines as online results.
    if (a + b + draws > before)
        ScoreLog(stderr, practice ? "btc: practice score tick=%u P1=%u P2=%u draws=%u\n" :
                 "net: score confirmed tick=%u P1=%u P2=%u draws=%u\n", tick, a, b, draws);
    if (leave) {
        ScoreLog(stderr, "net: FT complete target=%u winner=P%u; GG; leaving session\n", tracker.target, tracker.setWinner);
        Port_NetLeave();
    }
    if (InterlockedExchange(&risingLeaveRequested, 0) && online) Port_NetLeave();
}

extern "C" void Competitive_ScoreSessionBegin(int role, const char *address, int port) {
    competitiveWindowUpdate(true);
    SDL_LockSpinlock(&scoreLock);
    tracker.reset();
    pendingExitPad = -1; exitReported = false;
    fightLive = battleSeen = false; battleSeenTick = 0;
    SDL_UnlockSpinlock(&scoreLock);
    if(role==3) { Port_SessionReturn(); return; }
    Port_NetSessionBegin(role, address, port);
    ScoreLog(stderr, "btc: session_begin online=%d\n", Port_NetSession() != 0);
}

extern "C" void Competitive_ScoreSessionEnd(void) {
    if (tracker.setWinner && tracker.target)
        ScoreLog(stderr, "btc: set_result P1=%u P2=%u target=%u\n", tracker.wins[0], tracker.wins[1], tracker.target);
    ScoreLog(stderr, "btc: session_end\n");
    competitiveWindowUpdate(false);
    SDL_LockSpinlock(&scoreLock);
    tracker.reset();
    fightLive = battleSeen = false; battleSeenTick = 0;
    SDL_UnlockSpinlock(&scoreLock);
    Port_NetSessionEnd();
}

extern "C" int Competitive_ScoreBattleEnd(void) {
    const int ended = BtlSeq_CheckBattleEnd();
    const bool tracked = Port_NetSession() || competitivePractice();
    if (tracked) {
        // Only tells the renderer that a fight is on screen (for the fight presentation).
        SDL_LockSpinlock(&scoreLock);
        battleSeen = true; battleSeenTick = tracker.lastTick;
        SDL_UnlockSpinlock(&scoreLock);
    }
    if (ended && tracked) {
        ScoreBattleResult *result = Battle_GetResult();
        if (result) {
            SDL_LockSpinlock(&scoreLock);
            tracker.observe((unsigned)result->winner);
            SDL_UnlockSpinlock(&scoreLock);
        }
    }
    return ended;
}

#include "competitive_theme.cpp"

extern "C" void OriginalImGuiRender(void) __asm__("_ZN5ImGui6RenderEv");

extern "C" void Competitive_ScoreRender(void) {
    ++renderedFrames;
    static CompetitiveMemory memory;
    static Uint64 winnerSince;
    CompetitiveSet set = {};
    bool active, show, live, inBattle;
    uint32_t last, completed;
    const bool practice = competitivePractice();
    SDL_LockSpinlock(&scoreLock);
    active = tracker.active;
    set.wins[0] = tracker.wins[0]; set.wins[1] = tracker.wins[1]; set.draws = tracker.draws;
    set.target = tracker.target; set.winner = tracker.setWinner;
    last = tracker.lastTick; completed = tracker.completedTick; live = fightLive;
    inBattle = battleSeen && last >= battleSeenTick && last - battleSeenTick < 30;
    SDL_UnlockSpinlock(&scoreLock);
    // Online the set is shown for the whole session; in practice only during fights,
    // so the game's own menus between fights stay clear.
    show = active && (!practice || inBattle);
    risingSocialDraw();
    const Uint64 now = SDL_GetTicks();
    memory.observe(set, active, now);
    if (show) {
        const int me = practice ? 0 : Port_NetMe();
        set.me = me == 0 || me == 1 ? me : -1;
        set.swapped = !practice && Port_HudSwap() != 0;
        set.practice = practice;
        if (practice) competitivePracticeNames();
        if (!set.winner && live && inBattle && set.fight() != memory.shownFight) {
            memory.shownFight = set.fight(); memory.bannerAt = now;
        }
        competitiveScorePanel(set, memory, now);
        if(set.winner) {
            if (!winnerSince) winnerSince = now;
            // Offline the game's own result menu (retry / select) must stay usable: the GG
            // card is shown for a few seconds and then only the scoreboard remains.
            const float progress = practice ? (float)(now - winnerSince) / competitivePracticeGgMs :
                                   last >= completed ? (float)(last - completed) / 300.0f : 0.0f;
            if (!practice || now - winnerSince < competitivePracticeGgMs)
                competitiveWinnerPanel(set, memory, progress, now, winnerSince);
            if(drawnWinner!=set.winner) {
                drawnWinner=set.winner;
                ScoreLog(stderr,"net: FT winner panel GG target=%u winner=P%u\n",set.target,set.winner);
            }
        } else {
            drawnWinner=0; winnerSince=0;
            competitiveFightBanner(set, memory.bannerAt, now);
        }
    } else if (!active || !set.winner) winnerSince = 0;
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

// Room control is independent of drawing. Poll at 20 Hz without creating a
// GPU overlay frame for a waiting member who has no visible HUD or bracket.
#include "competitive_client_lifecycle.cpp"
static void competitiveRoomTick() {
    static Uint64 last;
    const Uint64 now = SDL_GetTicks();
    if (last && now - last < 50) return;
    last = now;
    SDL_LockSpinlock(&scoreLock);
    const unsigned a=tracker.wins[0], b=tracker.wins[1];
    const unsigned winner=tracker.setWinner, target=tracker.target;
    SDL_UnlockSpinlock(&scoreLock);
    risingTournamentPump(a,b,winner,target);
    competitiveClientCloseTick();
}

static bool needs_score_frame(unsigned before) {
    const bool practice = competitivePractice();
    SDL_LockSpinlock(&scoreLock);
    const uint32_t last = tracker.lastTick;
    // Practice keeps the set between fights; build an extra frame only while fighting.
    const bool active = tracker.active && (!practice || (battleSeen && last >= battleSeenTick && last - battleSeenTick < 30));
    SDL_UnlockSpinlock(&scoreLock);
    // Native UI skips its frame when no menu, notice or meter is visible.
    // Build our own frame only in that case, after both backends are ready.
    return (active || risingModeActive || risingBracketOpen) && before == renderedFrames && ImGui::GetCurrentContext() &&
           ImGui::GetIO().BackendRendererUserData && ImGui::GetIO().BackendPlatformUserData;
}

extern "C" void Competitive_ScoreDraw(SDL_GPUCommandBuffer *cmd, SDL_GPUTexture *target) {
    const unsigned before = renderedFrames;
    competitiveVisualTheme();
    competitiveRoomTick();
    risingUiEnter();
    Ui_Draw(cmd, target);
    risingUiLeave();
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
    competitiveVisualTheme();
    competitiveRoomTick();
    risingUiEnter();
    Ui_DrawGL();
    risingUiLeave();
    if (needs_score_frame(before)) {
        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplSDL3_NewFrame();
        ImGui::NewFrame();
        Competitive_ScoreRender();
        nativeUiBuilt = true;
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
    }
}
