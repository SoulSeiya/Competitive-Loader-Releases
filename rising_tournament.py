"""Authoritative single-elimination bracket, independent of the combat transport."""
import secrets


def validate_snapshot(t):
    """Validate remote data before it is copied into the fixed-size native bridge."""
    if not isinstance(t, dict) or t.get("status") not in ("registration", "running", "finished"):
        raise ValueError("Estado de torneo inválido")
    if t.get("mode", "elimination") not in ("elimination", "all_vs_host"):
        raise ValueError("Modalidad inválida")
    for key in ("ft", "characters", "enrolled", "role", "current", "champion", "revision"):
        if type(t.get(key)) is not int or not 0 <= t[key] <= 0xFFFFFFFF:
            raise ValueError("Campo de torneo inválido")
    if not 1 <= t["ft"] <= 5 or not 1 <= t["characters"] <= 5 or t["enrolled"] > 32 or t["role"] > 2 or t["current"] > 31:
        raise ValueError("Límites de torneo inválidos")
    for key, size in (("id", 64), ("title", 96), ("champion_name", 64)):
        if not isinstance(t.get(key), str) or len(t[key]) > size:
            raise ValueError("Texto de torneo inválido")
    if type(t.get("self_enrolled")) is not bool or not isinstance(t.get("self_roster"), list) or len(t["self_roster"]) > 5:
        raise ValueError("Inscripción inválida")
    if any(not isinstance(c, str) or len(c) > 32 for c in t["self_roster"]):
        raise ValueError("Personaje inválido")
    if not isinstance(t.get("matches"), list) or len(t["matches"]) > 31:
        raise ValueError("Bracket demasiado grande")
    for index, m in enumerate(t["matches"]):
        if not isinstance(m, dict) or m.get("state") not in ("pending", "active", "done"):
            raise ValueError("Cruce inválido")
        for k in ("id", "round", "p1", "p2", "winner", "confirmations"):
            value = m.get(k)
            if value is None and k in ("p1", "p2", "winner"): continue
            if type(value) is not int or not 0 <= value <= 0xFFFFFFFF: raise ValueError("Campo de cruce inválido")
        if m["id"] != index + 1 or not 1 <= m["round"] <= 5 or not 0 <= m["confirmations"] <= 2:
            raise ValueError("Orden de bracket inválido")
        for k, size in (("name1", 64), ("name2", 64), ("code", 7)):
            if not isinstance(m.get(k), str) or len(m[k]) > size: raise ValueError("Texto de cruce inválido")
        if type(m.get("bots")) is not bool: raise ValueError("Identidad de bots inválida")
        if "playable" in m and type(m["playable"]) is not bool: raise ValueError("Capacidad de combate inválida")
        score = m.get("score")
        if score is not None and (not isinstance(score, list) or len(score) != 2 or any(type(v) is not int or not 0 <= v <= 5 for v in score)):
            raise ValueError("Marcador inválido")


class TournamentError(ValueError):
    pass


class Tournament:
    def __init__(self, announce, shuffle=None):
        self.announce = announce
        self.shuffle = shuffle or secrets.SystemRandom().shuffle
        self.id = secrets.token_hex(12)
        self.title = "Torneo BTC"
        self.ft = 2
        self.characters = 1
        self.status = "registration"
        self.entrants = {}
        self.matches = []
        self.disqualified = set()
        self.current = None
        self.champion = None
        self.revision = 0
        self.mode = "elimination"
        self.challenger = 0
        self.spectator_test_host = 0
        self.four_test_humans = []

    def prepare_four_player_test(self):
        humans=[p for p in self.entrants if not self.entrants[p]["bot"]]
        bots=[p for p in self.entrants if self.entrants[p].get("game_bot")]
        if self.status!="registration" or len(self.entrants)!=4 or len(humans)!=2 or len(bots)!=2:
            raise TournamentError("La prueba requiere dos jugadores conectados y dos bots de combate")
        self.four_test_humans=humans
        self.ft=1
        self.announce("PRUEBA: humano contra bot en cada semifinal; despues ambos humanos juegan la final, incluso si pierden contra el bot. FT1 / 180 segundos.")

    def prepare_spectator_test(self, uid):
        if self.status != "registration" or uid not in self.entrants or self.entrants[uid]["bot"]:
            raise TournamentError("La prueba necesita un humano y dos bots de combate")
        self.spectator_test_host = uid
        self.revision += 1

    def prepare_challenge(self, uid):
        """Local lab schedule: the person plays every bot, including after a loss."""
        if self.status != "registration" or uid not in self.entrants or self.entrants[uid]["bot"]:
            raise TournamentError("La prueba necesita un jugador humano inscrito")
        self.mode, self.challenger = "all_vs_host", uid
        self.revision += 1

    def configure(self, title, ft, characters):
        if self.status != "registration":
            raise TournamentError("El torneo ya empezó")
        if not isinstance(title, str) or not title.strip() or len(title) > 64:
            raise TournamentError("Escribe un nombre de torneo de hasta 64 caracteres")
        if type(ft) is not int or not 1 <= ft <= 5:
            raise TournamentError("El FT debe estar entre 1 y 5")
        if type(characters) is not int or not 1 <= characters <= 5:
            raise TournamentError("El máximo de personajes debe estar entre 1 y 5")
        title = "".join(c for c in title if c >= " " and c != "\x7f").strip()
        if not title:
            raise TournamentError("El nombre del torneo está vacío")
        if characters != self.characters and self.entrants:
            self.entrants.clear()
            self.announce("Cambio de límite de personajes: vuelve a inscribirte.")
        self.title = title
        self.ft, self.characters = ft, characters
        self.revision += 1

    def register(self, user, roster):
        if self.status != "registration":
            raise TournamentError("Las inscripciones están cerradas")
        if not isinstance(roster, list) or not 1 <= len(roster) <= self.characters:
            raise TournamentError(f"Inscribe entre 1 y {self.characters} personajes")
        if any(not isinstance(c, str) or not c.strip() or len(c) > 32 or
               any(ord(x) < 32 for x in c) for c in roster):
            raise TournamentError("Personajes declarados inválidos")
        roster = [c.strip() for c in roster]
        if len({c.casefold() for c in roster}) != len(roster):
            raise TournamentError("No repitas un personaje en tu inscripción")
        self.entrants[user["id"]] = dict(id=user["id"], name=user["name"], bot=user["bot"], game_bot=user.get("game_bot", False), roster=roster)
        self.revision += 1
        self.announce(user["name"] + " se inscribió en " + self.title)

    def withdraw(self, uid):
        if self.status != "registration":
            raise TournamentError("El torneo ya empezó; el anfitrión puede resolver una baja por WO")
        if uid in self.entrants:
            name = self.entrants.pop(uid)["name"]
            self.revision += 1
            self.announce(name + " retiró su inscripción")

    def start(self):
        if self.status != "registration":
            raise TournamentError("El torneo ya empezó")
        if not 2 <= len(self.entrants) <= 32:
            raise TournamentError("Se necesitan entre 2 y 32 inscritos")
        players = list(self.entrants)
        if self.four_test_humans:
            bots=[p for p in players if p not in self.four_test_humans]
            players=self.four_test_humans+[bots[1],bots[0]]
        if self.spectator_test_host:
            human = self.spectator_test_host
            if len(players) != 3 or human not in players or any(not self.entrants[p].get("game_bot") for p in players if p != human):
                raise TournamentError("La prueba necesita exactamente un humano y dos bots de combate")
            players = [human] + [p for p in players if p != human]
        if self.mode == "all_vs_host":
            opponents = [p for p in players if p != self.challenger]
            if len(players) != 4 or any(not self.entrants[p].get("game_bot") for p in opponents):
                raise TournamentError("La prueba requiere un humano y tres bots de combate")
            for p in opponents:
                self.matches.append(dict(id=len(self.matches)+1, round=1, sources=[],
                    p1=self.challenger, p2=p, winner=None, score=None, reports={}, code="", state="pending"))
            self.status = "running"
            self.revision += 1
            self.announce(f"Inicia {self.title}: tres FT{self.ft}, todos contra {self._name(self.challenger)}.")
            self._advance()
            return
        if not self.spectator_test_host and not self.four_test_humans:
            self.shuffle(players)
        size = 1 << (len(players) - 1).bit_length()
        seeds = [1, 2]
        while len(seeds) < size:
            total = len(seeds) * 2 + 1
            seeds = [x for seed in seeds for x in (seed, total - seed)]
        slots = [players[s - 1] if s <= len(players) else 0 for s in seeds]
        previous = []
        round_no = 1
        while size > 1:
            row = []
            for i in range(size // 2):
                mid = len(self.matches) + 1
                source = [] if round_no == 1 else [previous[2*i], previous[2*i+1]]
                self.matches.append(dict(id=mid, round=round_no, sources=source,
                    p1=slots[2*i] if round_no == 1 else None,
                    p2=slots[2*i+1] if round_no == 1 else None,
                    winner=None, score=None, reports={}, code="", state="pending"))
                row.append(mid)
            previous = row
            size //= 2
            round_no += 1
        self.status = "running"
        self.revision += 1
        self.announce(f"Inicia {self.title}: {len(players)} inscritos, FT{self.ft}.")
        self._advance()

    def _name(self, uid):
        return self.entrants[uid]["name"] if uid else "Pase libre"

    def _finish(self, match, winner, score=None, reason="resultado"):
        match.update(winner=winner, score=score, state="done", code="")
        self.revision += 1
        if winner:
            result = f"{score[0]}–{score[1]}" if score else reason
            self.announce(f"Cruce #{match['id']}: avanza {self._name(winner)} ({result}).")

    def _advance(self):
        before = self.current
        self.current = None
        for match in self.matches:
            if match["winner"] is not None:
                continue
            if match["sources"]:
                left, right = (self.matches[i-1]["winner"] for i in match["sources"])
                if left is None or right is None:
                    continue
                if self.four_test_humans and match["id"]==len(self.matches):
                    left,right=self.four_test_humans
                match["p1"], match["p2"] = left, right
            a, b = match["p1"], match["p2"]
            if a is None or b is None:
                continue
            if a and b and self.entrants[a].get("game_bot") and not self.entrants[b]["bot"]:
                # The person keeps the native host/menu controls against an automated client.
                match["p1"], match["p2"] = b, a
                a, b = b, a
            available = [p for p in (a, b) if p and p not in self.disqualified]
            if len(available) < 2:
                self._finish(match, available[0] if available else 0, reason="pase libre" if not a or not b else "WO")
            elif self.current is None:
                self.current = match["id"]
                match["state"] = "active"
            else:
                match["state"] = "pending"
        final = self.matches[-1] if self.matches else None
        if final and all(m["winner"] is not None for m in self.matches):
            self.status, self.champion, self.current = "finished", final["winner"] if self.mode == "elimination" else None, None
            if self.mode == "all_vs_host":
                wins = sum(m["winner"] == self.challenger for m in self.matches)
                self.announce(f"GG - Prueba completada: {self._name(self.challenger)}, {wins} de {len(self.matches)} sets ganados.")
            else:
                self.announce("Torneo terminado. " + ("Campeón: " + self._name(self.champion) if self.champion else "Sin campeón."))
                for place, uid in enumerate(self.podium(), 1):
                    self.announce(f"Podio {place}: {self._name(uid)}")
        elif self.current and self.current != before:
            match = self.matches[self.current-1]
            self.announce(f"Próxima pelea #{match['id']}: {self._name(match['p1'])} vs {self._name(match['p2'])} — FT{self.ft}.")

    def _active(self, tid, mid):
        if tid != self.id or type(mid) is not int or not 1 <= mid <= len(self.matches):
            raise TournamentError("El resultado no corresponde a este torneo/cruce")
        return self.matches[mid-1]

    def report(self, uid, tid, mid, score):
        match = self._active(tid, mid)
        if uid not in (match["p1"], match["p2"]):
            raise TournamentError("Solo los jugadores del cruce pueden confirmar el resultado")
        if not isinstance(score, list) or len(score) != 2 or any(type(v) is not int or not 0 <= v <= self.ft for v in score):
            raise TournamentError("Marcador inválido")
        if (score[0] == self.ft) == (score[1] == self.ft):
            raise TournamentError("Solo un jugador debe alcanzar el FT")
        if match["state"] == "done":
            if match["score"] == score:
                return  # Repeated delivery cannot advance a second time.
            raise TournamentError("El cruce ya terminó con otro resultado")
        if self.status != "running" or self.current != mid:
            raise TournamentError("Este cruce todavía no está activo")
        match["reports"][uid] = list(score)
        self.revision += 1
        reports = list(match["reports"].values())
        if len(reports) == 2 and reports[0] == reports[1]:
            self._finish(match, match["p1"] if score[0] == self.ft else match["p2"], list(score))
            self._advance()
        elif len(reports) == 2:
            self.announce(f"Cruce #{mid}: resultados distintos; ambos jugadores deben revisarlos.")

    def match_code(self, uid, tid, mid, code):
        match = self._active(tid, mid)
        if self.status != "running" or self.current != mid or uid != match["p1"]:
            raise TournamentError("Solo P1 del cruce activo puede publicar su código de combate")
        if not isinstance(code, str) or not 1 <= len(code) <= 7 or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" for c in code):
            raise TournamentError("Código de combate inválido")
        if not match["code"]:
            match["code"] = code
            self.revision += 1
        elif match["code"] != code:
            raise TournamentError("El cruce ya tiene un código; cancela o resuelve el intento antes de repetir")

    def disqualify(self, uid):
        if uid not in self.entrants:
            return
        if self.status == "registration":
            self.withdraw(uid)
        elif self.status == "running":
            self.disqualified.add(uid)
            self.revision += 1
            self._advance()

    def simulate(self):
        if self.status != "running" or self.current is None:
            raise TournamentError("No hay un cruce activo")
        match = self.matches[self.current-1]
        if not all(self.entrants[p]["bot"] for p in (match["p1"], match["p2"])):
            raise TournamentError("Solo se pueden simular cruces entre dos bots")
        if any(self.entrants[p].get("game_bot") for p in (match["p1"], match["p2"])):
            raise TournamentError("Este cruce usa instancias reales: se resuelve jugando, no por simulación")
        score = [self.ft, 0]
        self._finish(match, match["p1"], score, "simulación de bots")
        self._advance()

    def podium(self):
        if self.status != "finished" or self.mode != "elimination" or not self.champion:
            return []
        final = self.matches[-1]
        second = next((p for p in (final["p1"], final["p2"]) if p and p != self.champion), 0)
        result = [self.champion] + ([second] if second else [])
        # Three entrants have exactly one other defeated player; no third-place match needed.
        if len(self.entrants) == 3:
            result.extend(p for p in self.entrants if p not in result)
        return result

    def snapshot(self, uid):
        current = self.matches[self.current-1] if self.current else None
        role = 1 if current and current["p1"] == uid else 2 if current and current["p2"] == uid else 0
        result = dict(id=self.id, title=self.title, ft=self.ft, characters=self.characters, mode=self.mode,
            status=self.status, enrolled=len(self.entrants), self_enrolled=uid in self.entrants,
            self_roster=self.entrants.get(uid, {}).get("roster", []), role=role,
            revision=self.revision, current=self.current or 0, champion=self.champion or 0,
            champion_name=self._name(self.champion) if self.champion else "",
            podium=[dict(place=i, id=p, name=self._name(p)) for i,p in enumerate(self.podium(),1)],
            participants=list(self.entrants.values()), matches=[])
        for m in self.matches:
            result["matches"].append({k: m[k] for k in ("id", "round", "p1", "p2", "winner", "score", "state", "code")})
            result["matches"][-1].update(name1=self._name(m["p1"]) if m["p1"] is not None else "Por definir",
                name2=self._name(m["p2"]) if m["p2"] is not None else "Por definir",
                bots=any(self.entrants[p]["bot"] for p in (m["p1"], m["p2"]) if p),
                playable=all(not self.entrants[p]["bot"] or self.entrants[p].get("game_bot") for p in (m["p1"], m["p2"]) if p),
                confirmations=len(m["reports"]))
        return result
