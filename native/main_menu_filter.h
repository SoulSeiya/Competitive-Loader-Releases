#pragma once
// Preserve the selected disc item when removing the PC-only online entry.
static inline void CompetitiveFilterMainMenu(int *items, int &count, int &top, int cursor) {
    if (count < 1 || count > 12 || cursor < 0 || cursor > 3 || top < 0 || top >= count) return;
    const int selected = items[(top + cursor + 1) % count];
    int kept = 0, selectedIndex = -1;
    for (int i = 0; i < count; ++i) {
        if (items[i] == 11) continue;
        if (items[i] == selected) selectedIndex = kept;
        items[kept++] = items[i];
    }
    if (!kept) return;
    count = kept;
    if (selectedIndex < 0) selectedIndex = 0;
    top = (selectedIndex - cursor - 1 + count * 2) % count;
}
