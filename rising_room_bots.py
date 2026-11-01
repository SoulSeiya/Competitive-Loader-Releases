"""Local test users exercise the real room HTTP protocol; never control game characters."""
import threading
import time
from rising_room import PROTOCOL, RoomClient, RoomError


class RoomBots:
    def __init__(self, server, cycle=12, game_bots=False):
        self.server = server
        self.cycle = cycle
        self.game_bots = game_bots
        self.lock = threading.Lock()
        self.users = []
        self.number = 0
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._work, daemon=True)
        self.thread.start()

    def add(self, count):
        added = 0
        for _ in range(min(max(int(count), 0), 31)):
            if self.stop.is_set(): break
            self.number += 1
            client = RoomClient("127.0.0.1", self.server.port, self.server.room.host_token)
            try:
                state = client.send("join", name=f"Bot BTC {self.number:02}", bot=True, game_bot=self.game_bots,
                                    key=self.server.room.key, protocol=PROTOCOL, edition="BTC")
                user = dict(client=client, id=state["self_id"], next=time.monotonic()+self.cycle)
                with self.lock:
                    self.users.append(user)
                client.send("ready")
                client.send("chat", text="Bot de prueba conectado. Puedes expulsarme para probar la sala.")
                if state.get("tournament", {}).get("status") == "registration":
                    client.send("tournament_register", roster=["Personaje de prueba"])
                added += 1
            except RoomError:
                break  # Full room, duplicate name, closure: no retry/rejoin loop.
        return added

    def _work(self):
        while not self.stop.wait(.4):
            with self.lock:
                users = list(self.users)
            for user in users:
                if self.stop.is_set(): break
                try:
                    state = user["client"].send("poll")
                    tournament = state.get("tournament", {})
                    if tournament.get("status") == "registration" and not tournament.get("self_enrolled"):
                        user["client"].send("tournament_register", roster=["Personaje de prueba"])
                    if time.monotonic() >= user["next"]:
                        user["client"].send("ready")
                        user["next"] = time.monotonic() + self.cycle
                except RoomError:
                    with self.lock:
                        if user in self.users:
                            self.users.remove(user)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=3)
        with self.lock:
            users, self.users = self.users, []
        # Local host cleanup does not make 31 blocking requests after a lost connection.
        for user in users:
            try:
                self.server.room.handle(dict(op="leave", token=user["client"].token))
            except RoomError:
                pass
