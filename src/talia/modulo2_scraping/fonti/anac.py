"""Spider per i dati open ANAC/BDNCP — contratti pubblici, filtro Sicilia (regione 19).

Fonte dataset SmartCIG, pubblicato **per mese** (non per anno):
  .../dataset/smartcig-{anno}/filesystem/smartcig_csv_{anno}_{mese}.zip
  (~40 MB zippati a mese, ~450 MB l'anno; filtriamo per regione)

⚠️ L'URL `..._csv_logCsv.csv` **non è il dataset**: è un manifest che elenca
le sole risorse TTL. Fino al 2026-08-19 era configurato come sorgente, e lo
scraper ne leggeva 1288 byte di indice cercandoci dentro i contratti — da cui
un ANAC perennemente "muto" (0 atti, nessun errore). I file CSV esistono ma
non compaiono in quel manifest: si raggiungono per analogia col nome delle
risorse TTL (TAL-70).

Dati pubblici ai sensi del D.Lgs. 33/2013 e dell'art. 1 c. 32 L. 190/2012.

Flusso:
    1. Scarica (o legge da file) il CSV SmartCIG ANAC
    2. Filtra le righe con regione == 'SICILIA' (non sezione_regionale: alcuni
       enti siciliani stanno sotto "SEZIONE REGIONALE CENTRALE")
    3. Mappa ogni riga → AttoMetadato (tipo='contratto_anac')
    4. Per ogni atto aggancia l'ente via `istat_comune` (esatto), con fallback
       sulla denominazione
    5. Inserisce gli atti nuovi (idempotente: UNIQUE su ente_id × url_fonte)

Nota: l'url_fonte viene sintetizzato come
    https://dati.anticorruzione.it/opendata/cig/<cig>
"""

from __future__ import annotations

import csv
import datetime
import io
import logging
import sqlite3
import urllib.request
import zipfile
from collections.abc import Iterable, Iterator

from talia.modulo2_scraping.db import AttoMetadato, EnteMetadato, inserisci_atto, upsert_ente
from talia.modulo2_scraping.utils import ora_utc as _ora_utc
from talia.modulo2_scraping.utils import parse_data_iso as _parse_data_iso

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

FONTE_SCRAPER = "anac"
SEZIONE_SICILIA = "Sicilia"

_BASE_DOWNLOAD = "https://dati.anticorruzione.it/opendata/download/dataset"


def _url_manifest(anno: int) -> str:
    """URL del *manifest* delle risorse di un anno (non è il dataset).

    ⚠️ Elenca **solo** le risorse TTL, pur chiamandosi `..._csv_logCsv.csv`:
    fino al 2026-08-19 questo URL era configurato come se fosse il dataset, e
    lo scraper ne scaricava 1288 byte di indice cercandoci dentro i contratti —
    da cui l'ANAC perennemente "muta", con 0 atti e nessun errore (TAL-70).
    """
    return f"{_BASE_DOWNLOAD}/smartcig-{anno}/filesystem/smartcig-{anno}_csv_logCsv.csv"


def _url_smartcig(anno: int, mese: int, *, compresso: bool = True) -> str:
    """URL di un file mensile SmartCIG in CSV.

    Il dataset è pubblicato **per mese**, non in un unico file annuale, e i
    file CSV non compaiono nel manifest (che elenca i soli TTL): l'unico modo
    di trovarli è per analogia col nome delle risorse TTL. Lo zip pesa circa
    un quarto del CSV (47 MB contro 189 MB su 2024-11), quindi è il default.
    """
    estensione = "zip" if compresso else "csv"
    return (
        f"{_BASE_DOWNLOAD}/smartcig-{anno}/filesystem/smartcig_csv_{anno}_{mese:02d}.{estensione}"
    )


def _anno_default() -> int:
    """Anno civile più recente ragionevolmente pubblicato.

    ANAC pubblica con ritardo, ma molto meno dei 12-18 mesi ipotizzati in
    passato: al 2026-08-19 risultano disponibili tutti i 12 mesi del 2025.
    """
    return datetime.date.today().year - 1


#: Mantenuto per retrocompatibilità: è il manifest, non il dataset.
URL_DATASET_SMARTCIG = _url_manifest(_anno_default())

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

# Mappatura nomi alternativi usati da versioni diverse del CSV ANAC.
# I nomi `*_appaltante` e `oggetto_lotto`/`importo_lotto` sono quelli del
# tracciato in vigore (verificato sui file mensili 2025): senza questi alias
# nessuna riga veniva riconosciuta (TAL-70).
_ALIAS_COLONNE: dict[str, str] = {
    "denominazione_sa": "denominazione_amministrazione",
    "denominazione_amministrazione_appaltante": "denominazione_amministrazione",
    "cf_amministrazione_appaltante": "cf_amministrazione",
    "oggetto_gara": "oggetto_principale_contratto",
    "oggetto_lotto": "oggetto_principale_contratto",
    "importo_gara": "importo_totale_appalto",
    "importo_lotto": "importo_totale_appalto",
    "importo_complessivo_gara": "importo_complessivo",
    "data_creazione_cig": "data_creazione",
    "data_comunicazione": "data_creazione",
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
    """Filtra le righe siciliane.

    Il filtro è sulla colonna ``regione``, **non** su ``sezione_regionale``:
    quest'ultima indica la sezione ANAC competente, che per alcuni enti
    siciliani vale "SEZIONE REGIONALE CENTRALE" (verificato: la Casa di
    reclusione di San Cataldo). Filtrando sulla sezione quelle righe si
    perderebbero in silenzio. Si accetta comunque anche una
    ``sezione_regionale`` che nomini la Sicilia, per i tracciati più vecchi.
    """
    atteso = SEZIONE_SICILIA.lower()
    for r in righe:
        regione = r.get("regione", "").strip().lower()
        sezione = r.get("sezione_regionale", "").strip().lower()
        if regione == atteso or atteso in sezione:
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

    # Il tracciato espone `istat_comune` come <cod_regione><cod_istat_6>
    # (es. "019082054" → Partinico, 082054): è un aggancio **esatto**, molto
    # più affidabile del LIKE sulla denominazione, che su nomi come "COMUNE DI
    # SAN GIOVANNI" può agganciare il comune sbagliato.
    istat_csv = riga.get("istat_comune", "").strip()
    if len(istat_csv) >= 6:
        codice = istat_csv[-6:]
        if conn.execute("SELECT 1 FROM enti WHERE codice_istat = ?", (codice,)).fetchone():
            return codice

    # Poi cerca per denominazione (già nel DB)
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


def _fetch_mese(url: str, timeout: int = 300) -> str:
    """Scarica un file mensile SmartCIG, scompattandolo se è uno zip."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    if url.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            nomi = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if not nomi:
                raise ValueError(f"zip senza CSV: {url}")
            raw = zf.read(nomi[0])
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="replace")


def scarica_e_carica(
    conn: sqlite3.Connection,
    *,
    anno: int | None = None,
    mesi: Iterable[int] | None = None,
    crea_enti_mancanti: bool = True,
    _fetch_fn=_fetch_mese,
) -> dict[str, int]:
    """Scarica i file mensili SmartCIG di un anno e li carica nel DB.

    Args:
        conn:                connessione al DB già inizializzato.
        anno:                anno civile (default: anno corrente - 1).
        mesi:                mesi da scaricare (default: tutti e 12).
        crea_enti_mancanti:  vedi carica_csv_anac.
        _fetch_fn:           funzione di download iniettabile per i test.

    Un mese assente (404) o illeggibile non interrompe gli altri: ANAC
    pubblica i mesi progressivamente e l'anno in corso è quasi sempre parziale.

    Returns:
        dict con chiavi 'inseriti', 'duplicati', 'saltati', 'mesi_scaricati',
        'mesi_falliti'.
    """
    anno = anno or _anno_default()
    totali = {"inseriti": 0, "duplicati": 0, "saltati": 0, "mesi_scaricati": 0, "mesi_falliti": 0}
    for mese in mesi or range(1, 13):
        try:
            contenuto = _fetch_fn(_url_smartcig(anno, mese))
        except Exception as exc:  # noqa: BLE001 — un mese mancante non è fatale
            logger.warning("ANAC %d-%02d non scaricato: %s", anno, mese, exc)
            totali["mesi_falliti"] += 1
            continue
        esito = carica_csv_anac(contenuto, conn, crea_enti_mancanti=crea_enti_mancanti)
        for chiave in ("inseriti", "duplicati", "saltati"):
            totali[chiave] += esito.get(chiave, 0)
        totali["mesi_scaricati"] += 1
        logger.info("ANAC %d-%02d: %s", anno, mese, esito)
    return totali


__all__ = [
    "FONTE_SCRAPER",
    "SEZIONE_SICILIA",
    "URL_DATASET_SMARTCIG",
    "carica_csv_anac",
    "scarica_e_carica",
]
