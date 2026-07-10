"""Spider per l'albo pretorio del Comune di Agrigento (ASP.NET + DevExpress).

URL: https://servizionline.comune.agrigento.it/ServiziOnLine/AlboPretorio/AlboPretorio
Richiede Playwright: il contenuto è iniettato via callback DevExpress dopo networkidle.

Struttura DOM (dopo rendering Playwright):
  - Ogni atto: <li> contenente <div class="list-item">
  - Titolo: <span class="text text-custom p-1">{numero}/{anno} del {data} - {tipo} - ...
             <em>{oggetto}</em></span>
  - Permalink: attributo data-link="http://...?anno=YYYY&numero=NNN"
  - Paginazione: bottoni PBN (DevExpress) — cliccabili con Playwright

Codice ISTAT Agrigento: 084001

Dati pubblici ai sensi del D.lgs. 33/2013.
Richiede: pip install playwright && playwright install chromium
"""

from __future__ import annotations

import re
import sqlite3
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

FONTE_SCRAPER = "agrigento"
CODICE_ISTAT = "084001"

_BASE_URL = "https://servizionline.comune.agrigento.it"
_ALBO_URL = f"{_BASE_URL}/ServiziOnLine/AlboPretorio/AlboPretorio"

_RE_TAG = re.compile(r"<[^>]+>")
_RE_HEADER = re.compile(
    r"(\d+/\d{4})\s+del\s+(\d{2}/\d{2}/\d{4})\s+-\s+([^-]+?)\s+-",
    re.IGNORECASE,
)
_RE_OGGETTO = re.compile(r"<em>(.*?)</em>", re.DOTALL)
_RE_PERMALINK = re.compile(r'data-link="(https?://[^"]+anno=(\d+)[^"]*numero=(\d+))"')


# ---------------------------------------------------------------------------
# Parsing (puro HTML, testabile senza Playwright)
# ---------------------------------------------------------------------------


def _strip(html: str) -> str:
    return " ".join(_RE_TAG.sub("", unescape(html)).split())


def _parse_html(html: str) -> list[AttoMetadato]:
    """Estrae atti dal DOM già renderizzato (da Playwright o HTML fixture).

    Deduplicazione per url_fonte: un atto con lo stesso permalink viene emesso una sola volta.
    """
    atti: list[AttoMetadato] = []
    seen_urls: set[str] = set()

    for plink_m in _RE_PERMALINK.finditer(html):
        raw_url = unescape(plink_m.group(1))
        anno = plink_m.group(2)
        numero_plain = plink_m.group(3)

        if raw_url in seen_urls:
            continue
        seen_urls.add(raw_url)

        numero = f"{numero_plain}/{anno}"

        # Trova il titolo del list-item corrispondente tramite data-bs-target
        target = f"#collapse{numero_plain}_{anno}"
        target_idx = html.find(target)
        if target_idx < 0:
            continue

        span_m = re.search(
            r'<span class="text text-custom p-1">(.*?)</span>',
            html[max(0, target_idx - 200):target_idx + 800],
            re.DOTALL,
        )
        if not span_m:
            continue
        span_html = span_m.group(1)

        oggetto_m = _RE_OGGETTO.search(span_html)
        oggetto = _strip(oggetto_m.group(1)) if oggetto_m else None

        header_text = _strip(re.sub(r"<em>.*?</em>", "", span_html, flags=re.DOTALL))
        header_m = _RE_HEADER.search(header_text)
        tipo = _strip(header_m.group(3)).lower() if header_m else "atto"
        data_str = header_m.group(2) if header_m else None

        atti.append(AttoMetadato(
            ente_codice_istat=CODICE_ISTAT,
            tipo=tipo,
            url_fonte=raw_url,
            fonte_scraper=FONTE_SCRAPER,
            data_accesso=ora_utc(),
            numero=numero,
            oggetto=oggetto,
            data_atto=parse_data_iso(data_str),
            cig=estrai_cig(oggetto),
        ))

    return atti


def _ha_pagina_successiva(page) -> bool:
    """Controlla se esiste un bottone PBN (DevExpress next page) cliccabile."""
    pbn = page.locator('a[href*="PBN"]').first
    try:
        return pbn.is_visible(timeout=2000)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------


def scarica_atti(
    max_pagine: int = 20,
    base_url: str = _BASE_URL,
) -> Iterator[AttoMetadato]:
    """Scarica atti con Playwright (richiede: pip install playwright + playwright install chromium).

    Per i test usa _parse_html() con HTML fixture.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ImportError(
            "Playwright non installato. "
            "Esegui: pip install playwright && playwright install chromium"
        ) from exc

    albo_url = f"{base_url}/ServiziOnLine/AlboPretorio/AlboPretorio"
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(albo_url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(4000)

        for _ in range(max_pagine):
            html = page.content()
            atti = _parse_html(html)
            if not atti:
                break
            yield from atti

            if not _ha_pagina_successiva(page):
                break
            pbn = page.locator('a[href*="PBN"]').first
            pbn.click()
            page.wait_for_load_state("networkidle", timeout=20000)
            page.wait_for_timeout(2000)

        browser.close()


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
    denominazione: str = "Comune di Agrigento",
) -> None:
    """Upsert del Comune di Agrigento nel DB (prerequisito per inserisci_atto)."""
    upsert_ente(conn, EnteMetadato(
        denominazione=denominazione,
        codice_istat=codice_istat,
        provincia="AG",
    ))
