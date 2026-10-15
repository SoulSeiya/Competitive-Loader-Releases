#pragma once
#include <stdint.h>

// Reject commands before Windows enters a modal move/resize/system-menu loop.
inline bool CompetitiveWindowBlocks(unsigned message, uintptr_t param, bool online) {
    if (!online) return false;
    if (message == 0x112) { // WM_SYSCOMMAND
        const uintptr_t command = param & 0xfff0;
        return command == 0xf010 || command == 0xf000 || // SC_MOVE, SC_SIZE
               command == 0xf100 || command == 0xf090;   // SC_KEYMENU, SC_MOUSEMENU
    }
    if (message == 0xa1 || message == 0xa3 || message == 0xa4) {
        // WM_NCLBUTTONDOWN / double click / right button: caption and borders.
        return param == 2 || (param >= 10 && param <= 17);
    }
    return false;
}
