"""Utilità condivise tra i moduli di scraping (Modulo 2)."""

from __future__ import annotations

import re
from datetime import datetime, timezone

_RE_CIG = re.compile(r'\bCIG\s*[:\-]?\s*([A-Z0-9]{10})\b', re.IGNORECASE)


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
    return datetime.now(timezone.utc).isoformat()


def estrai_cig(testo: str | None) -> str | None:
    """Restituisce il primo CIG trovato nel testo, o None."""
    if not testo:
        return None
    m = _RE_CIG.search(testo)
    return m.group(1).upper() if m else None
