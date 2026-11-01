#pragma once
// Offline FT practice against the CPU. The Loader chooses the rules and passes them
// at launch (BTC_PRACTICE_FT / _SECONDS / _CHARACTERS). Nothing here is online:
// every use is also gated by Port_NetSession() == 0, and no result is reported.
struct CompetitivePracticeRules { unsigned ft, seconds, characters; };

// CpuLevel_FromSetting(4): the highest difficulty of the game's own settings.
enum { CompetitivePracticeCpuLevel = 29 };

inline bool CompetitivePracticeNumber(const char *text, unsigned &out) {
    if (!text || !*text) return false;
    unsigned value = 0;
    for (int i = 0; text[i]; ++i) {
        if (text[i] < '0' || text[i] > '9' || i >= 4) return false;
        value = value * 10 + (unsigned)(text[i] - '0');
    }
    out = value;
    return true;
}

inline bool CompetitivePracticeParse(const char *ft, const char *seconds, const char *characters,
                                     CompetitivePracticeRules &out) {
    CompetitivePracticeRules r = {};
    if (!CompetitivePracticeNumber(ft, r.ft) || !CompetitivePracticeNumber(seconds, r.seconds) ||
            !CompetitivePracticeNumber(characters, r.characters)) return false;
    if (r.ft < 1 || r.ft > 5 || r.characters < 1 || r.characters > 5) return false;
    if (r.seconds != 180 && r.seconds != 240 && r.seconds != 360 && r.seconds != 480) return false;
    out = r;
    return true;
}

// Index of the battle setup's time table (1..4) for the competitive durations.
inline int CompetitivePracticeTimeIndex(unsigned seconds) {
    switch (seconds) { case 180: return 1; case 240: return 2; case 360: return 3; case 480: return 4; default: return -1; }
}

// Only real CPU levels are raised; -1 (no CPU / special modes) is left alone.
inline int CompetitivePracticeCpu(int level) {
    return level >= 0 ? CompetitivePracticeCpuLevel : level;
}
