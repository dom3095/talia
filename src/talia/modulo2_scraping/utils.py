"""Utilità condivise tra i moduli di scraping (Modulo 2)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from html import unescape

_RE_CIG = re.compile(r"\bCIG\s*[:\-]?\s*([A-Z0-9]{10})\b", re.IGNORECASE)
_RE_TAG = re.compile(r"<[^>]+>")


def parse_data_iso(s: str | None) -> str | None:
    """Converte date italiane (dd/mm/yyyy) o già ISO (yyyy-mm-dd) in ISO-8601 yyyy-mm-dd."""
    if not s:
        return None
    s = s.strip()
    if len(s) == 10 and s[4] == "-":
        return s  # già ISO
    parts = s.split("/")
    if len(parts) == 3 and len(parts[2]) == 4:
        return f"{parts[2]}-{parts[1]:>02}-{parts[0]:>02}"
    return None


def ora_utc() -> str:
    """Timestamp UTC corrente in ISO-8601."""
    return datetime.now(UTC).isoformat()


def estrai_cig(testo: str | None) -> str | None:
    """Restituisce il primo CIG trovato nel testo, o None."""
    if not testo:
        return None
    m = _RE_CIG.search(testo)
    return m.group(1).upper() if m else None


# Categoria/intestazione → tipo atto TALIA, condivisa da hspromila.py,
# nicosia.py e serviziolinealbo.py (code review 2026-08-08): le tre copie
# erano già divergenti sull'ultima voce ("avviso" in nicosia.py, "avvis" —
# che intercetta anche il plurale "avvisi" — nelle altre due), un
# falso-negativo di classificazione silenzioso su nicosia.py.
TIPI_ATTO_DEFAULT = (
    ("ordinanza", "ordinanza"),
    ("delibera", "delibera"),
    ("determin", "determina"),
    ("concors", "concorso"),
    ("gara", "bando"),
    ("appalt", "bando"),
    ("band", "bando"),
    ("decret", "decreto"),
    ("avvis", "avviso"),
)


def strip_html(html: str) -> str:
    """Rimuove i tag HTML, decodifica le entità e collassa gli spazi bianchi.

    Estratta da 5 copie identiche negli scraper di modulo2_scraping/fonti/
    (halley, hspromila, jcitygov, nicosia, serviziolinealbo — code review
    2026-08-08): stessa logica, mai centralizzata nonostante `utils.py`
    fosse già il posto naturale (già usato da tutti per `parse_data_iso`/
    `ora_utc`/`estrai_cig`).
    """
    return " ".join(_RE_TAG.sub("", unescape(html)).split())
