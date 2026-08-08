"""Spider per l'albo pretorio del Comune di Nicosia (WordPress, tema "Developers Italia").

URL: https://comune.nicosia.en.it/tipi_documento/documento-albo-pretorio/

Piattaforma con custom post type `documento_pubblico` e tassonomia `tipi_documento`
(tema WordPress standard per PA italiane, "Designers Italia"). Stesso tema di Corleone
(mai attivato: solo 12 documenti totali nel CPT, quasi tutti migrati lo stesso giorno —
non un registro atti reale). A Nicosia invece la tassonomia "Documento Albo Pretorio" è
viva e paginata: si scarica solo quella (il CPT completo, ~950 documenti, contiene anche
moduli e documenti di riferimento statici senza data, non atti pubblicati).

Solo gli atti **attualmente in pubblicazione** sono in questa vista (~12 al momento
della scoperta, 2026-08-06): stesso pattern "finestra di pubblicazione" di
Palermo/Catania — serve scraping continuo per costruire uno storico.

La pagina lista mostra solo titolo/descrizione breve: la data reale ("Ultimo
aggiornamento") e la descrizione completa richiedono una fetch della pagina di
dettaglio per atto (il CPT non espone API REST, verificato).

Nota per sviluppi futuri: il backend reale è URBI (`asp.urbi.it`, DB_NAME esposto nei
link "Scarica documento" di ogni dettaglio), ma con un frontend Urbi più recente
("Bootstrap ITALIA") che non risponde al flusso HTTP già gestito da `urbi.py`
(costruito per l'interfaccia precedente, usata da Catania/Favara/Raffadali) — se in
futuro emergono altri comuni sulla stessa piattaforma, vale la pena investire nel
reverse engineering del nuovo flusso invece di replicare questo scraper WordPress.

Codice ISTAT Nicosia: 086012

Dati pubblici ai sensi del D.lgs. 33/2013.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import urllib.error
import urllib.request
from collections.abc import Iterable, Iterator
from html import unescape

from talia.modulo2_scraping.db import (
    AttoMetadato,
    EnteMetadato,
    inserisci_atto,
    upsert_ente,
)
from talia.modulo2_scraping.utils import TIPI_ATTO_DEFAULT, estrai_cig, ora_utc, parse_data_iso
from talia.modulo2_scraping.utils import strip_html as _strip

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

FONTE_SCRAPER = "nicosia"
CODICE_ISTAT = "086012"

_BASE_URL = "https://comune.nicosia.en.it"
_ALBO_PATH = "/tipi_documento/documento-albo-pretorio/"

_HEADERS = {"User-Agent": "TALIA-bot/0.1 (civic transparency; https://github.com/dom3095/talia)"}

_RE_CARD = re.compile(
    r'<a class="text-decoration-none" href="(https://[^"]+/documento_pubblico/[^"]+)">\s*'
    r'<h3 class="card-title h4">(.*?)</h3>',
    re.DOTALL,
)
_RE_DATA_AGGIORNAMENTO = re.compile(r"Ultimo aggiornamento:\s*<span[^>]*>\s*(\d{2}/\d{2}/\d{4})")
_RE_DESCRIZIONE = re.compile(
    r'Descrizione</h4>.*?<div class="infodato[^"]*">(.*?)</div>', re.DOTALL
)
_RE_NUMERO = re.compile(r"[Nn]\.?\s*(\d+)")

_TIPI = TIPI_ATTO_DEFAULT


def _tipo_da_titolo(titolo: str) -> str:
    t = titolo.lower()
    for chiave, tipo in _TIPI:
        if chiave in t:
            return tipo
    return "atto"


def _parse_lista(html: str) -> list[tuple[str, str]]:
    """Estrae (url, titolo) di ogni documento dalla pagina di archivio tassonomico."""
    return [(url, _strip(unescape(titolo))) for url, titolo in _RE_CARD.findall(html)]


def _parse_dettaglio(html: str, url: str, codice_istat: str) -> AttoMetadato | None:
    m_data = _RE_DATA_AGGIORNAMENTO.search(html)
    if not m_data:
        return None
    titolo_m = re.search(r"<title>(.*?)(?:\s*&#8211;.*)?</title>", html, re.DOTALL)
    titolo = _strip(unescape(titolo_m.group(1))) if titolo_m else url
    m_descr = _RE_DESCRIZIONE.search(html)
    oggetto = _strip(unescape(m_descr.group(1))) if m_descr else titolo
    numero_m = _RE_NUMERO.search(titolo)

    return AttoMetadato(
        ente_codice_istat=codice_istat,
        tipo=_tipo_da_titolo(titolo),
        url_fonte=url,
        fonte_scraper=FONTE_SCRAPER,
        data_accesso=ora_utc(),
        numero=numero_m.group(1) if numero_m else None,
        oggetto=oggetto or titolo,
        data_pub=parse_data_iso(m_data.group(1)),
        cig=estrai_cig(oggetto),
    )


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------


def scarica_atti(
    max_pagine: int = 20,
    base_url: str = _BASE_URL,
    codice_istat: str = CODICE_ISTAT,
) -> Iterator[AttoMetadato]:
    """Scarica gli atti attualmente in pubblicazione sull'albo pretorio di Nicosia.

    Due fasi: (1) elenca URL/titoli dalle pagine di archivio tassonomico
    (stateless, `/page/N/`); (2) per ciascun documento, una fetch di dettaglio
    per data e descrizione complete (il CPT non espone API REST).
    """
    voci: list[tuple[str, str]] = []
    for pagina in range(1, max_pagine + 1):
        url = f"{base_url}{_ALBO_PATH}" if pagina == 1 else f"{base_url}{_ALBO_PATH}page/{pagina}/"
        req = urllib.request.Request(url, headers=_HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                html = r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                break
            raise
        pagina_voci = _parse_lista(html)
        if not pagina_voci:
            break
        voci.extend(pagina_voci)

    totale = 0
    for url, _titolo in voci:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode("utf-8", errors="replace")
        atto = _parse_dettaglio(html, url, codice_istat)
        if atto:
            totale += 1
            yield atto

    if totale == 0:
        logger.warning(
            "nicosia %s: 0 atti estratti — struttura HTML cambiata o portale in manutenzione?",
            base_url,
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
    codice_istat: str = CODICE_ISTAT,
    denominazione: str = "Comune di Nicosia",
) -> None:
    """Upsert del Comune di Nicosia nel DB (prerequisito per inserisci_atto)."""
    upsert_ente(
        conn,
        EnteMetadato(denominazione=denominazione, codice_istat=codice_istat, provincia="EN"),
    )
