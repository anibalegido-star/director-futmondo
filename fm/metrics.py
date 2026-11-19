"""Métricas de jugador y cálculo del once ideal.

La idea central: medir cualquier movimiento por cuánto mejora TU once titular
proyectado (puntos por jornada), no por estadísticas sueltas.
"""

import statistics
from datetime import datetime, timezone
from itertools import combinations

ROLES = ("portero", "defensa", "centrocampista", "delantero")
FORMATIONS = [(3, 4, 3), (3, 5, 2), (4, 3, 3), (4, 4, 2), (4, 5, 1), (5, 3, 2), (5, 4, 1)]
UNAVAILABLE = {"injured", "injured2", "redcard"}
PRIOR = 4.0          # rendimiento de un suplente cualquiera (pts/jornada)
FULL_CONF_MATCHES = 6


def num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def parse_dt(s):
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def clause_info(p, summary=None, now=None):
    """Cláusula vigente.

    La ficha del jugador (/player/summary) devuelve la cláusula real, que incluye
    las subidas que haya hecho su dueño (se ven saltos redondos de +3M, +6M, +9M
    sobre clause.price). Si no hay ficha, se da el rango entre price y
    suggestedClause como hacía la v3, marcándolo como estimado.
    """
    now = now or datetime.now(timezone.utc)
    c = p.get("clause") if isinstance(p.get("clause"), dict) else {}
    price, sugg = num(c.get("price")), num(c.get("suggestedClause"))
    real = num((summary or {}).get("clause_real"))
    locked_until = None
    if c.get("transferred"):
        dt = parse_dt(c.get("transferDate"))
        if dt and dt > now:
            locked_until = dt.isoformat()
    if real > 0:
        return {"min": real, "max": real, "exact": True, "locked_until": locked_until,
                "raised": bool(price and real - price > 500_000)}
    # Sin ficha: si la cláusula se fijó hace poco (fichaje o subida reciente), clause.price
    # es la buena y suggestedClause suele ser el precio de compra antiguo (caso Carles Pérez:
    # price 10,49M = app; suggested 5,33M = lo que pagó su dueño).
    set_on = parse_dt(c.get("date"))
    if price > 0 and set_on and (now - set_on).days <= 60:
        return {"min": price, "max": price, "exact": False, "probable": True,
                "locked_until": locked_until, "raised": False}
    vals = [v for v in (price, sugg) if v > 0]
    if not vals:
        return {"min": 0, "max": 0, "exact": False, "locked_until": locked_until, "raised": False}
    return {"min": min(vals), "max": max(vals), "exact": len(set(vals)) == 1,
            "locked_until": locked_until, "raised": False}


def player_metrics(p, summary=None, rounds=None, season_rounds=None):
    avg = p.get("average") or {}
    a, a5, m = num(avg.get("average")), num(avg.get("averageLastFive")), int(num(avg.get("matches")))
    fitness = [num(x) for x in (avg.get("fitness") or []) if isinstance(x, (int, float))]
    conf = min(1.0, m / FULL_CONF_MATCHES)
    # "average" es la media POR PARTIDO JUGADO; "averageLastFive" ya cuenta como 0 las
    # jornadas sin jugar. Para no sobrevalorar a quien rota, la media de temporada se
    # multiplica por su tasa de participación (partidos jugados / jornadas disputadas).
    participation = min(1.0, m / season_rounds) if season_rounds else 1.0
    played_last5 = sum(1 for v in fitness if v != 0) if fitness else None
    # jornadas seguidas sin jugar al final de la serie (la lista va de más antigua a más reciente)
    absent_streak = 0
    for v in reversed(fitness):
        if v != 0:
            break
        absent_streak += 1
    base = conf * (0.55 * a5 + 0.45 * a * participation) + (1 - conf) * PRIOR * participation
    status = p.get("status") or ""
    next_factor = 0.0 if status in UNAVAILABLE else (0.6 if status == "doubt" else 1.0)
    reg = statistics.pstdev(fitness) if len(fitness) >= 2 else None
    starter_rate = None
    if rounds:
        last = sorted(rounds, key=lambda r: r["round"])[-5:]
        starter_rate = sum(1 for r in last if r["starter"]) / len(last)
    return {
        "id": p.get("id"), "name": p.get("name"), "role": p.get("role"),
        "role2": p.get("role2") or "", "club": p.get("team"), "status": status,
        "points": num(p.get("points")), "value": num(p.get("value")), "change": num(p.get("change")),
        "avg": round(a, 2), "avg5": round(a5, 2), "matches": m, "fitness": fitness,
        "form_delta": round(a5 - a, 2) if m >= 3 else 0.0,
        "regularity": round(reg, 2) if reg is not None else None,
        "starter_rate": starter_rate,
        "participation": round(participation, 2),
        "played_last5": played_last5,
        "absent_streak": absent_streak,
        "proj": round(base, 2),
        "proj_next": round(base * next_factor, 2),
        "clause": clause_info(p, summary),
    }


REPLACEMENT = 3.0  # un hueco vacío se cubre con un fichaje barato de ~3 pts/jornada


def best_xi(players, key="proj_next"):
    """Mejor once posible respetando formaciones legales. Devuelve (puntos, ids, formación).

    Los huecos sin jugador se rellenan con un suplente virtual de nivel REPLACEMENT,
    para no exagerar lo que aporta un fichaje a un equipo con la plantilla corta.
    """
    by_role = {}
    for r in ROLES:
        lst = sorted((pl for pl in players if pl["role"] == r), key=lambda x: -x[key])
        lst += [{"id": None, key: REPLACEMENT}] * 5
        by_role[r] = lst
    if not by_role["portero"]:
        gk_pts, gk = 0.0, []
    else:
        gk_pts, gk = by_role["portero"][0][key], [by_role["portero"][0]["id"]]
    best = (-1.0, [], None)
    for d, c, f in FORMATIONS:
        picks, total = list(gk), gk_pts
        for role, n in (("defensa", d), ("centrocampista", c), ("delantero", f)):
            chosen = by_role[role][:n]
            total += sum(x[key] for x in chosen)
            picks += [x["id"] for x in chosen if x["id"]]
        if total > best[0]:
            best = (total, picks, f"{d}-{c}-{f}")
    return round(best[0], 2), best[1], best[2]


def xi_gain(squad, candidate, key="proj_next", drop_ids=()):
    """Cuántos puntos por jornada gana tu once si incorporas al candidato."""
    base, _, _ = best_xi(squad, key)
    new_squad = [p for p in squad if p["id"] not in drop_ids] + [candidate]
    new, _, _ = best_xi(new_squad, key)
    return round(new - base, 2)


def percentile(vals, q):
    vals = sorted(vals)
    if not vals:
        return None
    k = (len(vals) - 1) * q
    f, c = int(k), min(int(k) + 1, len(vals) - 1)
    return vals[f] + (vals[c] - vals[f]) * (k - f)


__all__ = ["ROLES", "num", "parse_dt", "clause_info", "player_metrics", "best_xi",
           "xi_gain", "percentile", "combinations"]
