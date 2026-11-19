"""Configuración: rutas y credenciales.

Las credenciales se leen del .env de esta carpeta y, si no existe, del .env de la
carpeta superior (Escritorio\\futmondo\\.env), que es el que ya usa el script diario.
Acepta los dos estilos de nombre que han usado las versiones anteriores.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
DB_PATH = DATA / "director.db"
FINANZAS = ROOT / "finanzas.json"
OUTPUT_HTML = ROOT / "panel_director.html"
BRIEFING_JSON = DATA / "briefing.json"


def _load_env():
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover
        return
    for candidate in (ROOT / ".env", ROOT.parent / ".env"):
        if candidate.exists():
            load_dotenv(candidate, override=False)


def _first(*names):
    for n in names:
        v = os.getenv(n, "").strip()
        if v:
            return v
    return ""


def credentials():
    _load_env()
    creds = {
        "token": _first("FUTMONDO_TOKEN"),
        "user_id": _first("FUTMONDO_USER_ID", "FUTMONDO_USERID"),
        "championship_id": _first("FUTMONDO_CHAMPIONSHIP_ID"),
        "userteam_id": _first("FUTMONDO_USERTEAM_ID", "FUTMONDO_OWN_TEAM_ID"),
    }
    missing = [k for k, v in creds.items() if not v]
    if missing:
        raise RuntimeError(
            "Faltan credenciales en .env: " + ", ".join(missing)
            + ". Copia .env.example a .env o usa el .env de la carpeta superior."
        )
    return creds


def anthropic_key():
    _load_env()
    return _first("ANTHROPIC_API_KEY")


def anthropic_model():
    _load_env()
    return _first("DIRECTOR_MODEL") or "claude-sonnet-5-5"
