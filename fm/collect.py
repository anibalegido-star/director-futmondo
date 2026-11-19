"""Descarga de datos y normalización a un formato canónico único.

Formato canónico de una captura:
{
  "captured_at": ISO UTC, "my_team_id": str,
  "teams":   [{id, name, points, team_value, clauses_in, clauses_out}],
  "rosters": {team_id: [jugador crudo de la API]},
  "market":  [jugador crudo], "my_market": [...], "news": [...],
  "summaries": {player_id: {"clause_real": float, "rounds": [...]}}
}
También convierte los informe_futmondo.json antiguos (v2/v3) al mismo formato.
"""

import json
from datetime import datetime, timezone

from .api import FutmondoAPI
from .config import RAW, credentials


def _as_list(x, keys=("players", "list", "data")):
    if isinstance(x, list):
        return x
    if isinstance(x, dict):
        for k in keys:
            if isinstance(x.get(k), list):
                return x[k]
    return []


def _teams(champ):
    out = []
    for t in (champ or {}).get("teams", []):
        cl = (t.get("clauses") or {}).get("t") or {}
        out.append({
            "id": t.get("id") or t.get("teamid"),
            "name": t.get("name"),
            "slug": t.get("teamslug"),
            "points": t.get("points"),
            "team_value": t.get("teamValue"),
            "clauses_in": cl.get("in"),
            "clauses_out": cl.get("out"),
        })
    return out


def collect_live(with_summaries=True, log=print):
    """Descarga una captura completa. Si falla un bloque esencial, lanza excepción."""
    c = credentials()
    api = FutmondoAPI(c["token"], c["user_id"], c["championship_id"], c["userteam_id"])
    snap = {
        "captured_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "my_team_id": c["userteam_id"],
        "errors": [],
    }
    log("Descargando clasificación...")
    champ = api.championship()
    snap["teams"] = _teams(champ)
    snap["config"] = (champ or {}).get("configuration") or {}

    log("Descargando plantillas de los 12 equipos...")
    snap["rosters"] = {}
    for t in snap["teams"]:
        roster = _as_list(api.roster(t["id"]))
        if not roster:
            raise RuntimeError(f"Plantilla vacía para {t['name']}: no guardo una captura parcial")
        snap["rosters"][t["id"]] = roster

    log("Descargando mercado y noticias...")
    snap["market"] = _as_list(api.market())
    for key, fn in (("my_market", api.my_market), ("news", api.pressroom)):
        try:
            val = fn()
            snap[key] = val.get("news", []) if key == "news" and isinstance(val, dict) else _as_list(val)
        except Exception as e:  # no esenciales
            snap[key] = []
            snap["errors"].append(f"{key}: {e}")

    snap["summaries"] = {}
    if with_summaries:
        jobs = [(p["id"], tid) for tid, ro in snap["rosters"].items() for p in ro]
        jobs += [(p["id"], None) for p in snap["market"]]
        log(f"Descargando fichas de {len(jobs)} jugadores (cláusula real + jornadas)...")
        fails = 0
        for i, (pid, tid) in enumerate(jobs, 1):
            try:
                s = api.player_summary(pid, tid)
                if s:
                    snap["summaries"][pid] = {"clause_real": s["clause_real"], "rounds": s["rounds"]}
            except Exception as e:
                fails += 1
                if fails <= 3:
                    snap["errors"].append(f"summary {pid}: {e}")
            if i % 50 == 0:
                log(f"   {i}/{len(jobs)}")
        if fails:
            snap["errors"].append(f"fichas fallidas: {fails}/{len(jobs)}")
    save_raw(snap)
    return snap


def save_raw(snap):
    RAW.mkdir(parents=True, exist_ok=True)
    stamp = snap["captured_at"][:16].replace(":", "")
    path = RAW / f"captura_{stamp}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False)
    return path


def canonical_from_informe(informe, my_team_id=None, captured_at=None):
    """Convierte un informe_futmondo.json (scripts v2/v3) al formato canónico."""
    teams = _teams(informe.get("campeonato"))
    by_name = {t["name"]: t["id"] for t in teams}
    rosters = {}
    for name, roster in (informe.get("rivales") or {}).items():
        if isinstance(roster, list) and name in by_name:
            rosters[by_name[name]] = roster
    if not my_team_id:
        mine = {p.get("id") for p in informe.get("mi_equipo") or []}
        best = max(rosters.items(), key=lambda kv: len(mine & {p.get("id") for p in kv[1]}), default=None)
        my_team_id = best[0] if best else None
    gen = informe.get("generado_en")
    if not captured_at and gen:
        # los informes antiguos guardaban hora local de Madrid sin zona
        dt = datetime.fromisoformat(gen)
        if dt.tzinfo is None:
            try:
                from zoneinfo import ZoneInfo
                dt = dt.replace(tzinfo=ZoneInfo("Europe/Madrid"))
            except Exception:  # Windows sin base de zonas horarias (paquete tzdata)
                from datetime import timedelta
                summer = 4 <= dt.month <= 10
                dt = dt.replace(tzinfo=timezone(timedelta(hours=2 if summer else 1)))
        captured_at = dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    news = informe.get("noticias_fichajes") or {}
    return {
        "captured_at": captured_at,
        "my_team_id": my_team_id,
        "teams": teams,
        "config": (informe.get("campeonato") or {}).get("configuration") or {},
        "rosters": rosters,
        "market": informe.get("mercado") or [],
        "my_market": informe.get("mis_jugadores_en_mercado") or [],
        "news": news.get("news", []) if isinstance(news, dict) else [],
        "summaries": {},
        "errors": informe.get("errores") or [],
    }
