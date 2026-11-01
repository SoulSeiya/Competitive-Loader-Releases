// Included by competitive_score.cpp; reviewed 0.1.38.1 Pad ABI.
extern "C" { void Pad_UpdateGameButtons(int); extern unsigned char gPad[]; }
extern "C" void Competitive_RankedPadUpdate(int pad) {
    Pad_UpdateGameButtons(pad);
    const ScoreBattleResult *battle = Battle_GetResult();
    if (pad < 0 || pad > 1 || !rankedStartSession || !Port_NetSession() ||
            gPortMenuMode || !battle || (battle->winner & 0x1f)) return;
    // Pad.gameHeld/gamePressed/gameRepeat, not raw controller bytes. Strip only
    // START after the original conversion, on both pads and rollback replays.
    // Selection and result menus keep their normal controls.
    for (unsigned offset = 0x188; offset <= 0x190; offset += 4) {
        unsigned value;
        unsigned char *word = gPad + pad * 0x1c0 + offset;
        memcpy(&value, word, sizeof(value));
        value &= ~0x1000u;
        memcpy(word, &value, sizeof(value));
    }
}
