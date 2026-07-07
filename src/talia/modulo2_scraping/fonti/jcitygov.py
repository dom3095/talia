"""Spider generico per albi pretori su portale jCityGov (Maggioli Spa / Liferay).

Portali supportati: *.trasparenza-valutazione-merito.it
URL albo: https://{comune}.trasparenza-valutazione-merito.it/web/trasparenza/papca-g/-/papca

Flusso HTTP (session-based, nessun JS):
  1. GET  /web/trasparenza/papca-g/-/papca    → inizializza JSESSIONID
  2. POST eseguiFiltro (lifecycle=1)          → imposta filtro "tutto", risposta = pagina 1
  3. GET  mostraLista + paginationAction=NEXT → pagine successive; la sessione tiene il cursore

Struttura riga:
  <tr class="master-detail-list-line..." data-id="{id_pubblicazione}">
    <td class="categoria text"><span class="categoria_categoria">…</span>
                               <span class="categoria_sottocategoria">…</span></td>
    <td class="annonumero number">{anno}/{numero}</td>
    <td class="oggetto text">{oggetto}</td>
    <td>{dd/mm/yyyy}  {dd/mm/yyyy}</td>   ← data_pub  data_scadenza
    <td>{n_allegati}</td>
  </tr>

Dati pubblici ai sensi del D.lgs. 33/2013.
"""

from __future__ import annotations

import http.cookiejar
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from collections.abc import Iterable, Iterator
from html import unescape

from talia.modulo2_scraping.db import AttoMetadato, inserisci_atto
from talia.modulo2_scraping.utils import estrai_cig as _estrai_cig
from talia.modulo2_scraping.utils import ora_utc as _ora_utc
from talia.modulo2_scraping.utils import parse_data_iso as _data_iso

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

FONTE_SCRAPER = "jcitygov"
_PORTLET = "jcitygovalbopubblicazioni_WAR_jcitygovalbiportlet"
_ALBO_PATH = "/web/trasparenza/papca-g/-/papca"
_PAPCA_PATH = "/web/trasparenza/papca-g"
_DEFAULT_LIMIT = 200
_DEFAULT_DELAY = 0.5

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_RE_TAG = re.compile(r"<[^>]+>")
_RE_ROW = re.compile(
    r'<tr\s+class="master-detail-list-line[^"]*"\s+data-id="(\d+)">(.*?)</tr>',
    re.DOTALL | re.IGNORECASE,
)
_RE_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL | re.IGNORECASE)
_RE_SPAN_CAT = re.compile(
    r'<span class="categoria_categoria">(.*?)</span>.*?'
    r'<span class="categoria_sottocategoria">(.*?)</span>',
    re.DOTALL | re.IGNORECASE,
)
_RE_NEXT = re.compile(
    r'paginationAction=NEXT[^"\']*',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Utilità
# ---------------------------------------------------------------------------


def _strip(html: str) -> str:
    return " ".join(_RE_TAG.sub("", unescape(html)).split())


def _parse_tipo(cell_html: str) -> str:
    m = _RE_SPAN_CAT.search(cell_html)
    if m:
        cat = _strip(m.group(1))
        sub = _strip(m.group(2))
        return f"{cat} / {sub}".lower() if sub else cat.lower()
    return _strip(cell_html).lower() or "atto"


def _parse_date_cella(raw: str) -> tuple[str | None, str | None]:
    """Cella 'dd/mm/yyyy  dd/mm/yyyy' → (data_pub, data_scadenza) ISO.

    Usa findall per essere robusto rispetto al collasso degli spazi da _strip.
    """
    dates = re.findall(r"\d{2}/\d{2}/\d{4}", raw)
    d1 = _data_iso(dates[0]) if len(dates) > 0 else None
    d2 = _data_iso(dates[1]) if len(dates) > 1 else None
    return d1, d2


def _url_dettaglio(base_url: str, pub_id: str) -> str:
    return (
        f"{base_url}{_PAPCA_PATH}"
        f"?p_p_id={_PORTLET}"
        f"&_{_PORTLET}_id={pub_id}"
        f"&_{_PORTLET}_action=mostraDettaglio"
    )


# ---------------------------------------------------------------------------
# Parsing HTML pagina lista
# ---------------------------------------------------------------------------


def _parse_pagina(html: str, base_url: str, codice_istat: str) -> list[AttoMetadato]:
    # Alcuni tenant non hanno la colonna "Anno e Numero Registro": in quel caso
    # le celle sono [tipo, oggetto, periodo] invece di [tipo, numero, oggetto,
    # periodo] e senza questo controllo oggetto e date finiscono nei campi
    # sbagliati (successo con Castel di Iudica & co., run del 2026-07-07).
    ha_numero = "Anno e Numero" in html
    i_oggetto = 2 if ha_numero else 1
    i_date = 3 if ha_numero else 2

    atti = []
    for m in _RE_ROW.finditer(html):
        pub_id = m.group(1)
        row_html = m.group(2)
        celle = list(_RE_CELL.finditer(row_html))
        if len(celle) <= i_date:
            continue

        tipo = _parse_tipo(celle[0].group(1))
        numero_raw = _strip(celle[1].group(1)) if ha_numero else ""  # "2026/1031"
        oggetto = _strip(celle[i_oggetto].group(1)) or None
        data_pub, data_scad = _parse_date_cella(_strip(celle[i_date].group(1)))

        # Separa anno/numero dal formato "YYYY/NNNN"
        numero = None
        if "/" in numero_raw:
            _, _, n = numero_raw.rpartition("/")
            numero = n or None

        atti.append(AttoMetadato(
            ente_codice_istat=codice_istat,
            tipo=tipo,
            url_fonte=_url_dettaglio(base_url, pub_id),
            fonte_scraper=FONTE_SCRAPER,
            data_accesso=_ora_utc(),
            numero=numero,
            oggetto=oggetto,
            data_pub=data_pub,
            data_scadenza=data_scad,
            cig=_estrai_cig(oggetto),
        ))
    return atti


# ---------------------------------------------------------------------------
# HTTP: opener con cookie + eventuale skip SSL
# ---------------------------------------------------------------------------


def _build_opener(skip_ssl: bool = False) -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    handlers: list = [urllib.request.HTTPCookieProcessor(jar)]
    if skip_ssl:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        handlers.append(urllib.request.HTTPSHandler(context=ctx))
    return urllib.request.build_opener(*handlers)


def _fetch(opener, url: str, data: bytes | None = None, timeout: int = 30, _retry: int = 1) -> str:
    req = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": _USER_AGENT},
    )
    for attempt in range(_retry + 1):
        try:
            with opener.open(req, timeout=timeout) as r:
                enc = r.headers.get_content_charset("utf-8")
                return r.read().decode(enc, errors="replace")
        except TimeoutError:
            if attempt == _retry:
                raise
            time.sleep(2)


# ---------------------------------------------------------------------------
# API pubblica: scarica_atti
# ---------------------------------------------------------------------------


def scarica_atti(
    base_url: str,
    codice_istat: str,
    *,
    limit: int = _DEFAULT_LIMIT,
    delay: float = _DEFAULT_DELAY,
    categoria_id: str = "0",
    skip_ssl: bool = False,
    _opener=None,
) -> Iterator[AttoMetadato]:
    """Scarica atti dall'albo pretorio jCityGov di un comune.

    Args:
        base_url:     URL base del portale, es. "https://caltanissetta.trasparenza-valutazione-merito.it"
        codice_istat: codice ISTAT a 6 cifre del comune.
        limit:        numero massimo di atti da raccogliere (default 200).
        delay:        secondi di pausa tra le pagine (rate limiting).
        categoria_id: "0" = tutte le categorie; altro = filtro per categoria.
        skip_ssl:     True per ignorare errori SSL (es. Messina self-signed cert).
        _opener:      opener HTTP iniettabile per i test.
    """
    opener = _opener or _build_opener(skip_ssl=skip_ssl)
    base = base_url.rstrip("/")

    # 1. Setup sessione
    _fetch(opener, f"{base}{_ALBO_PATH}")

    # 2. Pagina 1 tramite eseguiFiltro (POST)
    filter_url = (
        f"{base}{_PAPCA_PATH}"
        f"?p_p_id={_PORTLET}&p_p_lifecycle=1&p_p_state=pop_up&p_p_mode=view"
        f"&_{_PORTLET}_action=eseguiFiltro&_{_PORTLET}_categoriaId={categoria_id}"
    )
    post_data = urllib.parse.urlencode({f"_{_PORTLET}_categoriaId": categoria_id}).encode()
    html = _fetch(opener, filter_url, data=post_data)

    raccolti = 0
    while raccolti < limit:
        atti = _parse_pagina(html, base, codice_istat)
        if not atti:
            break

        for atto in atti:
            if raccolti >= limit:
                return
            yield atto
            raccolti += 1

        # Controlla se c'è una pagina successiva
        if not _RE_NEXT.search(html):
            break

        time.sleep(delay)

        # 3. Pagine successive tramite paginationAction=NEXT (GET, lifecycle=0)
        next_url = (
            f"{base}{_PAPCA_PATH}"
            f"?p_p_id={_PORTLET}&p_p_lifecycle=0&p_p_state=pop_up&p_p_mode=view"
            f"&_{_PORTLET}_paginationAction=NEXT&_{_PORTLET}_action=mostraLista"
        )
        html = _fetch(opener, next_url)


# ---------------------------------------------------------------------------
# API pubblica: salva_atti
# ---------------------------------------------------------------------------


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
