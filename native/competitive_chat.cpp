/* Competitive Loader's backward-compatible online chat.

   The official net protocol ignores packet kinds it does not know.  Chat is
   therefore carried as its own packet and consumed before the official
   receiver sees it.  An unmodified peer continues playing normally; chat is
   simply available only when both players use Competitive Loader. */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <winsock2.h>
#include <windows.h>
#include <SDL3/SDL.h>

extern "C" {
int Ui_Event(const SDL_Event *ev);
int net_recv(uint8_t *pkt, int size, struct sockaddr_in *from);
void send_to_peer(const void *buf, int n);
int receive(void);
int Port_NetActive(void);
int Port_NetSession(void);
int Port_NetMe(void);
const char *Port_NetName(int player);
void Port_UiNotice(const char *text);
void Port_NetArrived(void);
void Port_NetSessionBegin(int role, const char *address, int port);
int Battle_Load(void);
void Gfx_BeginFrame(void);
void Gfx_EndFrame(int vsyncs);
void Dma_Flush(void);
int BtlSeq_Update(void);
void BtlSeq_StopTalk(void);
void CharSel_Draw(void);
void ADXT_StartAfs(void *adxt, int patid, int fid);
int BtlSeq_CheckBattleEnd(void);
int Battle_Restart(void);
SDL_Window *GsDraw_Window(void);
extern int gPortInputCapture;
extern int sConnected;
extern uint32_t sTick;
extern struct sockaddr_in sPeer;
/* PS2 pointers remain 32-bit addresses in the native port. */
extern uint32_t gBtlSeq;
extern uint32_t gCharSel;
extern int16_t gBattleTimeLimitTbl[8];
}

enum {
    CHAT_MAGIC = 0x4E335442u,
    CHAT_TYPE = 0x43484154u,
    SYNC_TYPE = 0x4353594Eu, /* "CSYN": ignored safely by an unmodified decomp */
    META_TYPE = 0x4D455441u, /* "META": loader version and competitive memory */
    SYNC_SELECT = 1,
    SYNC_BATTLE = 2,
    CHAT_MAX = 95,
};

typedef struct SyncPoint {
    uint32_t localGen;
    uint32_t localTick;
    uint32_t remoteGen;
    uint32_t remoteTick;
    uint64_t began;
} SyncPoint;

typedef struct CompetitiveMetaPacket {
    uint32_t magic;
    uint32_t type;
    uint32_t version;
    uint32_t flags;
    char memorySha256[65];
} CompetitiveMetaPacket;

typedef struct CompetitiveBattleResult {
    int32_t winner;
    int32_t reason;
} CompetitiveBattleResult;

static int sChatOpen;
static char sChatText[CHAT_MAX + 1];
static char sChatHistory[2][56];
static uint32_t sChatSerial;
static uint32_t sLastRemoteSerial;
static SyncPoint sSelectSync;
static SyncPoint sBattleSync;
static uint64_t sChatLastShown;
static uint64_t sRosterLastShown;
static int sRosterWasVisible;
static uint64_t sReadyLastShown;
static uint64_t sMetaLastSent;
static uint32_t sLocalVersion;
static uint32_t sRemoteVersion;
static char sLocalMemory[65];
static char sRemoteMemory[65];
static int sMetaReceived;
static int sSessionScore[2];
static int sBattleCounted;

/* Some Competitive AFS2 streams put a CRI end marker before the padded tail
   of the file. FFmpeg and the PS2 decoder stop at that marker; the compact PC
   decoder trusts the longer sample count in the header and interprets the
   tail as ADPCM, producing sustained hard clipping. Correct only the loaded
   AFS2 player's effective length, without changing gain or the audio file. */
typedef struct CompetitiveAdxPlayer {
    SDL_AudioStream *stream;
    char path[512];
    uint8_t *file;
    uint32_t size, data;
    uint32_t channels, rate, total;
    int loop;
    uint32_t loopStart, loopEnd;
    uint32_t pos;
    int c1, c2;
    int hist[2][2];
    int stat, paused;
    int vol;
    int pan[2];
} CompetitiveAdxPlayer;

static_assert(offsetof(CompetitiveAdxPlayer, total) == 544, "unexpected ADX player layout");
static_assert(sizeof(CompetitiveAdxPlayer) == 608, "unexpected ADX player size");

typedef struct CompetitiveAdxView {
    int stat, paused, left, vol, pan[2];
    char path[256];
} CompetitiveAdxView;

extern "C" CompetitiveAdxPlayer sPlayers[16];
extern "C" CompetitiveAdxView gPortAdxView[16];

static uint16_t competitive_be16(const uint8_t *p) {
    return (uint16_t)((uint16_t)p[0] << 8 | p[1]);
}

static void competitive_fix_adx_eof(void *adxt, int patid) {
    CompetitiveAdxPlayer *p = (CompetitiveAdxPlayer *)adxt;
    if (p == NULL || patid != 2 || p->file == NULL || p->channels < 1 || p->channels > 2 ||
        p->data >= p->size || p->rate == 0) {
        return;
    }
    size_t stride = (size_t)18 * p->channels;
    uint32_t frames = (uint32_t)((p->size - p->data) / stride);
    uint32_t declaredFrames = (p->total + 31) / 32;
    if (frames > declaredFrames) {
        frames = declaredFrames;
    }
    for (uint32_t frame = 0; frame < frames; frame++) {
        const uint8_t *block = p->file + p->data + (size_t)frame * stride;
        int eof = 0;
        for (uint32_t channel = 0; channel < p->channels; channel++) {
            if (competitive_be16(block + (size_t)channel * 18) & 0x8000) {
                eof = 1;
                break;
            }
        }
        if (!eof) {
            continue;
        }
        uint32_t eofSample = frame * 32;
        if (eofSample < p->total && (!p->loop || eofSample < p->loopEnd)) {
            p->loop = 0;
            p->total = eofSample;
            uintptr_t base = (uintptr_t)&sPlayers[0];
            uintptr_t current = (uintptr_t)p;
            if (current >= base && (current - base) % sizeof(*p) == 0) {
                size_t index = (current - base) / sizeof(*p);
                if (index < 16) {
                    uint64_t divisor = (uint64_t)p->rate * 1001;
                    gPortAdxView[index].left =
                        (int)(((uint64_t)eofSample * 60000 + divisor - 1) / divisor) + 1;
                }
            }
        }
        break;
    }
}

extern "C" void Competitive_ADXTStartAfs(void *adxt, int patid, int fid) {
    ADXT_StartAfs(adxt, patid, fid);
    competitive_fix_adx_eof(adxt, patid);
}

/* Moving or resizing a native Windows window enters a modal system loop. The
   renderer stops polling netplay while that loop owns the thread, which can
   freeze or desynchronise an online match. Subclass the SDL window only while
   online and reject those commands before Windows begins the modal loop. */
typedef LONG_PTR (WINAPI *CompetitiveGetWindowLongPtrW)(HWND, int);
typedef LONG_PTR (WINAPI *CompetitiveSetWindowLongPtrW)(HWND, int, LONG_PTR);
typedef LRESULT (WINAPI *CompetitiveCallWindowProcW)(WNDPROC, HWND, UINT, WPARAM, LPARAM);

static HWND sLockedWindow;
static WNDPROC sOriginalWindowProc;
static CompetitiveGetWindowLongPtrW sGetWindowLongPtrW;
static CompetitiveSetWindowLongPtrW sSetWindowLongPtrW;
static CompetitiveCallWindowProcW sCallWindowProcW;

static LRESULT CALLBACK competitive_window_proc(HWND hwnd, UINT message, WPARAM wparam, LPARAM lparam) {
    if (Port_NetActive()) {
        if (message == WM_SYSCOMMAND) {
            WPARAM command = wparam & 0xFFF0;
            if (command == SC_MOVE || command == SC_SIZE || command == SC_MINIMIZE ||
                command == SC_MAXIMIZE || command == SC_RESTORE) {
                return 0;
            }
        }
        if (message == WM_NCLBUTTONDOWN || message == WM_NCLBUTTONDBLCLK) {
            if (wparam == HTCAPTION || wparam == HTLEFT || wparam == HTRIGHT ||
                wparam == HTTOP || wparam == HTBOTTOM || wparam == HTTOPLEFT ||
                wparam == HTTOPRIGHT || wparam == HTBOTTOMLEFT || wparam == HTBOTTOMRIGHT ||
                wparam == HTMINBUTTON || wparam == HTMAXBUTTON) {
                return 0;
            }
        }
    }
    WNDPROC original = sOriginalWindowProc;
    if (message == WM_NCDESTROY && hwnd == sLockedWindow) {
        sLockedWindow = NULL;
        sOriginalWindowProc = NULL;
    }
    return original != NULL && sCallWindowProcW != NULL
        ? sCallWindowProcW(original, hwnd, message, wparam, lparam)
        : 0;
}

static int competitive_window_api(void) {
    if (sGetWindowLongPtrW != NULL && sSetWindowLongPtrW != NULL && sCallWindowProcW != NULL) {
        return 1;
    }
    HMODULE user32 = GetModuleHandleW(L"user32.dll");
    if (user32 == NULL) {
        return 0;
    }
    sGetWindowLongPtrW = (CompetitiveGetWindowLongPtrW)GetProcAddress(user32, "GetWindowLongPtrW");
    sSetWindowLongPtrW = (CompetitiveSetWindowLongPtrW)GetProcAddress(user32, "SetWindowLongPtrW");
    sCallWindowProcW = (CompetitiveCallWindowProcW)GetProcAddress(user32, "CallWindowProcW");
    return sGetWindowLongPtrW != NULL && sSetWindowLongPtrW != NULL && sCallWindowProcW != NULL;
}

static HWND competitive_sdl_hwnd(void) {
    SDL_Window *window = GsDraw_Window();
    if (window == NULL) {
        return NULL;
    }
    SDL_PropertiesID properties = SDL_GetWindowProperties(window);
    return (HWND)SDL_GetPointerProperty(properties, SDL_PROP_WINDOW_WIN32_HWND_POINTER, NULL);
}

static void competitive_window_lock_update(void) {
    int online = Port_NetActive();
    if (online && sLockedWindow == NULL && competitive_window_api()) {
        HWND hwnd = competitive_sdl_hwnd();
        if (hwnd != NULL) {
            LONG_PTR original = sGetWindowLongPtrW(hwnd, GWLP_WNDPROC);
            if (original != 0) {
                LONG_PTR previous = sSetWindowLongPtrW(hwnd, GWLP_WNDPROC, (LONG_PTR)competitive_window_proc);
                if (previous != 0) {
                    sLockedWindow = hwnd;
                    sOriginalWindowProc = (WNDPROC)previous;
                    fprintf(stderr, "bt3: online window lock active (F11/move/resize/minimize/maximize blocked)\n");
                }
            }
        }
    } else if (!online && sLockedWindow != NULL && competitive_window_api()) {
        HWND hwnd = sLockedWindow;
        WNDPROC original = sOriginalWindowProc;
        LONG_PTR current = sGetWindowLongPtrW(hwnd, GWLP_WNDPROC);
        if (current == (LONG_PTR)competitive_window_proc && original != NULL) {
            sSetWindowLongPtrW(hwnd, GWLP_WNDPROC, (LONG_PTR)original);
        }
        sLockedWindow = NULL;
        sOriginalWindowProc = NULL;
        fprintf(stderr, "bt3: online window lock released\n");
    }
}

/* Competitive online rules keep the four lobby choices but lengthen their
   real battle clocks: 60->180, 90->240, 180->360 and 240->480 seconds.
   Offline play is restored to the original table in the same process. */
static void competitive_time_limits(int online) {
    static const int16_t original[4] = {60, 90, 180, 240};
    static const int16_t competitive[4] = {180, 240, 360, 480};
    const int16_t *values = online ? competitive : original;
    for (int i = 0; i < 4; i++) {
        gBattleTimeLimitTbl[i + 1] = values[i];
    }
}

typedef DWORD (WINAPI *CompetitiveGetEnvironmentVariableA)(LPCSTR, LPSTR, DWORD);
static CompetitiveGetEnvironmentVariableA sGetEnvironmentVariableA;

extern "C" CompetitiveBattleResult *Battle_GetResult(void);

static DWORD competitive_get_environment(const char *name, char *value, DWORD capacity) {
    if (sGetEnvironmentVariableA == NULL) {
        HMODULE kernel32 = GetModuleHandleW(L"kernel32.dll");
        if (kernel32 != NULL) {
            sGetEnvironmentVariableA =
                (CompetitiveGetEnvironmentVariableA)GetProcAddress(kernel32, "GetEnvironmentVariableA");
        }
    }
    if (sGetEnvironmentVariableA == NULL) {
        return 0;
    }
    return sGetEnvironmentVariableA(name, value, capacity);
}

static uint32_t competitive_version_pack(const char *text) {
    unsigned major = 0, minor = 0, patch = 0;
    if (text == NULL || sscanf(text, "%u.%u.%u", &major, &minor, &patch) != 3 ||
        major > 255 || minor > 255 || patch > 255) {
        return 0;
    }
    return (major << 16) | (minor << 8) | patch;
}

static void competitive_metadata_load(void) {
    char version[32] = {0};
    char memory[65] = {0};
    competitive_get_environment("BT3_COMPETITIVE_LOADER_VERSION", version, sizeof(version));
    competitive_get_environment("BT3_COMPETITIVE_MEMORY_SHA256", memory, sizeof(memory));
    sLocalVersion = competitive_version_pack(version);
    SDL_strlcpy(sLocalMemory, memory[0] != '\0' ? memory : "none", sizeof(sLocalMemory));
    sRemoteVersion = 0;
    sRemoteMemory[0] = '\0';
    sMetaReceived = 0;
    sMetaLastSent = 0;
}

static void competitive_metadata_send(int force) {
    if (!Port_NetActive() || !sConnected) {
        return;
    }
    uint64_t now = SDL_GetTicks();
    if (!force && now - sMetaLastSent < 500) {
        return;
    }
    CompetitiveMetaPacket packet;
    memset(&packet, 0, sizeof(packet));
    packet.magic = CHAT_MAGIC;
    packet.type = META_TYPE;
    packet.version = sLocalVersion;
    SDL_strlcpy(packet.memorySha256, sLocalMemory, sizeof(packet.memorySha256));
    send_to_peer(&packet, (int)sizeof(packet));
    send_to_peer(&packet, (int)sizeof(packet));
    sMetaLastSent = now | 1u;
}

static const char *competitive_version_status(void) {
    if (!sMetaReceived || sRemoteVersion == 0 || sLocalVersion == 0) {
        return "...";
    }
    return sLocalVersion == sRemoteVersion ? "OK" : "DISTINTA";
}

static const char *competitive_memory_status(void) {
    if (!sMetaReceived || sRemoteMemory[0] == '\0') {
        return "...";
    }
    if (SDL_strcmp(sLocalMemory, "none") == 0 && SDL_strcmp(sRemoteMemory, "none") == 0) {
        return "SIN MEMORY";
    }
    return SDL_strcmp(sLocalMemory, sRemoteMemory) == 0 ? "OK" : "DISTINTA";
}

static const char *competitive_player_name(int player, const char *fallback) {
    const char *name = Port_NetName(player);
    return name != NULL && name[0] != '\0' ? name : fallback;
}

static int from_peer(const struct sockaddr_in *from) {
    return sConnected && from->sin_addr.s_addr == sPeer.sin_addr.s_addr && from->sin_port == sPeer.sin_port;
}

static void sync_reset(void) {
    memset(&sSelectSync, 0, sizeof(sSelectSync));
    memset(&sBattleSync, 0, sizeof(sBattleSync));
}

static void sync_send(uint32_t kind, const SyncPoint *point) {
    uint32_t pkt[5] = {CHAT_MAGIC, SYNC_TYPE, kind, point->localGen, point->localTick};
    send_to_peer(pkt, (int)sizeof(pkt));
    send_to_peer(pkt, (int)sizeof(pkt));
}

static int sync_timed_out(SyncPoint *point, const char *where) {
    uint64_t now = SDL_GetTicks();
    if (point->began == 0) {
        point->began = now | 1u;
    }
    if (now - point->began < 20000) {
        return 0;
    }
    char text[160];
    SDL_snprintf(text, sizeof(text), "Sincronización agotada en %s; ambos jugadores necesitan el mismo loader", where);
    Port_UiNotice(text);
    return 1;
}

static void sync_receive(const uint32_t header[5]) {
    SyncPoint *point = header[2] == SYNC_SELECT ? &sSelectSync : header[2] == SYNC_BATTLE ? &sBattleSync : NULL;
    uint32_t generation = header[3];
    if (point == NULL || generation == 0 || generation > point->remoteGen + 16) {
        return;
    }
    if (generation >= point->remoteGen) {
        point->remoteGen = generation;
        point->remoteTick = header[4];
    }
}

static void chat_show(void) {
    char box[160];
    if (sChatOpen) {
        SDL_snprintf(box, sizeof(box), "[ CHAT ] F2 Listo | F3 Espera\nF4 Buen combate | F5 Gracias\n> %.80s",
                     sChatText);
    } else {
        SDL_snprintf(box, sizeof(box), "[ CHAT ONLINE ]\n%s%s%s",
                     sChatHistory[0],
                     sChatHistory[0][0] != '\0' && sChatHistory[1][0] != '\0' ? "\n" : "",
                     sChatHistory[1]);
    }
    sChatLastShown = SDL_GetTicks();
    Port_UiNotice(box);
}

static void chat_history_add(const char *prefix, const char *text) {
    SDL_strlcpy(sChatHistory[0], sChatHistory[1], sizeof(sChatHistory[0]));
    SDL_snprintf(sChatHistory[1], sizeof(sChatHistory[1]), "%s%.45s",
                 prefix != NULL ? prefix : "", text != NULL ? text : "");
    chat_show();
}

static void chat_prompt(void) {
    chat_show();
}

static void chat_close(void) {
    sChatOpen = 0;
    gPortInputCapture = 0;
    SDL_StopTextInput(GsDraw_Window());
}

static void chat_backspace(void) {
    size_t n = strlen(sChatText);
    if (n == 0) {
        return;
    }
    do {
        n--;
    } while (n > 0 && ((unsigned char)sChatText[n] & 0xC0u) == 0x80u);
    sChatText[n] = '\0';
}

static void chat_append(const char *text) {
    size_t have = strlen(sChatText), add = text != NULL ? strlen(text) : 0;
    if (have >= CHAT_MAX || add == 0) {
        return;
    }
    if (add > CHAT_MAX - have) {
        add = CHAT_MAX - have;
        while (add > 0 && ((unsigned char)text[add] & 0xC0u) == 0x80u) {
            add--;
        }
    }
    memcpy(sChatText + have, text, add);
    sChatText[have + add] = '\0';
}

extern "C" int Competitive_ChatSend(const char *text) {
    uint8_t pkt[16 + CHAT_MAX];
    uint32_t header[4];
    size_t n;

    if (!Port_NetActive() || !sConnected || text == NULL || text[0] == '\0') {
        return 0;
    }
    n = strlen(text);
    if (n > CHAT_MAX) {
        n = CHAT_MAX;
    }
    header[0] = CHAT_MAGIC;
    header[1] = CHAT_TYPE;
    header[2] = ((uint32_t)SDL_GetTicks() << 8) ^ ++sChatSerial;
    header[3] = (uint32_t)n;
    memcpy(pkt, header, sizeof(header));
    memcpy(pkt + sizeof(header), text, n);
    /* It is a small UDP side channel.  Repeating it makes an isolated lost
       datagram unlikely; the serial lets the receiver discard duplicates. */
    send_to_peer(pkt, (int)(sizeof(header) + n));
    send_to_peer(pkt, (int)(sizeof(header) + n));
    send_to_peer(pkt, (int)(sizeof(header) + n));
    return 1;
}

static void chat_send_and_close(const char *text) {
    int ok = Competitive_ChatSend(text);
    chat_close();
    if (ok) {
        chat_history_add("Tú: ", text);
    } else {
        Port_UiNotice("No se pudo enviar: la partida online ya terminó");
    }
}

extern "C" int Competitive_NetRecv(uint8_t *pkt, int size, struct sockaddr_in *from) {
    int n;
    for (;;) {
        n = net_recv(pkt, size, from);
        if (n < 16) {
            return n;
        }
        uint32_t header[5] = {0};
        memcpy(header, pkt, n >= (int)sizeof(header) ? sizeof(header) : 16);
        if (header[0] == CHAT_MAGIC && header[1] == SYNC_TYPE && n >= (int)sizeof(header)) {
            if (from_peer(from)) {
                sync_receive(header);
            }
            continue;
        }
        if (header[0] == CHAT_MAGIC && header[1] == META_TYPE &&
            n >= (int)sizeof(CompetitiveMetaPacket)) {
            if (from_peer(from)) {
                CompetitiveMetaPacket metadata;
                memcpy(&metadata, pkt, sizeof(metadata));
                metadata.memorySha256[sizeof(metadata.memorySha256) - 1] = '\0';
                sRemoteVersion = metadata.version;
                SDL_strlcpy(sRemoteMemory, metadata.memorySha256, sizeof(sRemoteMemory));
                sMetaReceived = 1;
            }
            continue;
        }
        if (header[0] != CHAT_MAGIC || header[1] != CHAT_TYPE) {
            return n;
        }
        if (!from_peer(from)) {
            continue;
        }
        uint32_t length = header[3];
        if (length == 0 || length > CHAT_MAX || n < (int)(16 + length) || header[2] == sLastRemoteSerial) {
            continue;
        }
        sLastRemoteSerial = header[2];
        char text[CHAT_MAX + 1];
        memcpy(text, pkt + 16, length);
        text[length] = '\0';
        for (uint32_t i = 0; i < length; i++) {
            unsigned char ch = (unsigned char)text[i];
            if (ch < 0x20u && ch != '\t') {
                text[i] = ' ';
            }
        }
        const char *name = Port_NetName(1 - Port_NetMe());
        char prefix[24];
        SDL_snprintf(prefix, sizeof(prefix), "%s: ", name != NULL && name[0] != '\0' ? name : "Rival");
        chat_history_add(prefix, text);
        /* Consume chat here.  The official receiver never sees the extension
           and continues with the next gameplay packet. */
    }
}

/* A session can also begin without restarting the process. Clear every
   generation before the official connection resets its own counters. */
extern "C" void Competitive_NetSessionBegin(int role, const char *address, int port) {
    sync_reset();
    memset(sChatHistory, 0, sizeof(sChatHistory));
    memset(sSessionScore, 0, sizeof(sSessionScore));
    sBattleCounted = 0;
    sReadyLastShown = 0;
    sRosterLastShown = 0;
    competitive_metadata_load();
    Port_NetSessionBegin(role, address, port);
    competitive_time_limits(1);
    competitive_metadata_send(1);
}

/* Startup runs uncapped and hidden. Do not reveal character selection until
   both copies have completed their logos/save/bootstrap work. This hook is
   deliberately non-blocking because it runs from inside Port_VBlank. */
extern "C" void Competitive_NetArrived(void) {
    if (!Port_NetSession() || !sConnected) {
        Port_NetArrived();
        return;
    }
    competitive_metadata_send(0);
    if (sSelectSync.localGen == 0) {
        sSelectSync.localGen = 1;
        sSelectSync.localTick = sTick;
        sSelectSync.began = SDL_GetTicks() | 1u;
    }
    sync_send(SYNC_SELECT, &sSelectSync);
    uint64_t now = SDL_GetTicks();
    if (!sChatOpen && now - sReadyLastShown >= 750) {
        int me = Port_NetMe();
        char text[160];
        SDL_snprintf(text, sizeof(text),
                     "[ PREPARANDO ONLINE ]\nTú: %.20s - LISTO\nRival: %.20s - %s\nLoader %s | Memory %s",
                     competitive_player_name(me, "Jugador"),
                     competitive_player_name(1 - me, "Rival"),
                     sSelectSync.remoteGen == 1 ? "LISTO" : "CARGANDO",
                     competitive_version_status(), competitive_memory_status());
        Port_UiNotice(text);
        sReadyLastShown = now | 1u;
    }
    if (sSelectSync.remoteGen == 1) {
        uint32_t target = (sSelectSync.localTick > sSelectSync.remoteTick ? sSelectSync.localTick : sSelectSync.remoteTick) + 12;
        if (sTick >= target) {
            Port_NetArrived();
        }
    } else if (sync_timed_out(&sSelectSync, "selección de personajes")) {
        Port_NetArrived();
    }
}

/* Battle_Load contains a frame-based asynchronous loader. A quicker PC used
   to enter sequence initialization while its rival was still loading. Keep
   advancing harmless blank frames until both copies report the same battle
   generation, then release them on the same future network tick. */
extern "C" int Competitive_BattleLoad(void) {
    competitive_time_limits(Port_NetSession());
    if (sRosterWasVisible) {
        if (SDL_GetTicks() - sChatLastShown >= 6500) {
            Port_UiNotice("");
        }
        sRosterWasVisible = 0;
    }
    int result = Battle_Load();
    if (!Port_NetSession() || !sConnected) {
        return result;
    }
    SyncPoint *point = &sBattleSync;
    point->localGen++;
    point->localTick = sTick;
    point->began = SDL_GetTicks() | 1u;
    for (;;) {
        competitive_metadata_send(0);
        sync_send(SYNC_BATTLE, point);
        if (point->remoteGen == point->localGen) {
            uint32_t target = (point->localTick > point->remoteTick ? point->localTick : point->remoteTick) + 12;
            if (sTick >= target) {
                break;
            }
        } else if (sync_timed_out(point, "carga de la pelea")) {
            break;
        }
        Gfx_BeginFrame();
        Gfx_EndFrame(2);
        Dma_Flush();
    }
    return result;
}

/* Count the completed battle once, while keeping the game's own rematch
   system untouched. Battle_Restart clears only the per-fight guard, so the
   session score survives every native rematch. */
extern "C" int Competitive_BtlSeqCheckBattleEnd(void) {
    int ended = BtlSeq_CheckBattleEnd();
    if (!ended || !Port_NetSession() || sBattleCounted) {
        return ended;
    }
    CompetitiveBattleResult *result = Battle_GetResult();
    if (result == NULL) {
        return ended;
    }
    int winner = result->winner;
    if (winner & 1) {
        sSessionScore[0]++;
    } else if (winner & 2) {
        sSessionScore[1]++;
    } else if (!(winner & 4)) {
        return ended;
    }
    sBattleCounted = 1;
    int me = Port_NetMe();
    char text[160];
    if (winner & 4) {
        SDL_snprintf(text, sizeof(text), "[ EMPATE ]\nMarcador: %.18s %d - %d %.18s",
                     competitive_player_name(me, "Tú"), sSessionScore[me],
                     sSessionScore[1 - me], competitive_player_name(1 - me, "Rival"));
    } else {
        int side = (winner & 1) ? 0 : 1;
        SDL_snprintf(text, sizeof(text), "[ GANA %.28s ]\nMarcador: %.18s %d - %d %.18s",
                     competitive_player_name(side, "Jugador"),
                     competitive_player_name(me, "Tú"), sSessionScore[me],
                     sSessionScore[1 - me], competitive_player_name(1 - me, "Rival"));
    }
    Port_UiNotice(text);
    return ended;
}

extern "C" int Competitive_BattleRestart(void) {
    sBattleCounted = 0;
    return Battle_Restart();
}

/* The stage and fighter intros depend on local audio completion. Different
   audio devices can therefore advance on different frames. In an online
   session they are ended deterministically; offline keeps the original flow. */
extern "C" int Competitive_BtlSeqUpdate(void) {
    competitive_time_limits(Port_NetSession());
    uint8_t *seq = (uint8_t *)(uintptr_t)gBtlSeq;
    if (Port_NetSession() && seq != NULL) {
        int state = *(int *)(seq + 0);
        int *step = (int *)(seq + 8);
        if (state == 0) {
            /* StageIntro_Update returns state 1 immediately at step 6. */
            *step = 6;
        } else if (state == 1 || state == 5) {
            /* Both talk updates finish immediately at step 4. Their normal
               exit handlers still run, cleaning camera/poses/audio. */
            BtlSeq_StopTalk();
            *step = 4;
        }
    }
    return BtlSeq_Update();
}

/* Keep the online rival visible while the game's roster selector owns its
   work object. Refreshing before the standard six-second notice expires makes
   the small overlay persistent without changing the official UI renderer. */
extern "C" void Competitive_CharSelDraw(void) {
    CharSel_Draw();
    uint64_t now = SDL_GetTicks();
    int roster = Port_NetSession() && gCharSel != 0;
    if (roster && !sChatOpen && now - sChatLastShown >= 6500 && now - sRosterLastShown >= 3000) {
        competitive_metadata_send(0);
        int me = Port_NetMe();
        char text[160];
        SDL_snprintf(text, sizeof(text),
                     "[ ONLINE ] %.18s vs %.18s\nLoader %s | Memory %s\nMarcador %d - %d | T: chat",
                     competitive_player_name(me, "Tú"), competitive_player_name(1 - me, "Rival"),
                     competitive_version_status(), competitive_memory_status(),
                     sSessionScore[me], sSessionScore[1 - me]);
        Port_UiNotice(text);
        sRosterLastShown = now;
        sRosterWasVisible = 1;
    }
}

extern "C" int Competitive_UiEvent(const SDL_Event *ev) {
    competitive_window_lock_update();
    if (Port_NetActive() && ev->type == SDL_EVENT_KEY_DOWN && ev->key.key == SDLK_F11) {
        return 1;
    }
    if (!sChatOpen && Port_NetActive() && ev->type == SDL_EVENT_KEY_DOWN && !ev->key.repeat &&
        ev->key.scancode == SDL_SCANCODE_T) {
        sChatOpen = 1;
        sChatText[0] = '\0';
        gPortInputCapture = 1;
        SDL_StartTextInput(GsDraw_Window());
        chat_prompt();
        return 1;
    }
    if (!sChatOpen) {
        return Ui_Event(ev);
    }
    if (!Port_NetActive()) {
        chat_close();
        return Ui_Event(ev);
    }
    if (ev->type == SDL_EVENT_TEXT_INPUT) {
        chat_append(ev->text.text);
        chat_prompt();
        return 1;
    }
    if (ev->type == SDL_EVENT_KEY_DOWN && !ev->key.repeat) {
        if (ev->key.scancode == SDL_SCANCODE_F1) {
            chat_close();
            return Ui_Event(ev);
        } else if (ev->key.scancode == SDL_SCANCODE_F2) {
            chat_send_and_close("Listo");
        } else if (ev->key.scancode == SDL_SCANCODE_F3) {
            chat_send_and_close("Espera un momento");
        } else if (ev->key.scancode == SDL_SCANCODE_F4) {
            chat_send_and_close("Buen combate");
        } else if (ev->key.scancode == SDL_SCANCODE_F5) {
            chat_send_and_close("Gracias");
        } else if (ev->key.scancode == SDL_SCANCODE_ESCAPE) {
            chat_close();
            Port_UiNotice("Chat cancelado");
        } else if (ev->key.scancode == SDL_SCANCODE_BACKSPACE) {
            chat_backspace();
            chat_prompt();
        } else if (ev->key.scancode == SDL_SCANCODE_RETURN || ev->key.scancode == SDL_SCANCODE_KP_ENTER) {
            char sent[CHAT_MAX + 1];
            SDL_strlcpy(sent, sChatText, sizeof(sent));
            chat_send_and_close(sent);
        }
        return 1;
    }
    if (ev->type == SDL_EVENT_KEY_UP || ev->type == SDL_EVENT_TEXT_EDITING) {
        return 1;
    }
    return 1;
}
