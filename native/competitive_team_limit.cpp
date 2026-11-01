// Reviewed 0.1.38.1 selection layout (decomp src/menu/menu_e_b.c). Online, both peers
// enforce the cap negotiated in the native rules word; offline, only the practice cap
// chosen in the Loader applies. No room UI state is consulted.
//
// TeamSel_Run calls TeamSel_Update (animation only) and then TeamSel_Input, which is
// where the member cursor moves. The cap is therefore applied around TeamSel_Input,
// inside the same frame, comparing the cursor before and after the game's own input.
// Nothing is remembered between frames, so a rollback re-run computes the same result.
#include "team_limit_rules.h"
extern "C" {
extern uint32_t gTeamSel;
void TeamSel_Update(void);
float TeamSel_Input(int *);
void TeamSel_ClipGoto(int, int, int, char *);
void TeamSel_RequestFace(int);
}
enum {
    TeamSelSides = 0x8e8,       // TeamSel.side[2] (32-bit game pointers)
    TeamSideCursor = 0x12c,     // TeamSelSide.cur
    TeamSideCount = 0x134,      // TeamSelSide.memberCount
    TeamSideChara = 0x138,      // TeamSelSide.chara (portrait shown)
    TeamSideState = 0x13c,      // TeamSelSide.state
    TeamMemberSize = 0x30,      // sizeof(TsMember)
    TeamMemberChara = 0x1c,     // TsMember.chara
    TeamClipTeam = 6,           // TEAMSEL_CLIP_TEAM
};

// 5 = no cap. Defined by the including object (online rules word / offline practice).
static unsigned competitiveTeamCap();

static unsigned char *competitiveTeamSide(int p) {
    if (!gTeamSel) return 0;
    const uint32_t address = *(uint32_t *)((uintptr_t)gTeamSel + TeamSelSides + 4 * p);
    return address ? (unsigned char *)(uintptr_t)address : 0;
}

// Same sequence the native list movement uses, so highlight and portrait follow the cursor.
static void competitiveMoveTeamCursor(int p, unsigned char *side, int target) {
    TeamSel_ClipGoto(p + 1, p, TeamClipTeam, (char *)"fl_off_start");
    *(int *)(side + TeamSideCursor) = target;
    TeamSel_ClipGoto(p + 1, p, TeamClipTeam, (char *)"fl_on_start");
    const int member = target == CompetitiveTeamMenuPlate ? 0 : target;
    *(int *)(side + TeamSideChara) = *(int *)(side + member * TeamMemberSize + TeamMemberChara);
    TeamSel_RequestFace(p);
}

static void competitiveApplyTeamLimit(const int *before) {
    const unsigned limit = competitiveTeamCap();
    for (int p = 0; p < 2; ++p) {
        unsigned char *side = competitiveTeamSide(p);
        if (!side) continue;
        const int cursor = *(int *)(side + TeamSideCursor);
        const int target = CompetitiveTeamCursor(before ? before[p] : -1, cursor, *(int *)(side + TeamSideCount),
                                                 *(int *)(side + TeamSideState), limit);
        if (target != cursor) competitiveMoveTeamCursor(p, side, target);
    }
}

extern "C" float Competitive_TeamSelectInput(int *result) {
    const bool limited = gTeamSel && competitiveTeamCap() < 5;
    int before[2] = {-1, -1};
    if (limited)
        for (int p = 0; p < 2; ++p)
            if (unsigned char *side = competitiveTeamSide(p)) before[p] = *(int *)(side + TeamSideCursor);
    const float value = TeamSel_Input(result);
    if (limited && gTeamSel) competitiveApplyTeamLimit(before);
    return value;
}

// Safety net only: the input wrapper never leaves the cursor on the empty slot.
extern "C" void Competitive_TeamSelectUpdate() {
    TeamSel_Update();
    if (gTeamSel && competitiveTeamCap() < 5) competitiveApplyTeamLimit(0);
}
