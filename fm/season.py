"""Simulación del final de temporada.

Cada equipo suma, en las jornadas que quedan, un número de puntos aleatorio alrededor de su
ritmo esperado. El ritmo mezcla lo que lleva haciendo toda la temporada (puntos por jornada)
con la fuerza de su once actual, porque las plantillas cambian. La suma de muchas jornadas
independientes es aproximadamente normal, así que basta un sorteo por equipo y simulación.
"""
import math
import random

SD_JORNADA = 13.0   # desviación típica de los puntos de un equipo en una jornada (medida en tu liga)
PESO_RITMO = 0.5    # cuánto pesa lo hecho en la temporada frente al once actual
N_SIM = 20000
# Los fichajes que elegimos son los que mejor proyectan, y por eso suelen rendir algo menos de lo
# proyectado (sesgo de selección). Contamos solo el 60% de la mejora al estimar su efecto.
ENCOGIMIENTO = 0.6


def ritmo_por_equipo(teams, strength, jugadas):
    """Puntos esperados por jornada de cada equipo y el factor que traduce once ideal a puntos reales."""
    jugadas = max(jugadas, 1)
    pace = {t["id"]: (t.get("points") or 0) / jugadas for t in teams}
    xi = {t["id"]: (strength.get(t["id"]) or {}).get("xi") or 0 for t in teams}
    mx = sum(xi.values()) / len(xi) if xi else 0
    k = (sum(pace.values()) / len(pace)) / mx if mx else 1.0
    ritmo = {tid: PESO_RITMO * pace[tid] + (1 - PESO_RITMO) * xi[tid] * k for tid in pace}
    return ritmo, k


def simular(teams, ritmo, restantes, seed=7, n=N_SIM):
    """Devuelve los sorteos normalizados (para reutilizarlos al probar operaciones)."""
    rng = random.Random(seed)
    ids = [t["id"] for t in teams]
    draws = [[rng.gauss(0, 1) for _ in ids] for _ in range(n)]
    return {"ids": ids, "draws": draws, "restantes": restantes,
            "base": {t["id"]: t.get("points") or 0 for t in teams}, "ritmo": dict(ritmo)}


def posiciones(sim, my_id, extra_por_jornada=0.0):
    """Distribución de la posición final de my_id si su ritmo cambia en extra_por_jornada."""
    ids, R = sim["ids"], sim["restantes"]
    sd = SD_JORNADA * math.sqrt(R)
    mean = {t: sim["base"][t] + R * sim["ritmo"][t] for t in ids}
    mean[my_id] += R * extra_por_jornada
    me = ids.index(my_id)
    cuenta = [0] * len(ids)
    finales_mios = []
    for d in sim["draws"]:
        tot = [mean[t] + sd * z for t, z in zip(ids, d)]
        mine = tot[me]
        pos = 1 + sum(1 for j, v in enumerate(tot) if j != me and v > mine)
        cuenta[pos - 1] += 1
        finales_mios.append(mine)
    n = len(sim["draws"])
    dist = [c / n for c in cuenta]
    esperado = sum((i + 1) * p for i, p in enumerate(dist))
    finales_mios.sort()
    return {"dist": [round(p, 4) for p in dist], "esperada": round(esperado, 2),
            "puntos_finales": {"p10": round(finales_mios[int(n * .1)]), "p50": round(finales_mios[n // 2]),
                               "p90": round(finales_mios[int(n * .9)])}}


def resumen(teams, strength, jugadas, restantes, my_id, premiados=5):
    if not teams or my_id not in {t["id"] for t in teams} or restantes <= 0:
        return None
    ritmo, k = ritmo_por_equipo(teams, strength, jugadas)
    sim = simular(teams, ritmo, restantes)
    base = posiciones(sim, my_id)
    n = len(teams)
    actual = 1 + [t["id"] for t in teams].index(my_id)
    dist = base["dist"]
    # ¿cuántos puntos por jornada hacen falta para ganar un puesto de media?
    sens = []
    for extra in (2, 4, 6, 8):
        r = posiciones(sim, my_id, extra)
        sens.append({"extra": extra, "esperada": r["esperada"]})
    tabla = sorted(({"id": t["id"], "equipo": t["name"], "ritmo": round(ritmo[t["id"]], 1),
                     "final_esperado": round((t.get("points") or 0) + restantes * ritmo[t["id"]])}
                    for t in teams), key=lambda x: -x["final_esperado"])
    return {
        "_sim": sim, "factor_once": round(k, 3), "jornadas_restantes": restantes,
        "posicion_actual": actual, "posicion_esperada": base["esperada"], "distribucion": dist,
        "prob_subir": round(sum(dist[:actual - 1]), 3),
        "prob_bajar": round(sum(dist[actual:]), 3),
        "prob_top3": round(sum(dist[:3]), 3),
        "prob_ultimos": round(sum(dist[n - premiados:]), 3) if premiados else None,
        "puntos_finales": base["puntos_finales"], "mi_ritmo": round(ritmo[my_id], 1),
        "sensibilidad": sens, "tabla_final": tabla,
    }


def efecto(res, my_id, mejora_xi):
    """Cambio de posición esperada si tu once ideal mejora mejora_xi puntos por jornada."""
    if not res or not mejora_xi:
        return None
    extra = mejora_xi * res["factor_once"] * ENCOGIMIENTO
    r = posiciones(res["_sim"], my_id, extra)
    return round(r["esperada"] - res["posicion_esperada"], 2)
