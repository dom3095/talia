"""Test B3 — Spider ANAC open data (TAL-22).

Tutti offline: usa il CSV sintetico in tests/fonti/fixtures/anac_sample.csv.
Nessuna rete, nessun dato reale.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from talia.modulo2_scraping.db import (
    AttoMetadato,
    EnteMetadato,
    atti_per_ente,
    connetti,
    conta_atti,
    inizializza_db,
    upsert_ente,
)
from talia.modulo2_scraping.fonti.anac import (
    FONTE_SCRAPER,
    SEZIONE_SICILIA,
    _filtra_sicilia,
    _leggi_csv,
    _mappa_atto,
    _parse_data_iso,
    _parse_importo,
    _url_cig,
    carica_csv_anac,
    scarica_e_carica,
)

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "anac_sample.csv"


# ---------------------------------------------------------------------------
# Fixtures pytest
# ---------------------------------------------------------------------------


@pytest.fixture
def csv_content() -> str:
    return FIXTURE_CSV.read_text(encoding="utf-8")


@pytest.fixture
def db():
    conn = connetti(":memory:")
    inizializza_db(conn)
    return conn


@pytest.fixture
def db_con_palermo(db):
    upsert_ente(db, EnteMetadato(denominazione="Comune di Palermo", codice_istat="082053", provincia="PA"))
    return db


@pytest.fixture
def db_completo(db):
    """DB con i principali enti siciliani del CSV fixture."""
    upsert_ente(db, EnteMetadato(denominazione="Comune di Palermo", codice_istat="082053", provincia="PA"))
    upsert_ente(db, EnteMetadato(denominazione="Comune di Catania", codice_istat="087015", provincia="CT"))
    upsert_ente(db, EnteMetadato(denominazione="Comune di Messina", codice_istat="083048", provincia="ME"))
    upsert_ente(db, EnteMetadato(denominazione="Comune di Agrigento", codice_istat="084001", provincia="AG"))
    return db


# ---------------------------------------------------------------------------
# Test utilità
# ---------------------------------------------------------------------------


def test_parse_importo_virgola_italiana():
    assert _parse_importo("4.500,00") == 4500.0


def test_parse_importo_punto_separatore():
    assert _parse_importo("18000,00") == 18000.0


def test_parse_importo_none():
    assert _parse_importo("") is None
    assert _parse_importo(None) is None


def test_parse_data_gg_mm_aaaa():
    assert _parse_data_iso("12/01/2024") == "2024-01-12"


def test_parse_data_iso_passthrough():
    assert _parse_data_iso("2024-01-12") == "2024-01-12"


def test_parse_data_vuota():
    assert _parse_data_iso("") is None
    assert _parse_data_iso(None) is None


def test_url_cig_formato():
    url = _url_cig("ABC1234567A")
    assert url == "https://dati.anticorruzione.it/opendata/cig/ABC1234567A"


# ---------------------------------------------------------------------------
# Test parsing CSV
# ---------------------------------------------------------------------------


def test_leggi_csv_tutte_le_righe(csv_content):
    righe = list(_leggi_csv(csv_content))
    assert len(righe) == 10


def test_leggi_csv_colonne_normalizzate(csv_content):
    righe = list(_leggi_csv(csv_content))
    prima = righe[0]
    assert "cig" in prima
    assert "denominazione_amministrazione" in prima
    assert "sezione_regionale" in prima
    assert "oggetto_principale_contratto" in prima


def test_filtra_sicilia_conta(csv_content):
    tutte = list(_leggi_csv(csv_content))
    sicilia = list(_filtra_sicilia(iter(tutte)))
    # 7 righe siciliane (PA×3, CT×2, ME×1, AG×2) e 2 fuori Sicilia (Roma, Milano)
    # Contiamo dal file fixture: PA 3 + CT 2 + ME 1 + AG 2 = 8
    assert len(sicilia) == 8


def test_filtra_sicilia_esclude_altre_regioni(csv_content):
    tutte = list(_leggi_csv(csv_content))
    sicilia = list(_filtra_sicilia(iter(tutte)))
    for r in sicilia:
        assert r["sezione_regionale"].strip().lower() == SEZIONE_SICILIA.lower()


def test_mappa_atto_campi_essenziali():
    riga = {
        "cig": "ABC1234567A",
        "denominazione_amministrazione": "Comune di Palermo",
        "sezione_regionale": "Sicilia",
        "oggetto_principale_contratto": "Fornitura carta",
        "importo_totale_appalto": "4500,00",
        "data_creazione": "12/01/2024",
        "tipo_appalto": "Forniture",
        "codice_scelta_contraente": "23",
        "descrizione_scelta_contraente": "Affidamento diretto",
        "cf_amministrazione": "80016350821",
        "anno_pubblicazione": "2024",
        "mese_pubblicazione": "1",
        "numero_gara": "2024-00001",
    }
    atto = _mappa_atto(riga, "082053")
    assert atto is not None
    assert atto.cig == "ABC1234567A"
    assert atto.ente_codice_istat == "082053"
    assert atto.tipo == "contratto_anac"
    assert atto.fonte_scraper == FONTE_SCRAPER
    assert atto.importo_euro == 4500.0
    assert atto.data_atto == "2024-01-12"
    assert atto.url_fonte == "https://dati.anticorruzione.it/opendata/cig/ABC1234567A"


def test_mappa_atto_senza_cig_restituisce_none():
    riga = {
        "cig": "",
        "denominazione_amministrazione": "Comune di Palermo",
        "sezione_regionale": "Sicilia",
        "oggetto_principale_contratto": "Fornitura",
    }
    assert _mappa_atto(riga, "082053") is None


# ---------------------------------------------------------------------------
# Test carica_csv_anac
# ---------------------------------------------------------------------------


def test_carica_csv_inserisce_atti_ente_presente(csv_content, db_con_palermo):
    """Con Palermo nel DB, carica tutti gli atti di Palermo."""
    esiti = carica_csv_anac(csv_content, db_con_palermo, crea_enti_mancanti=False)
    assert esiti["inseriti"] == 3  # 3 atti Palermo nel fixture


def test_carica_csv_enti_mancanti_saltati(csv_content, db_con_palermo):
    """Enti non nel DB vengono saltati quando crea_enti_mancanti=False."""
    esiti = carica_csv_anac(csv_content, db_con_palermo, crea_enti_mancanti=False)
    # 8 siciliani - 3 palermo = 5 saltati (CT×2, ME×1, AG×2)
    assert esiti["saltati"] == 5


def test_carica_csv_crea_enti_mancanti(csv_content, db_con_palermo):
    """Con crea_enti_mancanti=True, gli enti sconosciuti vengono inseriti."""
    esiti = carica_csv_anac(csv_content, db_con_palermo, crea_enti_mancanti=True)
    # Tutti gli 8 atti siciliani devono essere inseriti
    assert esiti["inseriti"] == 8
    assert esiti["saltati"] == 0


def test_carica_csv_idempotente(csv_content, db_completo):
    """Secondo run non duplica (UNIQUE su ente_id × url_fonte)."""
    esiti1 = carica_csv_anac(csv_content, db_completo)
    esiti2 = carica_csv_anac(csv_content, db_completo)
    assert esiti1["inseriti"] == 8
    assert esiti2["inseriti"] == 0
    assert esiti2["duplicati"] == 8
    assert conta_atti(db_completo) == 8


def test_carica_csv_esclude_non_sicilia(csv_content, db_completo):
    """Roma e Milano non devono essere nel DB dopo il caricamento."""
    carica_csv_anac(csv_content, db_completo)
    # Solo 8 atti siciliani devono essere presenti
    assert conta_atti(db_completo) == 8


def test_carica_csv_atti_palermo_dettaglio(csv_content, db_completo):
    """Controlla i metadati di un atto specifico di Palermo."""
    carica_csv_anac(csv_content, db_completo)
    atti = atti_per_ente(db_completo, "082053")
    assert len(atti) == 3
    cig_list = {a["cig"] for a in atti}
    assert "ABC1234567A" in cig_list
    assert "BBC9876543Z" in cig_list
    assert "JJJ8888888H" in cig_list


def test_carica_csv_oggetto_salvato(csv_content, db_completo):
    """Verifica che l'oggetto dell'appalto sia salvato correttamente."""
    carica_csv_anac(csv_content, db_completo)
    atti = atti_per_ente(db_completo, "082053")
    oggetti = {a["oggetto"] for a in atti}
    assert "Fornitura carta per uffici anno 2024" in oggetti


# ---------------------------------------------------------------------------
# Test scarica_e_carica (con _fetch_fn mock)
# ---------------------------------------------------------------------------


def test_scarica_e_carica_con_mock(csv_content, db_completo):
    """Testa scarica_e_carica iniettando una funzione di fetch mock."""

    def _mock_fetch(url: str, timeout: int = 60) -> str:
        return csv_content

    esiti = scarica_e_carica(db_completo, _fetch_fn=_mock_fetch)
    assert esiti["inseriti"] == 8


def test_scarica_e_carica_idempotente(csv_content, db_completo):
    """Due chiamate consecutive non duplicano."""

    def _mock_fetch(url: str, timeout: int = 60) -> str:
        return csv_content

    scarica_e_carica(db_completo, _fetch_fn=_mock_fetch)
    esiti2 = scarica_e_carica(db_completo, _fetch_fn=_mock_fetch)
    assert esiti2["inseriti"] == 0
    assert esiti2["duplicati"] == 8
