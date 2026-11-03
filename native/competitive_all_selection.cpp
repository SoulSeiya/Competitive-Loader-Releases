// Additional selection screens in reviewed BTC 0.1.38.1: CharSel (single
// battles/training) and SoloSel (single-entrant modes). SaveCustom remains owned
// by the game: these wrappers only adjust its set selector, never saved items.
extern "C" {
extern uint32_t gCharSel, gSoloSel;
extern uint32_t gEntrySel, gUbTeamSel;
void CharSel_Input(int *);
void CharSel_ClipGoto(int, int, int, char *);
void SoloSel_Input(int *);
void SoloSel_ClipGoto(int, int, char *);
void EntrySel_Input(int *);
void EntrySel_ClipGoto(int, int, char *);
void UbTeamSel_Input(int *);
void UbTeamSel_ClipGoto(int, int, char *);
}

static int competitiveSavedSetCursor(int before, int current, int count) {
    if (count < 2 || count > 4 || (current > 0 && current < count)) return current;
    return before == 1 && current == 0 ? count - 1 : 1;
}

static void competitiveSingleSets(const int *before, int *after) {
    if (!gCharSel || (*(int *)((uintptr_t)gCharSel + 0x2fc) & 4)) return;
    for (int p = 0; p < 2; ++p) {
        const uint32_t address = *(uint32_t *)((uintptr_t)gCharSel + 0x4f8 + p * 4);
        if (!address) continue;
        unsigned char *side = (unsigned char *)(uintptr_t)address;
        const int state = *(int *)(side + 0x70);
        if (state != 2 && state != 5) continue;
        int &plate = *(int *)(side + 0x14);
        const int count = *(int *)((uintptr_t)gCharSel + 0x37d8 + p * 4);
        const int target = competitiveSavedSetCursor(before ? before[p] : -1, plate, count);
        if (target != plate) {
            if (state == 2) CharSel_ClipGoto(p + 3, p, 2, (char *)"fl_off_start");
            plate = target;
            if (state == 2) CharSel_ClipGoto(p + 3, p, 2, (char *)"fl_on_start");
        }
        if (after) after[p] = plate;
    }
}

extern "C" void Competitive_CharSelectInput(int *result) {
#ifdef BTC_COMBAT_TRACE
    competitiveTraceNames(gCharSel);
#endif
    int before[2] = {-1, -1};
    competitiveSingleSets(0, before);
    CharSel_Input(result);
    competitiveSingleSets(before, 0);
}

static int competitiveSoloSet(int before) {
    if (!gSoloSel) return -1;
    const uint32_t address = *(uint32_t *)((uintptr_t)gSoloSel + 0x21c);
    if (!address) return -1;
    unsigned char *side = (unsigned char *)(uintptr_t)address;
    const int state = *(int *)(side + 0x70);
    if (state != 2 && state != 5) return -1;
    int &plate = *(int *)(side + 0x14);
    int &count = *(int *)((uintptr_t)gSoloSel + 0x1964);
    if (count == 1) count = 4; // BTC also uses saved sets in native no-custom modes.
    const int target = competitiveSavedSetCursor(before, plate, count);
    if (target != plate) {
        if (state == 2) SoloSel_ClipGoto(2, 2, (char *)"fl_off_start");
        plate = target;
        if (state == 2) SoloSel_ClipGoto(2, 2, (char *)"fl_on_start");
    }
    return plate;
}

extern "C" void Competitive_SoloSelectInput(int *result) {
#ifdef BTC_COMBAT_TRACE
    competitiveTraceNames(gSoloSel,0x14);
#endif
    const int before = competitiveSoloSet(-1);
    SoloSel_Input(result);
    competitiveSoloSet(before);
}

// The remaining native selectors use an array of 0x30-byte members/entrants.
// The menu plate is outside that array and must never be treated as a fighter.
static int competitiveEntrantSet(uint32_t work, int selOffset, int stateOffset,
                                 int cursorOffset, int maxMembers, int countOffset,
                                 int movie, void (*clip)(int, int, char *), int before) {
    if (!work) return -1;
    const uint32_t address = *(uint32_t *)((uintptr_t)work + selOffset);
    if (!address) return -1;
    unsigned char *side = (unsigned char *)(uintptr_t)address;
    const int state = *(int *)(side + stateOffset);
    const int cursor = *(int *)(side + cursorOffset);
    if ((state != 2 && state != 5) || cursor < 0 || cursor >= maxMembers) return -1;
    int &plate = *(int *)(side + cursor * 0x30 + 0x14);
    int &count = *(int *)((uintptr_t)work + countOffset);
    if (count == 1) count = 4;
    const int target = competitiveSavedSetCursor(before, plate, count);
    if (target != plate) {
        if (state == 2) clip(movie, 2, (char *)"fl_off_start");
        plate = target;
        if (state == 2) clip(movie, 2, (char *)"fl_on_start");
    }
    return plate;
}

extern "C" void Competitive_EntrySelectInput(int *result) {
    const int before = competitiveEntrantSet(gEntrySel, 0x3c4, 0x1c4, 0x1c0, 8,
                                              0x1b0c, 2, EntrySel_ClipGoto, -1);
    EntrySel_Input(result);
    competitiveEntrantSet(gEntrySel, 0x3c4, 0x1c4, 0x1c0, 8, 0x1b0c, 2, EntrySel_ClipGoto, before);
}

extern "C" void Competitive_UbTeamSelectInput(int *result) {
    const int before = competitiveEntrantSet(gUbTeamSel, 0x344, 0x13c, 0x12c, 5,
                                              0x1abc, 3, UbTeamSel_ClipGoto, -1);
    UbTeamSel_Input(result);
    competitiveEntrantSet(gUbTeamSel, 0x344, 0x13c, 0x12c, 5, 0x1abc, 3, UbTeamSel_ClipGoto, before);
}
