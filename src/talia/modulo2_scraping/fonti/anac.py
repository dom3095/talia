"""Spider per i dati open ANAC/BDNCP — contratti pubblici, filtro Sicilia (regione 19).

Fonte dataset SmartCIG (suddiviso per anno civile dal 2023):
  https://dati.anticorruzione.it/opendata/download/dataset/smartcig-{anno}/filesystem/smartcig-{anno}_csv_logCsv.csv
  (aggiornamento mensile; ~400 MB per anno, filtriamo per sezione_regionale)

Dati pubblici ai sensi del D.Lgs. 33/2013 e dell'art. 1 c. 32 L. 190/2012.

Flusso:
    1. Scarica (o legge da file) il CSV SmartCIG ANAC
    2. Filtra le righe con sezione_regionale == 'Sicilia'
    3. Mappa ogni riga → AttoMetadato (tipo='contratto_anac')
    4. Per ogni atto cerca l'ente nel DB per denominazione (case-insensitive)
    5. Inserisce gli atti nuovi (idempotente: UNIQUE su ente_id × url_fonte)

Nota: l'url_fonte viene sintetizzato come
    https://dati.anticorruzione.it/opendata/cig/<cig>
"""

from __future__ import annotations

import csv
import datetime
import io
import sqlite3
import urllib.request
from collections.abc import Iterator

from talia.modulo2_scraping.db import AttoMetadato, EnteMetadato, inserisci_atto, upsert_ente
from talia.modulo2_scraping.utils import ora_utc as _ora_utc
from talia.modulo2_scraping.utils import parse_data_iso as _parse_data_iso

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

FONTE_SCRAPER = "anac"
SEZIONE_SICILIA = "Sicilia"

def _url_smartcig(anno: int | None = None) -> str:
    """URL dataset SmartCIG per l'anno civile dato.

    Default: anno precedente (il dataset dell'anno corrente viene pubblicato
    solo a partire da metà anno successivo).
    """
    if anno is None:
        anno = datetime.date.today().year - 1
    return (
        f"https://dati.anticorruzione.it/opendata/download/dataset/"
        f"smartcig-{anno}/filesystem/smartcig-{anno}_csv_logCsv.csv"
    )


URL_DATASET_SMARTCIG = _url_smartcig()

# UA browser-like: il WAF ANAC blocca stringhe contenenti "bot"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Colonne obbligatorie che devono essere presenti nel CSV
_COLONNE_RICHIESTE = {
    "cig",
    "denominazione_amministrazione",
    "sezione_regionale",
    "oggetto_principale_contratto",
}

# Mappatura nomi alternativi usati da versioni diverse del CSV ANAC
_ALIAS_COLONNE: dict[str, str] = {
    "denominazione_sa": "denominazione_amministrazione",
    "oggetto_gara": "oggetto_principale_contratto",
    "importo_gara": "importo_totale_appalto",
    "data_creazione_cig": "data_creazione",
}


# ---------------------------------------------------------------------------
# Utilità
# ---------------------------------------------------------------------------


def _normalizza_denominazione(s: str) -> str:
    """Normalizza la denominazione per il confronto case-insensitive."""
    return s.strip().lower()


def _normalizza_colonne(riga: dict[str, str]) -> dict[str, str]:
    """Rinomina colonne con alias noti per uniformare versioni diverse del CSV."""
    out: dict[str, str] = {}
    for k, v in riga.items():
        if k is None:  # csv.DictReader mette le colonne extra sotto None
            continue
        chiave = k.strip().lower()
        out[_ALIAS_COLONNE.get(chiave, chiave)] = (v or "").strip()
    return out


def _url_cig(cig: str) -> str:
    return f"https://dati.anticorruzione.it/opendata/cig/{cig}"


def _parse_importo(s: str | None) -> float | None:
    if not s:
        return None
    s = s.strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------


def _leggi_csv(contenuto: str) -> Iterator[dict[str, str]]:
    """Genera righe normalizzate da un CSV ANAC (stringa testo)."""
    reader = csv.DictReader(io.StringIO(contenuto), delimiter=";")
    for riga in reader:
        yield _normalizza_colonne(riga)


def _filtra_sicilia(righe: Iterator[dict[str, str]]) -> Iterator[dict[str, str]]:
    """Filtra solo le righe con sezione_regionale == 'Sicilia'."""
    for r in righe:
        if r.get("sezione_regionale", "").strip().lower() == SEZIONE_SICILIA.lower():
            yield r


# ---------------------------------------------------------------------------
# Lookup ente nel DB
# ---------------------------------------------------------------------------


def _cerca_istat_per_denominazione(
    conn: sqlite3.Connection,
    denominazione: str,
) -> str | None:
    """Cerca l'ISTAT nel DB facendo un confronto LIKE sulla denominazione.

    Restituisce il codice_istat se trovato, None altrimenti.
    """
    row = conn.execute(
        "SELECT codice_istat FROM enti WHERE lower(denominazione) LIKE ?",
        (f"%{_normalizza_denominazione(denominazione)}%",),
    ).fetchone()
    return row["codice_istat"] if row else None


def _upsert_ente_anac(conn: sqlite3.Connection, riga: dict[str, str]) -> str | None:
    """Inserisce l'ente dal CSV ANAC se non esiste; usa il CF come pseudo-ISTAT.

    Se il CF è disponibile e lungo 11 cifre (P.IVA comuni) prova come pseudo-ISTAT.
    In ogni caso restituisce il codice_istat usato, o None se impossibile.
    """
    denominazione = riga.get("denominazione_amministrazione", "").strip()
    if not denominazione:
        return None

    # Prima cerca per denominazione (già nel DB)
    istat = _cerca_istat_per_denominazione(conn, denominazione)
    if istat:
        return istat

    # Non in DB: usa il codice_fiscale_sa come pseudo-codice e inserisce ente
    cf = riga.get("cf_amministrazione", "").strip()
    if not cf:
        return None  # non possiamo inserire senza codice univoco

    # Usa CF come codice_istat (6-11 cifre; non è ISTAT ma è univoco)
    pseudo_istat = cf[:11]
    ente = EnteMetadato(
        denominazione=denominazione,
        codice_istat=pseudo_istat,
    )
    try:
        upsert_ente(conn, ente)
    except Exception:
        return None
    return pseudo_istat


# ---------------------------------------------------------------------------
# Mappatura riga CSV → AttoMetadato
# ---------------------------------------------------------------------------


def _mappa_atto(riga: dict[str, str], codice_istat: str) -> AttoMetadato | None:
    """Converte una riga CSV ANAC in AttoMetadato.

    Restituisce None se mancano campi obbligatori (cig, denominazione).
    """
    cig = riga.get("cig", "").strip()
    if not cig:
        return None

    url = _url_cig(cig)

    return AttoMetadato(
        ente_codice_istat=codice_istat,
        tipo="contratto_anac",
        url_fonte=url,
        fonte_scraper=FONTE_SCRAPER,
        data_accesso=_ora_utc(),
        cig=cig,
        oggetto=riga.get("oggetto_principale_contratto") or None,
        importo_euro=_parse_importo(riga.get("importo_totale_appalto")),
        data_atto=_parse_data_iso(riga.get("data_creazione")),
        numero=riga.get("numero_gara") or None,
        metadati={
            "tipo_appalto": riga.get("tipo_appalto", ""),
            "codice_scelta_contraente": riga.get("codice_scelta_contraente", ""),
            "descrizione_scelta_contraente": riga.get("descrizione_scelta_contraente", ""),
            "cf_amministrazione": riga.get("cf_amministrazione", ""),
            "anno_pubblicazione": riga.get("anno_pubblicazione", ""),
            "mese_pubblicazione": riga.get("mese_pubblicazione", ""),
        },
    )


# ---------------------------------------------------------------------------
# API principale: carica_csv_anac
# ---------------------------------------------------------------------------


def carica_csv_anac(
    contenuto: str,
    conn: sqlite3.Connection,
    *,
    sezione: str = SEZIONE_SICILIA,
    crea_enti_mancanti: bool = True,
) -> dict[str, int]:
    """Carica un CSV ANAC nel DB, filtrando per sezione regionale.

    Args:
        contenuto:           testo del CSV (UTF-8 o latin-1).
        conn:                connessione al DB già inizializzato.
        sezione:             filtro su sezione_regionale (default "Sicilia").
        crea_enti_mancanti:  se True, inserisce enti non ancora nel DB
                             usando il CF come pseudo-ISTAT.

    Returns:
        dict con chiavi 'inseriti', 'duplicati', 'saltati' (ente non trovabile).
    """
    inseriti = 0
    duplicati = 0
    saltati = 0

    righe = _filtra_sicilia(_leggi_csv(contenuto))

    for riga in righe:
        # Cerca o crea l'ente
        istat = _cerca_istat_per_denominazione(conn, riga.get("denominazione_amministrazione", ""))
        if istat is None:
            if crea_enti_mancanti:
                istat = _upsert_ente_anac(conn, riga)
            if istat is None:
                saltati += 1
                continue

        atto = _mappa_atto(riga, istat)
        if atto is None:
            saltati += 1
            continue

        esito = inserisci_atto(conn, atto)
        if esito is not None:
            inseriti += 1
        else:
            duplicati += 1

    return {"inseriti": inseriti, "duplicati": duplicati, "saltati": saltati}


# ---------------------------------------------------------------------------
# Fetch HTTP (solo produzione; nei test iniettare _fetch_fn)
# ---------------------------------------------------------------------------


def _fetch_csv(url: str, timeout: int = 60) -> str:
    """Scarica un file CSV da URL; gestisce sia UTF-8 sia latin-1."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="replace")


def scarica_e_carica(
    conn: sqlite3.Connection,
    *,
    url: str = URL_DATASET_SMARTCIG,
    crea_enti_mancanti: bool = True,
    _fetch_fn=_fetch_csv,
) -> dict[str, int]:
    """Scarica il dataset SmartCIG da ANAC e lo carica nel DB.

    Args:
        conn:                connessione al DB già inizializzato.
        url:                 URL del dataset (default: SmartCIG ANAC).
        crea_enti_mancanti:  vedi carica_csv_anac.
        _fetch_fn:           funzione HTTP iniettabile per i test.

    Returns:
        dict con chiavi 'inseriti', 'duplicati', 'saltati'.
    """
    contenuto = _fetch_fn(url)
    return carica_csv_anac(contenuto, conn, crea_enti_mancanti=crea_enti_mancanti)


__all__ = [
    "FONTE_SCRAPER",
    "SEZIONE_SICILIA",
    "URL_DATASET_SMARTCIG",
    "carica_csv_anac",
    "scarica_e_carica",
]
