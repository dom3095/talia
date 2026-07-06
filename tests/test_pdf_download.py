"""Test download PDF on-demand da catene (TAL-47).

I test non fanno chiamate HTTP: usano HTML fixture sintetiche e un opener finto.
Struttura fixture ricalcata sulla pagina di dettaglio reale jCityGov
(/papca/display/<id>), anonimizzata.
"""

from __future__ import annotations

import base64
import json
import sqlite3
from pathlib import Path

from talia.modulo2_scraping import db
from talia.modulo2_scraping.pdf_download import (
    _url_display_format,
    motivo_selezione,
    procedimenti_critici,
    scarica_pdf_allegato,
    scarica_pdf_procedimento,
    trova_allegati,
)

# ---------------------------------------------------------------------------
# Fixture: pagina di dettaglio con 2 allegati
# ---------------------------------------------------------------------------

_URL_PDF_1 = "https://esempio.trasparenza-valutazione-merito.it/dl?id=111"
_URL_PDF_2 = "https://esempio.trasparenza-valutazione-merito.it/dl?id=222"


def _b64(url: str) -> str:
    return base64.b64encode(url.encode()).decode()


_HTML_DETTAGLIO = f"""
<table class="allegati">
<tbody>
<tr data-chiave-allegato="111" data-mimetype="application/pdf" class="riga">
  <td>determina.pdf</td>
  <td><a onclick="window.open(atob('{_b64(_URL_PDF_1)}'))">scarica</a></td>
</tr>
<tr data-chiave-allegato="222" data-mimetype="application/octet-stream" class="riga">
  <td>firma.p7m</td>
  <td><a onclick="window.open(atob('{_b64(_URL_PDF_2)}'))">scarica</a></td>
</tr>
</tbody>
</table>
"""

_HTML_SENZA_ALLEGATI = "<html><body><p>Dettaglio pubblicazione</p></body></html>"

# Pagina corrotta: righe allegato presenti ma base64 non decodificabile
_HTML_CORROTTO = """
<tr data-chiave-allegato="333" data-mimetype="application/pdf">
  <td><a onclick="window.open(atob('!!!non-base64!!!'))">scarica</a></td>
</tr>
"""

_PDF_BYTES = b"%PDF-1.4 contenuto finto del pdf"
_P7M_BYTES = b"\x30\x82firma binaria finta"


# ---------------------------------------------------------------------------
# Opener finto (niente HTTP)
# ---------------------------------------------------------------------------


class _RispostaFinta:
    def __init__(self, body: bytes, content_disposition: str = ""):
        self._body = body
        self._cd = content_disposition

    def read(self) -> bytes:
        return self._body

    @property
    def headers(self):
        return self

    def get_content_charset(self, default: str) -> str:
        return default

    def get(self, name: str, default: str = "") -> str:
        if name.lower() == "content-disposition":
            return self._cd or default
        return default

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _OpenerFinto:
    """Mappa url → risposta; registra le richieste fatte."""

    def __init__(self, risposte: dict[str, _RispostaFinta]):
        self._risposte = risposte
        self.richieste: list[str] = []

    def open(self, req, timeout=None):
        url = req.full_url
        self.richieste.append(url)
        if url not in self._risposte:
            raise AssertionError(f"URL inatteso: {url}")
        return self._risposte[url]


# ---------------------------------------------------------------------------
# _url_display_format
# ---------------------------------------------------------------------------


def test_url_display_da_mostradettaglio():
    url = (
        "https://esempio.trasparenza-valutazione-merito.it/web/trasparenza/papca-g"
        "?p_p_id=jcitygovalbopubblicazioni_WAR_jcitygovalbiportlet"
        "&_jcitygovalbopubblicazioni_WAR_jcitygovalbiportlet_id=4692608"
        "&_jcitygovalbopubblicazioni_WAR_jcitygovalbiportlet_action=mostraDettaglio"
    )
    assert _url_display_format(url) == (
        "https://esempio.trasparenza-valutazione-merito.it"
        "/web/trasparenza/papca-g/-/papca/display/4692608"
    )


def test_url_display_fallback_se_non_riconosciuto():
    url = "https://altro-portale.example/dettaglio?id=1"
    assert _url_display_format(url) == url


# ---------------------------------------------------------------------------
# trova_allegati
# ---------------------------------------------------------------------------


def _opener_dettaglio(html: str, url: str) -> _OpenerFinto:
    return _OpenerFinto({url: _RispostaFinta(html.encode())})


def test_trova_allegati_caso_normale():
    url = "https://esempio.trasparenza-valutazione-merito.it/web/trasparenza/papca-g/-/papca/display/1"
    allegati = trova_allegati(url, opener=_opener_dettaglio(_HTML_DETTAGLIO, url))
    assert len(allegati) == 2
    assert allegati[0].chiave_allegato == "111"
    assert allegati[0].mimetype == "application/pdf"
    assert allegati[0].url_download == _URL_PDF_1
    assert allegati[1].chiave_allegato == "222"
    assert allegati[1].url_download == _URL_PDF_2


def test_trova_allegati_zero_allegati(caplog):
    url = "https://esempio.trasparenza-valutazione-merito.it/web/trasparenza/papca-g/-/papca/display/2"
    with caplog.at_level("WARNING"):
        allegati = trova_allegati(url, opener=_opener_dettaglio(_HTML_SENZA_ALLEGATI, url))
    assert allegati == []
    # Convenzione progetto: 0 risultati → WARNING esplicito, mai silenzio
    assert any("essun allegato" in r.message for r in caplog.records)


def test_trova_allegati_base64_corrotto():
    url = "https://esempio.trasparenza-valutazione-merito.it/web/trasparenza/papca-g/-/papca/display/3"
    allegati = trova_allegati(url, opener=_opener_dettaglio(_HTML_CORROTTO, url))
    # La riga c'è ma l'URL non è decodificabile: allegato senza url_download
    assert len(allegati) == 1
    assert allegati[0].url_download is None


# ---------------------------------------------------------------------------
# scarica_pdf_allegato: estensione dai magic bytes + idempotenza
# ---------------------------------------------------------------------------


def test_estensione_pdf_da_magic_bytes(tmp_path):
    opener = _OpenerFinto({_URL_PDF_1: _RispostaFinta(_PDF_BYTES)})
    result = scarica_pdf_allegato(_URL_PDF_1, tmp_path / "3388_111", opener=opener)
    assert result is not None
    path, _, _ = result
    assert path.suffix == ".pdf"
    assert path.read_bytes() == _PDF_BYTES


def test_estensione_bin_se_non_pdf(tmp_path):
    opener = _OpenerFinto({_URL_PDF_2: _RispostaFinta(_P7M_BYTES)})
    result = scarica_pdf_allegato(_URL_PDF_2, tmp_path / "3388_222", opener=opener)
    assert result is not None
    path, _, _ = result
    assert path.suffix == ".bin"


def test_idempotenza_skip_se_gia_scaricato(tmp_path):
    opener = _OpenerFinto({_URL_PDF_1: _RispostaFinta(_PDF_BYTES)})
    base = tmp_path / "3388_111"
    scarica_pdf_allegato(_URL_PDF_1, base, opener=opener)
    assert len(opener.richieste) == 1

    # Secondo giro: il file esiste → nessuna nuova richiesta HTTP
    result = scarica_pdf_allegato(_URL_PDF_1, base, opener=opener)
    assert result is not None
    assert len(opener.richieste) == 1


# ---------------------------------------------------------------------------
# scarica_pdf_procedimento: end-to-end su DB in memoria
# ---------------------------------------------------------------------------


def _db_con_procedimento() -> sqlite3.Connection:
    conn = db.connetti(":memory:")
    db.inizializza_db(conn)
    # Stesso schema di engine/catena._evolvi_schema
    conn.executescript(
        """
        CREATE TABLE procedimenti (
            id INTEGER PRIMARY KEY, ente_id INTEGER, tipo TEXT, cig TEXT,
            oggetto TEXT, data_avvio TEXT, data_chiusura TEXT, stato_finale TEXT,
            metodo_individuazione TEXT, creato_a TEXT
        );
        ALTER TABLE atti ADD COLUMN procedimento_id INTEGER;
        ALTER TABLE atti ADD COLUMN ruolo_in_catena TEXT;
        ALTER TABLE atti ADD COLUMN numero_settoriale TEXT;
        """
    )
    db.upsert_ente(conn, db.EnteMetadato(denominazione="Comune di Esempio", codice_istat="099999"))
    conn.execute(
        """
        INSERT INTO procedimenti (id, ente_id, oggetto, stato_finale,
                                  metodo_individuazione, creato_a)
        VALUES (653, 1, 'SELEZIONE DI ESEMPIO', 'revocato', 'contenimento_oggetto', '2026-07-05')
        """
    )
    conn.execute(
        """
        INSERT INTO atti (ente_id, tipo, data_accesso, url_fonte, fonte_scraper,
                          metadati, procedimento_id, ruolo_in_catena, numero)
        VALUES (1, 'determina', '2026-07-05', ?, 'jcitygov', '{}', 653, 'revoca', '932')
        """,
        (
            "https://esempio.trasparenza-valutazione-merito.it/web/trasparenza/papca-g/-/papca/display/1",
        ),
    )
    conn.commit()
    return conn


def test_scarica_procedimento_end_to_end(tmp_path):
    conn = _db_con_procedimento()
    url_dettaglio = "https://esempio.trasparenza-valutazione-merito.it/web/trasparenza/papca-g/-/papca/display/1"
    opener = _OpenerFinto(
        {
            url_dettaglio: _RispostaFinta(_HTML_DETTAGLIO.encode()),
            _URL_PDF_1: _RispostaFinta(_PDF_BYTES, 'attachment; filename="determina.pdf"'),
            _URL_PDF_2: _RispostaFinta(_P7M_BYTES, 'attachment; filename="firma.p7m"'),
        }
    )

    scaricati = scarica_pdf_procedimento(conn, 653, dest_dir=tmp_path, opener=opener, delay=0)

    assert len(scaricati) == 2
    assert sorted(p.suffix for p in scaricati) == [".bin", ".pdf"]

    # url_pdf punta al PRIMO allegato PDF (non alla firma .bin)
    row = conn.execute("SELECT url_pdf FROM atti WHERE id = 1").fetchone()
    assert row["url_pdf"] == _URL_PDF_1

    # meta.json presente e coerente
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert len(meta) == 2
    assert meta[0]["filename_originale"] == "determina.pdf"
    assert all(m["hash_sha256"] for m in meta)

    # motivo_selezione.json: giustificazione esplicabile della selezione, dal DB
    motivo = json.loads((tmp_path / "motivo_selezione.json").read_text())
    assert motivo["procedimento_id"] == 653
    assert motivo["stato_finale"] == "revocato"
    assert motivo["metodo_individuazione"] == "contenimento_oggetto"
    assert motivo["atti"][0]["ruolo_in_catena"] == "revoca"
    assert motivo["atti"][0]["url_fonte"].startswith("https://")
    assert "disclaimer" in motivo
    # I segnali sono specifici della catena, non formule generiche
    tipi = {s["tipo"] for s in motivo["segnali"]}
    assert "esito_critico" in tipi
    assert "avvio_non_in_albo" in tipi  # la catena di test ha solo la revoca


def test_motivo_selezione_procedimento_inesistente():
    conn = _db_con_procedimento()
    assert motivo_selezione(conn, 999) == {}


def test_segnali_stesso_giorno_e_riferimento_non_riscontrato():
    conn = _db_con_procedimento()
    # Aggiungo l'atto di avvio pubblicato lo STESSO GIORNO della revoca,
    # e la revoca cita "N. 33/2025" che non esiste nella catena (caso reale Palma)
    conn.execute(
        "UPDATE atti SET data_pub = '2026-06-05', "
        "oggetto = \"REVOCA IN AUTOTUTELA DELL'AVVISO APPROVATO CON DETERMINAZIONE N. 33/2025\" "
        "WHERE id = 1"
    )
    conn.execute(
        """INSERT INTO atti (ente_id, tipo, data_accesso, url_fonte, fonte_scraper, metadati,
                             procedimento_id, ruolo_in_catena, numero, numero_settoriale, data_pub)
           VALUES (1, 'determina', '2026-07-06', 'https://esempio.tvm.it/display/2', 'jcitygov',
                   '{}', 653, 'avvio', '1706', '35/2025', '2026-06-05')"""
    )
    # Atto vecchio fuori catena: estende la copertura DB dell'ente al 2024, così
    # il riferimento citato "N. 33/2025" è DENTRO la finestra e il segnale scatta
    conn.execute(
        """INSERT INTO atti (ente_id, tipo, data_accesso, url_fonte, fonte_scraper,
                             metadati, data_pub)
           VALUES (1, 'determina', '2026-07-06', 'https://esempio.tvm.it/display/3',
                   'jcitygov', '{}', '2024-01-01')"""
    )
    conn.commit()

    motivo = motivo_selezione(conn, 653)
    tipi = {s["tipo"] for s in motivo["segnali"]}
    assert "avvio_e_chiusura_stesso_giorno" in tipi
    assert "riferimento_non_riscontrato" in tipi  # 33/2025 ∉ {1706, 35/2025, 932}
    assert "avvio_non_in_albo" not in tipi  # ora l'avvio c'è

    # Se la revoca cita un numero presente in catena, nessun falso positivo
    conn.execute(
        "UPDATE atti SET oggetto = \"REVOCA DELL'AVVISO APPROVATO CON DETERMINAZIONE N. 35/2025\" "
        "WHERE id = 1"
    )
    conn.commit()
    motivo = motivo_selezione(conn, 653)
    assert "riferimento_non_riscontrato" not in {s["tipo"] for s in motivo["segnali"]}


def test_riferimento_fuori_copertura_non_scatta():
    """Un numero citato di un anno PRECEDENTE alla copertura DB dell'ente non è
    un'anomalia dell'ente: è un limite del nostro scraping (anti-falso-positivo)."""
    conn = _db_con_procedimento()
    # Copertura ente: solo 2026. La revoca cita un atto del 2008.
    conn.execute(
        "UPDATE atti SET data_pub = '2026-06-05', "
        "oggetto = \"REVOCA DELL'AVVISO APPROVATO CON DETERMINAZIONE N. 81/2008\" "
        "WHERE id = 1"
    )
    conn.commit()
    motivo = motivo_selezione(conn, 653)
    assert "riferimento_non_riscontrato" not in {s["tipo"] for s in motivo["segnali"]}


def test_procedimenti_critici_seleziona_solo_fonti_supportate():
    conn = _db_con_procedimento()
    # Il proc. 653 (revocato, fonte jcitygov) è selezionato
    assert procedimenti_critici(conn) == [653]
    # Con una fonte diversa non c'è nulla da scaricare
    assert procedimenti_critici(conn, fonti=("portalepa",)) == []
    # Un procedimento 'aggiudicato' non è critico
    conn.execute("UPDATE procedimenti SET stato_finale = 'aggiudicato' WHERE id = 653")
    assert procedimenti_critici(conn) == []


def test_procedimenti_critici_round_robin_e_limite():
    conn = _db_con_procedimento()
    db.upsert_ente(conn, db.EnteMetadato(denominazione="Comune B", codice_istat="099998"))
    # Ente 1 ha già il proc. 653; aggiungo 700 (ente 1) e 800, 801 (ente 2)
    for proc_id, ente_id in ((700, 1), (800, 2), (801, 2)):
        conn.execute(
            """INSERT INTO procedimenti (id, ente_id, stato_finale, metodo_individuazione, creato_a)
               VALUES (?, ?, 'revocato', 'cig', '2026-07-06')""",
            (proc_id, ente_id),
        )
        conn.execute(
            """INSERT INTO atti (ente_id, tipo, data_accesso, url_fonte, fonte_scraper,
                                 metadati, procedimento_id)
               VALUES (?, 'determina', '2026-07-06', ?, 'jcitygov', '{}', ?)""",
            (ente_id, f"https://esempio.tvm.it/display/{proc_id}", proc_id),
        )
    conn.commit()

    # Round-robin: un procedimento per ente a ogni giro, non tutti dell'ente 1 prima
    assert procedimenti_critici(conn, limite=3) == [653, 800, 700]
    # Senza limite: tutti, ordinati per ente
    assert procedimenti_critici(conn, limite=None) == [653, 700, 800, 801]


def test_scarica_procedimento_inesistente(caplog):
    conn = _db_con_procedimento()
    with caplog.at_level("WARNING"):
        scaricati = scarica_pdf_procedimento(conn, 999, dest_dir=Path("/nonusato"), delay=0)
    assert scaricati == []
    assert any("essun atto" in r.message for r in caplog.records)
