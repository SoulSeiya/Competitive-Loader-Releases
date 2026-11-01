"""Per-Loader shared-memory bridge: no socket IO runs on a game/render thread."""
import ctypes as C
import logging
import mmap
import secrets
import socket
import threading
import time
import queue

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
    _fields_ = [(k, C.c_uint32) for k in ("status", "ft", "characters", "enrolled", "self_enrolled", "role", "current", "champion", "count", "revision", "mode", "seconds")] + [
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
                ("seconds", C.c_uint32), ("tournament_id", C.c_char * 65)]


class Shared(C.Structure):
    _fields_ = [("magic", C.c_uint32), ("version", C.c_uint32), ("state_seq", C.c_uint32),
                ("command_seq", C.c_uint32), ("ack_seq", C.c_uint32),
                ("state", State), ("command", Command)]


def encoded(value, size):
    # Drop an incomplete UTF-8 tail so ImGui never receives invalid text.
    return str(value).encode("utf-8")[:size - 1].decode("utf-8", "ignore").encode("utf-8")


# The service answers these when the room no longer exists (declined or expired
# direct challenge, host left). Retrying for 12 seconds only delays the release.
TERMINAL_ROOM_ERRORS=("Ya no perteneces","cerró la sala","no existe o ha caducado","La sala ya no está disponible")


def terminal_room_error(message):
    return any(text in str(message) for text in TERMINAL_ROOM_ERRORS)


def decoded(value):
    return bytes(value).split(b"\0", 1)[0].decode("utf-8", "replace")


class RoomBridge:
    def __init__(self, logger=None, client=None, preserve_membership=False,profile_store=None):
        self.profile_store=profile_store
        self.history_revision=None
        self.name = "Local\\BTC-RisingBattle-" + secrets.token_hex(16)
        self.memory = mmap.mmap(-1, C.sizeof(Shared), tagname=self.name)
        self.shared = Shared.from_buffer(self.memory)
        self.shared.magic, self.shared.version = MAGIC, 6
        self.log = logger or logging.getLogger("competitive.room")
        self.client = client
        self.preserve_membership = preserve_membership
        self.runtime = None
        self.ranked_room_code = None
        self.game_pid = None
        self.game_bots = None
        self.observer = None
        self.server = None
        self.local_service = None
        self.bots = None
        self.snapshot = client.send("poll") if client else None
        try:
            self.local_address = socket.gethostbyname(socket.gethostname())
        except OSError:
            self.local_address = "127.0.0.1"
        self.address = self.local_address
        self.directory=[];self.directory_kind="";self.directory_version=0
        self.invite = ""
        self.key = ""
        self.notice = "Crea una sala o únete por IP y clave."
        self.stop = threading.Event()
        self.ui_commands = queue.Queue(maxsize=16)
        self._publish()
        self.thread = threading.Thread(target=self._work, daemon=True)
        self.thread.start()

    def submit(self, op, **values):
        """Queue desktop UI commands on the same worker as native commands."""
        command = Command(op=op)
        strings = {name: C.sizeof(kind) for name, kind in Command._fields_ if issubclass(kind, C.Array)}
        for name, value in values.items():
            if name in strings:
                value = encoded(value, strings[name])
            setattr(command, name, value)
        self.ui_commands.put_nowait(command)

    def _publish(self):
        if self.profile_store and self.snapshot:
            t=self.snapshot.get('tournament') or {};c=self.snapshot.get('combat') or {}
            revision=(t.get('id'),t.get('revision'),t.get('status'),t.get('self_enrolled'),c.get('id'),c.get('revision'),c.get('status'))
            if revision!=self.history_revision:
                try:self.profile_store.observe(self.snapshot);self.history_revision=revision
                except Exception:self.log.exception('No se pudo guardar el historial local')
        state = State()
        state.notice = encoded(self.notice, 257)
        state.address, state.key = encoded(self.address, 129), encoded(self.key, 65)
        state.invite = encoded(self.invite, 385)
        if self.snapshot:
            s = self.snapshot
            state.connected = 1 | (2 if self.ranked_room_code and s.get('room_code') == self.ranked_room_code else 0)
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
            t = s.get("combat") or s.get("tournament")
            if t:
                dst = state.tournament
                dst.status = {"registration": 0, "running": 1, "finished": 2}[t["status"]]
                for key in ("ft", "characters", "enrolled", "role", "current", "champion", "revision"):
                    setattr(dst, key, t[key])
                dst.self_enrolled = int(t["self_enrolled"])
                dst.seconds = t.get("seconds", 180)
                dst.mode = 2 if t.get("mode")=="duel" else int(t.get("mode") == "all_vs_host")
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

    def _leave(self, notify=True):
        if self.observer:self.observer.cancel()
        if self.game_bots:
            self.game_bots.close()
            self.game_bots = None
        if self.bots:
            self.bots.close()
            self.bots = None
        if notify and self.client and not self.preserve_membership:
            try:
                self.client.send("leave")
            except (RoomError,OSError):
                self.log.warning("ROOM_LEAVE_UNCONFIRMED; clearing local membership")
        self.client = None
        self.snapshot = None
        if self.server:
            self.server.close()
            self.server = None
        self.address = self.local_address
        self.key = self.invite = ""

    def _execute(self, command):
        if command.op==46:
            if (self.snapshot or {}).get('combat',{}).get('status')!='finished':
                raise RoomError('Espera a que el resultado esté confirmado antes de cerrar el duelo temporal')
            # Do not close the host's remote room yet: the peer must be able to
            # fetch the confirmed result. Hidden membership expires naturally.
            self._leave(notify=False);self.notice='Duelo finalizado. GG.';return
        if command.op==45:
            if self.client:raise RoomError('Sal de tu sala actual antes de aceptar otra invitación')
            from rising_service import ServiceClient
            client=ServiceClient(decoded(command.address),decoded(command.key),decoded(command.text))
            snapshot=client.send('poll')
            self.client,self.snapshot=client,snapshot;self.address=decoded(command.address);self.invite=snapshot['room_code']
            self.notice='Invitación aceptada. Preparando la conexión del combate.';return
        if command.op==42:
            from rising_service import ServiceClient
            kind=decoded(command.key)
            client=ServiceClient(decoded(command.address))
            self.directory=client.send('list',kind=kind)['rooms'];self.directory_kind=kind;self.directory_version+=1
            self.notice='Lista actualizada.';return
        if command.op in (43,44):
            if self.client:raise RoomError('Sal de la sala actual antes de cambiar')
            from rising_service import ServiceClient
            client=ServiceClient(decoded(command.address),decoded(command.key) if command.op==44 else '')
            values=dict(name=decoded(command.name),protocol=PROTOCOL,edition='BTC',password=decoded(command.text))
            if command.op==43:values.update(title=decoded(command.title),capacity=command.capacity,kind=decoded(command.key))
            snapshot=client.send('create' if command.op==43 else 'join',**values)
            self.client,self.snapshot=client,snapshot;self.address=decoded(command.address);self.invite=snapshot['room_code']
            self.notice='Conectado.';return
        if command.op in (40,41):
            if not self.observer:raise RoomError('Usa el paquete experimental de espectador en los tres equipos')
            if command.op==41:
                self.observer.cancel();self.notice='Volviendo de espectador a tu juego.';return
            s=self.snapshot or {};t=s.get('combat') or s.get('tournament',{})
            if s.get('self_id')!=s.get('host_id') or t.get('role') in (1,2) or t.get('status')!='running':
                raise RoomError('El host puede observar cuando los otros dos están jugando')
            self.observer.watch(t['id'],t['current']);self.notice='Espectador experimental solicitado; consulta el estado del canal.';return
        op = command.op
        if op == 25:
            self.notice = decoded(command.text)
            self.log.info("ROOM_COMBAT_STATUS %s", self.notice)
            return
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
        if op in (19, 24, 26):
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
            spectator = op == 24
            rules_test = op == 26
            self.snapshot = self.client.send("create",name=decoded(command.name) or "UT Rising",
                                            title="Prueba de reglas: tú contra un bot" if rules_test else "Prueba BTC: semifinal bots y final contigo" if spectator else "Prueba BTC: tu + 3 bots",
                                            capacity=2 if rules_test else 3 if spectator else 4,protocol=PROTOCOL,edition="BTC")
            self.invite = self.snapshot["room_code"]
            # Private loopback adapter lets owned game workers use their existing transport.
            room = self.local_service.coordinator.rooms[self.client.code]
            self.server = RoomServer("", "", 0, bind="127.0.0.1", room=room)
            self.snapshot = self.client.send("tournament_config", title="Reglas BTC: humano contra bot" if rules_test else "Semifinal y final BTC - 180 segundos" if spectator else "Todos contra mi - prueba BTC", ft=1, characters=2 if rules_test else 1, seconds=180)
            self.snapshot = self.client.send("tournament_register", roster=["Libre (prueba)"])
            self.bots = RoomBots(self.server, game_bots=True)
            count = 1 if rules_test else 2 if spectator else 3
            if self.bots.add(count) != count:
                raise RoomError("No se pudieron registrar los bots de combate")
            with self.server.room.lock:
                if spectator:self.server.room.tournament.prepare_spectator_test(self.server.room.host_id)
                elif not rules_test:self.server.room.tournament.prepare_challenge(self.server.room.host_id)
                else:self.server.room.tournament.shuffle=lambda values:None # Human host is P1 in this private fixture.
            if spectator:
                self.game_bots = GameBotProcesses(self.server, self.bots, self.runtime, self.log,
                    local_spectator=True, human_pid=self.game_pid)
            else:self.game_bots = GameBotProcesses(self.server, self.bots, self.runtime, self.log)
            self.snapshot = self.client.send("poll")
            self.notice = ("PRUEBA PRIVADA: tú y un bot online. Guarda FT, tiempo y máximo de personajes; inscríbete de nuevo si cambias el máximo y pulsa Iniciar torneo." if rules_test else
                           "Tres inscritos. FT1, 180 s. Pulsa Iniciar torneo: observaras bots vs bots y jugaras la final contra el ganador." if spectator else
                           "Cuatro inscritos: tu y tres bots de combate. Todos contra ti, incluso si pierdes un set. Elige FT y pulsa Iniciar prueba.")
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
            elif op in (30,31,32,33):
                if self.observer and op in (30,31):self.observer.cancel()
                operations={30:'duel_offer',31:'duel_accept',32:'duel_decline',33:'duel_cancel'}
                values=dict(target=command.target,ft=command.ft,characters=command.characters,seconds=command.seconds) if op==30 else dict(duel_id=decoded(command.tournament_id))
                self.snapshot=self.client.send(operations[op],**values)
            elif 10 <= op <= 17:
                tid, mid = decoded(command.tournament_id), command.target
                operations = {
                    10: ("tournament_config", dict(title=decoded(command.title), ft=command.ft, characters=command.characters, seconds=command.seconds or 180)),
                    11: ("tournament_withdraw" if command.target else "tournament_register",
                         {} if command.target else dict(roster=[s.strip() for s in decoded(command.text).split(",") if s.strip()])),
                    12: ("tournament_start", {}), 13: ("tournament_simulate", {}), 14: ("tournament_reset", {}),
                    15: ("tournament_report", dict(tournament_id=tid, match=mid, score=[command.score1, command.score2])),
                    16: ("tournament_wo", dict(target=mid)),
                    17: ("tournament_code", dict(tournament_id=tid, match=mid, code=decoded(command.text))),
                }
                operation, values = operations[op]
                self.snapshot = self.client.send(operation, **values)
                self.log.info("ROOM_COMBAT op=%s revision=%s", operation, (self.snapshot.get("combat") or self.snapshot["tournament"])["revision"])
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
                native_command = seq != self.shared.ack_seq
                command = None
                if native_command:
                    command = Command.from_buffer_copy(bytes(self.shared.command))
                else:
                    try: command = self.ui_commands.get_nowait()
                    except queue.Empty: pass
                if command is not None:
                    try:
                        self._execute(command)
                        last_ok = time.monotonic()
                    except (RoomError, OSError, ValueError, KeyError, TypeError) as exc:
                        self.notice = str(exc)
                        self.log.warning("ROOM_COMMAND_FAILED op=%s reason=%s", command.op, self.notice)
                        if command.op in (1, 2, 9, 19, 24):
                            self._leave()
                    self._publish()
                    # Acknowledgement guarantees the matching state is already visible.
                    if native_command:
                        self.shared.ack_seq = seq
                now = time.monotonic()
                if self.client and now - last_poll >= 2.0:
                    last_poll = now
                    try:
                        self.snapshot = self.client.send("poll")
                        last_ok = now
                    except (RoomError, ValueError, KeyError, TypeError) as exc:
                        self.notice = str(exc)
                        if terminal_room_error(self.notice) or now - last_ok > 12:
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
        if self.observer:self.observer.close()
        self.thread.join(timeout=8)
        if not self.thread.is_alive():
            del self.shared
            self.memory.close()
