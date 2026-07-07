"""Spider per l'albo pretorio del Comune di Sambuca di Sicilia (Halley HSPromila, ASP.NET).

URL: https://servizionline.hspromilaprod.hypersicapp.net/cmssambucadisicilia/portale/
     albopretorio/albopretorioconsultazione.aspx?P=400

Variante Halley diversa da quella "EG" (`mc_p_ricerca.php`, vedi `halley.py`):
piattaforma ASP.NET (HSPromila), ma HTTP puro — la tabella atti è già presente
nell'HTML della prima GET, nessun rendering client-side necessario.

Limiti noti:
- Nessun link di dettaglio per singolo atto nella riga: si usa la pagina lista
  come url_fonte (soddisfa comunque il requisito di tracciabilità alla fonte).
- Non è stato verificato un meccanismo di paginazione/backfill: la pagina
  mostra un solo blocco di atti (95 alla prima verifica, 2026-07-08). Se in
  futuro emerge un parametro di paginazione, va aggiunto qui.

Codice ISTAT Sambuca di Sicilia: 084034

Dati pubblici ai sensi del D.lgs. 33/2013.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import urllib.request
from collections.abc import Iterable, Iterator
from html import unescape

from talia.modulo2_scraping.db import (
    AttoMetadato,
    EnteMetadato,
    inserisci_atto,
    upsert_ente,
)
from talia.modulo2_scraping.utils import estrai_cig, ora_utc, parse_data_iso

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

FONTE_SCRAPER = "sambucadisicilia"
CODICE_ISTAT = "084034"

_URL = (
    "https://servizionline.hspromilaprod.hypersicapp.net/cmssambucadisicilia/"
    "portale/albopretorio/albopretorioconsultazione.aspx?P=400"
)

_HEADERS = {"User-Agent": "TALIA-bot/0.1 (civic transparency; https://github.com/dom3095/talia)"}

_RE_ROW = re.compile(r'<tr class="">(.*?)</tr>', re.DOTALL)
_RE_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)
_RE_TAG = re.compile(r"<[^>]+>")

# Categoria → tipo atto TALIA
_TIPI = (
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


def _strip(html: str) -> str:
    return " ".join(_RE_TAG.sub("", unescape(html)).split())


def _tipo_da_categoria(categoria: str) -> str:
    c = categoria.lower()
    for chiave, tipo in _TIPI:
        if chiave in c:
            return tipo
    return "atto"


def _parse_pagina(html: str) -> list[AttoMetadato]:
    atti = []
    for row_m in _RE_ROW.finditer(html):
        cells = [_strip(c.group(1)) for c in _RE_CELL.finditer(row_m.group(1))]
        # cells: [hidden, key, data_interna, numero_atto, numero_registro,
        #         oggetto, categoria, ente_ufficio, data_inizio, data_fine]
        if len(cells) < 10:
            continue
        chiave_riga = cells[1]
        numero_registro = cells[4]
        oggetto = cells[5] or None
        categoria = cells[6]
        atti.append(AttoMetadato(
            ente_codice_istat=CODICE_ISTAT,
            tipo=_tipo_da_categoria(categoria),
            # Nessun link di dettaglio per singolo atto nella riga: si usa la
            # pagina lista con un frammento basato sulla "key" interna per
            # rendere url_fonte univoco (la dedup DB si basa su questo campo).
            url_fonte=f"{_URL}#{chiave_riga}",
            fonte_scraper=FONTE_SCRAPER,
            data_accesso=ora_utc(),
            numero=numero_registro or None,
            oggetto=oggetto,
            data_pub=parse_data_iso(cells[8]) if len(cells) > 8 else None,
            data_scadenza=parse_data_iso(cells[9]) if len(cells) > 9 else None,
            cig=estrai_cig(oggetto),
        ))
    return atti


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------


def scarica_atti(**_kwargs) -> Iterator[AttoMetadato]:
    """Scarica gli atti attualmente elencati sull'albo pretorio di Sambuca di Sicilia.

    Nessuna paginazione nota: la pagina espone un unico blocco di atti.
    """
    req = urllib.request.Request(_URL, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        html = r.read().decode("utf-8", errors="replace")
    atti = _parse_pagina(html)
    if not atti:
        logger.warning(
            "Sambuca di Sicilia: 0 atti estratti — struttura HTML cambiata"
            " o portale in manutenzione?"
        )
    yield from atti


def salva_atti(
    atti: Iterable[AttoMetadato],
    conn: sqlite3.Connection,
) -> dict[str, int]:
    """Persiste gli atti nel DB; ritorna {'inseriti': N, 'duplicati': M}."""
    inseriti = 0
    duplicati = 0
    for atto in atti:
        esito = inserisci_atto(conn, atto)
        if esito is not None:
            inseriti += 1
        else:
            duplicati += 1
    conn.commit()
    return {"inseriti": inseriti, "duplicati": duplicati}


def prepara_ente(conn: sqlite3.Connection) -> None:
    """Upsert del Comune di Sambuca di Sicilia nel DB (prerequisito per inserisci_atto)."""
    upsert_ente(conn, EnteMetadato(
        denominazione="Comune di Sambuca di Sicilia",
        codice_istat=CODICE_ISTAT,
        provincia="AG",
    ))
