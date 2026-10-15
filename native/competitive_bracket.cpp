// Bracket geometry is presentation only; winners and pairings come from the room.
static void risingBracket(const RisingTournament &t) {
    if (!t.count) return;
    if (ImGui::BeginChild("btc-bracket-tree", ImVec2(0, 285), ImGuiChildFlags_Borders,
            ImGuiWindowFlags_HorizontalScrollbar)) {
        ImDrawList *draw = ImGui::GetWindowDrawList();
        const ImVec2 origin = ImGui::GetCursorScreenPos();
        ImVec2 positions[31];
        unsigned rounds = 0, row = 0, lastRound = 0;
        const float stepX = 250, stepY = 82, width = 210, height = 66;
        for (unsigned i = 0; i < t.count; ++i) {
            const RisingMatch &m = t.matches[i];
            if (m.round != lastRound) { row = 0; lastRound = m.round; }
            rounds = m.round;
            const unsigned span = 1u << (m.round - 1);
            positions[i] = ImVec2(origin.x + (m.round-1)*stepX + 8,
                origin.y + ((float)row + .5f)*span*stepY + 22 - height*.5f);
            ++row;
        }
        unsigned previousStart = 0, currentStart = 0, previousCount = (t.count+1)/2;
        for (unsigned round = 2; round <= rounds; ++round) {
            currentStart = previousStart + previousCount;
            for (unsigned i = 0; i < previousCount/2; ++i) {
                const ImVec2 parent = positions[currentStart+i];
                for (unsigned side = 0; side < 2; ++side) {
                    const ImVec2 child = positions[previousStart+2*i+side];
                    const float elbow = child.x + width + 16;
                    const ImU32 color = IM_COL32(92, 116, 145, 255);
                    draw->AddLine(ImVec2(child.x+width,child.y+height*.5f),ImVec2(elbow,child.y+height*.5f),color,1.5f);
                    draw->AddLine(ImVec2(elbow,child.y+height*.5f),ImVec2(elbow,parent.y+height*.5f),color,1.5f);
                    draw->AddLine(ImVec2(elbow,parent.y+height*.5f),ImVec2(parent.x,parent.y+height*.5f),color,1.5f);
                }
            }
            previousStart = currentStart; previousCount /= 2;
        }
        for (unsigned i = 0; i < t.count; ++i) {
            const RisingMatch &m = t.matches[i]; const ImVec2 p = positions[i];
            draw->AddRectFilled(p,ImVec2(p.x+width,p.y+height),IM_COL32(22,31,47,255),5);
            draw->AddRect(p,ImVec2(p.x+width,p.y+height),m.status==1 ? IM_COL32(245,153,37,255) : IM_COL32(69,91,119,255),5);
            char label[80];
            SDL_snprintf(label,sizeof(label),m.status==2 ? "R%u #%u | %u-%u" : "R%u #%u",m.round,m.id,m.score1,m.score2);
            draw->AddText(ImVec2(p.x+7,p.y+3),IM_COL32(160,183,208,255),label);
            draw->PushClipRect(ImVec2(p.x+6,p.y+20),ImVec2(p.x+width-5,p.y+height-2),true);
            draw->AddText(ImVec2(p.x+7,p.y+23),m.winner && m.winner==m.p1 ? IM_COL32(110,231,165,255) : IM_COL32(225,232,243,255),m.name1);
            draw->AddText(ImVec2(p.x+7,p.y+43),m.winner && m.winner==m.p2 ? IM_COL32(110,231,165,255) : IM_COL32(225,232,243,255),m.name2);
            draw->PopClipRect();
        }
        ImGui::Dummy(ImVec2(rounds*stepX, ((t.count+1)/2)*stepY+30));
    }
    ImGui::EndChild();
}
