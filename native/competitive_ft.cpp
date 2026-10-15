// Included in the scoreboard object; extends the existing F1 Host menu.
#include <stdarg.h>
#include <string.h>
#include "ft_rules.h"
extern "C" {
extern uint32_t sRules;
int Port_Setting(const char *, int);
void Port_SettingSave(const char *, int);
void Port_SettingsWrite(void);
void Port_NetRulesSet(int, int, int);
int Port_LobbyStartQuick(int);
}
static int selectedFt = -1;
static bool quickRules;

static int selected_ft() {
    if (selectedFt < 0) {
        selectedFt = Port_Setting("competitive_ft", 0);
        if (selectedFt < 0 || selectedFt > 5) selectedFt = 0;
    }
    return selectedFt;
}

extern "C" void Competitive_FtRulesSet(int type, int dp, int time) {
    Port_NetRulesSet(type, dp, time);
    sRules = CompetitiveFtRules(sRules, quickRules ? 0 : (unsigned)selected_ft());
}

extern "C" int Competitive_FtQuickStart(int queue) {
    quickRules = true;
    const int result = Port_LobbyStartQuick(queue);
    quickRules = false;
    return result;
}

extern "C" void Competitive_FtHostRow(const char *format, ...) {
    if (format && strcmp(format, "The host's choices apply to both players.") == 0) {
        selected_ft();
        ImGui::SetNextItemWidth(260.0f);
        const char *choices[] = {"Sin FT (libre)", "FT1", "FT2", "FT3", "FT4", "FT5"};
        if (ImGui::Combo("Primero a (FT)", &selectedFt, choices, 6)) {
            Port_SettingSave("competitive_ft", selectedFt);
            Port_SettingsWrite();
        }
        ImGui::TextUnformatted("El primero en alcanzar esas victorias gana el set.");
    }
    va_list args;
    va_start(args, format);
    ImGui::TextDisabledV(format, args);
    va_end(args);
}
