"""Rising Battle room service. The host owns membership; combat stays in native netplay."""
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import threading
import time
import urllib.error
import urllib.request
from rising_tournament import Tournament, TournamentError, validate_snapshot

PROTOCOL = 1
MAX_USERS = 32


class RoomError(Exception):
    pass


def text(value, limit):
    if not isinstance(value, str):
        raise RoomError("Texto inválido")
    return "".join(c for c in value if c >= " " and c != "\x7f").strip()[:limit]


class Room:
    def __init__(self, title, name, capacity=8, clock=time.monotonic):
        if type(capacity) is not int or not 2 <= capacity <= MAX_USERS:
            raise RoomError("La capacidad debe estar entre 2 y 32")
        self.title = text(title, 64) or "Sala BTC"
        self.capacity = capacity
        self.clock = clock
        self.lock = threading.RLock()
        self.key = secrets.token_urlsafe(12)
        self.users = {}
        self.messages = deque(maxlen=64)
        self.next_id = 0
        self.next_message = 0
        self.closed = False
        self.last_chat = {}
        self.host_token, self.host_id = self._add(name)
        self._announce("Sala creada")
        self.tournament = Tournament(self._announce)

    def _add(self, name, bot=False, game_bot=False):
        name = text(name, 24)
        if not name:
            raise RoomError("Escribe tu nombre")
        if any(u["name"].casefold() == name.casefold() for u in self.users.values()):
            raise RoomError("Ese nombre ya está en la sala")
        self.next_id += 1
        token = secrets.token_urlsafe(32)
        self.users[token] = dict(id=self.next_id, name=name, ready=False, bot=bot, game_bot=game_bot, seen=self.clock())
        return token, self.next_id

    def _announce(self, message, author="Sala"):
        self.next_message += 1
        self.messages.append(dict(id=self.next_message, author=author, text=message))

    def _expire(self):
        now = self.clock()
        for token, user in list(self.users.items()):
            if now - user["seen"] > 30:
                self._remove(token, "perdió la conexión")

    def _remove(self, token, reason):
        user = self.users.pop(token)
        self.last_chat.pop(token, None)
        self._announce(user["name"] + " " + reason)
        self.tournament.disqualify(user["id"])
        if user["id"] == self.host_id:
            self.closed = True

    def handle(self, data):
        if not isinstance(data, dict):
            raise RoomError("Petición inválida")
        with self.lock:
            self._expire()
            if self.closed:
                raise RoomError("El anfitrión cerró la sala")
            op = data.get("op")
            token = data.get("token", "")
            if op == "join":
                if data.get("protocol") != PROTOCOL or data.get("edition") != "BTC":
                    raise RoomError("Esta sala requiere Rising Battle BTC compatible")
                key = data.get("key")
                if not isinstance(key, str) or not secrets.compare_digest(key, self.key):
                    raise RoomError("Clave de sala incorrecta")
                if len(self.users) >= self.capacity:
                    raise RoomError("La sala está llena")
                bot = data.get("bot") is True
                if bot and token != self.host_token:
                    raise RoomError("Solo el anfitrión puede añadir bots de prueba")
                token, _ = self._add(data.get("name"), bot=bot, game_bot=bot and data.get("game_bot") is True)
                self._announce(self.users[token]["name"] + " entró en la sala")
            elif not isinstance(token, str) or token not in self.users:
                raise RoomError("Ya no perteneces a esta sala (expulsión o desconexión)")
            user = self.users[token]
            user["seen"] = self.clock()
            if op == "chat":
                message = text(data.get("text"), 240)
                if not message:
                    raise RoomError("El mensaje está vacío")
                if self.clock() - self.last_chat.get(token, -100) < 0.5:
                    raise RoomError("Espera antes de enviar otro mensaje")
                self.last_chat[token] = self.clock()
                self._announce(message, user["name"])
            elif op == "ready":
                user["ready"] = not user["ready"]
            elif op == "kick":
                if user["id"] != self.host_id:
                    raise RoomError("Solo el anfitrión puede expulsar usuarios")
                target = data.get("target")
                other = next((t for t, u in self.users.items() if u["id"] == target), None)
                if other is None or other == token:
                    raise RoomError("Selecciona otro usuario de la sala")
                self._remove(other, "fue expulsado por el anfitrión")
            elif op == "leave":
                self._remove(token, "salió de la sala")
                return {"left": True}
            elif isinstance(op, str) and op.startswith("tournament_"):
                host_only = ("tournament_config", "tournament_start", "tournament_simulate", "tournament_reset", "tournament_wo")
                if op in host_only and user["id"] != self.host_id:
                    raise RoomError("Solo el anfitrión puede organizar el torneo")
                try:
                    if op == "tournament_config":
                        self.tournament.configure(data.get("title"), data.get("ft"), data.get("characters"))
                    elif op == "tournament_register":
                        self.tournament.register(user, data.get("roster"))
                    elif op == "tournament_withdraw":
                        self.tournament.withdraw(user["id"])
                    elif op == "tournament_start":
                        self.tournament.start()
                    elif op == "tournament_report":
                        self.tournament.report(user["id"], data.get("tournament_id"), data.get("match"), data.get("score"))
                    elif op == "tournament_code":
                        self.tournament.match_code(user["id"], data.get("tournament_id"), data.get("match"), data.get("code"))
                    elif op == "tournament_simulate":
                        self.tournament.simulate()
                    elif op == "tournament_reset":
                        self._announce("El anfitrión cerró el torneo anterior. Se abren nuevas inscripciones.")
                        self.tournament = Tournament(self._announce)
                    elif op == "tournament_wo":
                        uid = data.get("target")
                        if type(uid) is not int or uid not in self.tournament.entrants or self.tournament.status != "running":
                            raise RoomError("Selecciona un participante del torneo activo para dar WO")
                        self._announce(self.tournament.entrants[uid]["name"] + ": baja por decisión del anfitrión (WO).")
                        self.tournament.disqualify(uid)
                    else:
                        raise RoomError("Operación desconocida")
                except TournamentError as exc:
                    raise RoomError(str(exc)) from None
            elif op not in ("join", "poll"):
                raise RoomError("Operación desconocida")
            return dict(protocol=PROTOCOL, title=self.title, capacity=self.capacity,
                        self_id=user["id"], host_id=self.host_id, token=token,
                        users=[{k: u[k] for k in ("id", "name", "ready", "bot", "game_bot")} for u in self.users.values()],
                        messages=list(self.messages), tournament=self.tournament.snapshot(user["id"]))


class RoomServer:
    def __init__(self, title, name, port=7001, capacity=8, bind="0.0.0.0", room=None):
        self.room = room if room is not None else Room(title, name, capacity)
        room = self.room

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                try:
                    self.connection.settimeout(3)
                    if self.path != "/btc-room":
                        raise RoomError("Ruta desconocida")
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 4096:
                        raise RoomError("Petición demasiado grande o vacía")
                    result = room.handle(json.loads(self.rfile.read(length)))
                    code = 200
                except (RoomError, ValueError, TypeError, OSError) as exc:
                    result, code = {"error": str(exc)}, 400
                payload = json.dumps(result, ensure_ascii=False).encode("utf-8")
                try:
                    self.send_response(code)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except OSError:
                    pass

            def log_message(self, *args):
                pass  # Never log membership tokens or the invitation key.

        class Server(ThreadingHTTPServer):
            daemon_threads = True
            request_queue_size = 32

            def verify_request(self, request, address):
                if threading.active_count() > 96:
                    return False
                request.settimeout(3)
                return True

        self.http = Server((bind, port), Handler)
        self.port = self.http.server_port
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        with self.room.lock:
            self.room.closed = True
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=4)


class RoomClient:
    def __init__(self, address, port, token=""):
        # Only a host/IP is accepted, never a URL, credentials or path.
        if not isinstance(address, str) or not address or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-" for c in address):
            raise RoomError("Escribe una IPv4 o un nombre de equipo, sin http://")
        if type(port) is not int or not 1 <= port <= 65535:
            raise RoomError("Puerto inválido")
        self.url = f"http://{address}:{port}/btc-room"
        self.token = token
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def send(self, op, **values):
        data = dict(values, op=op, token=self.token)
        req = urllib.request.Request(self.url, json.dumps(data).encode("utf-8"),
                                     {"Content-Type": "application/json"})
        try:
            with self.opener.open(req, timeout=2) as response:
                raw = response.read(262145)
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read(4096)).get("error", "Petición rechazada")
            except (ValueError, OSError):
                detail = "Petición rechazada"
            finally:
                exc.close()
            raise RoomError(detail) from None
        except OSError as exc:
            raise RoomError("No se pudo conectar con la sala: " + str(exc)) from None
        if len(raw) > 262144:
            raise RoomError("Respuesta de sala demasiado grande")
        try:
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError()
            if op != "leave" and (result.get("protocol") != PROTOCOL or
                    not isinstance(result.get("users"), list) or len(result["users"]) > MAX_USERS or
                    not isinstance(result.get("messages"), list) or len(result["messages"]) > 64):
                raise ValueError()
            if op != "leave":
                if not isinstance(result.get("token"), str) or not 1 <= len(result["token"]) <= 128:
                    raise ValueError()
                if any(type(result.get(k)) is not int or not 1 <= result[k] <= 0xFFFFFFFF
                       for k in ("self_id", "host_id", "capacity")) or result["capacity"] > MAX_USERS:
                    raise ValueError()
                result["title"] = text(result.get("title"), 64)
                for user in result["users"]:
                    if not isinstance(user, dict) or type(user.get("id")) is not int or not 1 <= user["id"] <= 0xFFFFFFFF:
                        raise ValueError()
                    user["name"] = text(user.get("name"), 24)
                    if type(user.get("ready")) is not bool:
                        raise ValueError()
                    if type(user.get("bot", False)) is not bool:
                        raise ValueError()
                for message in result["messages"]:
                    if not isinstance(message, dict):
                        raise ValueError()
                    message["author"] = text(message.get("author"), 24)
                    message["text"] = text(message.get("text"), 240)
                if "tournament" in result:
                    validate_snapshot(result["tournament"])
        except (ValueError, TypeError, RoomError):
            raise RoomError("Respuesta de sala incompatible") from None
        self.token = result.get("token", self.token)
        return result


def smoke_test():
    """Exercise the packaged HTTP dependencies without opening a game or a public port."""
    server = RoomServer("BTC smoke", "Host", port=0, bind="127.0.0.1")
    bots = None
    try:
        host = RoomClient("127.0.0.1", server.port, server.room.host_token)
        guest = RoomClient("127.0.0.1", server.port)
        state = guest.send("join", name="Guest", key=server.room.key, protocol=PROTOCOL, edition="BTC")
        if len(state["users"]) != 2:
            raise RoomError("La prueba no registró al invitado")
        guest_id = state["self_id"]
        guest.send("chat", text="BTC room smoke")
        if host.send("poll")["messages"][-1]["text"] != "BTC room smoke":
            raise RoomError("La prueba no recibió el chat")
        host.send("kick", target=guest_id)
        try:
            guest.send("poll")
        except RoomError:
            pass
        else:
            raise RoomError("La prueba no revocó al invitado expulsado")
        from rising_invite import make_invite, read_invite
        from rising_room_bots import RoomBots
        address, port, key = read_invite(make_invite("127.0.0.1", server.port, server.room.key))
        invited = RoomClient(address, port)
        invited.send("join", name="Code Guest", key=key, protocol=PROTOCOL, edition="BTC")
        bots = RoomBots(server)
        if bots.add(2) != 2 or len(host.send("poll")["users"]) != 4:
            raise RoomError("Falló la prueba de bots empaquetados")
        until = time.monotonic() + 5
        while host.send("poll")["tournament"]["enrolled"] != 2 and time.monotonic() < until:
            time.sleep(.05)
        state = host.send("tournament_start")["tournament"]
        if state["enrolled"] != 2 or state["status"] != "running":
            raise RoomError("Falló la inscripción de torneo empaquetado")
        if host.send("tournament_simulate")["tournament"]["status"] != "finished":
            raise RoomError("Falló el cierre del torneo empaquetado")
    finally:
        if bots: bots.close()
        server.close()
