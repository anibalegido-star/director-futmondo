"""Calendario de LaLiga (openfootball, dominio público) y emparejamiento con Futmondo."""

import json
import re
import unicodedata
from pathlib import Path

import requests

from .config import DATA

URL = "https://raw.githubusercontent.com/openfootball/football.json/master/{season}/es.1.json"
CACHE = DATA / "calendario_{season}.json"

# nombre en Futmondo -> nombre en openfootball
ALIAS = {
    "Athletic de Bilbao": "Athletic Club", "Osasuna": "CA Osasuna",
    "Atlético de Madrid": "Club Atlético de Madrid", "Alavés": "Deportivo Alavés",
    "Elche": "Elche CF", "Barcelona": "FC Barcelona", "Getafe": "Getafe CF",
    "Levante": "Levante UD", "Málaga": "Málaga CF", "Celta de Vigo": "RC Celta de Vigo",
    "Deportivo de la Coruña": "RC Deportivo La Coruña", "Espanyol": "RCD Espanyol de Barcelona",
    "Rayo Vallecano": "Rayo Vallecano de Madrid", "Betis": "Real Betis Balompié",
    "Real Madrid": "Real Madrid CF", "Racing": "Real Racing Club de Santander",
    "Real Sociedad": "Real Sociedad de Fútbol", "Sevilla": "Sevilla FC",
    "Valencia": "Valencia CF", "Villarreal": "Villarreal CF",
}


def _norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", "", s).strip()


def load(season="2026-27", log=print):
    """Descarga el calendario (y guarda copia). Si falla, usa la copia guardada."""
    cache = Path(str(CACHE).format(season=season))
    try:
        r = requests.get(URL.format(season=season), timeout=20)
        r.raise_for_status()
        data = r.json()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data), encoding="utf-8")
    except Exception as e:
        if not cache.exists():
            log(f"   ⚠ Sin calendario de LaLiga ({e})")
            return None
        log(f"   ⚠ Calendario no actualizado ({e}); uso la copia guardada")
        data = json.loads(cache.read_text(encoding="utf-8"))
    return data


class Calendar:
    def __init__(self, data, futmondo_clubs):
        self.matches = []
        for m in (data or {}).get("matches", []):
            n = int(re.sub(r"\D", "", m.get("round", "")) or 0)
            self.matches.append({"round": n, "date": m.get("date"), "time": m.get("time"),
                                 "home": m["team1"], "away": m["team2"]})
        of_names = {x for m in self.matches for x in (m["home"], m["away"])}
        self.to_of = {}
        for club in futmondo_clubs:
            if club in ALIAS and ALIAS[club] in of_names:
                self.to_of[club] = ALIAS[club]
                continue
            hit = [o for o in of_names if _norm(club) and _norm(club) in _norm(o)]
            if len(hit) == 1:
                self.to_of[club] = hit[0]
        self.from_of = {v: k for k, v in self.to_of.items()}

    def fixture(self, club, rnd):
        """(rival en nombre Futmondo, en_casa, fecha) de un club en una jornada."""
        of = self.to_of.get(club)
        for m in self.matches:
            if m["round"] == rnd and of in (m["home"], m["away"]):
                home = m["home"] == of
                rival = m["away"] if home else m["home"]
                return {"rival": self.from_of.get(rival, rival), "casa": home, "fecha": m["date"],
                        "hora": m.get("time")}
        return None

    def next_round(self, today_iso):
        """Primera jornada con algún partido a partir de hoy."""
        future = sorted({m["round"] for m in self.matches if (m["date"] or "") >= today_iso[:10]})
        return future[0] if future else None
