"""El "parte del Director Deportivo": un resumen escrito de la situación.

Si hay ANTHROPIC_API_KEY en el .env, lo redacta Claude a partir del briefing
(cuesta céntimos por informe). Si no, se genera un parte por reglas con los
mismos datos. En ambos casos el agente solo recomienda: no puja, no paga
cláusulas ni toca tu cuenta.
"""

import json

import requests

from .config import anthropic_key, anthropic_model

SYSTEM = """Eres el Director Deportivo de un equipo de Futmondo (fantasy de LaLiga), trabajando para su manager.
Recibes un briefing en JSON calculado por un motor de análisis. Escribe en español de España un parte
breve y directo (máximo 250 palabras) para que el manager decida rápido:
1. Situación en una frase (posición, a quién puede alcanzar y qué ritmo necesita).
2. Las 3 decisiones más importantes de hoy, con cifras concretas (pujas, cláusulas, riesgos) y el porqué.
3. Una idea de estrategia a medio plazo (posición débil, perfil de rivales, ventas).
Reglas: usa solo los datos del briefing, no inventes lesiones ni noticias. Si una cláusula no es exacta,
dilo y pide confirmarla en la app. Recuerda que los precios caducan en horas. No uses tablas."""


def _compact(b):
    keep = {
        "mi_equipo": b["mi_equipo"], "situacion": b["situacion"], "finanzas": b["finanzas"],
        "posiciones": b["posiciones"], "posicion_debil": b["posicion_debil"],
        "decisiones": b["decisiones"][:8],
        "mercado_top": [{k: m[k] for k in ("name", "role", "club", "value_M", "mejora_xi", "puja", "veredicto", "expira")}
                        for m in b["mercado"][:6]],
        "clausulazos_top": [{k: c[k] for k in ("name", "equipo_rival", "clausula_min_M", "clausula_max_M",
                                               "clausula_exacta", "mejora_xi", "rival_directo")}
                            for c in b["clausulazos"][:5]],
        "riesgos_blindaje": [{k: x[k] for k in ("name", "nivel", "clausula_M", "interesado", "perdida_si_me_lo_quitan")}
                             for x in b["blindaje"] if x["nivel"] in ("ALTO", "MEDIO")],
        "ventas": [{k: v[k] for k in ("name", "accion", "motivos", "valor_M")} for v in b["ventas"][:4]],
        "rivales": [{k: r[k] for k in ("pos", "equipo", "gap_conmigo", "xi_proyectado", "perfil", "posicion_debil")}
                    for r in b["rivales"]],
    }
    return json.dumps(keep, ensure_ascii=False)


def claude_memo(briefing, timeout=60):
    key = anthropic_key()
    if not key:
        return None
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": anthropic_model(), "max_tokens": 900, "system": SYSTEM,
              "messages": [{"role": "user", "content": "Briefing de hoy:\n" + _compact(briefing)}]},
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    return "".join(part.get("text", "") for part in data.get("content", []) if part.get("type") == "text").strip()


def rules_memo(b):
    s = b["situacion"]
    lines = []
    head = f"Vas {s.get('posicion')}º de {s.get('equipos')} tras unas {s.get('jornada_aprox')} jornadas."
    objs = s.get("objetivos") or []
    if objs:
        o = objs[0]
        head += (f" {o['equipo']} está a {o['gap']} pts: necesitas {o['pts_extra_por_jornada']} pts más por jornada "
                 f"durante las {s['jornadas_restantes']} que quedan.")
        if o["diferencia_xi"] > 0:
            head += f" Tu once proyecta {o['diferencia_xi']} pts/jornada más que el suyo, así que es alcanzable."
        else:
            head += f" Hoy tu once proyecta {abs(o['diferencia_xi'])} pts/jornada menos: necesitas reforzarte."
    if s.get("perseguidor"):
        head += f" Por detrás, {s['perseguidor']['equipo']} a {s['perseguidor']['gap']} pts."
    lines.append(head)
    top = [d for d in b["decisiones"] if d["tipo"] != "DATOS"][:3]
    if top:
        lines.append("Prioridades de hoy:")
        for i, d in enumerate(top, 1):
            lines.append(f"{i}. {d['titulo']}. {d['detalle']}")
    weak = b.get("posicion_debil")
    if weak:
        p = b["posiciones"][weak]
        lines.append(f"A medio plazo: tu punto débil es {weak} ({p['mi_media_xi']} pts/jornada de media en tu once "
                     f"frente a {p['media_liga_xi']} en la liga). Ahí es donde cada millón rinde más.")
    hunters = [r for r in b["rivales"] if "cazador de cláusulas" in r["perfil"]]
    if hunters:
        lines.append("Ojo con " + ", ".join(r["equipo"] for r in hunters[:3]) +
                     ": viven de pagar cláusulas, así que tus jugadores con cláusula baja son su objetivo.")
    lines.append("Los precios cambian varias veces al día: confirma cada cifra en la app antes de pujar o pagar.")
    return "\n".join(lines)


def memo(briefing, log=print):
    try:
        text = claude_memo(briefing)
        if text:
            return {"texto": text, "autor": f"Claude ({anthropic_model()})"}
    except Exception as e:
        log(f"   ⚠ No se pudo generar el parte con Claude ({e}); uso el parte automático.")
    return {"texto": rules_memo(briefing), "autor": "reglas del motor (sin IA)"}
