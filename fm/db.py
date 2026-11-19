"""Histórico en SQLite: una fila por jugador y captura, más jornadas y fichajes.

La clave del Director es comparar en el tiempo (quién sube de valor, quién se
desinfla, quién blinda cláusulas), así que cada captura se guarda entera y
nunca se sobrescribe.
"""

import json
import sqlite3

from .config import DB_PATH, DATA

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at TEXT NOT NULL UNIQUE,
    source TEXT,
    my_team_id TEXT
);
CREATE TABLE IF NOT EXISTS team_snap (
    snapshot_id INTEGER, team_id TEXT, name TEXT, points REAL, team_value REAL,
    clauses_in INTEGER, clauses_out INTEGER,
    PRIMARY KEY (snapshot_id, team_id)
);
CREATE TABLE IF NOT EXISTS player_snap (
    snapshot_id INTEGER, player_id TEXT, owner TEXT, name TEXT, role TEXT, role2 TEXT,
    club TEXT, status TEXT, points REAL, value REAL, change REAL,
    avg REAL, avg5 REAL, matches INTEGER,
    clause_real REAL, clause_price REAL, clause_suggested REAL, locked_until TEXT,
    market_price REAL, market_expires TEXT, market_seller TEXT,
    PRIMARY KEY (snapshot_id, player_id, owner)
);
CREATE INDEX IF NOT EXISTS ix_player ON player_snap(player_id);
CREATE TABLE IF NOT EXISTS rounds (
    player_id TEXT, round INTEGER, points REAL, home INTEGER, starter INTEGER, st TEXT,
    PRIMARY KEY (player_id, round)
);
CREATE TABLE IF NOT EXISTS news (
    id TEXT PRIMARY KEY, created TEXT, player_id TEXT, player_name TEXT, club TEXT,
    buyer_id TEXT, buyer TEXT, seller_id TEXT, seller TEXT, price REAL, bids_json TEXT
);
"""


def connect(path=DB_PATH):
    DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _player_row(sid, p, owner, summaries):
    avg = p.get("average") or {}
    c = p.get("clause")
    if isinstance(c, dict):
        c_price, c_sugg = _num(c.get("price")), _num(c.get("suggestedClause"))
        locked = c.get("transferDate") if c.get("transferred") else None
    else:
        c_price = c_sugg = None
        locked = None
    s = summaries.get(p.get("id")) or {}
    seller = None
    if owner == "market":
        seller = None if p.get("computer") else (p.get("userTeam") or None)
    return (
        sid, p.get("id"), owner, p.get("name"), p.get("role"), p.get("role2") or "",
        p.get("team"), p.get("status") or "", _num(p.get("points")), _num(p.get("value")),
        _num(p.get("change")), _num(avg.get("average")), _num(avg.get("averageLastFive")),
        avg.get("matches"), _num(s.get("clause_real")), c_price, c_sugg, locked,
        _num(p.get("price")) if owner == "market" else None,
        p.get("expirationDate") if owner == "market" else None, seller,
    )


def save_snapshot(con, snap, source="api"):
    """Guarda una captura canónica (ver collect.canonical). Devuelve el id o None si ya existía."""
    cur = con.execute(
        "INSERT OR IGNORE INTO snapshots (captured_at, source, my_team_id) VALUES (?,?,?)",
        (snap["captured_at"], source, snap.get("my_team_id")),
    )
    if cur.rowcount == 0:
        return None
    sid = cur.lastrowid
    summaries = snap.get("summaries") or {}
    for t in snap.get("teams", []):
        con.execute("INSERT OR REPLACE INTO team_snap VALUES (?,?,?,?,?,?,?)", (
            sid, t["id"], t["name"], t.get("points"), t.get("team_value"),
            t.get("clauses_in"), t.get("clauses_out")))
    rows = []
    for team_id, roster in (snap.get("rosters") or {}).items():
        for p in roster or []:
            rows.append(_player_row(sid, p, team_id, summaries))
    for p in snap.get("market") or []:
        rows.append(_player_row(sid, p, "market", summaries))
    con.executemany(
        "INSERT OR REPLACE INTO player_snap VALUES (" + ",".join("?" * 21) + ")", rows)
    for pid, s in summaries.items():
        for r in s.get("rounds") or []:
            con.execute("INSERT OR REPLACE INTO rounds VALUES (?,?,?,?,?,?)", (
                pid, r["round"], _num(r.get("points")),
                1 if r.get("home") else 0, 1 if r.get("starter") else 0, r.get("st")))
    save_news(con, snap.get("news") or [])
    con.commit()
    return sid


def save_news(con, news):
    for n in news:
        pl = n.get("_player") or {}
        b = n.get("_buyer") or {}
        s = n.get("_seller") or {}
        con.execute("INSERT OR IGNORE INTO news VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            n.get("_id"), n.get("created"), pl.get("_id"), pl.get("name"),
            (n.get("_playerTeam") or {}).get("name"), b.get("_id"), b.get("name"),
            s.get("_id"), s.get("name"), _num(n.get("price")),
            json.dumps(n.get("bids") or [], ensure_ascii=False)))
