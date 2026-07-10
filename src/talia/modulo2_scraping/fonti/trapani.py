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

import logging
import re
import sqlite3
import urllib.request
from collections.abc import Iterable, Iterator
from datetime import date, timedelta
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

_LOG = logging.getLogger(__name__)

# Il server esclude gli atti la cui finestra di pubblicazione termina DOPO
# dataPubblicazioneAl: con al=oggi si perdono gli atti ancora in pubblicazione
# (nei giorni peggiori: 0 risultati — BUG-4). Margine futuro per includerli.
_MARGINE_FUTURO_GIORNI = 60

_BASE_URL = "https://servizi-trapani.e-pal.it"
_ALBO_PATH = "/AlboOnline/ricercaAlbo"

_HEADERS = {"User-Agent": "TALIA-bot/0.1 (civic transparency; https://github.com/dom3095/talia)"}

_RE_PANEL = re.compile(
    r'<div class="panel panel-primary">(.*?)'
    r'(?=<div class="panel panel-primary">|</div>\s*</div>\s*</div>\s*</div>)',
    re.DOTALL,
)
_RE_HEADING = re.compile(r'<div class="panel-heading titolo-albo"[^>]*>(.*?)</div>', re.DOTALL)
_RE_OGGETTO = re.compile(r"Oggetto:\s*(.*?)(?=</div>|$)", re.DOTALL)
_RE_NUMERO_ALBO = re.compile(r"Registrazione Albo n\.\s*([\d]+)/(\d{4})")
_RE_TIPO_PUB = re.compile(
    r'Tipo pubblicazione:.*?<div class="testata-dati[^"]*"[^>]*>\s*([^<]+)',
    re.DOTALL | re.IGNORECASE,
)
_RE_DATA_PUB = re.compile(r"Pubblicazione dal\s+(\d{2}/\d{2}/\d{4})")
_RE_DATA_FINE = re.compile(r"(?<!\w)al\s+(\d{2}/\d{2}/\d{4})")
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

        atti.append(
            AttoMetadato(
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
            )
        )
    return atti


def _next_page_url(
    html: str,
    current_page: int,
    base_url: str = _BASE_URL,
) -> str | None:
    """Restituisce l'URL della pagina successiva se presente nella paginazione."""
    for m in _RE_NEXT_PAGE.finditer(html):
        if int(m.group(2)) == current_page + 1:
            return base_url + unescape(m.group(1))
    return None


def _build_url(
    dal: str,
    al: str,
    page: int = 1,
    base_url: str = _BASE_URL,
) -> str:
    return (
        f"{base_url}{_ALBO_PATH}?dataPubblicazioneDal={dal}&dataPubblicazioneAl={al}&page={page}"
    )


def _intervallo_default(oggi: date | None = None) -> tuple[str, str]:
    """Intervallo di ricerca di default: 1 gennaio → oggi + margine futuro.

    Il margine futuro è necessario perché il server esclude gli atti la cui
    finestra di pubblicazione termina dopo dataPubblicazioneAl (BUG-4).
    """
    if oggi is None:
        oggi = date.today()
    dal = f"{oggi.year}-01-01"
    al = (oggi + timedelta(days=_MARGINE_FUTURO_GIORNI)).isoformat()
    return dal, al


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------


def scarica_atti(
    dal: str | None = None,
    al: str | None = None,
    max_pagine: int = 50,
    base_url: str = _BASE_URL,
) -> Iterator[AttoMetadato]:
    """Scarica atti dall'albo pretorio di Trapani.

    dal/al: stringhe ISO yyyy-mm-dd. Default: 1 gennaio anno corrente → oggi+60gg
    (il margine futuro serve a includere gli atti ancora in pubblicazione, vedi
    _MARGINE_FUTURO_GIORNI). Richiede connettività di rete. Per i test usa
    _parse_page() con HTML fixture.
    """
    dal_default, al_default = _intervallo_default()
    if dal is None:
        dal = dal_default
    if al is None:
        al = al_default

    url: str | None = _build_url(dal, al, 1, base_url)
    current_page = 1

    for _ in range(max_pagine):
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode("utf-8", errors="replace")
        atti = _parse_page(html)
        if not atti:
            if current_page == 1:
                _LOG.warning(
                    "[Trapani] 0 atti dalla pagina 1 (%s): struttura HTML "
                    "cambiata o filtro data che esclude tutto?",
                    url,
                )
            break
        yield from atti
        url = _next_page_url(html, current_page, base_url)
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


def prepara_ente(
    conn: sqlite3.Connection,
    base_url: str = _BASE_URL,
    codice_istat: str = CODICE_ISTAT,
    denominazione: str = "Comune di Trapani",
) -> None:
    """Upsert del Comune di Trapani nel DB (prerequisito per inserisci_atto)."""
    upsert_ente(
        conn,
        EnteMetadato(
            denominazione=denominazione,
            codice_istat=codice_istat,
            provincia="TP",
        ),
    )
