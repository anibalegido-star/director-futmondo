"""Importa el histórico que ya existía en tu ordenador para no empezar en blanco.

Fuentes (todas opcionales, se saltan si no existen):
- informes JSON de los scripts v2/v3 (raíz y carpeta historico/)
- la base SQLite de futmondo_assistant (capturas de septiembre y octubre,
  con cláusulas reales y puntuaciones por jornada)
"""

import json
import sqlite3
from pathlib import Path

from .collect import canonical_from_informe
from .db import save_snapshot


def import_informes(con, paths, log=print):
    n = 0
    for p in paths:
        p = Path(p)
        if not p.exists():
            continue
        try:
            snap = canonical_from_informe(json.loads(p.read_text(encoding="utf-8")))
        except Exception as e:
            log(f"   ⚠ {p.name}: {e}")
            continue
        if snap.get("captured_at") and snap["rosters"] and save_snapshot(con, snap, source=f"informe:{p.name}"):
            n += 1
    return n


def import_assistant_db(con, db_path, log=print):
    db_path = Path(db_path)
    if not db_path.exists():
        return 0
    src = sqlite3.connect(db_path)
    n = 0
    # una captura por día basta (había varias seguidas de prueba el mismo día)
    snaps = src.execute("SELECT id, captured_at FROM snapshots ORDER BY captured_at").fetchall()
    per_day = {}
    for sid, ts in snaps:
        per_day[ts[:10]] = (sid, ts)
    for sid, ts in per_day.values():
        teams = [{"id": tid, "name": name, "points": pts, "team_value": tv,
                  "clauses_in": ((json.loads(raw).get("clauses") or {}).get("t") or {}).get("in"),
                  "clauses_out": ((json.loads(raw).get("clauses") or {}).get("t") or {}).get("out")}
                 for tid, name, pts, tv, raw in src.execute(
                     "SELECT team_id, name, points, team_value, raw_json FROM team_snapshots WHERE snapshot_id=?", (sid,))]
        rosters, summaries = {}, {}
        for tid, raw, clause in src.execute(
                "SELECT team_id, raw_json, clause FROM roster_snapshots WHERE snapshot_id=?", (sid,)):
            p = json.loads(raw)
            if not isinstance(p.get("clause"), dict):
                p["clause"] = None
            rosters.setdefault(tid, []).append(p)
            if clause:
                summaries[p.get("id")] = {"clause_real": clause, "rounds": []}
        market = []
        for raw, in src.execute("SELECT raw_json FROM market_snapshots WHERE snapshot_id=?", (sid,)):
            p = json.loads(raw)
            if not isinstance(p.get("clause"), dict):
                p["clause"] = None
            market.append(p)
        if not rosters:
            continue
        snap = {"captured_at": ts, "my_team_id": None, "teams": teams, "rosters": rosters,
                "market": market, "news": [], "summaries": summaries}
        if save_snapshot(con, snap, source="futmondo_assistant"):
            n += 1
    # jornadas
    try:
        rows = src.execute("SELECT player_id, round, points, is_home, initial_lineup, st "
                           "FROM player_matchday_performance").fetchall()
        con.executemany("INSERT OR IGNORE INTO rounds VALUES (?,?,?,?,?,?)", rows)
        con.commit()
    except sqlite3.Error as e:
        log(f"   ⚠ jornadas: {e}")
    return n


def bootstrap(con, futmondo_dir, log=print):
    """Importa todo lo disponible bajo Escritorio\\futmondo (la carpeta padre)."""
    base = Path(futmondo_dir)
    informes = sorted(base.glob("historico/*.json")) + sorted(base.glob("v3/historico/*.json"))
    informes += [base / "informe_futmondo.json", base / "v3" / "informe_futmondo.json"]
    a = import_informes(con, informes, log)
    dbs = [base / "futmondo2/futmondo_assistant/data/futmondo.db",
           base.parent.parent / "Downloads/futmondo_assistant_v1_2_real_sync/futmondo_assistant_v1_2/data/futmondo.db"]
    b = sum(import_assistant_db(con, d, log) for d in dbs)
    # fija mi equipo en capturas antiguas que no lo traían
    mine = con.execute("SELECT my_team_id FROM snapshots WHERE my_team_id IS NOT NULL "
                       "ORDER BY captured_at DESC LIMIT 1").fetchone()
    if mine:
        con.execute("UPDATE snapshots SET my_team_id=? WHERE my_team_id IS NULL", (mine[0],))
        con.commit()
    log(f"   Histórico importado: {a} informes + {b} capturas de futmondo_assistant")
    return a + b
