// Reviewed TeamSel ABI, BTC 0.1.38.1. Plate 0 is Normal; 1..3 are
// the saved item sets. Saved custom characters offer plates 0..1 instead.
// Apply around native input: correcting only afterwards would let an immediate
// confirm accept Normal. All decisions depend on rollback simulation memory.
static bool competitiveCustomMenu() {
    return gTeamSel &&
           !(*(const int *)((uintptr_t)gTeamSel + 0x3bc) & 4); // stage menu
}

static int *competitiveMemberPlate(unsigned char *side) {
    const int cursor = *(int *)(side + TeamSideCursor);
    return cursor >= 0 && cursor < 5 ? (int *)(side + cursor * TeamMemberSize + 0x14) : 0;
}

static void competitiveCustomSelection(const int *before) {
    if (!competitiveCustomMenu()) return;
    for (int p = 0; p < 2; ++p) {
        unsigned char *side = competitiveTeamSide(p);
        if (!side) continue;
        const int state = *(int *)(side + TeamSideState);
        if (state != 2 && state != 5) continue;
        int *plate = competitiveMemberPlate(side);
        int &count = *(int *)((uintptr_t)gTeamSel + 0x3c28 + 4 * p);
        // BTC uses saved item sets in every selectable battle mode, including DP.
        // The native mode may offer only Normal; offer the real saved sets instead.
        if (count == 1) count = (*(int *)(side + 0x128) & 0x80) ? 2 : 4;
        if (!plate || count < 2 || count > 4 || (*plate > 0 && *plate < count)) continue;
        const int next = before && before[p] == 1 && *plate == 0 ? count - 1 : 1;
        if (state == 2) TeamSel_ClipGoto(p + 5, p, 2, (char *)"fl_off_start");
        *plate = next;
        if (state == 2) TeamSel_ClipGoto(p + 5, p, 2, (char *)"fl_on_start");
    }
}

// A mode that offers no custom set must not fall back to Normal. Keep cancel
// available, suppressing only confirm for the pad that controls that side.
static unsigned competitiveCustomConfirmBlock() {
    if (!competitiveCustomMenu()) return 0;
    unsigned blocked = 0;
    const int base = *(int *)((uintptr_t)gTeamSel + 0x3c58);
    for (int p = 0; p < 2; ++p) {
        unsigned char *side = competitiveTeamSide(p);
        if (!side) continue;
        const int state = *(int *)(side + TeamSideState);
        int *plate = competitiveMemberPlate(side);
        if ((state == 2 || state == 5) && plate && *plate <= 0 && p - base >= 0 && p - base < 2)
            blocked |= 1u << (p - base);
    }
    return blocked;
}
