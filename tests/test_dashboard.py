"""Test Modulo 3 — Dashboard Streamlit (TAL-30).

Smoke test: verifica che il modulo si importi e le funzioni di lettura DB
funzionino correttamente su un database in memoria.
"""

from __future__ import annotations

import json

import pytest

# L'app importa streamlit (extra 'dashboard'): senza, i test si skippano
# come i test OCR senza Tesseract. In CI l'extra è installato.
pytest.importorskip("streamlit", reason="extra 'dashboard' non installato")

from talia.modulo2_scraping.db import (
    AttoMetadato,
    EnteMetadato,
    connetti,
    inizializza_db,
    inserisci_atto,
    salva_red_flag,
    upsert_ente,
)

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn_popolato():
    """DB in memoria con un ente, un atto e un red flag."""
    conn = connetti(":memory:")
    inizializza_db(conn)

    ente = EnteMetadato(
        denominazione="Comune di Test",
        codice_istat="082999",
        provincia="AG",
        popolazione=10_000,
    )
    ente_id = upsert_ente(conn, ente)

    atto = AttoMetadato(
        ente_codice_istat="082999",
        tipo="determina",
        url_fonte="https://example.com/atto/1",
        fonte_scraper="test",
        data_accesso="2024-01-01T00:00:00",
        oggetto="Affidamento diretto servizio pulizia",
        importo_euro=50_000.0,
        data_atto="2024-01-15",
    )
    atto_id = inserisci_atto(conn, atto)

    salva_red_flag(
        conn,
        ente_id=ente_id,
        tipo_flag="frazionamento",
        severita="alta",
        descrizione="Potenziale frazionamento artificioso.",
        atti_cig=[{"id": atto_id, "url": "https://example.com/atto/1", "importo": 50_000.0}],
        periodo_da="2024-01-01",
        periodo_a="2024-03-31",
    )

    return conn


@pytest.fixture()
def conn_piccolo_comune():
    """DB in memoria con un piccolo comune (< 5000 ab.)."""
    conn = connetti(":memory:")
    inizializza_db(conn)

    ente = EnteMetadato(
        denominazione="Comune Piccolo",
        codice_istat="082001",
        provincia="PA",
        popolazione=1_500,
    )
    ente_id = upsert_ente(conn, ente)

    salva_red_flag(
        conn,
        ente_id=ente_id,
        tipo_flag="concentrazione_diretti",
        severita="media",
        descrizione="Concentrazione eccessiva affidamenti diretti.",
        atti_cig=[{"id": 99, "url": "https://example.com/atto/99", "tipo": "determina"}],
    )

    return conn


# ---------------------------------------------------------------------------
# Import smoke test
# ---------------------------------------------------------------------------


def test_modulo_dashboard_importabile():
    """Il modulo app è importabile senza errori di sintassi/dipendenze mancanti."""
    import talia.modulo3_dashboard.app as app_mod  # noqa: F401

    assert callable(app_mod.main)


# ---------------------------------------------------------------------------
# Test funzioni di lettura DB
# ---------------------------------------------------------------------------


def test_carica_flags_per_ente(conn_popolato):
    from talia.modulo3_dashboard.app import _carica_flags_per_ente

    rows = _carica_flags_per_ente(conn_popolato)
    assert len(rows) == 1
    assert rows[0]["denominazione"] == "Comune di Test"
    assert rows[0]["n_flags"] == 1
    assert rows[0]["n_alta"] == 1
    assert rows[0]["n_media"] == 0


def test_carica_flags_detail(conn_popolato):
    from talia.modulo3_dashboard.app import _carica_flags_detail

    rows = _carica_flags_per_ente_helper(conn_popolato)
    ente_id = rows[0]["ente_id"]
    flags = _carica_flags_detail(conn_popolato, ente_id)
    assert len(flags) == 1
    assert flags[0]["tipo_flag"] == "frazionamento"
    atti_cig = json.loads(flags[0]["atti_cig"])
    assert len(atti_cig) == 1
    assert atti_cig[0]["url"] == "https://example.com/atto/1"


def test_carica_atti_da_ids(conn_popolato):
    from talia.modulo3_dashboard.app import _carica_atti_da_ids

    # Ottieni l'id dell'atto inserito
    atto_row = conn_popolato.execute("SELECT id FROM atti LIMIT 1").fetchone()
    atto_id = atto_row["id"]

    mappa = _carica_atti_da_ids(conn_popolato, [atto_id])
    assert atto_id in mappa
    assert mappa[atto_id]["url_fonte"] == "https://example.com/atto/1"


def test_is_piccolo_comune():
    from talia.modulo3_dashboard.app import _is_piccolo_comune

    assert _is_piccolo_comune(1_000) is True
    assert _is_piccolo_comune(4_999) is True
    assert _is_piccolo_comune(5_000) is False
    assert _is_piccolo_comune(50_000) is False
    assert _is_piccolo_comune(None) is False


def test_comuni_virtuosi_separati(conn_popolato):
    """Un comune senza red flag deve apparire tra i virtuosi (n_flags == 0)."""
    from talia.modulo2_scraping.db import upsert_ente
    from talia.modulo3_dashboard.app import _carica_flags_per_ente

    # Aggiunge un secondo ente senza flag
    upsert_ente(
        conn_popolato,
        EnteMetadato(denominazione="Comune Virtuoso", codice_istat="082777", popolazione=20_000),
    )

    rows = _carica_flags_per_ente(conn_popolato)
    virtuosi = [r for r in rows if r["n_flags"] == 0]
    con_flags = [r for r in rows if r["n_flags"] > 0]

    assert any(r["denominazione"] == "Comune Virtuoso" for r in virtuosi)
    assert any(r["denominazione"] == "Comune di Test" for r in con_flags)


def test_piccolo_comune_nel_db(conn_piccolo_comune):
    from talia.modulo3_dashboard.app import _carica_flags_per_ente, _is_piccolo_comune

    rows = _carica_flags_per_ente(conn_piccolo_comune)
    assert len(rows) == 1
    assert _is_piccolo_comune(rows[0]["popolazione"]) is True


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _carica_flags_per_ente_helper(conn):
    from talia.modulo3_dashboard.app import _carica_flags_per_ente

    return _carica_flags_per_ente(conn)
