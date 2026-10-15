#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static int combos, saved = -1, writes, forwarded;
static bool choose;
namespace ImGui {
void SetNextItemWidth(float) {}
bool Combo(const char *, int *selection, const char *const *choices, int count) {
    ++combos;
    assert(count == 6 && strcmp(choices[5], "FT5") == 0);
    if (choose) { *selection = 5; return true; }
    return false;
}
void TextUnformatted(const char *) {}
void TextDisabledV(const char *format, va_list args) {
    if (strcmp(format, "other %d") == 0) forwarded = va_arg(args, int);
}
}
#include "../native/competitive_ft.cpp"
extern "C" {
uint32_t sRules;
int Port_Setting(const char *, int) { return 2; }
void Port_SettingSave(const char *key, int value) {
    assert(strcmp(key, "competitive_ft") == 0); saved = value;
}
void Port_SettingsWrite(void) { ++writes; }
void Port_NetRulesSet(int, int, int) { sRules = (114u << 16) | 0x123;
}
int Port_LobbyStartQuick(int queue) {
    assert(queue == 1 && CompetitiveFt(sRules) == 0);
    Competitive_FtRulesSet(1, 0, 4);
    assert(CompetitiveFt(sRules) == 0);
    return 42;
}
}
int main() {
    Competitive_FtRulesSet(0, 0, 0);
    assert(CompetitiveFt(sRules) == 2);
    assert((sRules & ~(7u << 13)) == ((114u << 16) | 0x123));
    assert(Competitive_FtQuickStart(1) == 42);
    assert(!quickRules && CompetitiveFt(sRules) == 0);
    Competitive_FtRulesSet(0, 0, 0);
    assert(CompetitiveFt(sRules) == 2); // next private room keeps the selection
    Competitive_FtHostRow("other %d", 17);
    assert(forwarded == 17 && combos == 0);
    choose = true;
    Competitive_FtHostRow("The host's choices apply to both players.");
    assert(combos == 1 && saved == 5 && writes == 1);
    Competitive_FtRulesSet(0, 0, 0);
    assert(CompetitiveFt(sRules) == 5);
    puts("FT integration OK: private rules, quick queue isolation, Host row and variadic forwarding.");
}
