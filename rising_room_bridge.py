"""Per-Loader shared-memory bridge: no socket IO runs on a game/render thread."""
import ctypes as C
import logging
import mmap
import secrets
import socket
import threading
import time

from rising_room import PROTOCOL, RoomClient, RoomError, RoomServer
from rising_invite import make_invite, read_invite
from rising_room_bots import RoomBots

MAGIC = 0x52435442


class User(C.Structure):
    _fields_ = [("id", C.c_uint32), ("flags", C.c_uint32), ("name", C.c_char * 65)]


class Match(C.Structure):
    _fields_ = [(k, C.c_uint32) for k in ("id", "round", "p1", "p2", "winner", "status", "score1", "score2", "confirmations", "bots")] + [
        ("name1", C.c_char * 65), ("name2", C.c_char * 65), ("code", C.c_char * 8)]


class TournamentState(C.Structure):
    _fields_ = [(k, C.c_uint32) for k in ("status", "ft", "characters", "enrolled", "self_enrolled", "role", "current", "champion", "count", "revision", "mode")] + [
        ("id", C.c_char * 65), ("title", C.c_char * 97), ("champion_name", C.c_char * 65),
        ("roster", C.c_char * 257), ("matches", Match * 31)]


class State(C.Structure):
    _fields_ = [("connected", C.c_uint32), ("self_id", C.c_uint32), ("host_id", C.c_uint32),
                ("count", C.c_uint32), ("chat_count", C.c_uint32), ("capacity", C.c_uint32),
                ("title", C.c_char * 97), ("address", C.c_char * 129),
                ("notice", C.c_char * 257), ("key", C.c_char * 65),
                ("users", User * 32), ("chat", (C.c_char * 385) * 64), ("invite", C.c_char * 385),
                ("chat_serial", C.c_uint32), ("tournament", TournamentState)]


class Command(C.Structure):
    _fields_ = [("op", C.c_uint32), ("target", C.c_uint32), ("port", C.c_uint32),
                ("capacity", C.c_uint32), ("name", C.c_char * 65), ("title", C.c_char * 97),
                ("address", C.c_char * 129), ("key", C.c_char * 65), ("text", C.c_char * 385),
                ("ft", C.c_uint32), ("characters", C.c_uint32), ("score1", C.c_uint32), ("score2", C.c_uint32),
                ("tournament_id", C.c_char * 65)]


class Shared(C.Structure):
    _fields_ = [("magic", C.c_uint32), ("version", C.c_uint32), ("state_seq", C.c_uint32),
                ("command_seq", C.c_uint32), ("ack_seq", C.c_uint32),
                ("state", State), ("command", Command)]


def encoded(value, size):
    # Drop an incomplete UTF-8 tail so ImGui never receives invalid text.
    return str(value).encode("utf-8")[:size - 1].decode("utf-8", "ignore").encode("utf-8")


def decoded(value):
    return bytes(value).split(b"\0", 1)[0].decode("utf-8", "replace")


class RoomBridge:
    def __init__(self, logger=None, client=None, preserve_membership=False):
        self.name = "Local\\BTC-RisingBattle-" + secrets.token_hex(16)
        self.memory = mmap.mmap(-1, C.sizeof(Shared), tagname=self.name)
        self.shared = Shared.from_buffer(self.memory)
        self.shared.magic, self.shared.version = MAGIC, 5
        self.log = logger or logging.getLogger("competitive.room")
        self.client = client
        self.preserve_membership = preserve_membership
        self.runtime = None
        self.game_bots = None
        self.server = None
        self.local_service = None
        self.bots = None
        self.snapshot = client.send("poll") if client else None
        try:
            self.local_address = socket.gethostbyname(socket.gethostname())
        except OSError:
            self.local_address = "127.0.0.1"
        self.address = self.local_address
        self.invite = ""
        self.key = ""
        self.notice = "Crea una sala o únete por IP y clave."
        self.stop = threading.Event()
        self._publish()
        self.thread = threading.Thread(target=self._work, daemon=True)
        self.thread.start()

    def _publish(self):
        state = State()
        state.notice = encoded(self.notice, 257)
        state.address, state.key = encoded(self.address, 129), encoded(self.key, 65)
        state.invite = encoded(self.invite, 385)
        if self.snapshot:
            s = self.snapshot
            state.connected = 1
            state.self_id, state.host_id = s["self_id"], s["host_id"]
            state.capacity, state.title = s["capacity"], encoded(s["title"], 97)
            state.count = len(s["users"])
            for i, user in enumerate(s["users"]):
                state.users[i].id = user["id"]
                state.users[i].flags = int(bool(user["ready"])) | (2 if user.get("bot") else 0) | (4 if user.get("game_bot") else 0)
                state.users[i].name = encoded(user["name"], 65)
            state.chat_count = len(s["messages"])
            state.chat_serial = s["messages"][-1]["id"] if s["messages"] else 0
            for i, message in enumerate(s["messages"]):
                state.chat[i].value = encoded(message["author"] + ": " + message["text"], 385)
            t = s.get("tournament")
            if t:
                dst = state.tournament
                dst.status = {"registration": 0, "running": 1, "finished": 2}[t["status"]]
                for key in ("ft", "characters", "enrolled", "role", "current", "champion", "revision"):
                    setattr(dst, key, t[key])
                dst.self_enrolled = int(t["self_enrolled"])
                dst.mode = int(t.get("mode") == "all_vs_host")
                dst.id, dst.title = encoded(t["id"], 65), encoded(t["title"], 97)
                dst.champion_name = encoded(t["champion_name"], 65)
                dst.roster = encoded(", ".join(t["self_roster"]), 257)
                dst.count = len(t["matches"])
                for i, match in enumerate(t["matches"]):
                    row = dst.matches[i]
                    for key in ("id", "round", "p1", "p2", "winner", "confirmations"):
                        setattr(row, key, match[key] or 0)
                    row.status = {"pending": 0, "active": 1, "done": 2}[match["state"]]
                    row.score1, row.score2 = match["score"] or [0, 0]
                    row.bots = (1 if match["bots"] and not match.get("playable", False) else 0) | (2 if match["bots"] and match.get("playable") else 0)
                    row.name1, row.name2, row.code = encoded(match["name1"], 65), encoded(match["name2"], 65), encoded(match["code"], 8)
        self.shared.state_seq += 1
        self.shared.state = state
        self.shared.state_seq += 1

    def _leave(self):
        if self.game_bots:
            self.game_bots.close()
            self.game_bots = None
        if self.bots:
            self.bots.close()
            self.bots = None
        if self.client and not self.preserve_membership:
            try:
                self.client.send("leave")
            except RoomError:
                pass
        self.client = None
        self.snapshot = None
        if self.server:
            self.server.close()
            self.server = None
        self.address = self.local_address
        self.key = self.invite = ""

    def _execute(self, command):
        op = command.op
        if op == 23:
            from rising_service import ServiceServer
            if not self.local_service:
                self.local_service = ServiceServer()
            self.notice = f"Servicio BTC local activo en http://127.0.0.1:{self.local_service.port}. Solo este equipo; no esta publicado en Internet."
            return
        if op in (21, 22):
            if self.client:
                raise RoomError("Sal de la sala actual antes de cambiar")
            from rising_service import ServiceClient
            client = ServiceClient(decoded(command.address), decoded(command.text) if op == 22 else "")
            if op == 21:
                snapshot = client.send("create", name=decoded(command.name), title=decoded(command.title),
                                       capacity=command.capacity, protocol=PROTOCOL, edition="BTC")
            else:
                snapshot = client.send("join", name=decoded(command.name), protocol=PROTOCOL, edition="BTC")
            self.client, self.snapshot = client, snapshot
            self.address = decoded(command.address)
            self.invite = snapshot["room_code"]
            self.notice = "Sala BTC conectada por codigo. F2: bracket. Tab: chat para toda la sala."
            return
        if op == 19:
            if self.client:
                raise RoomError("Sal de la sala actual para preparar la prueba")
            if not self.runtime:
                raise RoomError("Inicia el juego desde el Loader para preparar los bots de combate")
            from rising_game_bots import GameBotProcesses
            from rising_service import ServiceServer, ServiceClient
            if not self.local_service:
                self.local_service = ServiceServer(port=0)
            self.address = f"http://127.0.0.1:{self.local_service.port}"
            self.client = ServiceClient(self.address)
            self.snapshot = self.client.send("create",name=decoded(command.name) or "UT Rising",
                                            title="Prueba BTC: tu + 3 bots",capacity=4,protocol=PROTOCOL,edition="BTC")
            self.invite = self.snapshot["room_code"]
            # Private loopback adapter lets owned game workers use their existing transport.
            room = self.local_service.coordinator.rooms[self.client.code]
            self.server = RoomServer("", "", 0, bind="127.0.0.1", room=room)
            self.snapshot = self.client.send("tournament_config", title="Todos contra mi - prueba BTC", ft=1, characters=1)
            self.snapshot = self.client.send("tournament_register", roster=["Libre (prueba)"])
            self.bots = RoomBots(self.server, game_bots=True)
            if self.bots.add(3) != 3:
                raise RoomError("No se pudieron registrar los tres bots")
            with self.server.room.lock:
                self.server.room.tournament.prepare_challenge(self.server.room.host_id)
            self.game_bots = GameBotProcesses(self.server, self.bots, self.runtime, self.log)
            self.snapshot = self.client.send("poll")
            self.notice = "Cuatro inscritos: tu y tres bots de combate. Todos contra ti, incluso si pierdes un set. Elige FT y pulsa Iniciar prueba."
            return
        if op == 20:
            if not self.game_bots:
                raise RoomError("La vista local solo esta disponible en la prueba de bots de este equipo")
            self.game_bots.focus()
            self.notice = "Vista local de un bot. Es otra ventana del juego; no es el espectador online por replay."
            return
        if op in (1, 2, 9):
            if self.client:
                raise RoomError("Sal de la sala actual antes de cambiar")
            if op == 1:
                if not 1 <= command.port <= 65535:
                    raise RoomError("Puerto inválido")
                address = decoded(command.address) or self.local_address
                RoomClient(address, command.port)
                self.server = RoomServer(decoded(command.title), decoded(command.name),
                                         command.port, command.capacity)
                self.client = RoomClient("127.0.0.1", self.server.port, self.server.room.host_token)
                self.address = f"{address}:{self.server.port} (TCP)"
                self.key = self.server.room.key
                self.invite = make_invite(address, self.server.port, self.key)
                self.snapshot = self.client.send("poll")
                self.log.info("ROOM_CREATED capacity=%s port=%s", command.capacity, command.port)
            else:
                if op == 9:
                    address, port, key = read_invite(decoded(command.text))
                else:
                    address, port, key = decoded(command.address), command.port, decoded(command.key)
                client = RoomClient(address, port)
                self.snapshot = client.send("join", name=decoded(command.name), key=key,
                                            protocol=PROTOCOL, edition="BTC")
                self.client = client
                self.address = f"{address}:{port} (TCP)"
                self.log.info("ROOM_JOINED users=%s", len(self.snapshot["users"]))
            self.notice = "Sala conectada. Los combates se conectan desde Partida BTC."
        elif op == 5:
            self._leave()
            self.notice = "Has salido de la sala."
            self.log.info("ROOM_LEFT")
        elif self.client:
            if op == 3:
                self.snapshot = self.client.send("chat", text=decoded(command.text))
            elif op == 4:
                self.snapshot = self.client.send("kick", target=command.target)
                self.log.info("ROOM_KICK target=%s", command.target)
            elif op == 6:
                self.snapshot = self.client.send("ready")
            elif 10 <= op <= 17:
                tid, mid = decoded(command.tournament_id), command.target
                operations = {
                    10: ("tournament_config", dict(title=decoded(command.title), ft=command.ft, characters=command.characters)),
                    11: ("tournament_withdraw" if command.target else "tournament_register",
                         {} if command.target else dict(roster=[s.strip() for s in decoded(command.text).split(",") if s.strip()])),
                    12: ("tournament_start", {}), 13: ("tournament_simulate", {}), 14: ("tournament_reset", {}),
                    15: ("tournament_report", dict(tournament_id=tid, match=mid, score=[command.score1, command.score2])),
                    16: ("tournament_wo", dict(target=mid)),
                    17: ("tournament_code", dict(tournament_id=tid, match=mid, code=decoded(command.text))),
                }
                operation, values = operations[op]
                self.snapshot = self.client.send(operation, **values)
                self.log.info("ROOM_TOURNAMENT op=%s revision=%s", operation, self.snapshot["tournament"]["revision"])
            elif op in (7, 8):
                from rising_service import ServiceClient
                if isinstance(self.client, ServiceClient) and not self.server:
                    self.snapshot = self.client.send("bots_add" if op == 7 else "bots_remove", count=command.target)
                    self.notice = "Bots de sala actualizados. Prueban usuarios y chat; no juegan combates."
                    return
                if not self.server:
                    raise RoomError("Solo el anfitrión puede gestionar los bots")
                if op == 7:
                    if not self.bots:
                        self.bots = RoomBots(self.server)
                    added = self.bots.add(command.target)
                    self.log.info("ROOM_TEST_BOTS_ADDED count=%s", added)
                    self.notice = f"Añadidos {added} bots de prueba. No controlan personajes."
                else:
                    if self.bots:
                        self.bots.close()
                        self.bots = None
                    self.notice = "Bots de prueba retirados."
                self.snapshot = self.client.send("poll")
                return
            else:
                raise RoomError("Operación desconocida")
            self.notice = "Sala conectada."
        else:
            raise RoomError("No estás conectado a una sala")

    def _work(self):
        last_poll = time.monotonic()
        last_ok = last_poll
        try:
            while not self.stop.wait(0.05):
                seq = self.shared.command_seq
                if seq != self.shared.ack_seq:
                    command = Command.from_buffer_copy(bytes(self.shared.command))
                    try:
                        self._execute(command)
                        last_ok = time.monotonic()
                    except (RoomError, OSError, ValueError, KeyError, TypeError) as exc:
                        self.notice = str(exc)
                        self.log.warning("ROOM_COMMAND_FAILED op=%s reason=%s", command.op, self.notice)
                        if command.op in (1, 2, 9, 19):
                            self._leave()
                    self._publish()
                    # Acknowledgement guarantees the matching state is already visible.
                    self.shared.ack_seq = seq
                now = time.monotonic()
                if self.client and now - last_poll >= 0.5:
                    last_poll = now
                    try:
                        self.snapshot = self.client.send("poll")
                        last_ok = now
                    except (RoomError, ValueError, KeyError, TypeError) as exc:
                        self.notice = str(exc)
                        if "Ya no perteneces" in self.notice or "cerró la sala" in self.notice or now - last_ok > 12:
                            self._leave()
                            self.log.info("ROOM_DISCONNECTED")
                    self._publish()
        except Exception:
            self.log.exception("ROOM_BRIDGE_FAILED")
            self.notice = "Error de sala. Reinicia el Loader y consulta loader.log."
            self.snapshot = None
            self._publish()
        finally:
            self._leave()
            if self.local_service:
                self.local_service.close()
                self.local_service = None

    def close(self):
        self.stop.set()
        self.thread.join(timeout=8)
        if not self.thread.is_alive():
            del self.shared
            self.memory.close()
