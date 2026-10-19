"""Test dell'estrazione notturna del testo degli atti (TAL-77). Nessuna rete."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from talia.modulo2_scraping import testo_atti
from talia.modulo2_scraping.db import (
    AttoMetadato,
    EnteMetadato,
    connetti,
    inizializza_db,
    inserisci_atto,
    upsert_ente,
)
from talia.modulo2_scraping.pdf_download import Allegato
from talia.modulo2_scraping.testo_atti import (
    atti_da_estrarre,
    cig_univoco,
    estrai_testo_atti,
    tipo_utile,
)

_ORA = datetime.now(UTC)


@pytest.fixture()
def conn():
    c = connetti(":memory:")
    inizializza_db(c)
    for istat, nome in (("088009", "Comune di Ragusa"), ("088011", "Comune di Scicli")):
        upsert_ente(c, EnteMetadato(denominazione=nome, codice_istat=istat))
    return c


def _atto(conn, n, *, istat="088009", tipo="determine /determina dirigenziale",
          oggetto="AFFIDAMENTO SERVIZIO", fonte="jcitygov", giorni_fa=1, cig=None):  # fmt: skip
    return inserisci_atto(
        conn,
        AttoMetadato(
            ente_codice_istat=istat,
            tipo=tipo,
            oggetto=oggetto,
            url_fonte=f"https://ragusa.example.it/-/papca/display/{n}",
            fonte_scraper=fonte,
            data_accesso=(_ORA - timedelta(days=giorni_fa)).isoformat(),
            cig=cig,
        ),
    )


# --- selezione -------------------------------------------------------------


@pytest.mark.parametrize(
    ("tipo", "oggetto", "atteso"),
    [
        ("determine /atto di liquidazione", "LIQUIDAZIONE FATTURA", True),
        ("delibere /delibere di giunta", "CONCESSIONE PATROCINIO", True),
        ("atto in trasparenza /avvisi", "AVVISO PUBBLICO PER LA NOMINA", True),
        ("(stc) pubblicazioni di matrimonio", "ATTO N. 139", False),
        ("atto in trasparenza /deposito messi art.60", "", False),
        ("ordinanze /ordinanza dirigenziale", "ORDINANZA-INGIUNZIONE", False),
        ("altri atti", "PERMESSO DI COSTRUIRE N. 4/2026", False),
        ("informazioni ambientali", "", False),
    ],
)
def test_tipo_utile(tipo, oggetto, atteso):
    assert tipo_utile(tipo, oggetto) is atteso


def test_selezione_filtra_fonte_eta_tipo_e_gia_tentati(conn):
    buono = _atto(conn, 1)
    _atto(conn, 2, fonte="halley")  # piattaforma non supportata
    _atto(conn, 3, giorni_fa=40)  # link probabilmente scaduto
    _atto(conn, 4, tipo="(stc) pubblicazioni di matrimonio")
    tentato = _atto(conn, 5)
    conn.execute("UPDATE atti SET testo_estratto = '' WHERE id = ?", (tentato,))

    assert atti_da_estrarre(conn) == [buono]


def test_selezione_alterna_gli_enti(conn):
    ragusa = [_atto(conn, n) for n in range(3)]
    scicli = _atto(conn, 10, istat="088011")
    scelti = atti_da_estrarre(conn, limite=2)
    assert scicli in scelti
    assert len(set(scelti) & set(ragusa)) == 1


# --- CIG -------------------------------------------------------------------


def test_cig_univoco():
    assert cig_univoco("Affidamento ... CIG: B12345678A ... impegno") == "B12345678A"
    # Due CIG distinti: non si sceglie a caso.
    assert cig_univoco("CIG: B12345678A e CIG B98765432Z") is None
    # Lo stesso CIG ripetuto resta univoco.
    assert cig_univoco("CIG: B12345678A ... (CIG B12345678A)") == "B12345678A"
    # Solo il padre dell'accordo quadro: non è il CIG dell'atto.
    assert cig_univoco("CIG padre: A11111111A") is None
    assert cig_univoco("nessun codice") is None


# --- orchestrazione ----------------------------------------------------------


def _estrai_finto(risposte):
    def _fn(url_fonte, _opener, _cartella, _delay):
        r = risposte[url_fonte.rsplit("/", 1)[1]]
        if isinstance(r, Exception):
            raise r
        return r

    return _fn


def test_salva_testo_hash_e_cig_solo_se_mancante(conn):
    a = _atto(conn, 1)
    b = _atto(conn, 2, cig="Z00000000Z")
    estrai = _estrai_finto(
        {"1": ("Determina ... CIG: B12345678A", "h1"), "2": ("CIG: B12345678A", "h2")}
    )

    esito = estrai_testo_atti(conn, opener=object(), estrai=estrai)

    assert (esito.tentati, esito.con_testo, esito.cig_aggiunti) == (2, 2, 1)
    riga_a = conn.execute("SELECT * FROM atti WHERE id=?", (a,)).fetchone()
    assert riga_a["testo_estratto"].startswith("Determina")
    assert riga_a["hash_sha256"] == "h1"
    assert riga_a["cig"] == "B12345678A"
    # Un CIG già noto (dall'oggetto o dallo scraper) non viene sovrascritto.
    assert conn.execute("SELECT cig FROM atti WHERE id=?", (b,)).fetchone()[0] == "Z00000000Z"


def test_fallimenti_marcati_e_non_bloccanti(conn):
    import urllib.error

    a = _atto(conn, 1)  # nessun PDF in chiaro: definitivo
    b = _atto(conn, 2)  # errore di rete: da riprovare
    c = _atto(conn, 3)
    d = _atto(conn, 4)  # pagina sparita: definitivo
    estrai = _estrai_finto(
        {
            "1": None,
            "2": OSError("[Errno 54] Connection reset by peer"),
            "3": ("testo", "h"),
            "4": urllib.error.HTTPError("u", 404, "Not Found", {}, None),
        }
    )

    esito = estrai_testo_atti(conn, opener=object(), estrai=estrai)

    assert (esito.con_testo, esito.senza_testo, esito.rimandati) == (1, 2, 1)
    valori = dict(conn.execute("SELECT id, testo_estratto FROM atti").fetchall())
    # '' = tentato e chiuso; NULL = si riprova la notte dopo.
    assert valori[a] == "" and valori[d] == "" and valori[c] == "testo"
    assert valori[b] is None
    assert atti_da_estrarre(conn) == [b]


def test_primo_pdf_download_fallito_e_errore_di_rete(tmp_path, monkeypatch):
    """Se l'unico allegato non si scarica, non si può dire che il PDF non c'è."""
    allegati = [Allegato(chiave_allegato="1", mimetype="application/pdf", url_download="u1")]
    monkeypatch.setattr(testo_atti, "trova_allegati", lambda _url, opener, **_k: allegati)
    monkeypatch.setattr(testo_atti, "scarica_pdf_allegato", lambda *_a, **_k: None)

    with pytest.raises(testo_atti.ErroreRete):
        testo_atti._primo_pdf("https://x/display/1", None, tmp_path, 0)


def test_primo_pdf_salta_p7m_e_cancella_il_file(tmp_path, monkeypatch):
    allegati = [
        Allegato(chiave_allegato="1", mimetype="application/x-pkcs7-mime", url_download="u1"),
        Allegato(chiave_allegato="2", mimetype="application/x-pkcs7-mime", url_download="u2"),
    ]
    monkeypatch.setattr(testo_atti, "trova_allegati", lambda _url, opener, **_k: allegati)

    def _scarica(url, dest_base: Path, opener):
        ext = "bin" if url == "u1" else "pdf"  # .p7m prima, PDF in chiaro dopo
        p = dest_base.with_suffix(f".{ext}")
        p.write_bytes(b"x")
        return p, p.name, f"hash-{url}"

    monkeypatch.setattr(testo_atti, "scarica_pdf_allegato", _scarica)
    monkeypatch.setattr(testo_atti, "testo_pdf_nativo", lambda p: f"testo di {p.suffix}")

    testo, hash_sha = testo_atti._primo_pdf("https://x/display/1", None, tmp_path, 0)

    assert (testo, hash_sha) == ("testo di .pdf", "hash-u2")
    assert not list(tmp_path.glob("*.pdf"))
