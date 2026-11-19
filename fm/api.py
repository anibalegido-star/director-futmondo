"""Cliente de la API (no oficial) de Futmondo.

Reúne lo que funcionaba en las versiones anteriores:
- autenticación en el cuerpo de la petición (estilo v3, el que sigue funcionando a diario)
- reintentos con espera creciente y sesión nueva tras un corte
- respuestas envueltas o no en {"answer": ...}
- /1/player/summary para la cláusula REAL y las puntuaciones jornada a jornada
"""

import time

import requests

BASE_URL = "https://api.futmondo.com"

ENDPOINTS = {
    "championship": "/2/championship/teams",
    "market": "/1/market/players",
    "my_market": "/1/market/myplayers",
    "roster": "/1/userteam/roster",
    "pressroom": "/1/locker/pressroom",
    "player_summary": "/1/player/summary",
}


class FutmondoError(RuntimeError):
    pass


class FutmondoAPI:
    def __init__(self, token, user_id, championship_id, userteam_id, pause=0.15):
        self.token = token
        self.user_id = user_id
        self.championship_id = championship_id
        self.userteam_id = userteam_id
        self.pause = pause
        self._new_session()

    def _new_session(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
        })

    def _post(self, key, extra=None, retries=3):
        body = {
            "header": {"token": self.token, "userid": self.user_id},
            "query": {"championshipId": self.championship_id, "userteamId": self.userteam_id},
        }
        if extra:
            body["query"].update(extra)
        last = None
        for attempt in range(retries):
            try:
                r = self.session.post(BASE_URL + ENDPOINTS[key], json=body, timeout=25)
                r.raise_for_status()
                data = r.json()
                if isinstance(data, dict):
                    answer = data.get("answer", data)
                    if isinstance(answer, dict) and answer.get("error"):
                        raise FutmondoError(f"{key}: {answer.get('code') or answer}")
                    time.sleep(self.pause)
                    return answer
                time.sleep(self.pause)
                return data
            except FutmondoError:
                raise
            except (requests.RequestException, ValueError) as e:
                last = e
                if attempt < retries - 1:
                    time.sleep(1.5 * (attempt + 1))
                    self.session.close()
                    self._new_session()
        raise last

    # --- bloques de datos
    def championship(self):
        return self._post("championship", {"type": "market"})

    def roster(self, team_id):
        return self._post("roster", {"userteamId": team_id})

    def market(self):
        return self._post("market", {"type": "market"})

    def my_market(self):
        return self._post("my_market", {"type": "market"})

    def pressroom(self):
        return self._post("pressroom")

    def player_summary(self, player_id, team_id=None):
        """Ficha de jugador: cláusula real vigente + puntuación por jornada."""
        ans = self._post("player_summary", {
            "userteamId": team_id or self.userteam_id,
            "playerId": player_id,
        })
        if not isinstance(ans, dict):
            return None
        data = ans.get("data") or {}
        champ = ans.get("championship") or {}
        clause = champ.get("clause")
        clause_price = clause.get("price") if isinstance(clause, dict) else clause
        rounds = []
        for p in ans.get("points") or []:
            if p.get("round") is None:
                continue
            rounds.append({
                "round": p.get("round"),
                "points": p.get("points"),
                "home": p.get("isHomeTeam"),
                "starter": p.get("initialLineUp"),
                "st": p.get("st"),
            })
        return {"clause_real": clause_price, "rounds": rounds, "data": data}
