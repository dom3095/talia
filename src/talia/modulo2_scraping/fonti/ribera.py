"""Spider per l'albo pretorio del Comune di Ribera (WordPress, tema comunale).

URL: https://www.comune.ribera.ag.it/atti-pubblici/albo-pretorio/
Paginazione: querystring `?Pag=N` (stateless, nessuna sessione), 10 atti/pagina.
Dettaglio: `?action=visatto&id=<id>` (stesso URL usato come link su ogni cella).

Righe: <tr> con 5 celle (protocollo, oggetto, validità [2 date], categoria,
settore). L'oggetto in lista è troncato ("[...]"): il testo completo
richiederebbe una fetch della pagina di dettaglio, non fatta qui (come per
gli altri scraper "solo lista" del progetto).

Non è escluso che altri comuni siciliani usino lo stesso tema WordPress
("design-comuni-wordpress-theme"): da verificare in futuro con uno sweep.

Codice ISTAT Ribera: 084033

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

FONTE_SCRAPER = "ribera"
CODICE_ISTAT = "084033"

_BASE_URL = "https://www.comune.ribera.ag.it/atti-pubblici/albo-pretorio/"

_HEADERS = {"User-Agent": "TALIA-bot/0.1 (civic transparency; https://github.com/dom3095/talia)"}

_RE_ROW = re.compile(r"<tr>(.*?)</tr>", re.DOTALL)
_RE_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)
_RE_TAG = re.compile(r"<[^>]+>")
_RE_LINK = re.compile(r'href="([^"]*[?&]action=visatto&(?:amp;)?id=(\d+)[^"]*)"')

# Categoria URBI/WP → tipo atto TALIA
_TIPI = (
    ("ordinanza", "ordinanza"),
    ("delibera", "delibera"),
    ("determin", "determina"),
    ("concors", "concorso"),
    ("gara", "bando"),
    ("appalt", "bando"),
    ("band", "bando"),
    ("decret", "decreto"),
    ("avviso", "avviso"),
)


def _strip(html: str) -> str:
    return " ".join(_RE_TAG.sub("", unescape(html)).split())


def _tipo_da_categoria(categoria: str) -> str:
    c = categoria.lower()
    for chiave, tipo in _TIPI:
        if chiave in c:
            return tipo
    return "atto"


def _parse_pagina(html: str, base_url: str = _BASE_URL) -> list[AttoMetadato]:
    atti = []
    for row_m in _RE_ROW.finditer(html):
        row_html = row_m.group(1)
        link_m = _RE_LINK.search(row_html)
        if not link_m:
            continue  # riga di intestazione o servizio
        cells = [_strip(c.group(1)) for c in _RE_CELL.finditer(row_html)]
        if len(cells) < 5:
            continue

        protocollo, oggetto, validita, categoria = cells[0], cells[1], cells[2], cells[3]
        date = re.findall(r"\d{2}/\d{2}/\d{4}", validita)
        data_pub = parse_data_iso(date[0]) if len(date) > 0 else None
        data_scadenza = parse_data_iso(date[1]) if len(date) > 1 else None

        atti.append(AttoMetadato(
            ente_codice_istat=CODICE_ISTAT,
            tipo=_tipo_da_categoria(categoria),
            url_fonte=f"{base_url}?action=visatto&id={link_m.group(2)}",
            fonte_scraper=FONTE_SCRAPER,
            data_accesso=ora_utc(),
            numero=protocollo or None,
            oggetto=oggetto or None,
            data_pub=data_pub,
            data_scadenza=data_scadenza,
            cig=estrai_cig(oggetto),
        ))
    return atti


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------


def scarica_atti(
    max_pagine: int = 100,
    base_url: str = _BASE_URL,
) -> Iterator[AttoMetadato]:
    """Scarica atti dall'albo pretorio di Ribera.

    Paginazione stateless via querystring: nessuna sessione necessaria.
    """
    for pagina in range(1, max_pagine + 1):
        url = base_url if pagina == 1 else f"{base_url}?Pag={pagina}"
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode("utf-8", errors="replace")
        atti = _parse_pagina(html, base_url)
        if not atti:
            break
        yield from atti

    if pagina == 1 and not atti:
        logger.warning(
            "Ribera: 0 atti estratti — struttura HTML cambiata o portale in manutenzione?"
        )


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


def prepara_ente(
    conn: sqlite3.Connection,
    base_url: str = _BASE_URL,
    codice_istat: str = CODICE_ISTAT,
    denominazione: str = "Comune di Ribera",
) -> None:
    """Upsert del Comune di Ribera nel DB (prerequisito per inserisci_atto)."""
    upsert_ente(conn, EnteMetadato(
        denominazione=denominazione,
        codice_istat=codice_istat,
        provincia="AG",
    ))
