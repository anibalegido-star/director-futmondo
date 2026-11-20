"""Proyección partido a partido (Fase 1 del plan Moneyball).

Puntos esperados de un jugador en una jornada =
    P(titular) · puntos como titular  +  P(entra desde el banquillo) · puntos como suplente
    × factor casa/fuera (de la liga, por posición)
    × factor rival (lo que conceden a su posición, suavizado)
    (la forma reciente del equipo se muestra como información: en la prueba no mejoraba)

Todo se calcula con los datos de Futmondo por jornada (st = titular, bc = entró,
b = banquillo sin jugar, nc = no convocado) y el calendario de LaLiga.
Las medias se suavizan hacia la media de su posición: una racha corta no se
toma al pie de la letra.
"""

from collections import defaultdict
from statistics import mean

UNAVAILABLE = {"injured", "injured2", "redcard"}
# Ajustado con la prueba sobre las jornadas 7-12 (ver README): últimas 4 jornadas,
# poco suavizado individual, factor rival sí, racha del equipo solo informativa.
RECENCY = [0.40, 0.30, 0.20, 0.10]   # pesos de las últimas jornadas, la más reciente primero
K_PLAYER = 1.0      # partidos "ficticios" de media de su posición que se mezclan con los suyos
K_OPP = 10.0        # suavizado del factor rival
FORM_DECAY = 0.9    # cada jornada de antigüedad pesa un 10% menos


def _wmean(pairs):
    tw = sum(w for _, w in pairs)
    return sum(v * w for v, w in pairs) / tw if tw else None


class LeagueModel:
    """Aprende de todas las jornadas de todos los jugadores de la liga."""

    def __init__(self, players, rounds_by_player, calendar, upto_round=None):
        """players: {id: {role, club}} · rounds_by_player: {id: [{round, points, home, st}]}"""
        self.cal = calendar
        self.players = players
        self.upto = upto_round
        self.rounds = {}
        for pid, rs in rounds_by_player.items():
            lst = [r for r in rs if r.get("round") and (upto_round is None or r["round"] < upto_round)]
            self.rounds[pid] = sorted(lst, key=lambda r: r["round"])
        self.last_round = max((r["round"] for rs in self.rounds.values() for r in rs), default=0)
        self._league_stats()

    # -------------------------------------------------------------- liga
    def _league_stats(self):
        st_pts = defaultdict(list)
        sub_pts = defaultdict(list)
        home_pts = defaultdict(lambda: {True: [], False: []})
        conceded = defaultdict(list)          # (rival, role) -> puntos de titulares contra él
        team_round = defaultdict(lambda: defaultdict(float))
        for pid, rs in self.rounds.items():
            info = self.players.get(pid)
            if not info:
                continue
            role, club = info["role"], info["club"]
            for r in rs:
                pts = r.get("points") or 0
                if r.get("st") == "st":
                    st_pts[role].append(pts)
                    home_pts[role][bool(r.get("home"))].append(pts)
                    team_round[club][r["round"]] += pts
                    if self.cal:
                        fx = self.cal.fixture(club, r["round"])
                        if fx:
                            conceded[(fx["rival"], role)].append(pts)
                elif r.get("st") == "bc":
                    sub_pts[role].append(pts)
        self.role_st = {k: mean(v) for k, v in st_pts.items() if v}
        self.role_sub = {k: mean(v) for k, v in sub_pts.items() if v}
        self.home_factor = {}
        for role, d in home_pts.items():
            if d[True] and d[False]:
                m = mean(d[True] + d[False])
                self.home_factor[role] = {True: mean(d[True]) / m, False: mean(d[False]) / m}
        self.opp_factor = {}
        for (rival, role), v in conceded.items():
            base = self.role_st.get(role)
            if base:
                n = len(v)
                raw = mean(v) / base
                f = (raw * n + 1.0 * K_OPP) / (n + K_OPP)
                self.opp_factor[(rival, role)] = max(0.75, min(1.25, f))
        self.team_form = {}
        for club, by_round in team_round.items():
            rs = sorted(by_round)
            if len(rs) >= 5:
                season = mean(by_round[x] for x in rs)
                recent = mean(by_round[x] for x in rs[-3:])
                ratio = recent / season if season else 1
                self.team_form[club] = max(0.92, min(1.08, 1 + 0.5 * (ratio - 1)))

    # -------------------------------------------------------------- jugador
    def player_base(self, pid, status=""):
        info = self.players.get(pid) or {}
        role = info.get("role")
        rs = self.rounds.get(pid, [])
        # jornadas que su equipo ha jugado (si falta la jornada, no estuvo)
        by_round = {r["round"]: r for r in rs}
        recent_rounds = list(range(self.last_round, max(0, self.last_round - len(RECENCY)), -1))
        start_w = sub_w = tw = 0.0
        for w, rnd in zip(RECENCY, recent_rounds):
            r = by_round.get(rnd)
            st = r.get("st") if r else "nc"
            tw += w
            if st == "st":
                start_w += w
            elif st == "bc":
                sub_w += w
        p_start = start_w / tw if tw else 0.0
        p_sub = sub_w / tw if tw else 0.0

        role_st = self.role_st.get(role, 4.0)
        role_sub = self.role_sub.get(role, 1.5)
        st_pairs = [(r.get("points") or 0, FORM_DECAY ** (self.last_round - r["round"]))
                    for r in rs if r.get("st") == "st"]
        sub_pairs = [(r.get("points") or 0, FORM_DECAY ** (self.last_round - r["round"]))
                     for r in rs if r.get("st") == "bc"]
        n_st = sum(w for _, w in st_pairs)
        n_sub = sum(w for _, w in sub_pairs)
        pts_st = ((_wmean(st_pairs) or 0) * n_st + role_st * K_PLAYER) / (n_st + K_PLAYER)
        pts_sub = ((_wmean(sub_pairs) or 0) * n_sub + role_sub * K_PLAYER) / (n_sub + K_PLAYER)

        notes = []
        last2 = [by_round.get(x) for x in recent_rounds[:2]]
        returning = all((not r) or r.get("st") == "nc" for r in last2) and p_start < 0.5 and \
            any(r.get("st") == "st" for r in rs[:-2])
        if status in UNAVAILABLE:
            avail = [0.0, 0.5, 0.8]
            notes.append("lesionado o sancionado")
        elif status == "doubt":
            avail = [0.55, 1.0, 1.0]
            notes.append("duda para la jornada")
        else:
            avail = [1.0, 1.0, 1.0]
        if returning and status not in UNAVAILABLE:
            avail = [a * f for a, f in zip(avail, [0.6, 0.85, 1.0])]
            notes.append("vuelve tras no jugar: minutos inciertos")
        return {"p_start": p_start, "p_sub": p_sub, "pts_st": pts_st, "pts_sub": pts_sub,
                "avail": avail, "notes": notes, "role": role, "club": info.get("club")}

    def project(self, pid, status="", rounds_ahead=3):
        """Proyección para las próximas jornadas: lista de {round, rival, casa, pts, motivo}."""
        b = self.player_base(pid, status)
        base = b["p_start"] * b["pts_st"] + b["p_sub"] * b["pts_sub"]
        out = []
        start = self.last_round + 1
        for i in range(rounds_ahead):
            rnd = start + i
            fx = self.cal.fixture(b["club"], rnd) if self.cal else None
            f_home = f_opp = 1.0
            if fx:
                f_home = self.home_factor.get(b["role"], {}).get(bool(fx["casa"]), 1.0)
                f_opp = self.opp_factor.get((fx["rival"], b["role"]), 1.0)
            # la racha del equipo empeoraba los aciertos en la prueba: se muestra, no se multiplica
            pts = base * f_home * f_opp * b["avail"][min(i, 2)]
            out.append({"round": rnd, "rival": fx["rival"] if fx else None,
                        "casa": fx["casa"] if fx else None, "fecha": fx["fecha"] if fx else None,
                        "pts": round(pts, 2), "f_rival": round(f_opp, 2), "f_casa": round(f_home, 2)})
        return {"next": out[0]["pts"] if out else round(base, 2),
                "avg3": round(mean(x["pts"] for x in out), 2) if out else round(base, 2),
                "partidos": out, "p_titular": round(b["p_start"], 2), "p_suplente": round(b["p_sub"], 2),
                "pts_titular": round(b["pts_st"], 2), "forma_equipo": round(self.team_form.get(b["club"], 1.0), 2),
                "notas": b["notes"]}

    def explain(self, proj, role):
        """Una línea legible del porqué de la proyección de la próxima jornada."""
        if not proj["partidos"]:
            return ""
        m = proj["partidos"][0]
        bits = [f"titular {round(proj['p_titular'] * 100)}%"]
        if m["rival"]:
            lugar = "en casa" if m["casa"] else "fuera"
            fr = m["f_rival"]
            dif = "rival asequible" if fr >= 1.06 else ("rival difícil" if fr <= 0.94 else "rival normal")
            bits.append(f"{lugar} vs {m['rival']} ({dif})")
        if proj["forma_equipo"] >= 1.04:
            bits.append("equipo en racha")
        elif proj["forma_equipo"] <= 0.96:
            bits.append("equipo a la baja")
        bits += proj["notas"]
        return " · ".join(bits)
