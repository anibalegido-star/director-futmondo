"""Motor del Director Deportivo.

Toma la última captura + el histórico y produce un "briefing": situación,
decisiones priorizadas, mercado, clausulazos, blindaje, ventas, rivales y
estrategia. Todo son recomendaciones: la decisión y la ejecución son tuyas.
"""

import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from .metrics import (ROLES, best_xi, num, parse_dt, percentile, player_metrics, xi_gain)

TOTAL_ROUNDS = 38
BANDS = [(0, 5e6, "<5M"), (5e6, 15e6, "5-15M"), (15e6, 40e6, "15-40M"), (40e6, 1e12, ">40M")]
# Valores del análisis de 54 pujas reales (PROYECTO_FUTMONDO.md) si aún no hay datos propios
DEFAULT_OVERBID = {"<5M": (0.20, 0.47), "5-15M": (0.12, 0.30), "15-40M": (0.08, 0.20), ">40M": (0.03, 0.06)}


def swap_info(squad, cand, key="proj"):
    """Ganancia del once y a quién desplazaría el candidato."""
    base, ids, _ = best_xi(squad, key)
    new, new_ids, _ = best_xi(squad + [cand], key)
    out_ids = set(ids) - set(new_ids)
    names = [p["name"] for p in squad if p["id"] in out_ids]
    return round(new - base, 2), names


def plan_operations(mine, cand, cost_M, min_players=15, max_sells=2, top=4):
    """Formas de pagar un fichaje: vender 0, 1 o 2 jugadores tuyos.

    Para cada opción: cuánto mejora el once DESPUÉS de vender y fichar, cuánto
    dinero liberas (a valor de mercado, aproximado) y cuánto te falta o sobra
    para pagarlo. La app elige según tu saldo.
    """
    from itertools import combinations
    # aquí un hueco vale 0: no hay suplente gratis al vender a alguien tuyo
    base, _, _ = best_xi(mine, "proj", repl=0.0)
    # los que no puntúan en tu liga se venden siempre primero: es dinero sin coste
    can_sell = lambda p: not p.get("vendible_desde")   # reglas de tu liga: días mínimos tras comprar
    dead = [p for p in mine if p.get("fuera_liga") and can_sell(p)]
    sellable = [p for p in mine if not p.get("fuera_liga") and can_sell(p)]
    plans = []
    for k in range(0, max_sells + 1):
        if len(mine) - k - len(dead) + 1 < min_players:
            break
        for combo in combinations(sellable, k):
            combo = tuple(dead) + combo
            ids = {p["id"] for p in combo}
            squad = [p for p in mine if p["id"] not in ids] + [cand]
            new, _, _ = best_xi(squad, "proj", repl=0.0)
            raised = round(sum(p["value"] for p in combo) / 1e6, 2)
            plans.append({
                "vende": [p["name"] for p in combo],
                "ingresa_M": raised,
                "necesitas_M": round(cost_M - raised, 2),   # saldo mínimo para hacerlo
                "mejora_neta": round(new - base, 2),
                "jugadores_tras": len(squad),
            })
    # quedarse con las mejores por cada nivel de dinero necesario
    plans.sort(key=lambda x: (-x["mejora_neta"], x["necesitas_M"]))
    out = []
    for pl in plans:
        if pl["mejora_neta"] <= 0:
            continue
        # descarta opciones dominadas: misma o peor mejora y necesitan más saldo
        if any(o["mejora_neta"] >= pl["mejora_neta"] and o["necesitas_M"] <= pl["necesitas_M"] for o in out):
            continue
        out.append(pl)
    best = max((o["mejora_neta"] for o in out), default=0)
    for o in out:   # vender a un buen jugador para fichar a otro a veces casi no compensa: se marca
        o["rentable"] = o["mejora_neta"] >= 0.4 * best
    out.sort(key=lambda x: x["necesitas_M"])
    return out[:top]


def checklist(p, cost_M, kind, league):
    """Comprobaciones antes de pagar. ok: True/False/None (no se sabe)."""
    items = []
    items.append({"txt": "Juega en tu competición", "ok": not p.get("alertas"),
                  "nota": "; ".join(p.get("alertas") or []) or None})
    st = p.get("starter_rate")
    pl5 = p.get("played_last5")
    playing = (st is not None and st >= 0.6) or (st is None and pl5 is not None and pl5 >= 4)
    items.append({"txt": "Juega de titular últimamente", "ok": bool(playing),
                  "nota": None if playing else "rota o no juega: su media engaña"})
    healthy = p.get("status") not in ("injured", "injured2", "redcard", "doubt")
    items.append({"txt": "Sin lesión ni sanción", "ok": healthy,
                  "nota": None if healthy else f"estado: {p.get('status')}"})
    v = p["value"] / 1e6 if p.get("value") else 0
    ratio = cost_M / v if v else None
    fair = ratio is not None and ratio <= 2
    items.append({"txt": "Precio razonable para su valor", "ok": fair,
                  "nota": None if fair else (f"pagas {ratio:.1f} veces su valor ({v:.2f}M)" if ratio else "sin valor de mercado")})
    tr = p.get("trend7")
    if tr is not None:
        items.append({"txt": "Su valor no se desploma", "ok": tr > -8,
                      "nota": None if tr > -8 else f"{tr}% en 7 días"})
    days = league.get("playerMoveInDays")
    if kind == "clausula" and days:
        items.append({"txt": "Llega a tu equipo a tiempo", "ok": None,
                      "nota": f"en tu liga los traspasos se hacen efectivos {days} día(s) después del pago"})
    return items


def band_of(v):
    for lo, hi, name in BANDS:
        if lo <= v < hi:
            return name
    return ">40M"


def M(v):
    return round(num(v) / 1e6, 2)


# ------------------------------------------------------------------ histórico

def _history(con, latest_sid):
    """Valor de cada jugador en capturas anteriores, para tendencias."""
    rows = con.execute("""
        SELECT s.captured_at, ps.player_id, ps.value, ps.clause_real, ps.owner
        FROM player_snap ps JOIN snapshots s ON s.id = ps.snapshot_id
        ORDER BY s.captured_at""").fetchall()
    hist = defaultdict(list)
    for ts, pid, value, creal, owner in rows:
        hist[pid].append((parse_dt(ts), num(value), num(creal), owner))
    return hist


def _trend(hist, pid, now, days):
    series = hist.get(pid) or []
    target = now - timedelta(days=days)
    past = [v for (ts, v, _, _) in series if ts and ts <= target + timedelta(days=1) and v > 0]
    cur = [v for (ts, v, _, _) in series if ts and ts > now - timedelta(days=1)]
    if not past or not cur:
        return None
    ref = past[-1]
    return round((cur[-1] - ref) / ref * 100, 1)


def _rounds(con):
    out = defaultdict(list)
    for pid, rnd, pts, home, starter, st in con.execute(
            "SELECT player_id, round, points, home, starter, st FROM rounds"):
        if not st:   # capturas antiguas sin el código: lo deducimos
            st = "st" if starter else ("bc" if pts else "nc")
        out[pid].append({"round": rnd, "points": pts, "home": home, "starter": starter, "st": st})
    return out


# -------------------------------------------------------------- pujas de la liga

def bid_intel(con, teams_by_id):
    """Cómo puja la liga: sobreprecio sobre el segundo postor y sobre el valor del jugador."""
    values = defaultdict(list)
    for ts, pid, v in con.execute("""SELECT s.captured_at, ps.player_id, ps.value FROM player_snap ps
                                      JOIN snapshots s ON s.id=ps.snapshot_id"""):
        values[pid].append((parse_dt(ts), num(v)))
    over2 = defaultdict(list)
    prem = defaultdict(list)
    managers = defaultdict(lambda: {"ganadas": 0, "pujas": 0, "gastado": 0.0, "sobreprecios": []})
    clausulazos = defaultdict(int)
    recent = []
    for row in con.execute("SELECT * FROM news ORDER BY created DESC"):
        price = num(row["price"])
        created = parse_dt(row["created"])
        bids = json.loads(row["bids_json"] or "[]")
        buyer = teams_by_id.get(row["buyer_id"], row["buyer"])
        if row["buyer_id"] and row["seller_id"]:
            clausulazos[buyer] += 1
        if row["buyer_id"]:
            managers[buyer]["ganadas"] += 1
            managers[buyer]["gastado"] += price
            recent.append({"fecha": row["created"][:10], "comprador": buyer,
                           "vendedor": teams_by_id.get(row["seller_id"], row["seller"]) if row["seller_id"] else "Mercado",
                           "jugador": row["player_name"], "precio_M": M(price),
                           "tipo": "cláusula/traspaso" if row["seller_id"] else "mercado"})
        for b in bids:
            u = (b.get("u") or {})
            managers[teams_by_id.get(u.get("_id"), u.get("name"))]["pujas"] += 1
        if row["buyer_id"] and bids:
            second = max(num(b.get("bid")) for b in bids)
            if second > 0 and price >= second:
                pct = price / second - 1
                over2[band_of(price)].append(pct)
                managers[buyer]["sobreprecios"].append(pct)
        if row["buyer_id"] and not row["seller_id"] and created:
            cand = [(abs((ts - created).total_seconds()), v) for ts, v in values.get(row["player_id"], [])
                    if ts and v > 0 and ts <= created and (created - ts).days <= 4]
            if cand:
                v = min(cand)[1]
                prem[band_of(v)].append(price / v - 1)
    bands = {}
    for _, _, name in BANDS:
        o, p = over2.get(name, []), prem.get(name, [])
        d_med, d_p75 = DEFAULT_OVERBID[name]
        w = len(p) / (len(p) + 6)
        med = (percentile(p, .5) if p else d_med) * w + d_med * (1 - w)
        p75 = (percentile(p, .75) if p else d_p75) * w + d_p75 * (1 - w)
        bands[name] = {
            "n_pujas": len(o),
            "sobre_2o_mediana": round(percentile(o, .5), 3) if len(o) >= 3 else None,
            "sobre_2o_p75": round(percentile(o, .75), 3) if len(o) >= 3 else None,
            "n_valor": len(p),
            "sobre_valor_mediana": round(med, 3),
            "sobre_valor_p75": round(p75, 3),
            "fuente": f"{len(p)} fichajes de tu liga + estimación inicial" if w < 0.6 else f"{len(p)} fichajes de tu liga",
        }
    mgr = []
    for name, d in managers.items():
        if not name:
            continue
        mgr.append({"equipo": name, "fichajes": d["ganadas"], "pujas_perdidas_vistas": d["pujas"],
                    "gastado_M": M(d["gastado"]), "clausulazos": clausulazos.get(name, 0),
                    "sobreprecio_mediano": round(statistics.median(d["sobreprecios"]), 3) if d["sobreprecios"] else None})
    mgr.sort(key=lambda x: -x["fichajes"])
    return {"tramos": bands, "managers": mgr, "recientes": recent[:40]}


# ------------------------------------------------------------------ motor

def build_briefing(con, snap, finanzas=None):
    now = parse_dt(snap["captured_at"]) or datetime.now(timezone.utc)
    latest_sid = con.execute("SELECT id FROM snapshots WHERE captured_at=?", (snap["captured_at"],)).fetchone()
    latest_sid = latest_sid[0] if latest_sid else None
    hist = _history(con, latest_sid)
    rounds = _rounds(con)
    summaries = snap.get("summaries") or {}
    teams = sorted(snap["teams"], key=lambda t: -num(t.get("points")))
    teams_by_id = {t["id"]: t["name"] for t in teams}
    my_id = snap.get("my_team_id")
    my_name = teams_by_id.get(my_id, "Mi equipo")
    finanzas = finanzas or {}
    fondos = num(finanzas.get("fondos")) or None
    max_puja = num(finanzas.get("puja_maxima")) or fondos

    season_rounds = max((int(num((p.get("average") or {}).get("matches")))
                         for ro in snap["rosters"].values() for p in ro), default=0) or None

    # ---- Fase 1: calendario + modelo partido a partido
    from .fixtures import Calendar, load as load_calendar
    from .model import LeagueModel
    raw_all = [p for ro in snap["rosters"].values() for p in ro] + list(snap.get("market") or [])
    cal_data = load_calendar(log=lambda *_: None)
    cal = Calendar(cal_data, {p.get("team") for p in raw_all}) if cal_data else None
    lm = None
    if cal:
        info = {p["id"]: {"role": p.get("role"), "club": p.get("team")} for p in raw_all
                if p.get("team") in cal.to_of}
        lm = LeagueModel(info, {pid: rounds.get(pid, []) for pid in info}, cal)

    def enrich(p, owner):
        m = player_metrics(p, summaries.get(p.get("id")), rounds.get(p.get("id")), season_rounds)
        if lm and p.get("id") in lm.players:
            pr = lm.project(p["id"], p.get("status") or "")
            m["proj_antiguo"] = m["proj"]
            m["proj"] = pr["avg3"]              # fichajes y fuerza: próximas 3 jornadas
            m["proj_next"] = pr["next"]         # alineación: próxima jornada
            m["partidos"] = pr["partidos"]
            m["p_titular"] = pr["p_titular"]
            m["forma_equipo"] = pr["forma_equipo"]
            m["explica"] = lm.explain(pr, p.get("role"))
        m["owner"] = owner
        m["owner_name"] = teams_by_id.get(owner, "Mercado" if owner == "market" else owner)
        m["trend7"] = _trend(hist, m["id"], now, 7)
        m["trend30"] = _trend(hist, m["id"], now, 30)
        m["rounds"] = [[r["round"], r["points"], 1 if r["starter"] else 0]
                       for r in sorted(rounds.get(m["id"], []), key=lambda r: r["round"])][-12:]
        return m

    squads = {tid: [enrich(p, tid) for p in ro] for tid, ro in snap["rosters"].items()}
    market = [enrich(p, "market") for p in snap.get("market") or []]
    slug_to = {t.get("slug"): t for t in teams if t.get("slug")}
    for p, raw in zip(market, snap.get("market") or []):
        p["asking"] = num(raw.get("price"))
        p["expires"] = raw.get("expirationDate")
        seller = None if raw.get("computer") else slug_to.get(raw.get("userTeamSlug"))
        p["seller"] = (seller["name"] if seller else raw.get("userTeam")) if not raw.get("computer") else None
        p["mine"] = bool(seller and seller["id"] == my_id)
    my_listed = [p for p in market if p.get("mine")]
    market = [p for p in market if not p.get("mine")]
    # ---- control de competición: descarta jugadores que no puntúan en esta liga
    # (caso Carles Pérez: único jugador de su club, valor mínimo y jornadas de otro calendario)
    everyone = [p for sq in squads.values() for p in sq] + market
    club_count = Counter(p["club"] for p in everyone)
    maxr = [max(r[0] for r in p["rounds"]) for p in everyone if p.get("rounds")]
    league_round = Counter(maxr).most_common(1)[0][0] if maxr else None
    for p in everyone:
        alerts = []
        if club_count[p["club"]] < 3:
            alerts.append(f"único jugador del {p['club']} en la liga: probablemente no juega en esta competición")
        if league_round and p.get("rounds") and max(r[0] for r in p["rounds"]) > league_round + 1:
            alerts.append("sus jornadas no coinciden con las de tu liga")
        if p["value"] <= 1_050_000 and p["avg"] >= 6 and p["avg5"] >= 6 and p["matches"] >= 5:
            alerts.append("valor mínimo con medias altas: dato anómalo")
        p["alertas"] = alerts
        # dos indicios fuertes = fuera de la competición: no puntúa para nadie
        p["fuera_liga"] = bool(len(alerts) >= 2 or (alerts and club_count[p["club"]] < 3))
        if p["fuera_liga"]:
            p["proj"] = p["proj_next"] = 0.0

    mine = squads.get(my_id, [])
    alineacion, parte = _lineup_and_report(con, lm, mine, my_id, snap["captured_at"])
    current_round = max((p["matches"] for sq in squads.values() for p in sq if not p["fuera_liga"]), default=0)
    remaining = max(TOTAL_ROUNDS - current_round, 1)

    # ---- fuerza proyectada de cada equipo (once ideal)
    strength = {}
    for tid, sq in squads.items():
        pts, ids, form = best_xi(sq, "proj")
        pts_next, _, _ = best_xi(sq, "proj_next")
        strength[tid] = {"xi": pts, "xi_proxima": pts_next, "ids": ids, "formacion": form}
    my_xi_pts, my_xi_ids, my_form = best_xi(mine, "proj") if mine else (0, [], None)
    my_xi_next, my_xi_next_ids, my_form_next = best_xi(mine, "proj_next") if mine else (0, [], None)

    # ---- situación en la tabla
    pos = next((i for i, t in enumerate(teams) if t["id"] == my_id), None)
    tabla = []
    for i, t in enumerate(teams):
        st = strength.get(t["id"], {})
        tabla.append({"pos": i + 1, "equipo": t["name"], "id": t["id"], "puntos": round(num(t["points"]), 1),
                      "valor_M": M(t.get("team_value")), "xi_proyectado": st.get("xi"),
                      "clausulazos_in": t.get("clauses_in"), "clausulazos_out": t.get("clauses_out"),
                      "es_mio": t["id"] == my_id})
    situacion = {"posicion": pos + 1 if pos is not None else None, "equipos": len(teams),
                 "jornada_aprox": current_round, "jornadas_restantes": remaining,
                 "mi_xi_proyectado": my_xi_pts, "mi_xi_proxima": my_xi_next, "formacion": my_form_next}
    if pos is not None:
        me = teams[pos]
        objetivos = []
        for j in range(max(0, pos - 3), pos):
            t = teams[j]
            gap = num(t["points"]) - num(me["points"])
            diff_xi = round(my_xi_pts - strength.get(t["id"], {}).get("xi", 0), 1)
            objetivos.append({"equipo": t["name"], "pos": j + 1, "gap": round(gap, 1),
                              "pts_extra_por_jornada": round(gap / remaining, 1),
                              "diferencia_xi": diff_xi,
                              "lo_alcanzas_a_este_ritmo": diff_xi > 0 and diff_xi * remaining > gap})
        situacion["objetivos"] = list(reversed(objetivos))
        lider = teams[0]
        situacion["gap_lider"] = round(num(lider["points"]) - num(me["points"]), 1)
        situacion["pts_extra_por_jornada_lider"] = round(situacion["gap_lider"] / remaining, 1)
        if pos + 1 < len(teams):
            t = teams[pos + 1]
            situacion["perseguidor"] = {"equipo": t["name"], "gap": round(num(me["points"]) - num(t["points"]), 1)}

    # ---- posiciones: mis once vs la media de los once de la liga
    league_role = defaultdict(list)
    for tid, sq in squads.items():
        ids = set(strength[tid]["ids"])
        for role in ROLES:
            vals = [p["proj"] for p in sq if p["id"] in ids and p["role"] == role]
            if vals and tid != my_id:
                league_role[role].append(sum(vals) / len(vals))
    my_role = {}
    for role in ROLES:
        vals = [p["proj"] for p in mine if p["id"] in set(my_xi_ids) and p["role"] == role]
        lg = statistics.mean(league_role[role]) if league_role[role] else 0
        mv = sum(vals) / len(vals) if vals else 0
        my_role[role] = {"mi_media_xi": round(mv, 2), "media_liga_xi": round(lg, 2),
                         "diferencia": round(mv - lg, 2), "jugadores": sum(1 for p in mine if p["role"] == role)}
    weakest = min(my_role, key=lambda r: my_role[r]["diferencia"]) if mine else None

    intel = bid_intel(con, teams_by_id)
    cfg = snap.get("config") or {}
    league = {"min_jugadores": int(num(cfg.get("numberOfPlayers"), 15)) or 15,
              "max_jugadores": int(num(cfg.get("maxPlayersInRoster"), 25)) or 25,
              "playerMoveInDays": cfg.get("playerMoveInDays"),
              "euros_por_punto": num(cfg.get("moneyPerPoint")) or None,
              "presupuesto_inicial": num(cfg.get("budget")) or None,
              "dias_para_vender": int(num(cfg.get("playerRetention"), 0)) or None,
              "duracion_pujas_dias": cfg.get("bidDuration"),
              "dias_activar_clausula": cfg.get("enablingClause"),
              "prima_ranking": num(cfg.get("moneyPerRanking")) or None,
              "posiciones_premiadas": cfg.get("usersToRank"),
              "ranking": cfg.get("rankingMode")}
    # 2. no se puede vender a quien compraste hace menos de N días
    hold = league["dias_para_vender"] or 0
    bought = {}
    for row in con.execute("SELECT player_id, created FROM news WHERE buyer_id=?", (my_id,)):
        d = parse_dt(row[1])
        if d and (row[0] not in bought or d > bought[row[0]]):
            bought[row[0]] = d
    for raw in snap["rosters"].get(my_id, []):
        c = raw.get("clause") if isinstance(raw.get("clause"), dict) else {}
        for k in ("transferDate", "date"):
            d = parse_dt(c.get(k))
            if d and (now - d).days < 7 and (raw["id"] not in bought or d > bought[raw["id"]]):
                bought[raw["id"]] = d
    for p in mine:
        d = bought.get(p["id"])
        free = d + timedelta(days=hold) if d and hold else None
        p["vendible_desde"] = free.isoformat() if free and free > now else None

    def bid_plan(p):
        b = intel["tramos"][band_of(p["value"])]
        # en tu liga se puede pujar por debajo del valor: el mínimo es el precio de salida
        floor = p["asking"] or p["value"]
        target = max(floor, p["value"] * (1 + b["sobre_valor_mediana"]))
        aggressive = max(target, p["value"] * (1 + b["sobre_valor_p75"]))
        return {"minimo_M": M(floor), "objetivo_M": M(target), "agresiva_M": M(aggressive),
                "base": b["fuente"]}

    # ---- mercado
    mercado = []
    for p in market:
        gain, desplaza = swap_info(mine, p)
        plan = bid_plan(p)
        cost = plan["objetivo_M"] or M(p["asking"])
        p_out = _public(p)
        p_out.update({"mejora_xi": gain, "mejora_por_M": round(gain / cost, 3) if cost else 0,
                      "precio_salida_M": M(p["asking"]), "puja": plan, "desplaza": desplaza,
                      "vendedor": p["seller"] or "Mercado (máquina)", "expira": p["expires"],
                      "asequible": (max_puja is None) or plan["objetivo_M"] * 1e6 <= max_puja})
        p_out["veredicto"] = _verdict_market(p_out, p)
        mercado.append(p_out)
    mercado.sort(key=lambda x: (-{"PUJAR": 2, "VIGILAR": 1, "PASAR": 0}[x["veredicto"]], -x["mejora_xi"]))
    by_id = {p["id"]: p for p in market}
    for item in mercado:
        if item["veredicto"] == "PASAR" and item["mejora_xi"] < 1:
            continue
        src = by_id[item["id"]]
        item["operaciones"] = plan_operations(mine, src, item["puja"]["objetivo_M"], league["min_jugadores"])
        item["antes_de_pagar"] = checklist(src, item["puja"]["objetivo_M"], "puja", league)
        item["calidad_precio"] = round(item["mejora_xi"] / max(item["puja"]["objetivo_M"], 0.5), 3)

    # ---- clausulazos sobre rivales
    clausulas = []
    bloqueados = []
    for tid, sq in squads.items():
        if tid == my_id:
            continue
        rival_pts = num(next((t["points"] for t in teams if t["id"] == tid), 0))
        star = max(sq, key=lambda x: x["points"]) if sq else None
        for p in sq:
            c = p["clause"]
            if not c["max"]:
                continue
            if c["locked_until"]:
                bloqueados.append({"jugador": p["name"], "equipo": p["owner_name"],
                                   "clausula_M": M(c["max"]), "libre_desde": c["locked_until"][:16],
                                   "id": p["id"], "role": p["role"], "club": p["club"]})
                continue
            if p.get("fuera_liga") or p.get("alertas"):
                continue
            if p["matches"] < 3 or p["status"] in ("injured", "injured2") or p["absent_streak"] >= 3:
                continue
            gain, desplaza = swap_info(mine, p)
            if gain <= 0.3:
                continue
            cost = (c["min"] + c["max"]) / 2
            dep = round(p["points"] / rival_pts * 100, 1) if rival_pts else 0
            above = pos is not None and 0 < teams.index(next(t for t in teams if t["id"] == tid)) < pos + 1 and \
                teams.index(next(t for t in teams if t["id"] == tid)) >= pos - 3
            item = _public(p)
            item.update({
                "equipo_rival": p["owner_name"], "clausula_min_M": M(c["min"]), "clausula_max_M": M(c["max"]),
                "clausula_exacta": c["exact"], "clausula_subida": c["raised"],
                "colchon_M": M(p["value"] - c["max"]),
                "mejora_xi": gain, "mejora_por_M": round(gain / (cost / 1e6), 3) if cost else 0,
                "desplaza": desplaza, "clausula_M": M(c["max"]),
                "dependencia_rival_pct": dep if star and star["id"] == p["id"] else None,
                "rival_directo": bool(above),
                "asequible": fondos is None or c["max"] <= fondos,
            })
            bonus = 1 + (0.3 if above else 0) + ((dep / 100) if item["dependencia_rival_pct"] else 0)
            item["score"] = round(item["mejora_por_M"] * bonus * 100, 2)
            clausulas.append(item)
    clausulas.sort(key=lambda x: -x["score"])
    every_by_id = {p["id"]: p for sq in squads.values() for p in sq}
    for item in clausulas[:15]:
        src = every_by_id[item["id"]]
        item["operaciones"] = plan_operations(mine, src, item["clausula_max_M"], league["min_jugadores"])
        item["antes_de_pagar"] = checklist(src, item["clausula_max_M"], "clausula", league)
        item["calidad_precio"] = round(item["mejora_xi"] / max(item["clausula_max_M"], 0.5), 3)

    # ---- blindaje de mi plantilla
    hunters = {t["id"]: (t.get("clauses_in") or 0) for t in teams if t["id"] != my_id}
    max_hunt = max(hunters.values(), default=1) or 1
    blindaje = []
    xi_ids = set(my_xi_ids)
    for p in mine:
        c = p["clause"]
        if not c["max"]:
            continue
        cm = max(c["max"] / 1e6, 0.5)
        best = (0.0, None, 0.0)
        for tid, sq in squads.items():
            if tid == my_id:
                continue
            g = xi_gain(sq, p, "proj")
            eff = g / cm
            weighted = eff * (0.5 + 0.5 * hunters.get(tid, 0) / max_hunt)
            if weighted > best[2]:
                best = (g, tid, weighted)
        in_xi = p["id"] in xi_ids
        loss = xi_gain([q for q in mine if q["id"] != p["id"]], p, "proj") if in_xi else 0
        item = _public(p)
        item.update({"clausula_M": M(c["max"]), "clausula_exacta": c["exact"], "valor_M": M(p["value"]),
                     "en_mi_once": in_xi, "perdida_si_me_lo_quitan": loss,
                     "interesado": teams_by_id.get(best[1]), "ganancia_interesado": round(best[0], 2),
                     "eficiencia_para_rival": round(best[0] / cm, 3), "riesgo": round(best[2], 3),
                     "bloqueado_hasta": c["locked_until"]})
        if c["locked_until"]:
            item["nivel"] = "PROTEGIDO"
        elif best[0] >= 1.0 and best[2] >= 0.25 and loss >= 1:
            item["nivel"] = "ALTO"
        elif best[0] >= 0.5 and best[2] >= 0.1 and in_xi:
            item["nivel"] = "MEDIO"
        elif loss >= 5 and best[2] >= 0.05:
            item["nivel"] = "MEDIO"  # pieza clave: aunque sea caro, vigílalo
        else:
            item["nivel"] = "BAJO"
        blindaje.append(item)
    blindaje.sort(key=lambda x: (-["BAJO", "PROTEGIDO", "MEDIO", "ALTO"].index(x["nivel"]), -x["riesgo"]))

    # ---- ventas / descartes
    ventas = []
    xi_set = set(my_xi_ids)
    once_jornada = {x["id"] for x in (alineacion or {}).get("once", [])}
    xi_set |= once_jornada  # si juega la próxima jornada, no se recomienda vender por "no entrar"
    for p in mine:
        reasons = []
        if p["id"] not in xi_set:
            reasons.append("no entra en tu once (ni esta jornada ni en las 3 próximas)")
        if p["trend7"] is not None and p["trend7"] < -5:
            reasons.append(f"su valor cae un {abs(p['trend7'])}% en 7 días")
        if p["form_delta"] <= -1.5:
            reasons.append(f"forma a la baja ({p['avg5']} últimos 5 vs {p['avg']} de media)")
        if p["starter_rate"] is not None and p["starter_rate"] < 0.4:
            reasons.append("pierde la titularidad")
        elif p["played_last5"] is not None and p["played_last5"] <= 2 and p["matches"] < (season_rounds or 0) * 0.6:
            reasons.append(f"apenas juega ({p['played_last5']} de las últimas 5 jornadas, {p['matches']} partidos en total)")
        if p["status"] in ("injured", "injured2"):
            reasons.append("lesionado")
        if not reasons or (p["id"] in xi_set and len(reasons) < 2):
            continue
        item = _public(p)
        item.update({"motivos": reasons, "valor_M": M(p["value"]),
                     "accion": "VENDER" if p["id"] not in xi_set and p["value"] >= 2e6 else "VIGILAR"})
        ventas.append(item)
    ventas.sort(key=lambda x: (x["accion"] != "VENDER", -x["valor_M"]))

    # ---- rivales
    rivales = []
    mgr_by = {m["equipo"]: m for m in intel["managers"]}
    for i, t in enumerate(teams):
        if t["id"] == my_id:
            continue
        sq = squads.get(t["id"], [])
        if not sq:
            continue
        star = max(sq, key=lambda x: x["points"])
        sin_estrella = round(strength[t["id"]]["xi"] - best_xi([p for p in sq if p["id"] != star["id"]], "proj")[0], 1)
        dep = round(star["points"] / num(t["points"]) * 100, 1) if num(t["points"]) else 0
        roles = {r: [p["proj"] for p in sq if p["id"] in set(strength[t["id"]]["ids"]) and p["role"] == r] for r in ROLES}
        weak = min((r for r in ROLES if roles[r]), key=lambda r: sum(roles[r]) / len(roles[r]), default=None)
        injured = [p["name"] for p in sq if p["status"] in ("injured", "injured2") and p["id"] in set(strength[t["id"]]["ids"])]
        m = mgr_by.get(t["name"], {})
        rivales.append({
            "pos": i + 1, "equipo": t["name"], "puntos": round(num(t["points"]), 1),
            "gap_conmigo": round(num(t["points"]) - num(teams[pos]["points"]), 1) if pos is not None else None,
            "valor_M": M(t.get("team_value")), "xi_proyectado": strength[t["id"]]["xi"],
            "estrella": star["name"], "dependencia_pct": dep, "posicion_debil": weak,
            "lesionados_en_once": injured, "clausulazos_hechos": t.get("clauses_in"),
            "clausulazos_sufridos": t.get("clauses_out"), "fichajes_vistos": m.get("fichajes"),
            "sobreprecio_mediano": m.get("sobreprecio_mediano"),
            "perfil": _profile(t, m, dep), "sin_estrella": sin_estrella,
        })

    # ---- traspasos en curso: la API marca la cláusula pagada (transferred) y el cambio
    # de equipo se hace a medianoche (transferDate). No dice quién la pagó.
    pendientes = list(bloqueados)
    for p in mine:
        if p["clause"]["locked_until"]:
            pendientes.append({"jugador": p["name"], "equipo": my_name, "clausula_M": M(p["clause"]["max"]),
                               "libre_desde": p["clause"]["locked_until"][:16], "id": p["id"],
                               "role": p["role"], "club": p["club"], "mio": True})

    # ---- decisiones priorizadas
    decisiones = _decisions(mercado, clausulas, blindaje, ventas, mine, my_xi_next_ids, fondos, situacion)
    for p in mine:
        if p.get("fuera_liga"):
            decisiones.insert(0, {"tipo": "ALERTA", "prioridad": 98,
                                  "titulo": f"{p['name']} no puntúa en tu liga",
                                  "detalle": "Según los datos, " + "; ".join(p["alertas"]) + ". No cuenta para tu once: véndelo"
                                             + (f" (tu liga no te deja hasta el {_local_day(p['vendible_desde'])})" if p.get("vendible_desde") else "")
                                             + " o reclama a Futmondo.",
                                  "jugador_id": p["id"]})
    for t in pendientes:
        if t.get("mio"):
            decisiones.insert(0, {"tipo": "ALERTA", "prioridad": 99,
                                  "titulo": f"Te han pagado la cláusula de {t['jugador']}",
                                  "detalle": f"Se va de tu equipo a las 00:00 por {t['clausula_M']}M. Busca sustituto.",
                                  "jugador_id": t["id"]})

    return {
        "generado": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "liga": league,
        "alineacion": alineacion, "parte_jornada": parte,
        "modelo": {"activo": bool(lm), "ultima_jornada": lm.last_round if lm else None},
        "captura": snap["captured_at"],
        "mi_equipo": my_name,
        "finanzas": {"fondos_M": M(fondos) if fondos else None,
                     "puja_maxima_M": M(max_puja) if max_puja else None,
                     "fuente": "finanzas.json" if fondos else "sin datos (rellena finanzas.json)"},
        "situacion": situacion, "tabla": tabla, "posiciones": my_role, "posicion_debil": weakest,
        "mi_once": [_public(p) | {"en_once": p["id"] in set(my_xi_next_ids)} for p in
                    sorted(mine, key=lambda x: (ROLES.index(x["role"]) if x["role"] in ROLES else 9, -x["proj"]))],
        "decisiones": decisiones, "mercado": mercado,
        "mis_jugadores_en_venta": [_public(p) | {"precio_salida_M": M(p["asking"]), "expira": p["expires"]}
                                   for p in my_listed] + [
            {"id": x.get("id"), "name": x.get("name"), "role": x.get("role"), "club": x.get("team"),
             "value_M": M(x.get("value")), "precio_salida_M": M(x.get("price")), "expira": x.get("expirationDate"),
             "pujas": len(x.get("bids") or [])}
            for x in (snap.get("my_market") or []) if x.get("id") not in {q["id"] for q in my_listed}], "clausulazos": clausulas[:30],
        "bloqueados": bloqueados, "traspasos_pendientes": pendientes, "blindaje": blindaje, "ventas": ventas, "rivales": rivales,
        "pujas_liga": intel, "historico": {"capturas": con.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0],
                                           "desde": con.execute("SELECT MIN(captured_at) FROM snapshots").fetchone()[0]},
        "errores_captura": snap.get("errors") or [],
    }


def _lineup_and_report(con, lm, mine, my_id, captured_at):
    """Alineación de la próxima jornada + registro de proyecciones + parte de la anterior."""
    from .metrics import best_lineup
    if not lm or not mine:
        return None, None
    nxt = lm.last_round + 1
    pts, form, picks = best_lineup(mine, "proj_next")
    once_ids = [p["id"] for p, _ in picks]
    once = []
    for p, used in picks:
        once.append({"id": p["id"], "name": p["name"], "role": p["_orig"], "juega_de": used,
                     "proj_next": p.get("proj_next"), "p_titular": p.get("p_titular"),
                     "explica": p.get("explica"), "status": p.get("status"),
                     "partido": (p.get("partidos") or [None])[0]})
    banquillo = [{"id": p["id"], "name": p["name"], "role": p["role"], "proj_next": p.get("proj_next"),
                  "explica": p.get("explica")}
                 for p in sorted(mine, key=lambda x: -(x.get("proj_next") or 0)) if p["id"] not in once_ids]
    dudas = [o for o in once if o["status"] == "doubt" or (o["p_titular"] is not None and o["p_titular"] < 0.6)]
    # registro (se sobrescribe hasta que empieza la jornada)
    for p in mine:
        if p.get("proj_next") is not None:
            con.execute("INSERT OR REPLACE INTO projections VALUES (?,?,?,?)",
                        (nxt, p["id"], p["proj_next"], captured_at))
    con.execute("INSERT OR REPLACE INTO lineups VALUES (?,?,?,?,?)",
                (nxt, my_id, json.dumps(once_ids), pts, captured_at))
    con.commit()
    alineacion = {"jornada": nxt, "formacion": form, "pts": pts, "once": once,
                  "banquillo": banquillo, "dudas": dudas}
    # parte de la última jornada jugada, si la proyectamos
    last = lm.last_round
    row = con.execute("SELECT player_ids, proj_total FROM lineups WHERE round=? AND team_id=?",
                      (last, my_id)).fetchone()
    parte = None
    if row:
        ids = json.loads(row[0])
        actual = {pid: (r.get("points") or 0) for pid, rs in lm.rounds.items() for r in rs
                  if r["round"] == last}
        got = round(sum(actual.get(i, 0) for i in ids), 1)
        best_cand = [dict(p, proj_next=actual.get(p["id"], 0)) for p in mine]
        best_pts, _, _ = best_lineup(best_cand, "proj_next")
        projs = con.execute("SELECT player_id, proj FROM projections WHERE round=?", (last,)).fetchall()
        errs = [abs(pr - actual[pid]) for pid, pr in projs if pid in actual]
        parte = {"jornada": last, "proyectado": row[1], "real": got, "optimo": best_pts,
                 "error_medio": round(sum(errs) / len(errs), 2) if errs else None}
    return alineacion, parte


def _public(p):
    keys = ("id", "name", "role", "role2", "club", "status", "points", "avg", "avg5", "matches",
            "participation", "played_last5", "absent_streak", "alertas", "fuera_liga", "vendible_desde",
            "partidos", "p_titular", "explica", "forma_equipo", "proj_antiguo",
            "form_delta", "regularity", "starter_rate", "proj", "proj_next", "trend7", "trend30",
            "owner_name")
    out = {k: p.get(k) for k in keys}
    out["value_M"] = M(p["value"])
    out["change_M"] = round(num(p.get("change")) / 1e6, 3)
    out["change_pct"] = round(num(p.get("change")) / (num(p["value"]) - num(p.get("change"))) * 100, 1) \
        if num(p["value"]) - num(p.get("change")) > 0 else None
    out["fitness"] = p.get("fitness")
    out["rounds"] = p.get("rounds") or []
    return out


def _verdict_market(item, p):
    if p.get("fuera_liga") or p.get("alertas"):
        return "PASAR"
    if p["status"] in ("injured", "injured2") or p["matches"] < 2 or p["absent_streak"] >= 3:
        return "PASAR"
    if p["absent_streak"] >= 2 or p["status"] == "doubt":
        return "VIGILAR" if item["mejora_xi"] >= 0.4 else "PASAR"
    if item["mejora_xi"] >= 1.0 and item["asequible"]:
        return "PUJAR"
    if item["mejora_xi"] >= 0.4 or (p["trend7"] or 0) > 8:
        return "VIGILAR"
    return "PASAR"


def _profile(t, m, dep):
    tags = []
    if (t.get("clauses_in") or 0) >= 60:
        tags.append("cazador de cláusulas")
    if (m.get("sobreprecio_mediano") or 0) >= 0.15:
        tags.append("puja agresivo")
    if dep >= 15:
        tags.append("depende de su estrella")
    if (t.get("clauses_out") or 0) >= 60:
        tags.append("le quitan muchos jugadores")
    return tags or ["perfil discreto"]


def _decisions(mercado, clausulas, blindaje, ventas, mine, xi_next_ids, fondos, situacion):
    out = []
    for p in [x for x in mercado if x["veredicto"] == "PUJAR"][:3]:
        out.append({"tipo": "PUJAR", "prioridad": round(60 + p["mejora_xi"] * 10, 1),
                    "titulo": f"Pujar por {p['name']} ({p['role']}, {p['club']})",
                    "detalle": (f"Mejora tu once en +{p['mejora_xi']} pts/jornada. Puja objetivo "
                                f"{p['puja']['objetivo_M']}M (mínimo {p['puja']['minimo_M']}M, agresiva "
                                f"{p['puja']['agresiva_M']}M)."),
                    "expira": p["expira"], "jugador_id": p["id"]})
    for p in [x for x in clausulas if x["asequible"] and x["mejora_xi"] >= 1.0][:3]:
        rango = (f"{p['clausula_max_M']}M" if p["clausula_exacta"]
                 else f"{p['clausula_max_M']}M (probable, confirma en la app)" if p["clausula_min_M"] == p["clausula_max_M"]
                 else f"{p['clausula_min_M']}-{p['clausula_max_M']}M (confirma en la app)")
        extra = " Es de un rival directo." if p["rival_directo"] else ""
        if p.get("dependencia_rival_pct"):
            extra += f" Es su estrella ({p['dependencia_rival_pct']}% de sus puntos)."
        out.append({"tipo": "CLAUSULAZO", "prioridad": round(50 + p["score"] / 2, 1),
                    "titulo": f"Clausulazo a {p['name']} ({p['equipo_rival']})",
                    "detalle": f"Cláusula {rango}. +{p['mejora_xi']} pts/jornada en tu once.{extra}",
                    "jugador_id": p["id"]})
    # no tiene sentido gastar en blindar a quien casi no juega
    for p in [x for x in blindaje if x["nivel"] == "ALTO" and (x.get("played_last5") is None or x["played_last5"] >= 3)][:3]:
        out.append({"tipo": "BLINDAR", "prioridad": round(55 + p["perdida_si_me_lo_quitan"] * 8, 1),
                    "titulo": f"Subir la cláusula de {p['name']}",
                    "detalle": (f"Cláusula de solo {p['clausula_M']}M. A {p['interesado']} le subiría su once "
                                f"+{p['ganancia_interesado']} pts/jornada y perderlo te costaría "
                                f"{p['perdida_si_me_lo_quitan']} pts/jornada."),
                    "jugador_id": p["id"]})
    for p in [x for x in ventas if x["accion"] == "VENDER"][:2]:
        out.append({"tipo": "VENDER", "prioridad": 35 + min(p["valor_M"], 30) / 2,
                    "titulo": f"Vender a {p['name']} ({p['valor_M']}M)",
                    "detalle": "; ".join(p["motivos"]).capitalize() + ". Libera dinero para reforzar el once.",
                    "jugador_id": p["id"]})
    for p in mine:
        if p["status"] in ("injured", "injured2", "redcard", "doubt") and p["proj"] >= 6:
            out.append({"tipo": "ALINEACIÓN", "prioridad": 45 if p["status"] != "doubt" else 30,
                        "titulo": f"{p['name']}: {_status_es(p['status'])}",
                        "detalle": "Revisa la alineación de la próxima jornada.", "jugador_id": p["id"]})
    if not fondos:
        out.append({"tipo": "DATOS", "prioridad": 20, "titulo": "Introduce tus fondos en finanzas.json",
                    "detalle": "La API no da tu saldo; sin él no puedo filtrar qué pujas y cláusulas te puedes permitir."})
    out.sort(key=lambda d: -d["prioridad"])
    return out


def _local_day(iso):
    d = parse_dt(iso)
    try:
        from zoneinfo import ZoneInfo
        d = d.astimezone(ZoneInfo("Europe/Madrid"))
    except Exception:
        d = d + timedelta(hours=1)
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    return f"{dias[d.weekday()]} {d.day}/{d.month} a las {d:%H:%M}"


def _status_es(s):
    return {"injured": "lesionado", "injured2": "lesionado", "redcard": "sancionado",
            "doubt": "duda", "yellowcard": "apercibido"}.get(s, s)
