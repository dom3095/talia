"""Spider generico per albi pretori su piattaforma Halley HSPromila (ASP.NET).

Variante Halley diversa da quella "EG" (`mc_p_ricerca.php`, vedi `halley.py`):
piattaforma ASP.NET ospitata su `hypersicapp.net`, un sottodominio/slug per
tenant. HTTP puro: la tabella atti è già presente nell'HTML della prima GET,
nessun rendering client-side necessario nonostante il messaggio "Attendere
prego" mostri un placeholder di caricamento nel markup.

Riusata da Sambuca di Sicilia e Santo Stefano Quisquina (TAL-49).

Limiti noti:
- Nessun link di dettaglio per singolo atto nella riga: si usa la pagina
  lista con un frammento `#<id_riga>` come url_fonte, per renderlo univoco
  per atto (la dedup DB si basa su `(ente_id, url_fonte)` — senza il
  frammento, tutti gli atti tranne il primo verrebbero scartati come
  duplicati: bug scoperto e corretto nella prima versione, 2026-07-08).
- Non è stato verificato un meccanismo di paginazione/backfill: la pagina
  mostra un unico blocco di atti.

Dati pubblici ai sensi del D.lgs. 33/2013.
"""

from __future__ import annotations

import http.cookiejar
import logging
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Iterator

from talia.modulo2_scraping.db import AttoMetadato, inserisci_atto
from talia.modulo2_scraping.utils import (
    TIPI_ATTO_DEFAULT,
    estrai_cig,
    estrai_cig_padre,
    ora_utc,
    parse_data_iso,
)
from talia.modulo2_scraping.utils import strip_html as _strip

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

FONTE_SCRAPER = "hspromila"

_HEADERS = {"User-Agent": "TALIA-bot/0.1 (civic transparency; https://github.com/dom3095/talia)"}

_RE_ROW = re.compile(r'<tr class="">(.*?)</tr>', re.DOTALL)
_RE_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)

# Seconda skin della stessa piattaforma, con righe `itemstyle`/`alternatingitemstyle`
# e 6 colonne invece di 10 (TAL-70): teneva a zero Floresta e Cianciana, che
# rispondevano 200 con la tabella piena.
_RE_ROW_LEGACY = re.compile(
    r'<tr class="(?:itemstyle|alternatingitemstyle)"[^>]*>(.*?)</tr>', re.DOTALL
)
_RE_TOTALE_LEGACY = re.compile(r"Trovati\s+(\d+)\s+risultati", re.IGNORECASE)

# La skin legacy pagina a 10 risultati; le pagine successive si raggiungono
# solo via postback ASP.NET (`__doPostBack`), non con un parametro in query
# string. Su Floresta sono 4 pagine per 40 atti, su Cianciana 7 per 70: senza
# paginazione si prenderebbero solo i 10 più recenti.
_RE_PAGER = re.compile(r'<tr class="pagerstyle"[^>]*>(.*?)</tr>', re.DOTALL)
# Tollerante a spaziatura e ordine degli attributi: legare la regex a uno
# spazio singolo fra `class` e `href` la rompeva al primo a capo nel markup.
_RE_PAGER_LINK = re.compile(
    r'<a[^>]*class="DG_PagerCellPageLink"[^>]*__doPostBack\(&#39;([^&]+)&#39;'
    r"[^>]*>\s*([^<]*?)\s*</a>",
    re.DOTALL,
)
_RE_INPUT = re.compile(r"<input[^>]*>", re.IGNORECASE)
_RE_ATTR_NAME = re.compile(r'name="([^"]+)"')
_RE_ATTR_VALUE = re.compile(r'value="([^"]*)"')
_RE_ATTR_TYPE = re.compile(r'type="([^"]+)"')

# Su alcuni tenant la GET non elenca nulla: la pagina è il **form di ricerca**
# ASP.NET e i risultati compaiono solo dopo averlo inviato (verificato con
# Playwright su Floresta: 0 righe alla GET, 13 dopo "Avvia ricerca"). Su altri
# — la maggioranza — la stessa GET restituisce già la tabella. Si distingue il
# caso "form da inviare" dal caso "albo davvero vuoto" leggendo il messaggio
# del portale, non contando le righe (TAL-70, stessa lezione di Caccamo/TAL-68).
_RE_NESSUN_RISULTATO = re.compile(r"non ha prodotto risultati", re.IGNORECASE)

_TIPI = TIPI_ATTO_DEFAULT


def _tipo_da_categoria(categoria: str) -> str:
    c = categoria.lower()
    for chiave, tipo in _TIPI:
        if chiave in c:
            return tipo
    return "atto"


def _atto(
    *,
    codice_istat: str,
    url: str,
    chiave: str,
    numero: str,
    oggetto: str,
    categoria: str,
    data_inizio: str,
    data_fine: str,
) -> AttoMetadato:
    oggetto = oggetto or None
    return AttoMetadato(
        ente_codice_istat=codice_istat,
        tipo=_tipo_da_categoria(categoria),
        url_fonte=f"{url}#{chiave}",
        fonte_scraper=FONTE_SCRAPER,
        data_accesso=ora_utc(),
        numero=numero or None,
        oggetto=oggetto,
        data_pub=parse_data_iso(data_inizio),
        data_scadenza=parse_data_iso(data_fine),
        cig=estrai_cig(oggetto),
        cig_padre=estrai_cig_padre(oggetto),
    )


def _parse_moderna(html: str, url: str, codice_istat: str) -> list[AttoMetadato]:
    """Skin corrente: righe `<tr class="">` con 10 celle."""
    atti = []
    for row_m in _RE_ROW.finditer(html):
        cells = [_strip(c.group(1)) for c in _RE_CELL.finditer(row_m.group(1))]
        # cells: [hidden, key, data_interna, numero_atto, numero_registro,
        #         oggetto, categoria, ente_ufficio, data_inizio, data_fine]
        if len(cells) < 10:
            continue
        atti.append(
            _atto(
                codice_istat=codice_istat,
                url=url,
                chiave=cells[1],
                numero=cells[4],
                oggetto=cells[5],
                categoria=cells[6],
                data_inizio=cells[8],
                data_fine=cells[9],
            )
        )
    return atti


def _parse_legacy(html: str, url: str, codice_istat: str) -> list[AttoMetadato]:
    """Skin più vecchia: righe `<tr class="itemstyle">` con 6 celle.

    Stessa piattaforma e stesso URL, template diverso — è ciò che teneva a
    zero Floresta e Cianciana: il portale rispondeva 200 con la tabella
    piena, ma `_RE_ROW` cercava solo `<tr class="">` (TAL-70).

    Niente cella-chiave nascosta qui: come frammento univoco di `url_fonte`
    si usa il numero di registro, che è progressivo per comune.
    """
    atti = []
    for row_m in _RE_ROW_LEGACY.finditer(html):
        cells = [_strip(c.group(1)) for c in _RE_CELL.finditer(row_m.group(1))]
        # cells: [numero_registro, oggetto, categoria, ente_ufficio,
        #         data_inizio, data_fine]
        if len(cells) < 6:
            continue
        atti.append(
            _atto(
                codice_istat=codice_istat,
                url=url,
                chiave=cells[0],
                numero=cells[0],
                oggetto=cells[1],
                categoria=cells[2],
                data_inizio=cells[4],
                data_fine=cells[5],
            )
        )
    return atti


def _parse_pagina(html: str, url: str, codice_istat: str) -> list[AttoMetadato]:
    return _parse_moderna(html, url, codice_istat) or _parse_legacy(html, url, codice_istat)


def campi_form(html: str) -> dict[str, str]:
    """Campi ``hidden``/``text`` del form ASP.NET, da rigiocare nella postback.

    Include `__VIEWSTATE`/`__VIEWSTATEGENERATOR`/`__AntiXsrfToken`: senza il
    round-trip di quei valori WebForms risponde 200 con zero righe invece di
    un errore.
    """
    campi: dict[str, str] = {}
    for m in _RE_INPUT.finditer(html):
        tag = m.group(0)
        nome = _RE_ATTR_NAME.search(tag)
        if not nome:
            continue
        tipo = _RE_ATTR_TYPE.search(tag)
        if tipo and tipo.group(1).lower() not in ("hidden", "text"):
            continue
        valore = _RE_ATTR_VALUE.search(tag)
        campi[nome.group(1)] = valore.group(1) if valore else ""
    return campi


def link_pagine(html: str) -> dict[str, str]:
    """Mappa ``numero pagina -> target __doPostBack`` letta dal pager legacy."""
    pager = _RE_PAGER.search(html)
    if not pager:
        return {}
    return {testo: target for target, testo in _RE_PAGER_LINK.findall(pager.group(1)) if testo}


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------


def scarica_atti(
    url: str, codice_istat: str, *, max_pagine: int = 20, _retry: int = 1, **_kwargs
) -> Iterator[AttoMetadato]:
    """Scarica gli atti attualmente elencati su un albo pretorio Halley HSPromila.

    Args:
        url:          URL completo della pagina di consultazione albo, es.
                      "https://servizionline.hspromilaprod.hypersicapp.net/
                      cmssambucadisicilia/portale/albopretorio/
                      albopretorioconsultazione.aspx?P=400".
        codice_istat: codice ISTAT a 6 cifre del comune.

    Nessuna paginazione nota: la pagina espone un unico blocco di atti.

    Un retry con backoff di 2s su timeout/connessione (stesso pattern di
    `jcitygov.py`/`halley.py`): l'host condiviso `hspromilaprod.hypersicapp.net`
    (decine di tenant sullo stesso dominio) va in timeout più spesso se colpito
    da richieste consecutive ravvicinate per comuni diversi nello stesso run —
    non un fallimento persistente per singolo tenant (verificato: stesso
    comune, stessa richiesta, riprovata isolata, risponde 200 senza problemi).
    Cattura anche `urllib.error.URLError` (non solo `TimeoutError`, a
    differenza della versione originale): host condiviso sotto carico può
    anche chiudere la connessione (`ConnectionResetError`/`RemoteDisconnected`,
    entrambe sottoclassi di `OSError` incapsulate da `URLError`), non solo
    andare in timeout — drift trovato in code review confrontando con
    `halley.py`, che già catturava entrambe per lo stesso scenario.
    """
    # Opener con cookie jar condiviso fra GET e POST: la postback ASP.NET
    # viene rifiutata (risponde 200 con zero righe) se non ritrova il cookie
    # di sessione ottenuto con la GET.
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    req = urllib.request.Request(url, headers=_HEADERS)
    for tentativo in range(_retry + 1):
        try:
            with opener.open(req, timeout=20) as r:
                html = r.read().decode("utf-8", errors="replace")
            break
        except (TimeoutError, urllib.error.URLError):
            if tentativo == _retry:
                raise
            time.sleep(2)
    atti = _parse_pagina(html, url, codice_istat)

    # Skin legacy: le pagine oltre la prima esistono solo via postback.
    if atti and link_pagine(html):
        visti = {a.url_fonte for a in atti}
        pagina_html = html
        for numero in range(2, max_pagine + 1):
            target = link_pagine(pagina_html).get(str(numero))
            if not target:
                break
            pagina_html = _postback(opener, url, pagina_html, target)
            if pagina_html is None:
                break
            nuovi = [
                a for a in _parse_pagina(pagina_html, url, codice_istat) if a.url_fonte not in visti
            ]
            if not nuovi:
                break
            visti.update(a.url_fonte for a in nuovi)
            atti.extend(nuovi)
            time.sleep(1)

    if not atti:
        vuoto = _RE_NESSUN_RISULTATO.search(html)
        logger.warning(
            "hspromila %s: 0 atti estratti — %s",
            url,
            "il portale dichiara nessun risultato (albo vuoto?)"
            if vuoto
            else "struttura HTML cambiata o portale in manutenzione?",
        )
    yield from atti


def _postback(
    opener: urllib.request.OpenerDirector, url: str, html: str, target: str
) -> str | None:
    """Esegue un `__doPostBack` verso `target` rigiocando lo stato del form."""
    campi = campi_form(html)
    if not campi:
        return None
    campi["__EVENTTARGET"] = target
    campi["__EVENTARGUMENT"] = ""
    req = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(campi).encode(),
        headers={**_HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with opener.open(req, timeout=45) as r:
            return r.read().decode("utf-8", errors="replace")
    except (TimeoutError, urllib.error.URLError) as exc:
        logger.warning("hspromila %s: paginazione fallita (%s)", url, exc)
        return None


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
