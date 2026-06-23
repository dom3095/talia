"""Spider per l'albo pretorio del Comune di Trapani (piattaforma e-pal.it).

URL base: https://servizi-trapani.e-pal.it
Paginazione: GET con dataPubblicazioneDal/Al (ISO yyyy-mm-dd) e &page=N.
Struttura HTML: div.panel.panel-primary con panel-heading.titolo-albo e panel-body.

NOTA: il sito non espone permalink per singolo atto. url_fonte è una URL sintetica
costruita da numero e anno per garantire unicità nel DB.

Codice ISTAT Trapani: 081021

Dati pubblici ai sensi del D.lgs. 33/2013.
"""

from __future__ import annotations

import re
import sqlite3
import urllib.request
from collections.abc import Iterable, Iterator
from datetime import date
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

FONTE_SCRAPER = "trapani"
CODICE_ISTAT = "081021"

_BASE_URL = "https://servizi-trapani.e-pal.it"
_ALBO_PATH = "/AlboOnline/ricercaAlbo"

_HEADERS = {"User-Agent": "TALIA-bot/0.1 (civic transparency; https://github.com/dom3095/talia)"}

_RE_PANEL = re.compile(
    r'<div class="panel panel-primary">(.*?)'
    r'(?=<div class="panel panel-primary">|</div>\s*</div>\s*</div>\s*</div>)',
    re.DOTALL,
)
_RE_HEADING = re.compile(r'<div class="panel-heading titolo-albo"[^>]*>(.*?)</div>', re.DOTALL)
_RE_OGGETTO = re.compile(r'Oggetto:\s*(.*?)(?=</div>|$)', re.DOTALL)
_RE_NUMERO_ALBO = re.compile(r'Registrazione Albo n\.\s*([\d]+)/(\d{4})')
_RE_TIPO_PUB = re.compile(
    r'Tipo pubblicazione:.*?<div class="testata-dati[^"]*"[^>]*>\s*([^<]+)',
    re.DOTALL | re.IGNORECASE,
)
_RE_DATA_PUB = re.compile(r'Pubblicazione dal\s+(\d{2}/\d{2}/\d{4})')
_RE_DATA_FINE = re.compile(r'(?<!\w)al\s+(\d{2}/\d{2}/\d{4})')
_RE_NEXT_PAGE = re.compile(
    r'href="(/AlboOnline/ricercaAlbo\?[^"]*page=(\d+)[^"]*)"[^>]*class="step"',
)
_RE_TAG = re.compile(r"<[^>]+>")


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _strip(html: str) -> str:
    return " ".join(_RE_TAG.sub("", unescape(html)).split())


def _parse_page(html: str) -> list[AttoMetadato]:
    atti = []
    for panel_m in _RE_PANEL.finditer(html):
        panel_html = panel_m.group(1)

        heading_m = _RE_HEADING.search(panel_html)
        if not heading_m:
            continue
        heading_html = heading_m.group(1)
        heading_text = _strip(heading_html)

        num_m = _RE_NUMERO_ALBO.search(heading_text)
        if not num_m:
            continue
        numero_plain = num_m.group(1)
        anno = num_m.group(2)
        numero = f"{numero_plain}/{anno}"

        oggetto_m = _RE_OGGETTO.search(heading_html)
        oggetto = _strip(oggetto_m.group(1)) if oggetto_m else None

        tipo_m = _RE_TIPO_PUB.search(panel_html)
        tipo = _strip(tipo_m.group(1)).lower() if tipo_m else "atto"

        data_m = _RE_DATA_PUB.search(panel_html)
        data_fine_m = _RE_DATA_FINE.search(panel_html)

        # Permalink non disponibile sul sito: URL sintetica per unicità DB
        url = f"{_BASE_URL}/AlboOnline/albo/{numero_plain}/{anno}"

        atti.append(AttoMetadato(
            ente_codice_istat=CODICE_ISTAT,
            tipo=tipo,
            url_fonte=url,
            fonte_scraper=FONTE_SCRAPER,
            data_accesso=ora_utc(),
            numero=numero,
            oggetto=oggetto,
            data_atto=parse_data_iso(data_m.group(1)) if data_m else None,
            data_scadenza=parse_data_iso(data_fine_m.group(1)) if data_fine_m else None,
            cig=estrai_cig(oggetto),
        ))
    return atti


def _next_page_url(html: str, current_page: int) -> str | None:
    """Restituisce l'URL della pagina successiva se presente nella paginazione."""
    for m in _RE_NEXT_PAGE.finditer(html):
        if int(m.group(2)) == current_page + 1:
            return _BASE_URL + unescape(m.group(1))
    return None


def _build_url(dal: str, al: str, page: int = 1) -> str:
    return (
        f"{_BASE_URL}{_ALBO_PATH}"
        f"?dataPubblicazioneDal={dal}&dataPubblicazioneAl={al}&page={page}"
    )


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------


def scarica_atti(
    dal: str | None = None,
    al: str | None = None,
    max_pagine: int = 50,
) -> Iterator[AttoMetadato]:
    """Scarica atti dall'albo pretorio di Trapani.

    dal/al: stringhe ISO yyyy-mm-dd. Default: 1 gennaio anno corrente → oggi.
    Richiede connettività di rete. Per i test usa _parse_page() con HTML fixture.
    """
    oggi = date.today()
    if dal is None:
        dal = f"{oggi.year}-01-01"
    if al is None:
        al = oggi.isoformat()

    url: str | None = _build_url(dal, al, 1)
    current_page = 1

    for _ in range(max_pagine):
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode("utf-8", errors="replace")
        atti = _parse_page(html)
        if not atti:
            break
        yield from atti
        url = _next_page_url(html, current_page)
        if not url:
            break
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
    """Upsert del Comune di Trapani nel DB (prerequisito per inserisci_atto)."""
    upsert_ente(conn, EnteMetadato(
        denominazione="Comune di Trapani",
        codice_istat=CODICE_ISTAT,
        provincia="TP",
    ))
