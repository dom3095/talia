"""Spider generico per albi pretori su piattaforma URBI (Maggioli), variante Cloud.

Stessa piattaforma di Catania (`catania.py`, URBI self-hosted), riusata da
comuni ospitati su `cloud.urbi.it` sotto un DB_NAME diverso per tenant (Favara,
Raffadali — TAL-49). Flusso HTTP identico a Catania:

1. GET  <base>?DB_NAME=...&w3cbt=S                   → sessione
2. POST <base>?DB_NAME=...&w3cbt=S&StwEvent=910001    → prima pagina lista
3. POST <base>?...&StwEvent=9100030 (PaginaCorrente=N) → pagina N (10 atti/pagina)

L'albo ospita solo atti del comune stesso su cloud.urbi.it (a differenza di
Catania, che ospita anche atti di altri enti mittenti sullo stesso albo):
il filtro per `ente_mittente` resta comunque applicato per sicurezza.

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

from talia.modulo2_scraping.db import AttoMetadato, inserisci_atto
from talia.modulo2_scraping.utils import estrai_cig, estrai_cig_padre, ora_utc, parse_data_iso

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

FONTE_SCRAPER = "urbi"

_HEADERS = {"User-Agent": "TALIA-bot/0.1 (civic transparency; https://github.com/dom3095/talia)"}
_PAUSA_SECONDI = 1.0

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

# Alcuni tenant (es. Caccamo) rifiutano la ricerca con "Tipologia" vuota, che
# per tutti gli altri significa "Tutte". Il portale risponde 200 con un avviso
# e zero righe: senza riconoscerlo, lo scraper resta muto per sempre (Caccamo:
# 0 atti in 5 run consecutivi, dal 2026-07-14, senza mai un errore — TAL-68).
_RE_TIPOLOGIA_OBBLIGATORIA = re.compile(r"occorre selezionare la tipologia", re.I)
_RE_SELECT_TIPOLOGIA = re.compile(
    r'<select[^>]*name="Tipologia"[^>]*>(.*?)</select>', re.DOTALL | re.IGNORECASE
)
_RE_OPTION_VALUE = re.compile(r'<option[^>]*value="([^"]*)"')

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


def _url_dettaglio(base_url: str, qs_base: str, id_pubblica: str) -> str:
    return (
        f"{base_url}?{qs_base}&StwEvent=91000302"
        f"&IdMePubblica={id_pubblica}&curArchivio=&SOLCollegamentoAtti=S"
    )


def _parse_pagina(
    html: str, base_url: str, qs_base: str, codice_istat: str, ente_mittente: str
) -> tuple[list[AttoMetadato], int]:
    """Estrae gli atti dell'ente dalla pagina lista.

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
        if not ente_m or ente_m.group(1).strip().upper() != ente_mittente.upper():
            continue  # atto di altro ente ospitato sullo stesso albo
        oggetto_m = _RE_OGGETTO.search(row)
        oggetto = " ".join(unescape(oggetto_m.group(1)).split()) if oggetto_m else None
        pub_m = _RE_PUBBLICAZIONE.search(row)
        tipologia = _RE_TIPOLOGIA.search(row)
        atti.append(
            AttoMetadato(
                ente_codice_istat=codice_istat,
                tipo=_tipo_da_tipologia(tipologia.group(1) if tipologia else ""),
                url_fonte=_url_dettaglio(base_url, qs_base, id_m.group(1)),
                fonte_scraper=FONTE_SCRAPER,
                data_accesso=ora_utc(),
                numero=(pub_m.group(3).strip() if pub_m and pub_m.group(3) else None),
                oggetto=oggetto,
                data_pub=_data_iso(pub_m.group(1)) if pub_m else None,
                data_scadenza=_data_iso(pub_m.group(2)) if pub_m else None,
                cig=estrai_cig(oggetto),
                cig_padre=estrai_cig_padre(oggetto),
            )
        )
    return atti, righe


# ---------------------------------------------------------------------------
# Rete
# ---------------------------------------------------------------------------


def _post(opener: urllib.request.OpenerDirector, url: str, dati: dict[str, str]) -> str:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(dati).encode(), headers=_HEADERS)
    with opener.open(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def estrai_tipologie(html_form: str) -> list[str]:
    """Valori non vuoti della select "Tipologia" nella pagina di ricerca.

    Il valore vuoto (`Tutte`) è escluso di proposito: è esattamente quello che
    i tenant "esigenti" rifiutano, ed è la ricerca già tentata prima di
    arrivare qui.
    """
    select = _RE_SELECT_TIPOLOGIA.search(html_form)
    if not select:
        return []
    return [v for v in _RE_OPTION_VALUE.findall(select.group(1)) if v.strip()]


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------


def scarica_atti(
    base_url: str,
    qs_base: str,
    codice_istat: str,
    ente_mittente: str,
    *,
    max_pagine: int = 100,
) -> Iterator[AttoMetadato]:
    """Scarica gli atti in pubblicazione da un albo pretorio URBI (Cloud o self-hosted).

    Args:
        base_url:     URL del file .sto, es. "https://cloud.urbi.it/urbi/progs/urp/ur1ME001.sto".
        qs_base:      querystring fissa, es. "DB_NAME=wt00037115&w3cbt=S".
        codice_istat: codice ISTAT a 6 cifre del comune.
        ente_mittente: nome esatto dell'ente da tenere (es. "COMUNE DI FAVARA"),
                       per scartare atti di altri enti ospitati sullo stesso albo.
        max_pagine:   numero massimo di pagine da scaricare.

    Si ferma alla prima pagina senza righe o quando una pagina ripete gli
    stessi id della precedente (il portale ripropone l'ultima pagina se
    PaginaCorrente supera il totale).
    """
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    req = urllib.request.Request(f"{base_url}?{qs_base}", headers=_HEADERS)
    with opener.open(req, timeout=30) as r:
        html_form = r.read().decode("utf-8", errors="replace")

    totale = 0
    scartati = 0
    visti: set[str] = set()
    tipologia_richiesta = False

    def _ricerca(form: dict[str, str]) -> Iterator[AttoMetadato]:
        """Una ricerca completa (POST 910001 + paginazione), con i suoi contatori."""
        nonlocal totale, scartati, tipologia_richiesta
        ids_precedenti: set[str] = set()
        for pagina in range(1, max_pagine + 1):
            if pagina == 1:
                html = _post(opener, f"{base_url}?{qs_base}&StwEvent=910001", form)
                if _RE_TIPOLOGIA_OBBLIGATORIA.search(html):
                    tipologia_richiesta = True
                    return
            else:
                html = _post(
                    opener,
                    f"{base_url}?{qs_base}&StwEvent=9100030",
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
            atti, righe = _parse_pagina(html, base_url, qs_base, codice_istat, ente_mittente)
            if righe == 0:
                break
            scartati += righe - len(atti)
            # Le tipologie partizionano l'albo, ma un id ripetuto tra due
            # ricerche produrrebbe comunque un duplicato: si filtra qui.
            nuovi = [a for a in atti if a.url_fonte not in visti]
            visti.update(a.url_fonte for a in nuovi)
            totale += len(nuovi)
            yield from nuovi
            time.sleep(_PAUSA_SECONDI)

    yield from _ricerca(_FORM_RICERCA)

    if tipologia_richiesta:
        # Il tenant pretende una tipologia esplicita: si riprova una ricerca
        # per ciascuna, invece di arrendersi in silenzio. La condizione è il
        # messaggio del portale, non "zero atti": un albo genuinamente vuoto
        # non deve far partire 26 ricerche inutili ad ogni run.
        tipologie = estrai_tipologie(html_form)
        if tipologie:
            logger.info(
                "urbi %s: ricerca senza tipologia vuota — riprovo su %d tipologie",
                base_url,
                len(tipologie),
            )
            for t in tipologie:
                for atto in _ricerca({**_FORM_RICERCA, "Tipologia": t}):
                    # Marca la tipologia di provenienza: il runner usa questo
                    # confine per azzerare il contatore dello stop-on-known.
                    # Senza, la prima tipologia tutta già nota interromperebbe
                    # la scansione e le tipologie successive non verrebbero
                    # mai raggiunte — lo scraper tornerebbe muto dal secondo
                    # run in poi, in modo ancora più subdolo di prima.
                    atto.metadati = {**atto.metadati, "tipologia_ricerca": t}
                    yield atto

    if scartati:
        logger.info("urbi %s: scartati %d atti di altri enti mittenti", base_url, scartati)
    if totale == 0:
        logger.warning(
            "urbi %s: 0 atti estratti — struttura HTML cambiata o portale in manutenzione?",
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
