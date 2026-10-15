// Included by competitive_room.cpp: tournament UI and the native room-code handoff.
#include "competitive_bracket.cpp"
static void risingTournamentPanel(bool host) {
    const RisingTournament &t = risingState.tournament;
    if (!t.id[0] || !ImGui::CollapsingHeader("Torneo BTC", ImGuiTreeNodeFlags_DefaultOpen)) return;
    static char editingId[65], title[97], roster[385];
    static int ft = 2, characters = 1, score1, score2;
    if (strcmp(editingId, t.id) != 0) {
        SDL_snprintf(editingId, sizeof(editingId), "%s", t.id);
        SDL_snprintf(title, sizeof(title), "%s", t.title);
        ft = (int)t.ft; characters = (int)t.characters;
        roster[0] = 0;
    }
    if (t.status == 0) {
        if (host) {
            ImGui::InputText("Nombre / tematica", title, sizeof(title));
            ImGui::SliderInt("FT por combate", &ft, 1, 5);
            ImGui::SliderInt("Maximo de personajes por jugador", &characters, 1, 5);
            if (ImGui::Button("Guardar reglas del torneo")) {
                SDL_snprintf(risingCommand.title, sizeof(risingCommand.title), "%s", title);
                risingCommand.ft = (unsigned)ft; risingCommand.characters = (unsigned)characters;
                risingSend(10);
            }
        }
        ImGui::Text("%s | FT%u | hasta %u personajes | %u inscritos", t.title, t.ft, t.characters, t.enrolled);
        ImGui::InputText("Tus personajes (separados por coma)", roster, sizeof(roster));
        ImGui::TextWrapped("Inscripcion declarada por nombres. La seleccion de combate aun no bloquea personajes fuera de esta lista.");
        if (ImGui::Button(t.self_enrolled ? "Actualizar mi inscripcion" : "Inscribirme al torneo")) {
            SDL_snprintf(risingCommand.text, sizeof(risingCommand.text), "%s", roster);
            risingSend(11);
        }
        if (t.self_enrolled) {
            ImGui::SameLine();
            if (ImGui::Button("Retirar mi inscripcion")) risingSend(11, 1);
            ImGui::TextWrapped("Inscrito: %s", t.roster);
        } else ImGui::TextUnformatted("No estas inscrito: permaneceras en la sala mientras juegan los participantes.");
        if (t.mode) ImGui::TextWrapped("Todos contra mi: tres sets consecutivos contra bots. Perder un set no te elimina. No es un bracket de eliminacion.");
        if (host && ImGui::Button(t.mode ? "Iniciar prueba (tres sets contra ti)" : "Iniciar torneo (cerrar inscripciones y sortear)")) risingSend(12);
    } else {
        ImGui::Text("%s | FT%u | %u inscritos", t.title, t.ft, t.enrolled);
        if (t.status == 2) {
            ImGui::Text("GG - %s", t.mode ? "Prueba completada" : t.champion ? t.champion_name : "Sin campeon");
        } else {
            ImGui::Text("Cruce actual: #%u | Tu puesto: %s", t.current,
                t.role == 1 ? "Jugador 1" : t.role == 2 ? "Jugador 2" : "Esperando en la sala");
            if (!t.role) ImGui::TextUnformatted("La visualizacion como espectador todavia no esta implementada.");
            if (host && !t.role) {
                if (ImGui::Button("Ver combate local de bots (otra ventana)")) risingSend(20);
                ImGui::TextWrapped("Vista local de prueba: observa una instancia de bot de este equipo. No es una conexion de espectador online.");
            }
            if (t.role && risingMatchNotice[0]) ImGui::TextWrapped("%s", risingMatchNotice);
        }
        if (!t.mode) risingBracket(t);
        if ((t.mode || ImGui::CollapsingHeader("Tabla de cruces")) && ImGui::BeginTable("btc-bracket", 4, ImGuiTableFlags_Borders | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
            ImGui::TableSetupColumn("Ronda / cruce"); ImGui::TableSetupColumn("Jugador 1");
            ImGui::TableSetupColumn("Jugador 2"); ImGui::TableSetupColumn("Resultado"); ImGui::TableHeadersRow();
            for (unsigned i = 0; i < t.count; ++i) {
                const RisingMatch &m = t.matches[i];
                ImGui::TableNextRow(); ImGui::TableNextColumn(); ImGui::Text("R%u / #%u", m.round, m.id);
                ImGui::TableNextColumn(); ImGui::TextUnformatted(m.name1);
                ImGui::TableNextColumn(); ImGui::TextUnformatted(m.name2);
                ImGui::TableNextColumn();
                if (m.status == 2) {
                    if (!m.p1 || !m.p2 || (!m.score1 && !m.score2)) ImGui::TextUnformatted("Pase / WO");
                    else ImGui::Text("%u - %u", m.score1, m.score2);
                } else if (m.status == 1) ImGui::Text("En curso (%u/2 resultados)", m.confirmations);
                else ImGui::TextUnformatted("Pendiente");
            }
            ImGui::EndTable();
        }
        if (host && t.status == 1 && ImGui::Button("Simular siguiente cruce (solo bots)")) risingSend(13);
        if (t.role && t.status == 1) {
            ImGui::TextWrapped("Los resultados del combate automatico se envian al completar el FT. Tambien puedes confirmar el marcador manualmente; debe coincidir con el del rival.");
            ImGui::SliderInt("Victorias P1", &score1, 0, (int)t.ft);
            ImGui::SliderInt("Victorias P2", &score2, 0, (int)t.ft);
            if (ImGui::Button("Confirmar resultado de mi cruce")) {
                risingCommand.score1 = score1; risingCommand.score2 = score2;
                SDL_snprintf(risingCommand.tournament_id, sizeof(risingCommand.tournament_id), "%s", t.id);
                risingSend(15, t.current);
            }
        }
        if (host && t.status == 1 && t.current && t.current <= t.count) {
            const RisingMatch &m = t.matches[t.current-1];
            ImGui::TextUnformatted("Resolver baja (WO):");
            if (ImGui::Button("Dar WO a P1")) risingSend(16, m.p1);
            ImGui::SameLine(); if (ImGui::Button("Dar WO a P2")) risingSend(16, m.p2);
        }
        if (host && ImGui::Button("Nuevo torneo / cancelar actual")) ImGui::OpenPopup("Confirmar nuevo torneo");
        if (ImGui::BeginPopupModal("Confirmar nuevo torneo", NULL, ImGuiWindowFlags_AlwaysAutoResize)) {
            ImGui::TextUnformatted("Se cerrara el bracket actual y se abriran nuevas inscripciones.");
            if (ImGui::Button("Confirmar")) { risingSend(14); ImGui::CloseCurrentPopup(); }
            ImGui::SameLine(); if (ImGui::Button("Volver")) ImGui::CloseCurrentPopup();
            ImGui::EndPopup();
        }
    }
}
