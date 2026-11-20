"""Radar de noticias por palabras clave (gratis, sin IA).

Para tus jugadores y tus objetivos de fichaje busca en Google Noticias (formato RSS,
pensado para lectores de noticias) los titulares de los últimos días y marca los que
mencionan al jugador junto a palabras de lesión, alta, convocatoria, sanción o mercado.

No cambia las proyecciones: avisa con el titular y el enlace para que lo leas tú.
Por palabras se equivoca a veces (avisos falsos, noticias que se escapan).
"""

import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import requests

FEED = "https://news.google.com/rss/search?q={q}&hl=es&gl=ES&ceid=ES:es"

KEYWORDS = {
    "baja": ["lesion", "lesionado", "baja", "molestias", "no entrena", "se retira", "retirarse", "rotura",
             "esguince", "rotura fibrilar", "operado", "quirofano", "descartado", "fuera de la convocatoria",
             "no viaja", "ko", "dolencia", "sobrecarga", "pierde el partido", "se pierde"],
    "duda": ["duda", "en el aire", "entre algodones", "trabajo especifico", "al margen", "infiltrado"],
    "alta": ["alta medica", "recibe el alta", "vuelve a entrenar", "se ejercita con el grupo", "recuperado",
             "reaparece", "vuelve a la convocatoria", "entra en la convocatoria", "ya entrena"],
    "sancion": ["sancion", "sancionado", "expulsado", "roja", "tarjeta roja", "ciclo de amarillas", "suspension"],
    "mercado": ["renovacion", "renueva", "salida", "traspaso", "cedido", "cesion", "oferta", "venta",
                "mercado de invierno", "enero"],
    "rotacion": ["rotaciones", "rotacion", "once probable", "alineacion probable", "suplente", "banquillo"],
}
LABEL = {"baja": "Posible baja", "duda": "Duda", "alta": "Vuelve", "sancion": "Sanción",
         "mercado": "Mercado", "rotacion": "Alineación"}
PRIORITY = ["baja", "sancion", "duda", "alta", "rotacion", "mercado"]


def _norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()


def parse_feed(xml_text):
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        src = it.find("source")
        source = src.text.strip() if src is not None and src.text else ""
        pub = it.findtext("pubDate")
        try:
            when = parsedate_to_datetime(pub) if pub else None
        except (TypeError, ValueError):
            when = None
        # Google añade " - Fuente" al final del título
        if source and title.endswith(" - " + source):
            title = title[: -len(source) - 3]
        items.append({"titulo": title, "enlace": link, "fuente": source,
                      "fecha": when.isoformat() if when else None,
                      "desc": re.sub(r"<[^>]+>", " ", it.findtext("description") or "")})
    return items


def classify(text):
    t = " " + _norm(text) + " "
    hits = [k for k in PRIORITY if any(" " + w + " " in t for w in KEYWORDS[k])]
    return hits


def search(player_name, club, days=4, session=None, timeout=15):
    q = f'"{player_name}" {club}'
    s = session or requests
    r = s.get(FEED.format(q=quote_plus(q)), timeout=timeout,
              headers={"User-Agent": "Mozilla/5.0 (DirectorDeportivo; lector RSS personal)"})
    r.raise_for_status()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    surname = _norm(player_name).split(" ")[-1]
    out = []
    for it in parse_feed(r.text):
        if it["fecha"] and datetime.fromisoformat(it["fecha"]) < cutoff:
            continue
        if surname not in _norm(it["titulo"]):       # el jugador tiene que salir en el titular
            continue
        kinds = classify(it["titulo"] + " " + it["desc"])
        if kinds:
            out.append({k: it[k] for k in ("titulo", "enlace", "fuente", "fecha")} |
                       {"tipo": kinds[0], "etiqueta": LABEL[kinds[0]]})
    return out[:3]


def radar(briefing, max_players=30, pause=1.0, log=print):
    """Avisos para tus jugadores y tus principales objetivos de fichaje."""
    targets = []
    seen = set()
    def add(p, motivo):
        if p and p.get("id") not in seen and p.get("club"):
            seen.add(p["id"])
            targets.append((p, motivo))
    for p in briefing.get("mi_once", []):
        add(p, "tu jugador")
    for p in [m for m in briefing.get("mercado", []) if m.get("veredicto") in ("PUJAR", "VIGILAR")][:8]:
        add(p, "objetivo de fichaje")
    for p in briefing.get("clausulazos", [])[:5]:
        add(p, "objetivo de cláusula")
    targets = targets[:max_players]
    session = requests.Session()
    avisos, fails = [], 0
    for p, motivo in targets:
        try:
            for n in search(p["name"], p["club"], session=session):
                avisos.append(n | {"jugador": p["name"], "jugador_id": p["id"], "motivo": motivo})
        except Exception:
            fails += 1
        time.sleep(pause)
    if fails:
        log(f"   ⚠ Radar de noticias: {fails} búsquedas fallaron")
    order = {k: i for i, k in enumerate(PRIORITY)}
    avisos.sort(key=lambda a: (a["motivo"] != "tu jugador", order.get(a["tipo"], 9), a["fecha"] or ""), reverse=False)
    return {"avisos": avisos, "buscados": len(targets), "fallos": fails,
            "fuente": "Google Noticias (titulares de los últimos 4 días)"}
