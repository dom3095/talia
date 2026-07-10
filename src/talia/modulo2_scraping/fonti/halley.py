"""Spider generico per albi pretori su piattaforma Halley Informatica (Halley EG).

Vendor diffuso tra più comuni siciliani sotto domini diversi (Vittoria,
Sciacca, Adrano, Barcellona Pozzo di Gotto — TAL-49). Paginazione stateless
via querystring `?pag=N` (0-indexed, N=0 implicito sulla root), nessuna
sessione richiesta.

Struttura riga (dentro <tbody>, senza classe):
  <tr>
    <td>Numero pubblicazione, Mittente, Tipo</td>
    <td>Oggetto (link dettaglio mc_p_dettaglio.php?id_pubbl=N)</td>
    <td>Numero atto, Data atto</td>
    <td>Registro generale, Data registro generale</td>
    <td>Data inizio, Data fine</td>
    <td>Documento, Allegati</td>
  </tr>
Ogni riga appare due volte nell'HTML (variante desktop "hidden-xs" e mobile
"visible-xs" con etichette leggermente diverse): si prende la prima
occorrenza di ciascun campo.

Dati pubblici ai sensi del D.lgs. 33/2013.
"""

from __future__ import annotations

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

FONTE_SCRAPER = "halley"
_RICERCA_PATH = "/mc/mc_p_ricerca.php"
_DETTAGLIO_PATH = "/mc/mc_p_dettaglio.php"

_HEADERS = {"User-Agent": "TALIA-bot/0.1 (civic transparency; https://github.com/dom3095/talia)"}

_RE_TAG = re.compile(r"<[^>]+>")
_RE_ROW = re.compile(r"<tr>(.*?)</tr>", re.DOTALL)
_RE_FIELD = re.compile(
    r'<strong>([^<]+)</strong>(?:\s*<br>)?(?:\s*<a[^>]*>)?\s*<div[^>]*>(.*?)</div>',
    re.DOTALL,
)
_RE_LINK = re.compile(r'href="[^"]*id_pubbl=(\d+)"')

_NON_DEFINITO = "non definito"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _strip(html: str) -> str:
    return " ".join(_RE_TAG.sub("", unescape(html)).split())


def _campo(campi: dict[str, str], chiave: str) -> str | None:
    valore = _strip(campi.get(chiave, ""))
    return valore if valore and valore.lower() != _NON_DEFINITO else None


def _parse_pagina(html: str, base_url: str, codice_istat: str) -> list[AttoMetadato]:
    atti = []
    for row_m in _RE_ROW.finditer(html):
        row_html = row_m.group(1)
        if "<strong>Numero pubblicazione</strong>" not in row_html:
            continue

        campi: dict[str, str] = {}
        for chiave, valore in _RE_FIELD.findall(row_html):
            campi.setdefault(chiave, valore)

        link_m = _RE_LINK.search(row_html)
        if not link_m:
            continue
        url = f"{base_url}{_DETTAGLIO_PATH}?id_pubbl={link_m.group(1)}"

        tipo = _campo(campi, "Tipo")
        oggetto = _campo(campi, "Oggetto")

        atti.append(AttoMetadato(
            ente_codice_istat=codice_istat,
            tipo=(tipo or "atto").lower(),
            url_fonte=url,
            fonte_scraper=FONTE_SCRAPER,
            data_accesso=ora_utc(),
            numero=_campo(campi, "Numero atto"),
            oggetto=oggetto,
            data_atto=parse_data_iso(_campo(campi, "Data atto")),
            data_scadenza=parse_data_iso(_campo(campi, "Data fine")),
            cig=estrai_cig(oggetto),
        ))
    return atti


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------


def scarica_atti(
    base_url: str,
    codice_istat: str,
    *,
    max_pagine: int = 100,
    skip_ssl: bool = False,
) -> Iterator[AttoMetadato]:
    """Scarica atti da un albo pretorio Halley EG.

    Paginazione stateless via querystring: nessuna sessione necessaria.

    Args:
        base_url:     URL base del portale, es. "https://trasparenza.comune.vittoria.rg.it".
        codice_istat: codice ISTAT a 6 cifre del comune.
        max_pagine:   numero massimo di pagine da scaricare.
        skip_ssl:     True per ignorare errori di verifica del certificato
                      (es. Siculiana: catena incompleta lato server, cert
                      valido ma senza intermedio — non è un cert scaduto).
    """
    base = base_url.rstrip("/")
    ctx = None
    if skip_ssl:
        import ssl

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    for pagina in range(max_pagine):
        url = f"{base}{_RICERCA_PATH}" + (f"?pag={pagina}" if pagina else "")
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            html = r.read().decode("utf-8", errors="replace")
        atti = _parse_pagina(html, base, codice_istat)
        if not atti:
            break
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
