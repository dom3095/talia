"""Download PDF allegati da atti ricostruiti in catene procedurali.

Modulo TAL-47: estrae allegati da pagine di dettaglio jCityGov/Liferay
e scarica i PDF tramite endpoint `downloadAllegato` (HTTP puro, niente Playwright).

Pipeline:
  1. Dato url_fonte di un atto, fetcha la pagina mostraDettaglio
  2. Estrae gli allegati da <tr data-chiave-allegato="..." data-mimetype="...">
  3. Estrae gli URL di download base64-codificati negli onclick handler
  4. Scarica ogni allegato in data/raw/pdf/<ente>/<procedimento_id>/
  5. Salva meta.json con url_sorgente, atto_id, hash_sha256, data_download
  6. Aggiorna atti.url_pdf nel DB (idempotente)

Vincoli:
  - HTTP puro, nessun JavaScript
  - Rate limiting 1s tra richieste
  - Idempotente: skip se hash uguali
  - Log WARNING esplicito se 0 allegati
"""

from __future__ import annotations

import base64
import hashlib
import http.cookiejar
import json
import logging
import re
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path
from typing import NamedTuple

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_DEFAULT_DELAY = 1.0  # secondi tra richieste
_DEFAULT_TIMEOUT = 30  # secondi timeout HTTP
_DEFAULT_RETRIES = 1  # retry su timeout

# Regex per estrarre allegati dalla pagina di dettaglio
_RE_ALLEGATO_ROW = re.compile(
    r'<tr\s+data-chiave-allegato="(\d+)"\s+data-mimetype="([^"]*)"[^>]*>',
    re.IGNORECASE,
)

# Regex per estrarre URL base64 dagli onclick handler
_RE_ATOB_URL = re.compile(
    r"atob\('([a-zA-Z0-9+/=]+)'\)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Tipi
# ---------------------------------------------------------------------------


class Allegato(NamedTuple):
    """Metadati di un allegato estratto dalla pagina."""

    chiave_allegato: str  # ID univoco nel sistema jCityGov
    mimetype: str
    nome_file: str | None = None
    url_download: str | None = None  # URL di download diretto (base64-decodificato)


# ---------------------------------------------------------------------------
# Utilità
# ---------------------------------------------------------------------------


def _build_opener(skip_ssl: bool = False) -> urllib.request.OpenerDirector:
    """Crea un opener HTTP con gestione cookie."""
    jar = http.cookiejar.CookieJar()
    handlers: list = [urllib.request.HTTPCookieProcessor(jar)]
    if skip_ssl:
        import ssl

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        handlers.append(urllib.request.HTTPSHandler(context=ctx))
    return urllib.request.build_opener(*handlers)


def _fetch(
    opener: urllib.request.OpenerDirector,
    url: str,
    timeout: int = _DEFAULT_TIMEOUT,
    retry: int = _DEFAULT_RETRIES,
) -> str:
    """Scarica una pagina HTTP (testo)."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    for attempt in range(retry + 1):
        try:
            with opener.open(req, timeout=timeout) as r:
                enc = r.headers.get_content_charset("utf-8")
                return r.read().decode(enc, errors="replace")
        except (urllib.error.URLError, TimeoutError):
            if attempt == retry:
                raise
            time.sleep(2)
    raise RuntimeError(f"Unexpected: download retry exhausted for {url}")


def _fetch_binary(
    opener: urllib.request.OpenerDirector,
    url: str,
    timeout: int = _DEFAULT_TIMEOUT,
    retry: int = _DEFAULT_RETRIES,
) -> tuple[bytes, str]:
    """Scarica un file binario (PDF). Ritorna (contenuto, filename)."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    for attempt in range(retry + 1):
        try:
            with opener.open(req, timeout=timeout) as r:
                content = r.read()
                # Estrai filename da Content-Disposition
                disp = r.headers.get("content-disposition", "")
                filename = "download.bin"
                if "filename=" in disp:
                    # Estrai filename="..." o filename*=...
                    m = re.search(r'filename="?([^";\n]+)"?', disp)
                    if m:
                        filename = m.group(1).strip('"')
                return content, filename
        except (urllib.error.URLError, TimeoutError):
            if attempt == retry:
                raise
            time.sleep(2)
    raise RuntimeError(f"Unexpected: binary download retry exhausted for {url}")


def _sha256_bytes(data: bytes) -> str:
    """Calcola hash SHA256 di dati binari."""
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Parsing pagina dettaglio
# ---------------------------------------------------------------------------


def _url_display_format(url_fonte: str) -> str:
    """Converte URL mostraDettaglio in formato /papca/display/<id>.

    Estrae l'ID pubblicazione dall'URL mostraDettaglio e ritorna l'URL /papca/display.
    Se fallisce, ritorna l'URL originale.
    """
    # URL mostraDettaglio: .../papca-g?...&..._WAR_jcitygovalbiportlet_id=<ID>&...
    m = re.search(r"_jcitygovalbopubblicazioni_WAR_jcitygovalbiportlet_id=(\d+)", url_fonte)
    if m:
        pub_id = m.group(1)
        # Estrai base URL
        base = re.match(r"(https://[^/]+)", url_fonte)
        if base:
            return f"{base.group(1)}/web/trasparenza/papca-g/-/papca/display/{pub_id}"
    return url_fonte


def trova_allegati(url_fonte: str, opener=None) -> list[Allegato]:
    """Estrae allegati dalla pagina di dettaglio di un atto jCityGov.

    Args:
        url_fonte: URL della pagina mostraDettaglio (formato papca-g?...) oppure /papca/display/
        opener: opener HTTP iniettabile (default: new opener)

    Returns:
        Lista di Allegato con chiave_allegato, mimetype, e url_download (se trovato).

    Raises:
        URLError: se il fetch fallisce
    """
    opener = opener or _build_opener()

    # Se l'URL è nel formato mostraDettaglio, converti a /papca/display/<id>
    # che è più veloce e diretto
    url_display = _url_display_format(url_fonte)
    if url_display != url_fonte:
        _logger.debug(f"Convertito a formato display: {url_display}")
        url_fonte = url_display

    try:
        html = _fetch(opener, url_fonte)
    except urllib.error.URLError as e:
        _logger.warning(f"Errore fetch url_fonte {url_fonte}: {e}")
        return []

    allegati = []

    # Estrai righe <tr> con data-chiave-allegato
    for m in _RE_ALLEGATO_ROW.finditer(html):
        chiave = m.group(1)
        mimetype = m.group(2)
        allegati.append(Allegato(chiave_allegato=chiave, mimetype=mimetype))

    if not allegati:
        _logger.warning(f"Nessun allegato trovato in {url_fonte}")
        return []

    # Estrai URL di download (base64-coded negli onclick)
    urls_base64 = _RE_ATOB_URL.findall(html)
    urls_decoded = []
    for b64 in urls_base64:
        try:
            decoded = base64.b64decode(b64).decode("utf-8")
            urls_decoded.append(decoded)
        except Exception as e:
            _logger.debug(f"Errore decodifica base64: {e}")

    # Associa URL ai chiave_allegato
    # Nota: l'ordine dei base64 in atob() corrisponde all'ordine dei <tr>
    allegati_con_url = []
    for i, all_meta in enumerate(allegati):
        if i < len(urls_decoded):
            all_meta = all_meta._replace(url_download=urls_decoded[i])
        allegati_con_url.append(all_meta)

    _logger.info(f"Trovati {len(allegati_con_url)} allegati in {url_fonte}")
    return allegati_con_url


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


def scarica_pdf_allegato(
    url_download: str,
    dest_base: Path,
    opener=None,
) -> tuple[Path, str, str] | None:
    """Scarica un singolo allegato.

    L'estensione (.pdf / .bin) si decide DOPO il download, dai magic bytes
    ``%PDF``: il ``data-mimetype`` dichiarato dal portale non è affidabile
    (PDF reali arrivano anche con mimetype generico).

    Idempotente: se il file destinazione esiste già (con una delle due
    estensioni), non riscarica.

    Args:
        url_download: URL completo di download (già decodificato da base64)
        dest_base: percorso destinazione SENZA estensione
        opener: opener HTTP iniettabile

    Returns:
        (path_salvato, filename_originale, hash_sha256) oppure None se fallisce.
    """
    opener = opener or _build_opener()

    # Idempotenza: se già scaricato (con qualsiasi estensione), skip
    for ext in ("pdf", "bin"):
        esistente = dest_base.with_suffix(f".{ext}")
        if esistente.exists():
            hash_sha = _sha256_bytes(esistente.read_bytes())
            _logger.debug(f"Già presente, skip: {esistente.name} (hash {hash_sha[:8]}...)")
            return esistente, esistente.name, hash_sha

    try:
        content, filename = _fetch_binary(opener, url_download)
    except Exception as e:
        _logger.warning(f"Errore download {url_download}: {e}")
        return None

    if not content:
        _logger.warning(f"Download vuoto da {url_download}")
        return None

    hash_sha = _sha256_bytes(content)
    ext = "pdf" if content.startswith(b"%PDF") else "bin"
    dest_path = dest_base.with_suffix(f".{ext}")

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        dest_path.write_bytes(content)
        _logger.info(f"Salvato {dest_path.name} ({len(content)} bytes, hash {hash_sha[:8]}...)")
    except OSError as e:
        _logger.error(f"Errore salvataggio {dest_path}: {e}")
        return None

    return dest_path, filename, hash_sha


# Metodi di individuazione ad alta confidenza (vs fuzzy da verificare)
_METODI_ALTA_CONFIDENZA = ("cig", "riferimento", "contenimento_oggetto")

_RUOLI_CHIUSURA = ("revoca", "annullamento")

# "N. 33/2025", "n.33/2025", "N 33/2025" citati nell'oggetto di una revoca
_RE_NUMERO_CITATO = re.compile(r"\bn\.?\s*(\d{1,5}\s*/\s*20\d\d)\b", re.IGNORECASE)


def _segnali_catena(proc_row, atti_rows, anno_min_copertura: int | None = None) -> list[dict]:
    """Segnali specifici della catena, calcolati solo da dati deterministici del DB.

    Ogni segnale ha un dettaglio con l'evidenza: è la risposta concreta a
    "perché QUESTA catena?", non una formula uguale per tutte.

    ``anno_min_copertura`` è l'anno del più vecchio atto raccolto per l'ente:
    i segnali basati sull'assenza di un atto (es. riferimento citato e non
    riscontrato) scattano solo dentro la finestra di copertura del DB, per non
    confondere "l'ente ha sbagliato" con "il nostro scraping non arriva lì".
    """
    stato = proc_row[1]
    metodo = proc_row[2] or ""
    segnali: list[dict] = []

    chiusure = [a for a in atti_rows if a[2] in _RUOLI_CHIUSURA]
    avvii = [a for a in atti_rows if a[2] == "avvio"]

    # 1. Esito critico (il criterio base, ma con l'evidenza dell'atto)
    for c in chiusure:
        segnali.append(
            {
                "tipo": "esito_critico",
                "dettaglio": f"catena conclusa con {c[2]}: atto n.{c[1] or '?'} "
                f"pubblicato il {c[3] or 'data non nota'}",
            }
        )
    if not chiusure:
        segnali.append(
            {
                "tipo": "esito_critico",
                "dettaglio": f"stato finale '{stato}' assegnato dall'engine catena",
            }
        )

    # 2. Distanza avvio→chiusura (stesso giorno = anomalia temporale da verificare)
    date_avvio = sorted(a[3] for a in avvii if a[3])
    date_chiusura = sorted(c[3] for c in chiusure if c[3])
    if date_avvio and date_chiusura:
        d_avvio, d_fine = date_avvio[0], date_chiusura[-1]
        giorni = (date.fromisoformat(d_fine) - date.fromisoformat(d_avvio)).days
        if giorni == 0:
            segnali.append(
                {
                    "tipo": "avvio_e_chiusura_stesso_giorno",
                    "dettaglio": f"atto di avvio e atto di {chiusure[0][2]} risultano "
                    f"pubblicati lo stesso giorno ({d_avvio})",
                }
            )
        elif 0 < giorni <= 30:
            segnali.append(
                {
                    "tipo": "chiusura_rapida",
                    "dettaglio": f"{giorni} giorni tra avvio ({d_avvio}) e "
                    f"{chiusure[0][2]} ({d_fine})",
                }
            )

    # 3. Atto di avvio assente dall'albo raccolto
    if not avvii:
        segnali.append(
            {
                "tipo": "avvio_non_in_albo",
                "dettaglio": "nessun atto con ruolo 'avvio' nella catena: l'atto "
                "revocato/annullato non risulta tra quelli raccolti dall'albo",
            }
        )

    # 4. Riferimenti citati e non riscontrati (es. revoca cita "N. 33/2025"
    #    ma nessun atto della catena ha quel numero). Scatta SOLO se l'anno
    #    citato rientra nella copertura del DB per l'ente: fuori finestra
    #    l'assenza è colpa dello scraping, non dell'ente.
    numeri_catena = {str(a[1]).strip() for a in atti_rows if a[1]}
    numeri_catena |= {str(a[6]).strip() for a in atti_rows if len(a) > 6 and a[6]}
    for c in chiusure:
        for citato in _RE_NUMERO_CITATO.findall(c[4] or ""):
            citato_norm = citato.replace(" ", "")
            anno_citato = int(citato_norm.split("/")[1])
            if anno_min_copertura is not None and anno_citato < anno_min_copertura:
                continue
            if citato_norm not in numeri_catena and citato_norm.split("/")[0] not in numeri_catena:
                segnali.append(
                    {
                        "tipo": "riferimento_non_riscontrato",
                        "dettaglio": f"l'atto di {c[2]} n.{c[1] or '?'} cita "
                        f"'N. {citato}' ma nessun atto della catena ha quel numero "
                        "(possibile numero errato o atto mai pubblicato; l'anno "
                        f"citato {anno_citato} rientra nella copertura del DB "
                        f"per l'ente)",
                    }
                )

    # 5. Confidenza del metodo di individuazione
    if metodo and metodo not in _METODI_ALTA_CONFIDENZA:
        segnali.append(
            {
                "tipo": "individuazione_da_verificare",
                "dettaglio": f"catena individuata con metodo fuzzy '{metodo}': "
                "il collegamento tra gli atti è da verificare",
            }
        )

    # Dedup preservando l'ordine (catene con più chiusure gemelle producono doppioni)
    visti: set[tuple[str, str]] = set()
    unici = []
    for s in segnali:
        chiave = (s["tipo"], s["dettaglio"])
        if chiave not in visti:
            visti.add(chiave)
            unici.append(s)
    return unici


def motivo_selezione(conn: sqlite3.Connection, procedimento_id: int) -> dict:
    """Costruisce la giustificazione (esplicabile, dal DB) della selezione di una catena.

    Risponde a "perché questi PDF sono stati scaricati?" con soli dati deterministici:
    stato finale, metodo di individuazione, segnali specifici della catena (con
    evidenza), atti con url_fonte, red flags dell'ente pertinenti. Nessun giudizio:
    segnalazioni da verificare, non accertamenti.
    """
    proc = conn.execute(
        """
        SELECT p.id, p.stato_finale, p.metodo_individuazione, p.oggetto, p.ente_id,
               e.denominazione
        FROM procedimenti p JOIN enti e ON p.ente_id = e.id
        WHERE p.id = ?
        """,
        (procedimento_id,),
    ).fetchone()
    if proc is None:
        return {}

    atti = conn.execute(
        """
        SELECT id, numero, ruolo_in_catena, data_pub, oggetto, url_fonte,
               numero_settoriale
        FROM atti WHERE procedimento_id = ? ORDER BY data_pub, id
        """,
        (procedimento_id,),
    ).fetchall()

    # Red flags dell'ente pertinenti a QUESTA catena: la descrizione del flag
    # cita l'oggetto del procedimento (i flag di catena lo incorporano)
    flags = conn.execute(
        """
        SELECT tipo_flag, severita, descrizione, data_rilevazione
        FROM red_flags WHERE ente_id = ?
        """,
        (proc[4],),
    ).fetchall()
    oggetto_proc = (proc[3] or "")[:60]
    flags_pertinenti = [f for f in flags if oggetto_proc and oggetto_proc in (f[2] or "")]

    # Copertura DB per l'ente: anno del più vecchio atto raccolto
    riga_copertura = conn.execute(
        "SELECT MIN(COALESCE(data_atto, data_pub)) FROM atti WHERE ente_id = ?",
        (proc[4],),
    ).fetchone()
    anno_min = int(riga_copertura[0][:4]) if riga_copertura and riga_copertura[0] else None

    return {
        "procedimento_id": proc[0],
        "ente": proc[5],
        "criterio_selezione": (
            "catena ricostruita dall'engine con esito critico "
            "(stato_finale in: revocato, annullato)"
        ),
        "stato_finale": proc[1],
        "metodo_individuazione": proc[2],
        "oggetto": proc[3],
        "segnali": _segnali_catena(proc, atti, anno_min_copertura=anno_min),
        "atti": [
            {
                "atto_id": a[0],
                "numero": a[1],
                "numero_settoriale": a[6],
                "ruolo_in_catena": a[2],
                "data_pub": a[3],
                "oggetto": a[4],
                "url_fonte": a[5],
            }
            for a in atti
        ],
        "red_flags_procedimento": [
            {
                "tipo_flag": f[0],
                "severita": f[1],
                "descrizione": f[2],
                "data_rilevazione": f[3],
            }
            for f in flags_pertinenti
        ],
        "disclaimer": "Segnalazioni da verificare, non accertamenti.",
    }


def _scarica_pdf_atti(
    atti: list[tuple],
    cur: sqlite3.Cursor,
    dest_dir: Path,
    opener,
    delay: float,
) -> tuple[list[Path], list[dict]]:
    """Scarica gli allegati di una lista di atti ``(id, ente_id, url_fonte, ente_nome)``.

    Helper condiviso da ``scarica_pdf_procedimento`` (tutti gli atti di una
    catena) e ``scarica_pdf_atto`` (un atto singolo, senza catena). Aggiorna
    ``atti.url_pdf``/``hash_sha256`` in DB ma non fa commit né scrive
    meta.json: è responsabilità del chiamante, che conosce la directory e il
    tipo di selezione (procedimento vs atto singolo).
    """
    downloaded: list[Path] = []
    metadati: list[dict] = []

    for atto_id, _ente_id, url_fonte, _ente_nome in atti:
        if not url_fonte:
            _logger.warning(f"Atto {atto_id}: url_fonte mancante")
            continue

        _logger.info(f"Atto {atto_id}: scarico allegati da {url_fonte}")

        try:
            allegati = trova_allegati(url_fonte, opener=opener)
        except Exception as e:
            _logger.error(f"Atto {atto_id}: errore estrazione allegati: {e}")
            continue

        if not allegati:
            _logger.warning(f"Atto {atto_id}: nessun allegato trovato")
            continue

        db_aggiornato = False  # url_pdf punta al PRIMO PDF vero dell'atto, non all'ultimo allegato
        for all_meta in allegati:
            if not all_meta.url_download:
                _logger.warning(f"Atto {atto_id}: allegato {all_meta.chiave_allegato} senza URL")
                continue

            time.sleep(delay)  # Rate limiting

            dest_base = dest_dir / f"{atto_id}_{all_meta.chiave_allegato}"
            result = scarica_pdf_allegato(all_meta.url_download, dest_base, opener=opener)
            if result is None:
                continue

            dest_path, orig_filename, hash_sha = result
            downloaded.append(dest_path)

            if not db_aggiornato and dest_path.suffix == ".pdf":
                try:
                    cur.execute(
                        "UPDATE atti SET url_pdf = ?, hash_sha256 = ? WHERE id = ?",
                        (all_meta.url_download, hash_sha, atto_id),
                    )
                    db_aggiornato = True
                    _logger.debug(f"Atto {atto_id}: aggiornato url_pdf in DB")
                except sqlite3.Error as e:
                    _logger.warning(f"Atto {atto_id}: errore update DB: {e}")

            # Registra metadati
            metadati.append(
                {
                    "atto_id": atto_id,
                    "chiave_allegato": all_meta.chiave_allegato,
                    "url_sorgente": all_meta.url_download,
                    "filename_originale": orig_filename,
                    "filename_salvato": dest_path.name,
                    "hash_sha256": hash_sha,
                    "mimetype": all_meta.mimetype,
                    "data_download": datetime.now(UTC).isoformat(),
                }
            )

        time.sleep(delay)  # Pausa tra atti

    return downloaded, metadati


def scarica_pdf_procedimento(
    conn: sqlite3.Connection,
    procedimento_id: int,
    dest_dir: Path | None = None,
    opener=None,
    delay: float = _DEFAULT_DELAY,
) -> list[Path]:
    """Scarica i PDF di tutti gli atti di un procedimento.

    Args:
        conn: connessione SQLite al DB talia.db
        procedimento_id: ID del procedimento (foreign key a atti.procedimento_id)
        dest_dir: directory destinazione (default: data/raw/pdf/<ente>/<procedimento_id>/)
        opener: opener HTTP iniettabile
        delay: pausa tra richieste (rate limiting)

    Returns:
        Lista di Path ai file scaricati.

    Raises:
        sqlite3.Error: se la query fallisce
    """
    opener = opener or _build_opener()

    # Query atti del procedimento
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            a.id,
            a.ente_id,
            a.url_fonte,
            e.denominazione
        FROM atti a
        JOIN enti e ON a.ente_id = e.id
        WHERE a.procedimento_id = ?
        ORDER BY a.id
        """,
        (procedimento_id,),
    )
    atti = cur.fetchall()

    if not atti:
        _logger.warning(f"Nessun atto trovato per procedimento_id {procedimento_id}")
        return []

    # Determina directory destinazione
    if dest_dir is None:
        # data/raw/pdf/<ente>/<procedimento_id>/
        ente_nome = (atti[0][3] or "sconosciuto").lower().replace(" ", "_")
        dest_dir = Path("data/raw/pdf") / ente_nome / str(procedimento_id)

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    downloaded, metadati = _scarica_pdf_atti(atti, cur, dest_dir, opener, delay)

    # Salva meta.json + motivo_selezione.json (perché questa catena è stata scaricata)
    if metadati:
        meta_path = dest_dir / "meta.json"
        try:
            with open(meta_path, "w") as f:
                json.dump(metadati, f, indent=2, ensure_ascii=False)
            _logger.info(f"Salvato {meta_path} con {len(metadati)} allegati")
        except OSError as e:
            _logger.error(f"Errore salvataggio meta.json: {e}")

        motivo = motivo_selezione(conn, procedimento_id)
        if motivo:
            motivo_path = dest_dir / "motivo_selezione.json"
            try:
                with open(motivo_path, "w") as f:
                    json.dump(motivo, f, indent=2, ensure_ascii=False)
                _logger.info(f"Salvato {motivo_path}")
            except OSError as e:
                _logger.error(f"Errore salvataggio motivo_selezione.json: {e}")

    conn.commit()
    return downloaded


def scarica_pdf_atto(
    conn: sqlite3.Connection,
    atto_id: int,
    dest_dir: Path | None = None,
    opener=None,
    delay: float = _DEFAULT_DELAY,
) -> list[Path]:
    """Scarica gli allegati di un singolo atto, senza catena/procedimento.

    Serve per l'atto di riapertura di TAL-48 quando l'engine catena non lo ha
    (ancora) agganciato a una propria catena: ``scarica_pdf_procedimento``
    cercherebbe per ``atti.procedimento_id`` e non lo troverebbe.

    Args:
        conn: connessione SQLite al DB talia.db
        atto_id: ID dell'atto
        dest_dir: directory destinazione (default: data/raw/pdf/<ente>/atto_<atto_id>/)
        opener: opener HTTP iniettabile
        delay: pausa tra richieste (rate limiting)

    Returns:
        Lista di Path ai file scaricati.
    """
    opener = opener or _build_opener()

    cur = conn.cursor()
    cur.execute(
        """
        SELECT a.id, a.ente_id, a.url_fonte, e.denominazione
        FROM atti a
        JOIN enti e ON a.ente_id = e.id
        WHERE a.id = ?
        """,
        (atto_id,),
    )
    atti = cur.fetchall()

    if not atti:
        _logger.warning(f"Atto {atto_id} non trovato")
        return []

    if dest_dir is None:
        ente_nome = (atti[0][3] or "sconosciuto").lower().replace(" ", "_")
        dest_dir = Path("data/raw/pdf") / ente_nome / f"atto_{atto_id}"

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    downloaded, metadati = _scarica_pdf_atti(atti, cur, dest_dir, opener, delay)

    if metadati:
        meta_path = dest_dir / "meta.json"
        try:
            with open(meta_path, "w") as f:
                json.dump(metadati, f, indent=2, ensure_ascii=False)
            _logger.info(f"Salvato {meta_path} con {len(metadati)} allegati")
        except OSError as e:
            _logger.error(f"Errore salvataggio meta.json: {e}")

    conn.commit()
    return downloaded


# ---------------------------------------------------------------------------
# Selezione catene
# ---------------------------------------------------------------------------

# Fonti i cui atti sono scaricabili da questo modulo (dettaglio jCityGov/Liferay)
_FONTI_SUPPORTATE = ("jcitygov",)


def _diversifica_per_ente(rows: list[tuple[int, int]], limite: int | None) -> list[int]:
    """Round-robin tra enti su coppie ``(id, ente_id)``: un elemento a testa per giro.

    Un campione vario tra amministrazioni dice di più dello stesso numero di
    elementi tutti dello stesso ente. Condiviso da ``procedimenti_critici`` e
    ``procedimenti_da_riapertura``.
    """
    if limite is None:
        return [r[0] for r in rows]

    per_ente: dict[int, list[int]] = {}
    for item_id, ente_id in rows:
        per_ente.setdefault(ente_id, []).append(item_id)

    selezionati: list[int] = []
    code = list(per_ente.values())
    while code and len(selezionati) < limite:
        for coda in list(code):
            if len(selezionati) >= limite:
                break
            selezionati.append(coda.pop(0))
            if not coda:
                code.remove(coda)
    return selezionati


def procedimenti_critici(
    conn: sqlite3.Connection,
    fonti: tuple[str, ...] = _FONTI_SUPPORTATE,
    limite: int | None = 20,
) -> list[int]:
    """ID dei procedimenti revocati/annullati i cui atti vengono da fonti supportate.

    È il criterio di selezione della Fase 2: le catene con esito critico hanno
    priorità sul resto. Le catene su altre piattaforme (portalepa, ASP.NET)
    restano fuori finché non esiste un downloader dedicato.

    Con ``limite``, la selezione è diversificata per comune (round-robin tra gli
    enti, un procedimento a testa per giro): un campione vario tra amministrazioni
    dice di più dello stesso numero di catene di un solo ente.
    """
    segnaposto = ",".join("?" * len(fonti))
    rows = conn.execute(
        f"""
        SELECT DISTINCT p.id, p.ente_id
        FROM procedimenti p
        JOIN atti a ON a.procedimento_id = p.id
        WHERE p.stato_finale IN ('revocato', 'annullato')
          AND a.fonte_scraper IN ({segnaposto})
        ORDER BY p.ente_id, p.id
        """,
        fonti,
    ).fetchall()
    return _diversifica_per_ente(rows, limite)


def procedimenti_da_riapertura(
    conn: sqlite3.Connection,
    fonti: tuple[str, ...] = _FONTI_SUPPORTATE,
    limite: int | None = 20,
) -> list[int]:
    """ID dei red flag ``riapertura_dopo_revoca`` (TAL-48) su enti con fonti supportate.

    Ogni riga individua UNA coppia di bandi da scaricare (originale revocato/
    annullato + riapertura con oggetto simile): vedi ``scarica_pdf_riapertura``.
    Diversificato per ente come ``procedimenti_critici``.
    """
    segnaposto = ",".join("?" * len(fonti))
    rows = conn.execute(
        f"""
        SELECT rf.id, rf.ente_id
        FROM red_flags rf
        WHERE rf.tipo_flag = 'riapertura_dopo_revoca'
          AND EXISTS (
              SELECT 1 FROM atti a
              WHERE a.ente_id = rf.ente_id AND a.fonte_scraper IN ({segnaposto})
          )
        ORDER BY rf.ente_id, rf.id
        """,
        fonti,
    ).fetchall()
    return _diversifica_per_ente(rows, limite)


def scarica_pdf_riapertura(
    conn: sqlite3.Connection,
    red_flag_id: int,
    opener=None,
    delay: float = _DEFAULT_DELAY,
) -> list[Path]:
    """Scarica ENTRAMBI i bandi di una riapertura dopo revoca (TAL-48).

    Il flag ``riapertura_dopo_revoca`` referenzia due cose distinte: la
    catena originale revocata/annullata (procedimento) e il singolo atto di
    riapertura, che potrebbe non avere ancora una propria catena. Scarica
    prima la catena originale (che produce già il suo motivo_selezione.json
    via ``scarica_pdf_procedimento``), poi la riapertura — la sua catena se
    ne ha una, altrimenti il solo atto via ``scarica_pdf_atto`` — e infine un
    motivo_riapertura.json nella cartella della catena originale che spiega
    il collegamento tra le due (per il confronto testuale futuro, fuori
    scope qui: vedi TAL-48).

    Args:
        conn: connessione SQLite al DB talia.db
        red_flag_id: ID della riga in red_flags (tipo_flag='riapertura_dopo_revoca')
        opener: opener HTTP iniettabile
        delay: pausa tra richieste (rate limiting)

    Returns:
        Lista di Path ai file scaricati (entrambi i bandi).
    """
    opener = opener or _build_opener()

    row = conn.execute(
        "SELECT ente_id, atti_cig, descrizione FROM red_flags "
        "WHERE id = ? AND tipo_flag = 'riapertura_dopo_revoca'",
        (red_flag_id,),
    ).fetchone()
    if row is None:
        _logger.warning(f"Red flag {red_flag_id}: non trovato o non è riapertura_dopo_revoca")
        return []

    ente_id, atti_cig_raw, descrizione = row
    try:
        dettaglio = json.loads(atti_cig_raw or "[]")
    except json.JSONDecodeError:
        dettaglio = []
    if not dettaglio:
        _logger.warning(f"Red flag {red_flag_id}: atti_cig vuoto o non valido")
        return []

    info = dettaglio[0]
    id_catena_revocata = info.get("id_catena_revocata")
    atto_riapertura_id = info.get("atto_riapertura_id")

    downloaded: list[Path] = []
    dest_dir_originale = None

    if id_catena_revocata is not None:
        downloaded += scarica_pdf_procedimento(conn, id_catena_revocata, opener=opener, delay=delay)
        riga_ente = conn.execute(
            "SELECT denominazione FROM enti WHERE id = ?", (ente_id,)
        ).fetchone()
        ente_nome = (riga_ente[0] if riga_ente else "sconosciuto").lower().replace(" ", "_")
        dest_dir_originale = Path("data/raw/pdf") / ente_nome / str(id_catena_revocata)

    if atto_riapertura_id is not None:
        riga_atto = conn.execute(
            "SELECT procedimento_id FROM atti WHERE id = ?", (atto_riapertura_id,)
        ).fetchone()
        proc_id_riapertura = riga_atto[0] if riga_atto else None
        if proc_id_riapertura is not None and proc_id_riapertura != id_catena_revocata:
            downloaded += scarica_pdf_procedimento(
                conn, proc_id_riapertura, opener=opener, delay=delay
            )
        elif proc_id_riapertura is None:
            downloaded += scarica_pdf_atto(conn, atto_riapertura_id, opener=opener, delay=delay)

    if downloaded and dest_dir_originale is not None:
        dest_dir_originale.mkdir(parents=True, exist_ok=True)
        motivo_path = dest_dir_originale / "motivo_riapertura.json"
        try:
            with open(motivo_path, "w") as f:
                json.dump(
                    {
                        "red_flag_id": red_flag_id,
                        "criterio_selezione": (
                            "riapertura_dopo_revoca (TAL-48): atto con oggetto simile "
                            "pubblicato dallo stesso ente dopo la revoca/annullamento "
                            "di questa catena"
                        ),
                        "descrizione": descrizione,
                        "procedimento_originale_id": id_catena_revocata,
                        "atto_riapertura_id": atto_riapertura_id,
                        "disclaimer": "Segnalazione da verificare, non accertamento.",
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
            _logger.info(f"Salvato {motivo_path}")
        except OSError as e:
            _logger.error(f"Errore salvataggio motivo_riapertura.json: {e}")

    return downloaded


# ---------------------------------------------------------------------------
# Interfaccia CLI
# ---------------------------------------------------------------------------


def main():
    """CLI: scarica i PDF delle catene critiche (o di procedimenti espliciti)."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Download PDF on-demand da catene ricostruite (TAL-47)."
    )
    parser.add_argument(
        "proc_ids",
        nargs="*",
        type=int,
        help="ID procedimenti espliciti; se assenti, seleziona le catene critiche "
        "(revocato/annullato) su fonti supportate",
    )
    parser.add_argument("--db", default="talia.db", help="percorso DB (default: talia.db)")
    parser.add_argument(
        "--limite",
        type=int,
        default=20,
        help="massimo catene da scaricare, diversificate per comune (default: 20)",
    )
    parser.add_argument(
        "--riaperture",
        action="store_true",
        help="scarica le coppie originale+riapertura da red_flags "
        "'riapertura_dopo_revoca' (TAL-48) invece delle catene critiche",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"DB non trovato: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)

    if args.riaperture:
        flag_ids = args.proc_ids or procedimenti_da_riapertura(conn, limite=args.limite)
        _logger.info(f"Riaperture da scaricare: {len(flag_ids)} → {flag_ids}")
        for flag_id in flag_ids:
            _logger.info(f"=== Riapertura (red_flag {flag_id}) ===")
            try:
                downloaded = scarica_pdf_riapertura(conn, flag_id)
                print(f"Red flag {flag_id}: {len(downloaded)} file")
            except Exception as e:
                print(f"Red flag {flag_id}: errore: {e}", file=sys.stderr)
    else:
        procs = args.proc_ids or procedimenti_critici(conn, limite=args.limite)
        _logger.info(f"Procedimenti da scaricare: {len(procs)} → {procs}")

        for proc_id in procs:
            _logger.info(f"=== Procedimento {proc_id} ===")
            try:
                downloaded = scarica_pdf_procedimento(conn, proc_id)
                print(f"Proc. {proc_id}: {len(downloaded)} file")
            except Exception as e:
                print(f"Proc. {proc_id}: errore: {e}", file=sys.stderr)

    conn.close()


if __name__ == "__main__":
    main()
