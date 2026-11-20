"""Revisión de cada jornada: el once que recomendé, el que pusiste tú y el ideal a toro pasado.

Futmondo no nos da tu alineación, así que la deducimos: tus puntos de la jornada salen de la
diferencia de puntos de tu equipo entre dos capturas, y buscamos qué once legal de tu plantilla
suma exactamente eso. Si solo hay una combinación posible, sabemos qué pusiste; si hay varias
que solo se diferencian en jugadores que puntuaron lo mismo, el resultado es igual de válido.
"""
import json
from datetime import datetime, timedelta
from itertools import combinations, product

from .metrics import FORMATIONS, ROLES, best_lineup

TOL = 0.05           # tolerancia al comparar sumas de puntos
MAX_SOLUCIONES = 50  # si hay más, no merece la pena listarlas


def _iso(s):
    try:
        return datetime.fromisoformat((s or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def _team_points(con, team_id):
    """[(captured_at, puntos de mi equipo, puntos totales de la liga)] en orden temporal."""
    rows = con.execute(
        "SELECT s.captured_at, "
        "  (SELECT points FROM team_snap WHERE snapshot_id=s.id AND team_id=?), "
        "  (SELECT SUM(points) FROM team_snap WHERE snapshot_id=s.id) "
        "FROM snapshots s ORDER BY s.captured_at", (team_id,)).fetchall()
    return [(r[0], r[1], r[2]) for r in rows if r[1] is not None]


def _roster_at(con, captured_at, team_id):
    sid = con.execute("SELECT id FROM snapshots WHERE captured_at=?", (captured_at,)).fetchone()
    if not sid:
        return []
    rows = con.execute("SELECT player_id, name, role, role2 FROM player_snap "
                       "WHERE snapshot_id=? AND owner=?", (sid[0], team_id)).fetchall()
    return [{"id": r[0], "name": r[1], "role": r[2], "role2": r[3] or ""} for r in rows]


def _actual(con, rnd, ids):
    """Puntos reales de la jornada. Si no hay registro, no jugó: 0."""
    out = {}
    for pid in ids:
        r = con.execute("SELECT points, st FROM rounds WHERE player_id=? AND round=?", (pid, rnd)).fetchone()
        out[pid] = (round(r[0] or 0, 1), r[1]) if r else (0.0, None)
    return out


def deducir_once(roster, pts, objetivo):
    """Todas las alineaciones legales cuya suma coincide con tus puntos reales."""
    flex = [p for p in roster if p["role2"] in ROLES and p["role2"] != p["role"]]
    sols, vistas = [], set()
    for choice in product(*[(p["role"], p["role2"]) for p in flex]) if flex else [()]:
        over = {p["id"]: r for p, r in zip(flex, choice)}
        by = {r: [p for p in roster if over.get(p["id"], p["role"]) == r] for r in ROLES}
        for d, c, f in FORMATIONS:
            need = {"defensa": d, "centrocampista": c, "delantero": f}
            if not by["portero"] or any(len(by[r]) < n for r, n in need.items()):
                continue
            # sumas por línea para podar rápido
            lines = {r: [(round(sum(pts[x["id"]] for x in cmb), 1), cmb)
                         for cmb in combinations(by[r], n)] for r, n in need.items()}
            for gk in by["portero"]:
                g = pts[gk["id"]]
                for sd, cd in lines["defensa"]:
                    for sm, cm in lines["centrocampista"]:
                        rest = objetivo - g - sd - sm
                        for sf, cf in lines["delantero"]:
                            if abs(rest - sf) <= TOL:
                                ids = frozenset([gk["id"]] + [x["id"] for x in cd + cm + cf])
                                if ids not in vistas:
                                    vistas.add(ids)
                                    sols.append((ids, f"{d}-{c}-{f}"))
                                    if len(sols) > MAX_SOLUCIONES:
                                        return sols
    return sols


def _round_window(series, freeze_at, next_freeze_at):
    """Puntos de tu equipo al empezar la jornada y al acabar (o lo último que tengamos)."""
    start = next((s for s in series if s[0] == freeze_at), None)
    if not start:
        return None, None, True
    end = None
    if next_freeze_at:
        end = next((s for s in series if s[0] == next_freeze_at), None)
    provisional = end is None
    if end is None:
        end = series[-1]
        # damos la jornada por cerrada si las dos últimas capturas (separadas 10h o más) no cambian
        if len(series) >= 2:
            a, b = series[-2], series[-1]
            ta, tb = _iso(a[0]), _iso(b[0])
            if ta and tb and tb - ta >= timedelta(hours=10) and abs((a[2] or 0) - (b[2] or 0)) < TOL \
                    and b[0] > freeze_at and abs((b[2] or 0) - (start[2] or 0)) > TOL:
                provisional = False
    return start, end, provisional


def review_round(con, rnd, my_id, series, next_lineup):
    row = con.execute("SELECT player_ids, proj_total, captured_at FROM lineups WHERE round=? AND team_id=?",
                      (rnd, my_id)).fetchone()
    if not row:
        return None
    mio_ids, proj_total, freeze_at = json.loads(row[0]), row[1], row[2]
    roster = _roster_at(con, freeze_at, my_id)
    if not roster:
        return None
    ids = [p["id"] for p in roster]
    act = _actual(con, rnd, set(ids) | set(mio_ids))
    pts = {pid: v[0] for pid, v in act.items()}
    if not any(v[1] is not None for v in act.values()):
        return None  # la jornada aún no ha empezado para tus jugadores
    names = {p["id"]: p["name"] for p in roster}
    projs = dict(con.execute("SELECT player_id, proj FROM projections WHERE round=?", (rnd,)).fetchall())

    mio_pts = round(sum(pts.get(i, 0) for i in mio_ids), 1)
    ideal_pts, ideal_form, ideal_picks = best_lineup([dict(p, real=pts[p["id"]]) for p in roster], "real")
    ideal_ids = [p["id"] for p, _ in ideal_picks]

    start, end, provisional = _round_window(series, freeze_at, next_lineup)
    tus_pts = round(end[1] - start[1], 1) if start and end else None
    tu_once, dudosos, deduccion = None, [], "sin_datos"
    if tus_pts is not None:
        sols = deducir_once(roster, pts, tus_pts)
        if not sols:
            deduccion = "no_cuadra"
        else:
            comunes = frozenset.intersection(*[s for s, _ in sols])
            todos = frozenset.union(*[s for s, _ in sols])
            dudosos = sorted(todos - comunes)
            # si las alternativas solo cambian jugadores con los mismos puntos, da igual cuál
            if len(sols) == 1:
                deduccion = "exacta"
            elif len({round(pts[i], 1) for i in dudosos}) <= 1:
                deduccion = "equivalente"
            else:
                deduccion = "ambigua"
            # nos quedamos con la solución más parecida a mi recomendación
            tu_once = max(sols, key=lambda s: len(s[0] & set(mio_ids)))[0]

    def fila(pid):
        return {"id": pid, "name": names.get(pid, pid), "real": pts.get(pid, 0),
                "proj": round(projs[pid], 1) if pid in projs else None, "st": act.get(pid, (0, None))[1]}

    cambios = None
    if tu_once is not None and deduccion in ("exacta", "equivalente"):
        metiste = [fila(i) for i in tu_once - set(mio_ids)]
        quitaste = [fila(i) for i in set(mio_ids) - tu_once]
        cambios = {"metiste": sorted(metiste, key=lambda x: -x["real"]),
                   "quitaste": sorted(quitaste, key=lambda x: -x["real"]),
                   "balance": round(sum(x["real"] for x in metiste) - sum(x["real"] for x in quitaste), 1)}

    # mis fallos: los del once que rindieron muy por debajo, y los del banquillo que se salieron
    mio_rows = [fila(i) for i in mio_ids]
    fallos = [r for r in mio_rows if r["proj"] is not None and r["real"] <= r["proj"] - 4]
    banquillo_top = [fila(i) for i in ids if i not in mio_ids and pts[i] >= 6
                     and i in ideal_ids]
    errs = [abs(projs[i] - pts[i]) for i in ids if i in projs]
    return {
        "jornada": rnd, "provisional": provisional, "congelado": freeze_at,
        "director": {"proyectado": proj_total, "real": mio_pts, "once": sorted(mio_rows, key=lambda x: -x["real"])},
        "tu": {"real": tus_pts, "deduccion": deduccion,
               "once": sorted([fila(i) for i in tu_once], key=lambda x: -x["real"]) if tu_once else None,
               "dudosos": [names.get(i, i) for i in dudosos]},
        "ideal": {"real": ideal_pts, "formacion": ideal_form,
                  "once": sorted([fila(i) for i in ideal_ids], key=lambda x: -x["real"])},
        "cambios": cambios,
        "fallos": sorted(fallos, key=lambda x: x["real"] - x["proj"]),
        "banquillo": sorted(banquillo_top, key=lambda x: -x["real"]),
        "error_medio": round(sum(errs) / len(errs), 2) if errs else None,
    }


def review_all(con, my_id, upto_round):
    """Revisiones de todas las jornadas con recomendación guardada, la más reciente primero."""
    series = _team_points(con, my_id)
    rows = con.execute("SELECT round, captured_at FROM lineups WHERE team_id=? AND round<=? ORDER BY round",
                       (my_id, upto_round)).fetchall()
    freeze = {r[0]: r[1] for r in rows}
    out = []
    for rnd in sorted(freeze):
        # la captura con la que se congeló la siguiente jornada solo vale si esa jornada ya empezó
        nxt = freeze.get(rnd + 1) if (rnd + 1) <= upto_round else None
        rv = review_round(con, rnd, my_id, series, nxt)
        if rv:
            out.append(rv)
    resumen = None
    ok = [r for r in out if r["tu"]["real"] is not None and not r["provisional"]]
    if ok:
        cambiaste = [r for r in ok if r["cambios"] and (r["cambios"]["metiste"] or r["cambios"]["quitaste"])]
        resumen = {
            "jornadas": len(ok),
            "tu_total": round(sum(r["tu"]["real"] for r in ok), 1),
            "director_total": round(sum(r["director"]["real"] for r in ok), 1),
            "ideal_total": round(sum(r["ideal"]["real"] for r in ok), 1),
            "jornadas_con_cambios": len(cambiaste),
            "cambios_acertados": sum(1 for r in cambiaste if r["cambios"]["balance"] > 0),
            "cambios_fallados": sum(1 for r in cambiaste if r["cambios"]["balance"] < 0),
        }
    return {"jornadas": list(reversed(out)), "resumen": resumen}
