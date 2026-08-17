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

import logging
import re
import sqlite3
import time
import urllib.error
import urllib.request
from collections.abc import Iterable, Iterator

from talia.modulo2_scraping.db import AttoMetadato, inserisci_atto
from talia.modulo2_scraping.utils import estrai_cig, estrai_cig_padre, ora_utc, parse_data_iso
from talia.modulo2_scraping.utils import strip_html as _strip

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

FONTE_SCRAPER = "halley"
_RICERCA_PATH = "/mc/mc_p_ricerca.php"
_DETTAGLIO_PATH = "/mc/mc_p_dettaglio.php"

_HEADERS = {"User-Agent": "TALIA-bot/0.1 (civic transparency; https://github.com/dom3095/talia)"}

_RE_ROW = re.compile(r"<tr>(.*?)</tr>", re.DOTALL)
_RE_FIELD = re.compile(
    r"<strong>([^<]+)</strong>(?:\s*<br>)?(?:\s*<a[^>]*>)?\s*<div[^>]*>(.*?)</div>",
    re.DOTALL,
)
_RE_LINK = re.compile(r'href="[^"]*id_pubbl=(\d+)"')

_NON_DEFINITO = "non definito"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


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

        atti.append(
            AttoMetadato(
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
                cig_padre=estrai_cig_padre(oggetto),
            )
        )
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
    _retry: int = 1,
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

    Un retry con backoff di 2s su timeout/connessione rifiutata (stesso
    pattern di `jcitygov.py`/`hspromila.py`): alcuni tenant condividono un
    host Halley che va sporadicamente in `ConnectionRefusedError` sotto
    carico, non un fallimento persistente per singolo comune (scoperto
    2026-08-05: 4 comuni su un unico IP condiviso, tutti tornati
    raggiungibili a distanza di secondi).
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
        for tentativo in range(_retry + 1):
            try:
                with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
                    html = r.read().decode("utf-8", errors="replace")
                break
            except (TimeoutError, urllib.error.URLError):
                if tentativo == _retry:
                    raise
                time.sleep(2)
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


# ---------------------------------------------------------------------------
# Amministrazione Trasparente (TAL-62)
#
# Applicazione completamente separata dall'Albo Pretorio (Zend Framework,
# `/zf/index.php/trasparenza/...` — non `/mc/mc_p_*.php`): stesso vendor
# Halley, sistema diverso, HTML diverso, nessun riuso possibile dei parser
# sopra. Verificato dal vivo (Aci Bonaccorsi, 2026-08-16): nessuna sessione
# richiesta (richieste HTTP dirette come l'Albo Pretorio), nessuna data di
# scadenza sulle righe (a differenza dell'Albo, che la espone sempre) — un
# segnale in più a favore di una ritenzione permanente, non a termine. Un
# export CSV esiste (`esporta-csv/categoria/<id>`) ma non include l'URL del
# documento: usato solo per Excel dall'utente umano, non utile per lo
# scraping (serve comunque la tabella HTML per url_fonte).
# ---------------------------------------------------------------------------

FONTE_SCRAPER_TRASPARENZA = "halley_trasparenza"
_TRASPARENZA_LANDING = "/zf/index.php/trasparenza/index/index"

_RE_CATEGORIA_MENU = re.compile(
    r"<a href='/zf/index\.php/trasparenza/index/index/categoria/(\d+)'[^>]*>([^<]+)</a>"
)
_RE_RIGA_TRASPARENZA = re.compile(r'<tr\s+data-href="([^"]+)"[^>]*>(.*?)</tr>', re.DOTALL)
_RE_DESCRIZIONE_TRASPARENZA = re.compile(r'class="prevent-default">\s*(.*?)\s*</a>', re.DOTALL)
_RE_PESO_FILE = re.compile(r"\s*\([\d.,]+\s*[KMG]B\)\s*$")
_RE_INSERITA = re.compile(r"Inserita il (\d{2}/\d{2}/\d{4})")
_RE_SUCCESSIVA = re.compile(r">Successiva")

# Sottoinsieme di categorie con contenuto rilevante per la checklist
# (procedure di gara/concorso — dove servono i red flag di TAL-23/48): la
# tassonomia D.lgs. 33/2013 ha decine di categorie (organigramma, bilanci,
# consulenti...), la maggior parte fuori scope per ora.
CATEGORIE_TRASPARENZA_DEFAULT = (
    "Bandi di concorso",
    "Bandi di gara e contratti",
)


def _ssl_context(skip_ssl: bool):
    if not skip_ssl:
        return None
    import ssl

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _parse_pagina_trasparenza(
    html: str, base_url: str, codice_istat: str, categoria: str
) -> list[AttoMetadato]:
    atti = []
    for href, row_html in _RE_RIGA_TRASPARENZA.findall(html):
        m_desc = _RE_DESCRIZIONE_TRASPARENZA.search(row_html)
        if not m_desc:
            continue
        oggetto = _RE_PESO_FILE.sub("", _strip(m_desc.group(1))) or None

        m_data = _RE_INSERITA.search(row_html)
        data_pub = parse_data_iso(m_data.group(1)) if m_data else None

        atti.append(
            AttoMetadato(
                ente_codice_istat=codice_istat,
                tipo=categoria.lower(),
                url_fonte=f"{base_url}{href}",
                fonte_scraper=FONTE_SCRAPER_TRASPARENZA,
                data_accesso=ora_utc(),
                oggetto=oggetto,
                data_pub=data_pub,
                cig=estrai_cig(oggetto),
                cig_padre=estrai_cig_padre(oggetto),
            )
        )
    return atti


def scopri_categorie_trasparenza(base_url: str, *, skip_ssl: bool = False) -> dict[str, str]:
    """Scopre le categorie di Amministrazione Trasparente e i relativi ID.

    Il menu (`/zf/.../trasparenza/index/index`) contiene un link per
    categoria (`.../categoria/<id>`) con il nome leggibile come testo —
    a differenza di jCityGov, l'ID di categoria è già nell'URL, non serve
    un attributo separato.
    """
    base = base_url.rstrip("/")
    req = urllib.request.Request(f"{base}{_TRASPARENZA_LANDING}", headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20, context=_ssl_context(skip_ssl)) as r:
            html = r.read().decode("utf-8", errors="replace")
    except (TimeoutError, urllib.error.URLError):
        return {}
    return {_strip(label): cat_id for cat_id, label in _RE_CATEGORIA_MENU.findall(html)}


def scarica_atti_trasparenza(
    base_url: str,
    codice_istat: str,
    *,
    categorie: Iterable[str] = CATEGORIE_TRASPARENZA_DEFAULT,
    max_pagine_per_categoria: int = 100,
    skip_ssl: bool = False,
    _retry: int = 1,
) -> Iterator[AttoMetadato]:
    """Scarica atti dalla sezione Amministrazione Trasparente di un comune Halley.

    A differenza dell'Albo Pretorio (bacheca temporanea), qui non c'è una
    data di scadenza sulle righe — verificato dal vivo su Aci Bonaccorsi:
    17 pagine solo per "Bandi di concorso", nessun segnale di rotazione a
    breve termine. Gli atti hanno `fonte_scraper = "halley_trasparenza"`
    (non "halley"). Nessuna deduplicazione qui con gli atti già raccolti
    dall'Albo Pretorio per lo stesso comune (stessa nota di jcitygov.py,
    TAL-62): valutata separatamente.
    """
    base = base_url.rstrip("/")
    ctx = _ssl_context(skip_ssl)
    categorie_disponibili = scopri_categorie_trasparenza(base_url, skip_ssl=skip_ssl)

    for nome_categoria in categorie:
        cat_id = categorie_disponibili.get(nome_categoria)
        if not cat_id:
            logger.warning(
                "halley trasparenza %s: categoria %r non trovata tra quelle esposte",
                base,
                nome_categoria,
            )
            continue

        for pagina in range(1, max_pagine_per_categoria + 1):
            suffisso = f"/page/{pagina}" if pagina > 1 else ""
            url = f"{base}{_TRASPARENZA_LANDING}/categoria/{cat_id}{suffisso}"
            req = urllib.request.Request(url, headers=_HEADERS)
            for tentativo in range(_retry + 1):
                try:
                    with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
                        html = r.read().decode("utf-8", errors="replace")
                    break
                except (TimeoutError, urllib.error.URLError):
                    if tentativo == _retry:
                        raise
                    time.sleep(2)

            atti = _parse_pagina_trasparenza(html, base, codice_istat, nome_categoria)
            if not atti:
                if pagina == 1:
                    logger.warning("halley trasparenza %s: 0 atti in %r", base, nome_categoria)
                break

            yield from atti

            if not _RE_SUCCESSIVA.search(html):
                break
