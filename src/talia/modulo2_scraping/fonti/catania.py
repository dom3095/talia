"""Spider per l'albo pretorio del Comune di Catania (URBI/Maggioli).

URL base: https://servizionline.comune.catania.it (DB_NAME=wt00041571)

Il portale è un wizard "stepper" URBI (.sto) ma il flusso è HTTP puro,
nessun JavaScript client-side necessario:

1. GET  ur1ME001.sto?DB_NAME=...&w3cbt=S            → sessione
2. POST ...&StwEvent=910001  (form step 1→2)         → prima pagina lista
3. POST ...&StwEvent=9100030 (ElencoPubblicazioni_PaginaCorrente=N)
   → pagina N della lista (10 atti/pagina)

Ogni riga della lista contiene già tutti i metadati (ente mittente,
tipologia, oggetto, periodo di pubblicazione, numero registro) e l'id
IdMePubblica, con cui si costruisce l'URL di dettaglio stabile (GET).

L'albo ospita anche atti di ALTRI enti (es. altri comuni): vengono
scartati, si tengono solo quelli con mittente "COMUNE DI CATANIA".
Come Trapani, l'albo espone solo atti in pubblicazione (~15 gg):
serve scraping continuo per non perdere atti.

Codice ISTAT Catania: 087015

Dati pubblici ai sensi del D.lgs. 33/2013.
"""

from __future__ import annotations

import http.cookiejar
import logging
import re
import sqlite3
import time
import urllib.parse
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

FONTE_SCRAPER = "catania"
CODICE_ISTAT = "087015"
ENTE_MITTENTE = "COMUNE DI CATANIA"

_BASE = "https://servizionline.comune.catania.it/urbi/progs/urp/ur1ME001.sto"
_QS_COMUNE = "DB_NAME=wt00041571&w3cbt=S"

_HEADERS = {"User-Agent": "TALIA-bot/0.1 (civic transparency; https://github.com/dom3095/talia)"}

_PAUSA_SECONDI = 1.0

# Form step 1→2 del wizard (ricerca senza filtri: il filtro data del portale
# è inaffidabile — ritorna 0 atti — quindi si enumera tutto e si pagina).
_FORM_RICERCA = {
    "Stepper_StepAttivo": "1",
    "Stepper_StepAttivoNome": "Opzioni di ricerca",
    "Stepper_NextStep": "2",
    "Stepper_NextStepNome": "",
    "idTreeView1": "TreeView_Id",
    "SOLCollegamentoAtti": "S",
    "RifAttoAnno": "",
    "DaData": "",
    "AData": "",
    "Tipologia": "",
    "EnteMittente": "",
    "Oggetto": "",
    "OggettoType": "%like%",
}

_RE_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL)
_RE_ID = re.compile(r"IdMePubblica=(\d+)")
_RE_ENTE = re.compile(r"Ente Mittente\s*<strong>([^<]*)</strong>")
_RE_TIPOLOGIA = re.compile(r"Tipologia Atto\s*<strong>([^<]*)</strong>")
_RE_OGGETTO = re.compile(r"<br><strong>(.*?)</strong>\s*<br>", re.DOTALL)
_RE_PUBBLICAZIONE = re.compile(
    r"in pubblicazione dal\s+([\d-]+)\s+al\s+([\d-]+)(?:\s*\(reg\.\s*([^)]+)\))?"
)

# Tipologia URBI → tipo atto TALIA
_TIPI = (
    ("ordinanza", "ordinanza"),
    ("delibera", "delibera"),
    ("determin", "determina"),
    ("concors", "concorso"),
    ("gara", "bando"),
    ("appalt", "bando"),
    ("band", "bando"),
    ("decret", "decreto"),
)


# ---------------------------------------------------------------------------
# Parsing (testabile offline con fixture)
# ---------------------------------------------------------------------------


def _tipo_da_tipologia(tipologia: str) -> str:
    t = tipologia.lower()
    for chiave, tipo in _TIPI:
        if chiave in t:
            return tipo
    return "atto"


def _data_iso(s: str | None) -> str | None:
    # il portale usa dd-mm-yyyy: normalizza a dd/mm/yyyy per parse_data_iso
    return parse_data_iso(s.replace("-", "/")) if s else None


def _url_dettaglio(id_pubblica: str) -> str:
    return (
        f"{_BASE}?{_QS_COMUNE}&StwEvent=91000302"
        f"&IdMePubblica={id_pubblica}&curArchivio=&SOLCollegamentoAtti=S"
    )


def _parse_pagina(html: str) -> tuple[list[AttoMetadato], int]:
    """Estrae gli atti del COMUNE DI CATANIA dalla pagina lista.

    Ritorna (atti, n_righe_totali): n_righe_totali conta anche gli atti di
    altri enti mittenti, per distinguere "pagina vuota" da "tutti scartati".
    """
    atti: list[AttoMetadato] = []
    righe = 0
    for row_m in _RE_ROW.finditer(html):
        row = row_m.group(1)
        id_m = _RE_ID.search(row)
        if not id_m:
            continue  # header o righe di servizio
        righe += 1
        ente_m = _RE_ENTE.search(row)
        if not ente_m or ente_m.group(1).strip().upper() != ENTE_MITTENTE:
            continue  # atto di altro ente ospitato sull'albo di Catania
        oggetto_m = _RE_OGGETTO.search(row)
        oggetto = " ".join(unescape(oggetto_m.group(1)).split()) if oggetto_m else None
        pub_m = _RE_PUBBLICAZIONE.search(row)
        tipologia = _RE_TIPOLOGIA.search(row)
        atti.append(
            AttoMetadato(
                ente_codice_istat=CODICE_ISTAT,
                tipo=_tipo_da_tipologia(tipologia.group(1) if tipologia else ""),
                url_fonte=_url_dettaglio(id_m.group(1)),
                fonte_scraper=FONTE_SCRAPER,
                data_accesso=ora_utc(),
                numero=(pub_m.group(3).strip() if pub_m and pub_m.group(3) else None),
                oggetto=oggetto,
                data_pub=_data_iso(pub_m.group(1)) if pub_m else None,
                data_scadenza=_data_iso(pub_m.group(2)) if pub_m else None,
                cig=estrai_cig(oggetto),
            )
        )
    return atti, righe


# ---------------------------------------------------------------------------
# Rete
# ---------------------------------------------------------------------------


def _post(opener: urllib.request.OpenerDirector, url: str, dati: dict[str, str]) -> str:
    req = urllib.request.Request(
        url, data=urllib.parse.urlencode(dati).encode(), headers=_HEADERS
    )
    with opener.open(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------


def scarica_atti(max_pagine: int = 100) -> Iterator[AttoMetadato]:
    """Scarica gli atti in pubblicazione dall'albo pretorio di Catania.

    Richiede rete. Per i test usare _parse_pagina() con HTML fixture.
    Si ferma alla prima pagina senza righe o quando una pagina ripete
    gli stessi id della precedente (il portale ripropone l'ultima pagina
    se PaginaCorrente supera il totale).
    """
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    req = urllib.request.Request(f"{_BASE}?{_QS_COMUNE}", headers=_HEADERS)
    with opener.open(req, timeout=30) as r:
        r.read()

    totale = 0
    scartati = 0
    ids_precedenti: set[str] = set()
    for pagina in range(1, max_pagine + 1):
        if pagina == 1:
            html = _post(opener, f"{_BASE}?{_QS_COMUNE}&StwEvent=910001", _FORM_RICERCA)
        else:
            html = _post(
                opener,
                f"{_BASE}?{_QS_COMUNE}&StwEvent=9100030",
                {
                    "Stepper_StepAttivo": "2",
                    "ElencoPubblicazioni_DimensionePagina": "10",
                    "ElencoPubblicazioni_PaginaCorrente": str(pagina),
                },
            )
        ids_pagina = set(_RE_ID.findall(html))
        if ids_pagina and ids_pagina == ids_precedenti:
            break  # oltre l'ultima pagina il portale ripete l'ultima
        ids_precedenti = ids_pagina
        atti, righe = _parse_pagina(html)
        if righe == 0:
            break
        scartati += righe - len(atti)
        totale += len(atti)
        yield from atti
        time.sleep(_PAUSA_SECONDI)

    if scartati:
        logger.info("Catania: scartati %d atti di altri enti mittenti", scartati)
    if totale == 0:
        logger.warning(
            "Catania: 0 atti estratti — struttura HTML cambiata o portale in manutenzione?"
        )


def salva_atti(
    atti: Iterable[AttoMetadato],
    conn: sqlite3.Connection,
) -> dict[str, int]:
    """Persiste gli atti nel DB; ritorna {'inseriti': N, 'duplicati': M}."""
    inseriti = 0
    duplicati = 0
    for atto in atti:
        if inserisci_atto(conn, atto) is not None:
            inseriti += 1
        else:
            duplicati += 1
    conn.commit()
    return {"inseriti": inseriti, "duplicati": duplicati}


def prepara_ente(conn: sqlite3.Connection) -> None:
    """Upsert del Comune di Catania nel DB (prerequisito per inserisci_atto)."""
    upsert_ente(conn, EnteMetadato(
        denominazione="Comune di Catania",
        codice_istat=CODICE_ISTAT,
        provincia="CT",
    ))
