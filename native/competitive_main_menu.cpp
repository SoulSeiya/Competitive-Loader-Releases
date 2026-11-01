#include "main_menu_filter.h"
extern "C" {
void MainMenu_Init(int);
extern uint32_t gMainMenu;
void Competitive_MainMenuInit(int section) {
    MainMenu_Init(section);
    Competitive_MenuHello();
    if (!gMainMenu) return;
    // Reviewed 0.1.38.1: twelve 32-bit item ids; game pointers remain 32-bit.
    unsigned char *menu = (unsigned char *)(uintptr_t)gMainMenu;
    CompetitiveFilterMainMenu((int *)(menu + 0x118), *(int *)(menu + 0x148),
                             *(int *)(menu + 0x14c), *(int *)(menu + 0x10c));
}
}
