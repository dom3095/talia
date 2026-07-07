"""Spider generico per albi pretori su piattaforma "portalepa" PHP.

Stessa piattaforma di Siracusa (`siracusa.py`), riusata da più comuni sotto
domini diversi (es. Gela: dominio proprio; Monreale: *.soluzionipa.it) — TAL-49.
Path riconoscibile: /openweb/albo/albo_pretorio.php, righe
<tr class="paginated_element"> con 5 celle
(numero, oggetto, tipo_atto, data_affissione, fine_pubblicazione).

Nota: alcuni tenant (es. Partinico, variante "_full") hanno un layout di
colonne diverso e NON sono compatibili con questo modulo — vedi TAL-49.

Dati pubblici ai sensi del D.lgs. 33/2013.
"""

from __future__ import annotations

import http.cookiejar
import re
import sqlite3
import urllib.request
from collections.abc import Iterable, Iterator
from html import unescape

from talia.modulo2_scraping.db import AttoMetadato, inserisci_atto
from talia.modulo2_scraping.utils import estrai_cig, ora_utc, parse_data_iso

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

FONTE_SCRAPER = "portalepa"
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


def _parse_page(html: str, base_url: str, codice_istat: str) -> list[AttoMetadato]:
    atti = []
    for row_m in _RE_ROW.finditer(html):
        row_html = row_m.group(1)
        cells = [_strip(c.group(1)) for c in _RE_CELL.finditer(row_html)]
        if len(cells) < 3:
            continue
        link_m = _RE_LINK.search(row_html)
        if not link_m:
            continue
        url = base_url + "/" + link_m.group(1).lstrip("/")
        # tipo_atto è "Determina nr.X del dd/mm/yyyy" → estrai la prima parola
        tipo_raw = cells[2] if len(cells) > 2 else ""
        tipo = tipo_raw.split()[0].lower() if tipo_raw else "atto"
        oggetto = cells[1] or None
        atti.append(AttoMetadato(
            ente_codice_istat=codice_istat,
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


def _next_page_links(html: str, base_url: str) -> dict[int, str]:
    """Restituisce {numero_pagina: url} per tutti i link di paginazione."""
    links: dict[int, str] = {}
    for m in _RE_NEXT.finditer(html):
        page_num = int(m.group(2))
        links[page_num] = base_url + unescape(m.group(1))
    return links


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------


def scarica_atti(
    base_url: str,
    codice_istat: str,
    *,
    max_pagine: int = 100,
) -> Iterator[AttoMetadato]:
    """Scarica atti da un albo pretorio "portalepa" (famiglia di Siracusa).

    Args:
        base_url:     URL base del portale, es. "https://portale.comune.gela.cl.it".
        codice_istat: codice ISTAT a 6 cifre del comune.
        max_pagine:   numero massimo di pagine da scaricare.
    """
    # CookieJar necessario: portalepa imposta PHPSESSID alla prima risposta
    # e rifiuta le richieste successive senza cookie (HTTP 400).
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    base = base_url.rstrip("/")
    url = base + _ALBO_PATH
    current_page = 1
    for _ in range(max_pagine):
        req = urllib.request.Request(url, headers=_HEADERS)
        with opener.open(req, timeout=20) as r:
            html = r.read().decode("utf-8", errors="replace")
        atti = _parse_page(html, base, codice_istat)
        if not atti:
            break
        yield from atti
        next_links = _next_page_links(html, base)
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
