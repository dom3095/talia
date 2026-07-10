"""Spider per l'albo pretorio del Comune di Palermo (SISPI, JSP).

URL base: https://albopretorio.comune.palermo.it

Contrariamente alla nota storica ("Playwright obbligatorio"), il portale serve
HTML statico lato server: basta HTTP puro con cookie di sessione (JSESSIONID).
Il flusso è stateful:

1. GET /                                  → sessione + cookie
2. GET home.jsp?...info=servizi.jsp...    → card delle categorie documentali
3. GET home.jsp?...scelta_tipo_documento  → URL push reale della categoria
   (i parametri TD del menu NON coincidono con quelli del push: vanno scoperti,
   es. menu TD=20 → push TD=2010)
4. GET  /albopretorio/pu/push-tabella-delibere.do?...&TD=<td>&TDDES=<descr>
   → prima pagina della tabella (10 righe)
5. POST /albopretorio/dbmanager/tabella-lista-piu.do (form 'passaggio')
   → pagina successiva (dipende dallo stato di sessione: mai interleave
   di categorie sulla stessa sessione)

Limite noto: il dettaglio atto (tabella-modifica.do?row=N) è relativo alla
pagina corrente della sessione, quindi NON è un URL stabile. Come url_fonte
si usa l'URL della lista di categoria + fragment con il numero di protocollo.

Codice ISTAT Palermo: 082053

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

FONTE_SCRAPER = "palermo"
CODICE_ISTAT = "082053"

_BASE_URL = "https://albopretorio.comune.palermo.it"
_SERVIZI_PATH = "/albopretorio/jsp/home.jsp?modo=info&info=servizi.jsp&ARECOD=70&SERCOD=-1"
_LISTA_PIU_PATH = "/albopretorio/dbmanager/tabella-lista-piu.do"

_HEADERS = {"User-Agent": "TALIA-bot/0.1 (civic transparency; https://github.com/dom3095/talia)"}

_PAUSA_SECONDI = 1.0  # cortesia verso il server tra richieste di pagina

# Card categoria in servizi.jsp: titolo + onclick verso scelta_tipo_documento.jsp
_RE_CATEGORIA = re.compile(
    r"<h5[^>]*class='card-title[^>]*>([^<]+)</h5>.*?"
    r"location\.href='([^']*scelta_tipo_documento\.jsp[^']*)'",
    re.DOTALL,
)
# In scelta_tipo_documento.jsp: URL push reale della tabella
_RE_PUSH = re.compile(r"href\s*=\s*'([^']*push-tabella-delibere\.do[^']*)'")
_RE_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL)
_RE_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)
_RE_DETTAGLIO = re.compile(r"tabella-modifica\.do\?row=\d+")
_RE_PAGINE = re.compile(r"pagina\s+(\d+)\s+di\s+(\d+)", re.IGNORECASE)
_RE_HIDDEN = re.compile(r"<input[^>]+type='hidden'[^>]+name='([^']+)'[^>]+value='([^']*)'")
_RE_TAG = re.compile(r"<[^>]+>")

# Etichetta categoria → tipo atto normalizzato
_TIPO_DA_CATEGORIA = {
    "delibere": "delibera",
    "determinazioni dirigenziali": "determina",
    "determinazioni/ord. sindacali": "ordinanza",
    "avvisi e bandi di concorso": "concorso",
    "bandi, avvisi, gare di appalti ed esiti": "bando",
    "avvisi ed atti diversi": "avviso",
    "avvisi ed atti di altri enti": "avviso",
    "convocazioni": "convocazione",
    "concessione": "concessione",
    "pubblicazioni di matrimonio": "matrimonio",
    "documento generico": "atto",
}

# Categorie rilevanti per i red flags TALIA (default: niente matrimoni ecc.)
CATEGORIE_DEFAULT = ("delibera", "determina", "ordinanza", "concorso", "bando")


# ---------------------------------------------------------------------------
# Parsing (testabile offline con fixture)
# ---------------------------------------------------------------------------


def _strip(html: str) -> str:
    return " ".join(_RE_TAG.sub("", unescape(html)).split())


def _parse_categorie(html: str) -> list[tuple[str, str]]:
    """Estrae (etichetta, url_scelta_tipo) dalle card di servizi.jsp."""
    return [(_strip(label), unescape(url)) for label, url in _RE_CATEGORIA.findall(html)]


def _parse_pagina(html: str, url_lista: str, tipo: str) -> list[AttoMetadato]:
    """Estrae gli atti dalle righe della tabella albo.

    Layout riga dati: [indice+link dettaglio, numero, data, oggetto,
    inizio pubblicazione, fine pubblicazione].
    """
    atti = []
    for row_m in _RE_ROW.finditer(html):
        row_html = row_m.group(1)
        if not _RE_DETTAGLIO.search(row_html):
            continue  # header, conteggio righe, righe di servizio
        cells = [_strip(c.group(1)) for c in _RE_CELL.finditer(row_html)]
        if len(cells) < 6:
            continue
        numero = cells[1] or None
        oggetto = cells[3] or None
        atti.append(
            AttoMetadato(
                ente_codice_istat=CODICE_ISTAT,
                tipo=tipo,
                url_fonte=f"{url_lista}#prot-{numero}" if numero else url_lista,
                fonte_scraper=FONTE_SCRAPER,
                data_accesso=ora_utc(),
                numero=numero,
                oggetto=oggetto,
                data_atto=parse_data_iso(cells[2]),
                data_pub=parse_data_iso(cells[4]),
                data_scadenza=parse_data_iso(cells[5]),
                cig=estrai_cig(oggetto),
            )
        )
    return atti


def _parse_paginazione(html: str) -> tuple[int, int]:
    """Ritorna (pagina_corrente, pagine_totali); (1, 1) se assente."""
    m = _RE_PAGINE.search(html)
    return (int(m.group(1)), int(m.group(2))) if m else (1, 1)


def _parse_hidden(html: str) -> dict[str, str]:
    """Campi hidden del form 'passaggio' (necessari al POST di paginazione)."""
    return dict(_RE_HIDDEN.findall(html))


# ---------------------------------------------------------------------------
# Rete
# ---------------------------------------------------------------------------


def _apri_sessione() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    _get(opener, _BASE_URL + "/")  # imposta JSESSIONID e cookie CSRF
    return opener


def _get(opener: urllib.request.OpenerDirector, url: str) -> str:
    req = urllib.request.Request(url, headers=_HEADERS)
    with opener.open(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def _post(opener: urllib.request.OpenerDirector, url: str, dati: dict[str, str]) -> str:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(dati).encode(), headers=_HEADERS)
    with opener.open(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def _scopri_categorie(opener: urllib.request.OpenerDirector) -> dict[str, str]:
    """Ritorna {tipo_normalizzato: url_push_assoluto} scoprendo il menu reale.

    Passa dalla pagina servizi e da scelta_tipo_documento perché i parametri
    TD delle card non coincidono con quelli dell'URL push effettivo.
    """
    categorie: dict[str, str] = {}
    html = _get(opener, _BASE_URL + _SERVIZI_PATH)
    for label, url_scelta in _parse_categorie(html):
        tipo = _TIPO_DA_CATEGORIA.get(label.lower())
        if tipo is None:
            logger.info("Palermo: categoria non mappata ignorata: %r", label)
            continue
        url_scelta = urllib.parse.urljoin(_BASE_URL + "/albopretorio/jsp/", url_scelta)
        push_m = _RE_PUSH.search(_get(opener, url_scelta))
        if not push_m:
            logger.warning("Palermo: push URL non trovato per categoria %r", label)
            continue
        url_push = urllib.parse.urljoin(url_scelta, unescape(push_m.group(1)))
        # il portale emette TDDES con spazi letterali: vanno percent-encoded
        url_push = urllib.parse.quote(url_push, safe=":/?&=%")
        # una categoria può mappare sullo stesso tipo: tieni la prima
        categorie.setdefault(tipo, url_push)
        time.sleep(_PAUSA_SECONDI)
    return categorie


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------


def scarica_atti(
    max_pagine: int = 100,
    categorie: Iterable[str] = CATEGORIE_DEFAULT,
) -> Iterator[AttoMetadato]:
    """Scarica atti dall'albo pretorio di Palermo.

    max_pagine è il tetto complessivo (10 atti/pagina), ripartito in
    sequenza sulle categorie richieste. Richiede rete; per i test usare
    _parse_pagina() e le altre funzioni pure con HTML fixture.
    """
    opener = _apri_sessione()
    disponibili = _scopri_categorie(opener)
    mancanti = set(categorie) - set(disponibili)
    if mancanti:
        logger.warning("Palermo: categorie richieste non trovate nel menu: %s", mancanti)

    pagine_lette = 0
    totale_atti = 0
    for tipo in categorie:
        url_push = disponibili.get(tipo)
        if url_push is None or pagine_lette >= max_pagine:
            continue
        # il GET del push resetta lo stato tabella della sessione sulla categoria
        html = _get(opener, url_push)
        while True:
            atti = _parse_pagina(html, url_push, tipo)
            yield from atti
            totale_atti += len(atti)
            pagine_lette += 1
            corrente, totali = _parse_paginazione(html)
            if not atti or corrente >= totali or pagine_lette >= max_pagine:
                break
            time.sleep(_PAUSA_SECONDI)
            html = _post(opener, _BASE_URL + _LISTA_PIU_PATH, _parse_hidden(html))

    if totale_atti == 0:
        logger.warning(
            "Palermo: 0 atti estratti (%d pagine lette) — struttura HTML cambiata "
            "o albo irraggiungibile?",
            pagine_lette,
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
    """Upsert del Comune di Palermo nel DB (prerequisito per inserisci_atto)."""
    upsert_ente(
        conn,
        EnteMetadato(
            denominazione="Comune di Palermo",
            codice_istat=CODICE_ISTAT,
            provincia="PA",
        ),
    )
