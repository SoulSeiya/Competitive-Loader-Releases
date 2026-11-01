#pragma once
// Pure cursor rule for the reviewed 0.1.38.1 team select (decomp src/menu/menu_e_b.c).
// In the member list (state 6) TeamSel_Input moves TeamSelSide.cur over the chosen
// members, the empty "add a member" slot (cur == memberCount) and the menu plate (5).
// Once the negotiated cap is reached the empty slot must be skipped, in the direction
// the player was moving: coming from the plate (left) -> last member; otherwise
// (right from the last member, or just after adding one) -> the plate.
enum {
    CompetitiveTeamStateList = 6,
    CompetitiveTeamMenuPlate = 5,
};

inline int CompetitiveTeamCursor(int before, int cursor, int count, int state, unsigned limit) {
    if (limit >= 5 || state != CompetitiveTeamStateList || count < 1 || count < (int)limit ||
            cursor != count || cursor >= CompetitiveTeamMenuPlate)
        return cursor;
    return before == CompetitiveTeamMenuPlate ? count - 1 : CompetitiveTeamMenuPlate;
}
