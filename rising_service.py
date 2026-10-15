"""BTC coordinator: one short code, up to 32 members, independent combat codes.

Run behind an HTTPS reverse proxy for Internet use. No game data is relayed.
State is ephemeral; restart closes rooms. This module has no third-party dependencies.
"""
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse
import json
import secrets
import threading
import time
import urllib.parse

from rising_room import Room, RoomClient, RoomError, PROTOCOL

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def room_code(value):
    if not isinstance(value, str):
        raise RoomError("Código de sala inválido")
    value = value.strip().upper()
    if value.startswith("BTC-"):
        value = value[4:]
    if len(value) != 6 or any(c not in ALPHABET for c in value):
        raise RoomError("Usa el código BTC de seis letras/números")
    return value


class Coordinator:
    def __init__(self, clock=time.monotonic, capacity=256):
        self.clock, self.capacity = clock, capacity
        self.lock = threading.RLock()
        self.rooms = {}
        self.limits = {}
        self.bots = {}

    def _cleanup(self):
        for code, room in list(self.rooms.items()):
            with room.lock:
                tokens = self.bots.get(code, set())
                tokens.intersection_update(room.users)
                for token in tokens:
                    room.users[token]["seen"] = self.clock()
                room._expire()
                if room.closed:
                    del self.rooms[code]
                    self.bots.pop(code, None)
        now = self.clock()
        for ip, events in list(self.limits.items()):
            while events and now-events[0] >= 3600:
                events.popleft()
            if not events:
                del self.limits[ip]

    def _limit(self, ip):
        events = self.limits.setdefault(ip, deque())
        if len(events) >= 60 or len(self.limits) > 4096:
            raise RoomError("Demasiados intentos de crear/entrar; espera antes de repetir")
        events.append(self.clock())

    def handle(self, data, ip="local"):
        if not isinstance(data, dict):
            raise RoomError("Petición inválida")
        op = data.get("op")
        # Admission is serialized; each room retains its own operation lock.
        with self.lock:
            self._cleanup()
            if op in ("create", "join"):
                self._limit(ip)
            if op == "create":
                if data.get("protocol") != PROTOCOL or data.get("edition") != "BTC":
                    raise RoomError("Versión del servicio BTC incompatible")
                if len(self.rooms) >= self.capacity:
                    raise RoomError("Servicio de salas lleno")
                code = "".join(secrets.choice(ALPHABET) for _ in range(6))
                while code in self.rooms:
                    code = "".join(secrets.choice(ALPHABET) for _ in range(6))
                room = Room(data.get("title"), data.get("name"), data.get("capacity", 8), clock=self.clock)
                self.rooms[code] = room
                values = dict(op="poll", token=room.host_token)
            else:
                code = room_code(data.get("code"))
                room = self.rooms.get(code)
                if room is None:
                    raise RoomError("La sala no existe o ha caducado")
                values = dict(data)
                if op == "join":
                    # Knowing a code invites a person, never authorizes a bot or host action.
                    values.update(key=room.key, bot=False, game_bot=False)
            if op in ("bots_add", "bots_remove"):
                with room.lock:
                    token = data.get("token")
                    if not isinstance(token, str) or token != room.host_token or token not in room.users:
                        raise RoomError("Solo el anfitrión puede gestionar los bots")
                    room.handle(dict(op="poll", token=token))
                    tokens = self.bots.setdefault(code, set())
                    if op == "bots_add":
                        count = data.get("count")
                        if type(count) is not int or not 1 <= count <= 31:
                            raise RoomError("Elige entre 1 y 31 bots")
                        for _ in range(min(count, room.capacity-len(room.users))):
                            number = room.next_id+1
                            name = f"Bot BTC {number:02}"
                            while any(u["name"].casefold() == name.casefold() for u in room.users.values()):
                                number += 1
                                name = f"Bot BTC {number:02}"
                            bot = room.handle(dict(op="join", token=token, key=room.key,
                                name=name, bot=True, protocol=PROTOCOL, edition="BTC"))["token"]
                            tokens.add(bot)
                            room.handle(dict(op="ready", token=bot))
                            room.handle(dict(op="chat", token=bot, text="Bot de sala conectado para probar usuarios, chat y expulsiones."))
                            if room.tournament.status == "registration":
                                room.handle(dict(op="tournament_register", token=bot, roster=["Personaje de prueba"]))
                    else:
                        for bot in list(tokens):
                            if bot in room.users:
                                room.handle(dict(op="leave", token=bot))
                        tokens.clear()
                    values = dict(op="poll", token=token)
            result = room.handle(values)
        result["room_code"] = "BTC-"+code
        return result


class ServiceServer:
    def __init__(self, bind="127.0.0.1", port=7010, coordinator=None):
        self.coordinator = coordinator or Coordinator()
        coordinator = self.coordinator
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                try:
                    self.connection.settimeout(3)
                    if self.path != "/v1/rooms":
                        raise RoomError("Ruta desconocida")
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 4096:
                        raise RoomError("Petición demasiado grande o vacía")
                    result = coordinator.handle(json.loads(self.rfile.read(length)), self.client_address[0])
                    status = 200
                except (RoomError, ValueError, TypeError, OSError) as exc:
                    result, status = {"error": str(exc)}, 400
                payload = json.dumps(result, ensure_ascii=False).encode("utf-8")
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers(); self.wfile.write(payload)
                except OSError:
                    pass
            def log_message(self, *args):
                pass  # Never log invitation codes, membership tokens or chat.
        class Server(ThreadingHTTPServer):
            daemon_threads = True
            request_queue_size = 32
            def verify_request(self, connection, address):
                connection.settimeout(3)
                return threading.active_count() < 96
        self.http = Server((bind, port), Handler)
        self.port = self.http.server_port
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
    def close(self):
        self.http.shutdown(); self.http.server_close(); self.thread.join(timeout=3)


class ServiceClient(RoomClient):
    def __init__(self, url, code="", token=""):
        super().__init__("127.0.0.1", 1, token)
        parsed = urllib.parse.urlsplit(url.strip())
        if (parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or
                parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
            raise RoomError("Usa la URL base del servicio BTC, sin ruta ni credenciales")
        if parsed.scheme == "http" and parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise RoomError("El servicio remoto requiere HTTPS")
        self.url = url.strip().rstrip("/") + "/v1/rooms"
        self.code = room_code(code) if code else ""
    def send(self, op, **values):
        result = super().send(op, code=self.code, **values)
        if op != "leave":
            self.code = room_code(result.get("room_code"))
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7010)
    args = parser.parse_args()
    server = ServiceServer(args.bind, args.port)
    print(f"BTC coordinator listening on {args.bind}:{server.port}", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        server.close()


def smoke_test():
    server=ServiceServer(port=0)
    try:
        url=f"http://127.0.0.1:{server.port}"
        host=ServiceClient(url)
        state=host.send("create",name="Host",title="BTC smoke",capacity=4,protocol=PROTOCOL,edition="BTC")
        guests=[ServiceClient(url,state["room_code"]) for _ in range(3)]
        for i,g in enumerate(guests):g.send("join",name=f"Guest {i}",protocol=PROTOCOL,edition="BTC")
        if len(host.send("poll")["users"])!=4:raise RoomError("Falló el servicio empaquetado")
        guests[-1].send("chat",text="Codigo y chat de cuatro")
        if guests[0].send("poll")["messages"][-1]["text"]!="Codigo y chat de cuatro":raise RoomError("Falló el chat del servicio")
        host.send("leave")
    finally:server.close()


if __name__ == "__main__":
    main()
