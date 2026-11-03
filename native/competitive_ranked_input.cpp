// Included by competitive_score.cpp; reviewed 0.1.38.1 Pad ABI.
extern "C" {
void Pad_UpdateGameButtons(int);
int BattleSide_GetControl(int);
extern unsigned char gPad[];
extern uint32_t gBtlSeq;
}
extern "C" void Competitive_RankedPadUpdate(int pad) {
    Pad_UpdateGameButtons(pad);
    const ScoreBattleResult *battle = Battle_GetResult();
    if (pad < 0 || pad > 1 || gPortMenuMode || !battle || (battle->winner & 0x1f)) return;
    // Reviewed BtlSeq.state at +0: 0 stage intro, 1 character talk, 2 ready,
    // 3 combat. Read simulation state on every call, including rollback. No latch
    // or wall-clock timer: rematches get their own skippable intros.
    if (!gBtlSeq) return;
    int phase;
    memcpy(&phase, (const void *)(uintptr_t)gBtlSeq, sizeof(phase));
    if (phase != 2 && phase != 3) return;
    // BattleSide.control: 0 human pad, 2 CPU (including the idle training
    // opponent). Inspect both actual sides, not menu choice, session type or
    // screen split: casual online and local P1/P2 use the same rule as ranked.
    // CPU battles retain pause, even if a stale ranked session flag exists.
    if (BattleSide_GetControl(0) != 0 || BattleSide_GetControl(1) != 0) return;
    // Pad.gameHeld/gamePressed/gameRepeat, not raw controller bytes. Strip only
    // START after the original conversion, on both pads and rollback replays.
    // Selection, intros and result menus keep their normal controls. Ready is
    // already locked so holding Start through the intro cannot open pause.
    for (unsigned offset = 0x188; offset <= 0x190; offset += 4) {
        unsigned value;
        unsigned char *word = gPad + pad * 0x1c0 + offset;
        memcpy(&value, word, sizeof(value));
        value &= ~0x1000u;
        memcpy(word, &value, sizeof(value));
    }
}
