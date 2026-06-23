"""Spider per l'albo pretorio del Comune di Siracusa (portalepa PHP).

URL base: https://portalepa.comune.siracusa.it
Paginazione: link embedded nella pagina, parametro tabella_albo[page]=N con CSRF token.
Righe: <tr class="paginated_element"> con 5 celle
       (numero, oggetto, tipo_atto, data_affissione, fine_pubblicazione).

Codice ISTAT Siracusa: 089018

Dati pubblici ai sensi del D.lgs. 33/2013.
"""

from __future__ import annotations

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

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

FONTE_SCRAPER = "siracusa"
CODICE_ISTAT = "089018"

_BASE_URL = "https://portalepa.comune.siracusa.it"
_ALBO_PATH = "/openweb/albo/albo_pretorio.php"

_HEADERS = {"User-Agent": "TALIA-bot/0.1 (civic transparency; https://github.com/dom3095/talia)"}

_RE_ROW = re.compile(r'<tr class="paginated_element">(.*?)</tr>', re.DOTALL)
_RE_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)
_RE_LINK = re.compile(r"href=[\"']([^\"']*albo_dettagli\.php\?id=(\d+)[^\"']*)[\"']")
_RE_TAG = re.compile(r"<[^>]+>")
_RE_NEXT = re.compile(
    r"href=[\"'](/openweb/albo/albo_pretorio\.php\?tabella_albo\[page\]=(\d+)&[^\"']+)[\"']",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _strip(html: str) -> str:
    return " ".join(_RE_TAG.sub("", unescape(html)).split())


def _parse_page(html: str) -> list[AttoMetadato]:
    atti = []
    for row_m in _RE_ROW.finditer(html):
        row_html = row_m.group(1)
        cells = [_strip(c.group(1)) for c in _RE_CELL.finditer(row_html)]
        if len(cells) < 3:
            continue
        link_m = _RE_LINK.search(row_html)
        if not link_m:
            continue
        url = _BASE_URL + "/" + link_m.group(1).lstrip("/")
        # tipo_atto in portalepa è "Determina nr.X del dd/mm/yyyy" → estrai la prima parola
        tipo_raw = cells[2] if len(cells) > 2 else ""
        tipo = tipo_raw.split()[0].lower() if tipo_raw else "atto"
        oggetto = cells[1] or None
        atti.append(AttoMetadato(
            ente_codice_istat=CODICE_ISTAT,
            tipo=tipo,
            url_fonte=url,
            fonte_scraper=FONTE_SCRAPER,
            data_accesso=ora_utc(),
            numero=cells[0] or None,
            oggetto=oggetto,
            data_atto=parse_data_iso(cells[3]) if len(cells) > 3 else None,
            data_scadenza=parse_data_iso(cells[4]) if len(cells) > 4 else None,
            cig=estrai_cig(oggetto),
        ))
    return atti


def _next_page_links(html: str) -> dict[int, str]:
    """Restituisce {numero_pagina: url} per tutti i link di paginazione."""
    links: dict[int, str] = {}
    for m in _RE_NEXT.finditer(html):
        page_num = int(m.group(2))
        links[page_num] = _BASE_URL + unescape(m.group(1))
    return links


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------


def scarica_atti(max_pagine: int = 100) -> Iterator[AttoMetadato]:
    """Scarica atti dall'albo pretorio di Siracusa.

    Richiede connettività di rete. Per i test usa _parse_page() con HTML fixture.
    """
    url: str = _BASE_URL + _ALBO_PATH
    current_page = 1
    for _ in range(max_pagine):
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode("utf-8", errors="replace")
        atti = _parse_page(html)
        if not atti:
            break
        yield from atti
        next_links = _next_page_links(html)
        next_url = next_links.get(current_page + 1)
        if not next_url:
            break
        url = next_url
        current_page += 1


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
    """Upsert del Comune di Siracusa nel DB (prerequisito per inserisci_atto)."""
    upsert_ente(conn, EnteMetadato(
        denominazione="Comune di Siracusa",
        codice_istat=CODICE_ISTAT,
        provincia="SR",
    ))
