"""Director Deportivo de Futmondo: descarga, analiza y genera el panel.

Uso:
    python run.py                      captura nueva + análisis + panel
    python run.py --offline            sin descargar: usa la última captura guardada
    python run.py --rapido             sin fichas de jugador (más rápido, cláusulas estimadas)
    python run.py --fondos 40.5 --puja-max 44.6     guarda tu saldo (en millones) y sale
"""

import argparse
import json
import sys
import webbrowser
from pathlib import Path

# Evita el fallo de octubre: la consola de Windows no sabía imprimir emojis.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fm.collect import canonical_from_informe, collect_live
from fm.config import BRIEFING_JSON, FINANZAS, OUTPUT_HTML, RAW, ROOT
from fm.db import connect, save_snapshot
from fm.engine import build_briefing
from fm.importer import bootstrap
from fm.narrative import memo
from fm.ui import build_html


def load_finanzas():
    if FINANZAS.exists():
        try:
            d = json.loads(FINANZAS.read_text(encoding="utf-8"))
            return {"fondos": (d.get("fondos_millones") or 0) * 1e6 or None,
                    "puja_maxima": (d.get("puja_maxima_millones") or 0) * 1e6 or None}
        except Exception as e:
            print(f"⚠ finanzas.json no se pudo leer: {e}")
    return {}


def latest_offline_snapshot():
    raws = sorted(RAW.glob("captura_*.json"))
    if raws:
        return json.loads(raws[-1].read_text(encoding="utf-8")), raws[-1].name
    informe = ROOT.parent / "informe_futmondo.json"
    if informe.exists():
        return canonical_from_informe(json.loads(informe.read_text(encoding="utf-8"))), informe.name
    return None, None


def main():
    ap = argparse.ArgumentParser(description="Director Deportivo de Futmondo")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--rapido", action="store_true")
    ap.add_argument("--abrir", action="store_true", help="abre el panel al terminar")
    ap.add_argument("--exportar", metavar="RUTA", help="escribe el análisis cifrado para la app móvil (usa $DIRECTOR_KEY)")
    ap.add_argument("--sin-panel", action="store_true", help="no genera panel_director.html")
    ap.add_argument("--fondos", type=float, help="tu saldo disponible, en millones")
    ap.add_argument("--puja-max", type=float, help="puja máxima que te permite la app, en millones")
    a = ap.parse_args()

    if a.fondos is not None or a.puja_max is not None:
        d = json.loads(FINANZAS.read_text(encoding="utf-8")) if FINANZAS.exists() else {}
        if a.fondos is not None:
            d["fondos_millones"] = a.fondos
        if a.puja_max is not None:
            d["puja_maxima_millones"] = a.puja_max
        FINANZAS.write_text(json.dumps(d, indent=2), encoding="utf-8")
        print(f"Guardado en finanzas.json: {d}")
        return 0

    con = connect()
    if con.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0] == 0:
        print("Primera ejecución: importando el histórico que ya tenías...")
        bootstrap(con, ROOT.parent)

    snap, origin, warning = None, None, None
    if not a.offline:
        try:
            snap = collect_live(with_summaries=not a.rapido)
            origin = "API (ahora)"
        except Exception as e:
            warning = f"No se pudo descargar de Futmondo ({e}). Muestro la última captura guardada."
            print("⚠ " + warning)
    if snap is None:
        snap, origin = latest_offline_snapshot()
        if snap is None:
            print("ERROR: no hay ninguna captura disponible. Revisa el .env y la conexión.")
            return 1
    save_snapshot(con, snap, source=origin)

    print("Analizando...")
    briefing = build_briefing(con, snap, load_finanzas())
    if warning:
        briefing["errores_captura"] = [warning] + briefing["errores_captura"]
    briefing["origen"] = origin
    parte = memo(briefing)
    BRIEFING_JSON.write_text(json.dumps({"briefing": briefing, "parte": parte}, ensure_ascii=False, indent=1),
                             encoding="utf-8")
    if not a.sin_panel:
        build_html(briefing, parte, OUTPUT_HTML)
    if a.exportar:
        from fm.crypto import encrypt_bytes
        payload = json.dumps({"briefing": briefing, "parte": parte}, ensure_ascii=False).encode("utf-8")
        Path(a.exportar).parent.mkdir(parents=True, exist_ok=True)
        Path(a.exportar).write_bytes(encrypt_bytes(payload))
        print(f"   Datos cifrados para la app: {a.exportar}")

    s = briefing["situacion"]
    print(f"\n✅ Análisis listo" + ("" if a.sin_panel else f": {OUTPUT_HTML}"))
    print(f"   Vas {s.get('posicion')}º · once proyectado {s.get('mi_xi_proxima')} pts/jornada")
    for d in briefing["decisiones"][:5]:
        print(f"   [{d['tipo']}] {d['titulo']}")
    if a.abrir:
        webbrowser.open(Path(OUTPUT_HTML).as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
