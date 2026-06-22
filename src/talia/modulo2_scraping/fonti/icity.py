"""Spider per albi pretori basati su software iCity/iPublic (Maggioli Spa).

iCity è uno dei software più diffusi tra i comuni siciliani (e italiani).
URL tipica lista: https://<comune>/icity/albo/albo.do?page=N
URL tipica dettaglio: https://<comune>/icity/albo/detail.do?id=XXXXX

Zero dipendenze esterne: usa html.parser e urllib dalla stdlib.

Disclaimer: i dati raccolti sono atti pubblici ai sensi del D.lgs. 33/2013.
Rispettare sempre robots.txt e un rate limiting adeguato.
"""

from __future__ import annotations

import re
import sqlite3
import time
import urllib.parse
import urllib.request
from collections.abc import Iterable, Iterator
from datetime import datetime, timezone
from html.parser import HTMLParser

from talia.modulo2_scraping.db import AttoMetadato, inserisci_atto, upsert_ente, EnteMetadato

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

FONTE_SCRAPER = "icity"
_DEFAULT_DELAY = 1.0    # secondi tra le richieste HTTP
_DEFAULT_LIMIT = 200    # atti massimi per singolo run
_USER_AGENT = "TALIA-bot/0.1 (civic transparency; https://github.com/dom3095/talia)"

_RE_CIG = re.compile(r'\bCIG\s*[:\-]?\s*([A-Z0-9]{10})\b', re.IGNORECASE)
_RE_IMPORTO = re.compile(r'€\s*([\d.]+,\d{2})')


# ---------------------------------------------------------------------------
# Utilità
# ---------------------------------------------------------------------------


def _data_iso(s: str | None) -> str | None:
    """Converte data italiana "dd/mm/yyyy" in ISO-8601 "yyyy-mm-dd"."""
    if not s:
        return None
    s = s.strip()
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', s)
    if m:
        return f"{m.group(3)}-{m.group(2):>02}-{m.group(1):>02}"
    return None


def _estrai_cig(testo: str | None) -> str | None:
    """Restituisce il primo CIG trovato nel testo, o None."""
    if not testo:
        return None
    m = _RE_CIG.search(testo)
    return m.group(1).upper() if m else None


def _estrai_importo(testo: str | None) -> float | None:
    """Restituisce il primo importo in euro trovato nel testo, o None."""
    if not testo:
        return None
    m = _RE_IMPORTO.search(testo)
    if not m:
        return None
    try:
        return float(m.group(1).replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _ora_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Parser HTML: lista atti
# ---------------------------------------------------------------------------


class _ListaParser(HTMLParser):
    """Estrae le righe della tabella atti dalla pagina lista iCity."""

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.righe: list[dict[str, str | None]] = []
        # stato interno
        self._in_tbody = False
        self._in_tr = False
        self._in_td = False
        self._celle: list[str] = []
        self._cur_testo = ""
        self._cur_link: str | None = None

    def handle_starttag(self, tag: str, attrs: list) -> None:
        d = dict(attrs)
        if tag == "tbody":
            self._in_tbody = True
        elif tag == "tr" and self._in_tbody:
            self._in_tr = True
            self._celle = []
            self._cur_link = None
        elif tag in ("td", "th") and self._in_tr:
            self._in_td = True
            self._cur_testo = ""
        elif tag == "a" and self._in_tr:
            href = d.get("href", "")
            if href and ("detail" in href or "id=" in href):
                self._cur_link = urllib.parse.urljoin(self.base_url, href)

    def handle_data(self, data: str) -> None:
        if self._in_td:
            self._cur_testo += data

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._in_td:
            self._celle.append(self._cur_testo.strip())
            self._in_td = False
        elif tag == "tr" and self._in_tr:
            if self._cur_link and self._celle:
                self.righe.append({
                    "url_dettaglio": self._cur_link,
                    "numero": self._celle[0] if len(self._celle) > 0 else None,
                    "tipo": self._celle[1] if len(self._celle) > 1 else None,
                    "oggetto": self._celle[2] if len(self._celle) > 2 else None,
                    "data_pub_raw": self._celle[3] if len(self._celle) > 3 else None,
                    "data_scad_raw": self._celle[4] if len(self._celle) > 4 else None,
                })
            self._in_tr = False
        elif tag == "tbody":
            self._in_tbody = False


def _parse_lista(html: str, base_url: str) -> list[dict[str, str | None]]:
    """Estrae le voci dalla pagina lista albo iCity.

    Ritorna una lista di dict con chiavi:
    url_dettaglio, numero, tipo, oggetto, data_pub_raw, data_scad_raw.
    """
    parser = _ListaParser(base_url)
    parser.feed(html)
    return parser.righe


# ---------------------------------------------------------------------------
# Parser HTML: dettaglio atto
# ---------------------------------------------------------------------------


class _DettaglioParser(HTMLParser):
    """Estrae i metadati dalla pagina di dettaglio di un atto iCity."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.campi: dict[str, str] = {}
        self.url_pdf: str | None = None
        # stato
        self._in_dt = False
        self._in_dd = False
        self._cur_dt = ""
        self._cur_dd = ""

    def handle_starttag(self, tag: str, attrs: list) -> None:
        d = dict(attrs)
        if tag == "dt":
            self._in_dt = True
            self._cur_dt = ""
        elif tag == "dd":
            self._in_dd = True
            self._cur_dd = ""
        elif tag == "a":
            href = d.get("href", "")
            cls = d.get("class", "")
            if href and (".pdf" in href.lower() or "getDoc" in href or "scarica" in cls.lower()):
                self.url_pdf = href

    def handle_data(self, data: str) -> None:
        if self._in_dt:
            self._cur_dt += data
        elif self._in_dd:
            self._cur_dd += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "dt":
            self._in_dt = False
            self._cur_dt = self._cur_dt.strip().lower()
        elif tag == "dd":
            self._in_dd = False
            if self._cur_dt:
                self.campi[self._cur_dt] = self._cur_dd.strip()
            self._cur_dd = ""


def _parse_dettaglio(html: str, url: str, codice_istat: str) -> AttoMetadato:
    """Estrae i metadati completi dalla pagina di dettaglio di un atto iCity.

    Args:
        html: contenuto HTML della pagina di dettaglio.
        url: URL della pagina (usato come url_fonte).
        codice_istat: codice ISTAT del comune (6 cifre).
    """
    p = _DettaglioParser()
    p.feed(html)
    c = p.campi

    # Mappatura flessibile dei nomi dei campi iCity (variano tra versioni)
    def _get(*chiavi: str) -> str | None:
        for k in chiavi:
            v = c.get(k) or c.get(k.replace(" ", " "))
            if v:
                return v
        return None

    oggetto = _get("oggetto", "titolo", "descrizione")

    return AttoMetadato(
        ente_codice_istat=codice_istat,
        tipo=(_get("tipo atto", "tipo") or "determina").lower(),
        url_fonte=url,
        fonte_scraper=FONTE_SCRAPER,
        data_accesso=_ora_utc(),
        numero=_get("numero", "n. pubbl.", "num."),
        data_atto=_data_iso(_get("data atto", "data delibera", "data determina")),
        data_pub=_data_iso(_get("data pubblicazione", "pubbl. dal", "data inizio")),
        data_scadenza=_data_iso(_get("data scadenza", "pubbl. al", "data fine")),
        url_pdf=urllib.parse.urljoin(url, p.url_pdf) if p.url_pdf else None,
        cig=_estrai_cig(oggetto),
        oggetto=oggetto,
        importo_euro=_estrai_importo(oggetto),
    )


# ---------------------------------------------------------------------------
# Recupero pagine (usato solo in produzione, skippato nei test)
# ---------------------------------------------------------------------------


def _fetch(url: str, timeout: int = 15) -> str:
    """Scarica una pagina HTTP e ne restituisce il testo."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        encoding = resp.headers.get_content_charset("utf-8")
        return resp.read().decode(encoding)


# ---------------------------------------------------------------------------
# API pubblica: scarica_atti
# ---------------------------------------------------------------------------


def scarica_atti(
    base_url: str,
    codice_istat: str,
    *,
    limit: int = _DEFAULT_LIMIT,
    delay: float = _DEFAULT_DELAY,
    _fetch_fn=_fetch,          # iniettabile nei test
) -> Iterator[AttoMetadato]:
    """Genera metadati degli atti dall'albo pretorio iCity di un comune.

    Args:
        base_url: URL base del portale iCity, es. "https://comune.palermo.it/icity/albo"
        codice_istat: codice ISTAT a 6 cifre del comune, es. "082053"
        limit: numero massimo di atti da raccogliere.
        delay: secondi di attesa tra le pagine (rate limiting).
        _fetch_fn: funzione HTTP iniettabile per i test.

    Yields:
        AttoMetadato per ogni atto trovato.
    """
    lista_url = base_url.rstrip("/") + "/albo.do"
    raccolti = 0
    pagina = 1

    while raccolti < limit:
        url_pagina = f"{lista_url}?page={pagina}"
        html = _fetch_fn(url_pagina)
        righe = _parse_lista(html, base_url)

        if not righe:
            break

        for riga in righe:
            if raccolti >= limit:
                return
            url_det = riga["url_dettaglio"]
            if not url_det:
                continue
            html_det = _fetch_fn(url_det)
            atto = _parse_dettaglio(html_det, url_det, codice_istat)
            yield atto
            raccolti += 1
            time.sleep(delay)

        pagina += 1
        time.sleep(delay)


# ---------------------------------------------------------------------------
# API pubblica: salva_atti
# ---------------------------------------------------------------------------


def salva_atti(
    atti: Iterable[AttoMetadato],
    conn: sqlite3.Connection,
) -> dict[str, int]:
    """Persiste gli atti nel DB e ritorna un contatore degli esiti.

    Returns:
        dict con chiavi 'inseriti' e 'duplicati'.
    """
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
