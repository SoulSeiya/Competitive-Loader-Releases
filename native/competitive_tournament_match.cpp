// The two assigned players use the existing, signed native matchmaking service.
// Room members waiting for a turn never join the combat transport.
extern "C" {
int Port_LobbyStartCode(int, const char *);
const char *Port_LobbyCode(void);
const char *Port_LobbyError(void);
int Port_LobbyPoll(void);
void Port_LobbyLaunch(void);
void Port_NetOptions(int, int);
void Port_NetNameSet(const char *);
void Port_NetRulesSet(int, int, int);
}
static char risingMatchTournament[65];
static unsigned risingMatchId;
static int risingMatchStage; // 0 idle, 1 finding peer, 2 launched, -1 failed
static bool risingMatchReported;
static bool risingCodePublished;
static Uint64 risingCodeSentAt;
static char risingMatchNotice[257];
static char risingPublishedMatchNotice[257];
static int risingLastLobbyState = -99;
static bool risingResultPending;
static unsigned risingResult1, risingResult2;
static Uint64 risingResultSentAt;

// Show the native connection phase in the desktop Loader too. No membership or
// combat code is sent with diagnostics; the existing bridge owns the log.
struct RisingMatchStatusPublisher {
    ~RisingMatchStatusPublisher() {
        if (!risingState.connected || !risingMatchNotice[0] || risingBusy() ||
                strcmp(risingMatchNotice, risingPublishedMatchNotice) == 0) return;
        SDL_snprintf(risingCommand.text, sizeof(risingCommand.text), "%s", risingMatchNotice);
        if (risingSend(25)) SDL_snprintf(risingPublishedMatchNotice, sizeof(risingPublishedMatchNotice), "%s", risingMatchNotice);
    }
};

static void risingTournamentPump(unsigned wins1, unsigned wins2, unsigned winner, unsigned target) {
    risingRead();
    RisingMatchStatusPublisher publishStatus;
    const bool online = Port_NetSession() != 0;
    const RisingTournament &t = risingState.tournament;
    if (online && risingMatchStage == 2 && winner && target && !risingResultPending && !risingMatchReported) {
        risingResultPending = true;
        risingResult1 = wins1; risingResult2 = wins2;
        risingResultSentAt = 0;
    }
    if (risingResultPending && (!risingState.connected || strcmp(t.id, risingMatchTournament) != 0 ||
            t.current != risingMatchId || t.status == 2)) {
        risingResultPending = false;
        risingMatchReported = true;
    }
    if (risingResultPending && !risingBusy() && (!risingResultSentAt || SDL_GetTicks() - risingResultSentAt >= 1000)) {
        risingCommand.score1 = risingResult1; risingCommand.score2 = risingResult2;
        SDL_snprintf(risingCommand.tournament_id, sizeof(risingCommand.tournament_id), "%s", risingMatchTournament);
        if (risingSend(15, risingMatchId)) risingResultSentAt = SDL_GetTicks();
    }
    if (online) {
        if (risingMatchStage == 2 && !winner && (!risingState.connected ||
                strcmp(t.id, risingMatchTournament) != 0 || t.current != risingMatchId || t.status == 2))
            InterlockedExchange(&risingLeaveRequested, 1); // Game tick owns session return, never the renderer.
        return;
    }
    if (!risingState.connected || t.status != 1 || !t.current || !t.role || t.current > t.count) {
        if (risingMatchStage == 1) Port_LobbyCancel();
        risingMatchStage = 0;
        risingMatchId = 0;
        return;
    }
    const RisingMatch &m = t.matches[t.current-1];
    if (m.bots & 1) return; // Only dummy room bots skip combat; game bots have their own client process.
    if (risingMatchId != t.current || strcmp(risingMatchTournament, t.id) != 0) {
        if (risingMatchStage == 1) Port_LobbyCancel();
        risingMatchStage = 0; risingMatchReported = risingCodePublished = false;
        risingCodeSentAt = 0;
        risingResultPending = false;
        risingMatchId = t.current;
        SDL_snprintf(risingMatchTournament, sizeof(risingMatchTournament), "%s", t.id);
        risingMatchNotice[0] = 0;
        risingLastLobbyState = -99;
    }
    if (risingMatchStage == 0 && !risingBusy()) {
        if(SDL_getenv("BTC_MATCH_UNCONFIGURED")) {
            SDL_snprintf(risingMatchNotice,sizeof(risingMatchNotice),"Falta configurar el Worker BTC en el Loader. Este cruce espera nuestro servicio; no usa el servidor oficial.");
            return;
        }
        if (t.role == 2 && !m.code[0]) {
            SDL_snprintf(risingMatchNotice,sizeof(risingMatchNotice),"P2: esperando a que P1 publique el codigo de combate.");
            return;
        }
        for (unsigned i = 0; i < risingState.count; ++i)
            if (risingState.users[i].id == risingState.self_id) Port_NetNameSet(risingState.users[i].name);
        Port_NetOptions(8, -2);
        // Preserve personal Host defaults: these rules belong only to this tournament match.
        const int timeChoice=CompetitiveTournamentTime(t.seconds);
        if(timeChoice<0 || t.characters<1 || t.characters>5) {
            risingMatchStage=-1;
            SDL_snprintf(risingMatchNotice,sizeof(risingMatchNotice),"Reglas incompatibles: actualiza ambos Loaders y guarda las reglas del torneo.");
            return;
        }
        Port_NetRulesSet(t.characters > 1 ? 1 : 0, 0, timeChoice);
        sRules = CompetitiveFtRules(sRules, t.ft);
        sRules = CompetitiveTeamLimitRules(sRules, t.characters);
        const int result = Port_LobbyStartCode(t.role == 1, t.role == 1 ? "" : m.code);
        if (result < 0) {
            risingMatchStage = -1;
            SDL_snprintf(risingMatchNotice, sizeof(risingMatchNotice), "No se pudo iniciar la conexion del cruce. Revisa el registro del Loader.");
            return;
        }
        risingMatchStage = 1;
        fprintf(stderr,"bt3: tournament: match=%u role=P%u matchmaking started\n",t.current,t.role);
        SDL_snprintf(risingMatchNotice, sizeof(risingMatchNotice), "Conectando cruce #%u por codigo nativo...", t.current);
    }
    if (risingMatchStage != 1) return;
    if (t.role == 1 && m.code[0]) risingCodePublished = true;
    if (t.role == 1 && !risingCodePublished && !risingBusy() && (!risingCodeSentAt || SDL_GetTicks()-risingCodeSentAt >= 1000)) {
        const char *code = Port_LobbyCode();
        if (code && code[0]) {
            SDL_snprintf(risingCommand.text, sizeof(risingCommand.text), "%s", code);
            SDL_snprintf(risingCommand.tournament_id, sizeof(risingCommand.tournament_id), "%s", t.id);
            if (risingSend(17, t.current)) risingCodeSentAt = SDL_GetTicks();
        }
    }
    const int state = Port_LobbyPoll();
    if (state != risingLastLobbyState) {
        risingLastLobbyState = state;
        fprintf(stderr,"bt3: tournament: match=%u role=P%u lobby_state=%d\n",t.current,t.role,state);
    }
    if (state == 2) {
        risingMatchStage = 2;
        SDL_snprintf(risingMatchNotice,sizeof(risingMatchNotice),"Cruce #%u: rival conectado. Abriendo seleccion de personajes...",t.current);
        Port_LobbyLaunch();
        if (nativeNetOpen) Ui_Toggle();
    } else if (state < 0 || state == 0) {
        risingMatchStage = -1;
        const char *why = Port_LobbyError();
        const char *fallback = state == -4 ? "Los dos juegos no pueden comunicarse por red. Revisa NAT/firewall o relay." :
            state == 0 ? "La conexion del cruce se cancelo antes de iniciar la partida." : "El servicio de combate rechazo la conexion o el codigo caduco.";
        SDL_snprintf(risingMatchNotice, sizeof(risingMatchNotice), "Error de conexion: %s", why && why[0] ? why : fallback);
        fprintf(stderr,"bt3: tournament: match=%u role=P%u failed state=%d: %s\n",t.current,t.role,state,risingMatchNotice);
    } else if (state == 1) {
        SDL_snprintf(risingMatchNotice,sizeof(risingMatchNotice),"Cruce #%u: ambos juegos encontrados; intentando conexion directa o relay...",t.current);
    } else if (state == 3) {
        SDL_snprintf(risingMatchNotice,sizeof(risingMatchNotice),t.role == 1 ?
            "Cruce #%u: codigo preparado; esperando a que P2 lo encuentre desde su juego..." :
            "Cruce #%u: buscando el codigo de combate de P1...",t.current);
    }
}
