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
from datetime import UTC, datetime
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


def motivo_selezione(conn: sqlite3.Connection, procedimento_id: int) -> dict:
    """Costruisce la giustificazione (esplicabile, dal DB) della selezione di una catena.

    Risponde a "perché questi PDF sono stati scaricati?" con soli dati deterministici:
    stato finale della catena, metodo con cui l'engine l'ha individuata, ruolo di ogni
    atto con il suo url_fonte, e le red flags registrate per l'ente. Nessun giudizio:
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
        SELECT id, numero, ruolo_in_catena, data_pub, oggetto, url_fonte
        FROM atti WHERE procedimento_id = ? ORDER BY data_pub, id
        """,
        (procedimento_id,),
    ).fetchall()

    flags = conn.execute(
        """
        SELECT tipo_flag, severita, descrizione, data_rilevazione
        FROM red_flags WHERE ente_id = ?
        """,
        (proc[4],),
    ).fetchall()

    return {
        "procedimento_id": proc[0],
        "ente": proc[5],
        "criterio_selezione": (
            "catena ricostruita dall'engine (stato_finale != 'sconosciuto'); "
            "priorità a revocato/annullato"
        ),
        "stato_finale": proc[1],
        "metodo_individuazione": proc[2],
        "oggetto": proc[3],
        "atti": [
            {
                "atto_id": a[0],
                "numero": a[1],
                "ruolo_in_catena": a[2],
                "data_pub": a[3],
                "oggetto": a[4],
                "url_fonte": a[5],
            }
            for a in atti
        ],
        "red_flags_ente": [
            {
                "tipo_flag": f[0],
                "severita": f[1],
                "descrizione": f[2],
                "data_rilevazione": f[3],
            }
            for f in flags
        ],
        "disclaimer": "Segnalazioni da verificare, non accertamenti.",
    }


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

    downloaded = []
    metadati = []  # Per meta.json

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


# ---------------------------------------------------------------------------
# Interfaccia CLI (per test manuali)
# ---------------------------------------------------------------------------


def main():
    """Test manuale: scarica allegati dai 3 atti di Palma (proc. 653-655)."""
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    db_path = Path("talia.db")
    if not db_path.exists():
        print(f"DB non trovato: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)

    # Scarica i 3 procedimenti (653, 654, 655)
    procs = [653, 654, 655]
    for proc_id in procs:
        _logger.info(f"\n=== Procedimento {proc_id} ===")
        try:
            downloaded = scarica_pdf_procedimento(conn, proc_id)
            print(f"Scaricati {len(downloaded)} file")
        except Exception as e:
            print(f"Errore: {e}", file=sys.stderr)

    conn.close()


if __name__ == "__main__":
    main()
