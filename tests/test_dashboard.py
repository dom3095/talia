"""Test Modulo 3 — Dashboard Streamlit (TAL-30).

Smoke test: verifica che il modulo si importi e le funzioni di lettura DB
funzionino correttamente su un database in memoria.
"""

from __future__ import annotations

import json
from pathlib import Path

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
# Test statistiche di ingestione (tab "Statistiche")
# ---------------------------------------------------------------------------


def test_carica_statistiche_generali(conn_popolato):
    from talia.modulo3_dashboard.app import _carica_statistiche_generali

    stats = _carica_statistiche_generali(conn_popolato)
    assert stats["tot_atti"] == 1
    assert stats["tot_enti_con_atti"] == 1
    assert stats["tot_red_flags"] == 1
    # L'atto di fixture ha data_accesso 2024-01-01: fuori dalla finestra 7/30gg "oggi".
    assert stats["atti_7g"] == 0
    assert stats["atti_30g"] == 0


def test_carica_atti_per_giorno_include_atto_recente():
    from datetime import UTC, datetime

    from talia.modulo2_scraping.db import (
        AttoMetadato,
        EnteMetadato,
        connetti,
        inizializza_db,
        inserisci_atto,
        upsert_ente,
    )
    from talia.modulo3_dashboard.app import _carica_atti_per_giorno

    conn = connetti(":memory:")
    inizializza_db(conn)
    upsert_ente(conn, EnteMetadato(denominazione="Comune di Test", codice_istat="082999"))

    oggi = datetime.now(UTC).isoformat()
    inserisci_atto(
        conn,
        AttoMetadato(
            ente_codice_istat="082999",
            tipo="determina",
            url_fonte="https://example.com/atto/oggi",
            fonte_scraper="test",
            data_accesso=oggi,
        ),
    )

    trend = _carica_atti_per_giorno(conn, giorni=1)
    assert len(trend) == 1
    assert trend[0]["n"] == 1


def test_carica_atti_per_provincia(conn_popolato):
    from talia.modulo3_dashboard.app import _carica_atti_per_provincia

    righe = _carica_atti_per_provincia(conn_popolato)
    assert len(righe) == 1
    assert righe[0]["provincia"] == "AG"
    assert righe[0]["n"] == 1


def test_carica_atti_per_tipo(conn_popolato):
    from talia.modulo3_dashboard.app import _carica_atti_per_tipo

    righe = _carica_atti_per_tipo(conn_popolato)
    assert righe[0]["tipo"] == "determina"
    assert righe[0]["n"] == 1


def test_carica_atti_per_fonte(conn_popolato):
    from talia.modulo3_dashboard.app import _carica_atti_per_fonte

    righe = _carica_atti_per_fonte(conn_popolato)
    assert righe[0]["fonte_scraper"] == "test"
    assert righe[0]["n"] == 1


# ---------------------------------------------------------------------------
# Test mappa di copertura (tab "Mappa copertura")
# ---------------------------------------------------------------------------

_GEOJSON_FINTO = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"name": "Comune Coperto", "com_istat_code": "082999"},
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [0, 0]]]},
        },
        {
            "type": "Feature",
            "properties": {"name": "Comune Mai Censito", "com_istat_code": "082111"},
            "geometry": {"type": "Polygon", "coordinates": [[[1, 1], [1, 2], [2, 2], [1, 1]]]},
        },
    ],
}


def test_carica_stato_scraper_per_comune(conn_popolato):
    from talia.modulo3_dashboard.app import _carica_stato_scraper_per_comune

    stato = _carica_stato_scraper_per_comune(conn_popolato)
    assert "082999" in stato
    assert stato["082999"]["n_atti"] == 1


def test_costruisci_geojson_copertura_comune_coperto_vs_non_censito():
    from talia.modulo3_dashboard.app import _costruisci_geojson_copertura

    stato_per_comune = {"082999": {"stato_scraper": "attivo", "n_atti": 5}}
    risultato = _costruisci_geojson_copertura(_GEOJSON_FINTO, stato_per_comune)

    coperto = risultato["features"][0]["properties"]
    non_censito = risultato["features"][1]["properties"]

    assert coperto["stato_label"] == "Coperto"
    assert coperto["n_atti"] == 5
    assert non_censito["stato_label"] == "Non censito"
    assert non_censito["n_atti"] == 0
    assert coperto["fill_color"] != non_censito["fill_color"]


def test_costruisci_geojson_copertura_non_muta_originale():
    from talia.modulo3_dashboard.app import _costruisci_geojson_copertura

    originale_props_prima = dict(_GEOJSON_FINTO["features"][0]["properties"])
    _costruisci_geojson_copertura(_GEOJSON_FINTO, {})
    assert _GEOJSON_FINTO["features"][0]["properties"] == originale_props_prima


def test_calcola_copertura_popolazione():
    from talia.modulo3_dashboard.app import _calcola_copertura_popolazione

    stato_per_comune = {"082999": {"stato_scraper": "attivo", "n_atti": 5}}
    popolazione_per_comune = {"082999": 10_000, "082111": 2_000}

    esito = _calcola_copertura_popolazione(_GEOJSON_FINTO, stato_per_comune, popolazione_per_comune)

    assert esito["tot_comuni"] == 2
    assert esito["tot_popolazione"] == 12_000
    assert esito["coperti_comuni"] == 1
    assert esito["coperti_popolazione"] == 10_000
    assert esito["per_stato"] == {"attivo": 1, "non_censito": 1}


def test_calcola_copertura_popolazione_escluso_default_conta_come_coperto():
    from talia.modulo3_dashboard.app import _calcola_copertura_popolazione

    stato_per_comune = {
        "082999": {"stato_scraper": "escluso_default", "n_atti": 0},
        "082111": {"stato_scraper": "bloccato", "n_atti": 0},
    }
    esito = _calcola_copertura_popolazione(_GEOJSON_FINTO, stato_per_comune, {})

    assert esito["coperti_comuni"] == 1
    assert esito["per_stato"] == {"escluso_default": 1, "bloccato": 1}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _carica_flags_per_ente_helper(conn):
    from talia.modulo3_dashboard.app import _carica_flags_per_ente

    return _carica_flags_per_ente(conn)


# ---------------------------------------------------------------------------
# Tab "Analisi fascicolo" (TAL-60)
# ---------------------------------------------------------------------------

_SAMPLES = Path(__file__).resolve().parent.parent / "data" / "samples"


def _fascicolo_bytes(cartella: str) -> list[tuple[str, bytes, str | None]]:
    percorso = _SAMPLES / cartella
    return [(f.name, f.read_bytes(), None) for f in sorted(percorso.glob("*.txt"))]


def test_analizza_file_caricati_txt_produce_report():
    from talia.modulo3_dashboard.app import _analizza_file_caricati

    report = _analizza_file_caricati(_fascicolo_bytes("fascicolo_coerente"), valuta_llm=False)

    assert report.esiti
    assert len(report.atti) == 2


def test_analizza_file_caricati_pdf(pdf_minimo):
    # Ramo .pdf mai esercitato dagli altri test di questo file (usano solo
    # fixture .txt): scrive un PDF reale su disco temporaneo e verifica che
    # `estrai_testo` via file caricato produca testo, non solo che non crashi.
    pytest.importorskip("pdfplumber", reason="extra 'pdf' non installato")
    from talia.modulo3_dashboard.app import _analizza_file_caricati

    file_caricati = [
        ("indizione.pdf", pdf_minimo("Determina di indizione concorso pubblico"), None),
        ("annullamento.pdf", pdf_minimo("Determina di annullamento in autotutela"), None),
    ]
    report = _analizza_file_caricati(file_caricati, valuta_llm=False)

    assert report.esiti
    assert len(report.atti) == 2


def test_analizza_file_caricati_descrizione_compare_nel_report(pdf_minimo):
    from talia.modulo3_dashboard.app import _analizza_file_caricati

    file_caricati = [
        (
            "allegato.pdf",
            pdf_minimo("Vedi allegato."),
            "Determina di revoca in autotutela del bando",
        ),
    ]
    report = _analizza_file_caricati(file_caricati, valuta_llm=False)

    assert report.atti[0].descrizione == "Determina di revoca in autotutela del bando"


def test_analizza_file_caricati_descrizione_guida_classificazione(pdf_minimo):
    # Un allegato con poco testo proprio (es. solo tabelle/numeri, nessuna
    # delle formule che l'euristica cerca) rimarrebbe SCONOSCIUTO senza aiuto;
    # la descrizione dell'utente lo aggancia comunque al ruolo giusto (TAL-60).
    from talia.engine.fascicolo import RuoloAtto
    from talia.engine.pdf_text import da_testo
    from talia.modulo1_fascicolo.analisi import classifica_ruolo

    testo_povero = da_testo("Prospetto economico: voce 1 € 100, voce 2 € 200.")
    assert classifica_ruolo(testo_povero) is RuoloAtto.SCONOSCIUTO
    assert classifica_ruolo(testo_povero, "revoca in autotutela del bando") is RuoloAtto.AUTOTUTELA


def test_mostra_report_fascicolo_espone_descrivi_citazione():
    # Regressione: descrivi_citazione era privata (_descr_citazione) in
    # report.py, resa pubblica per essere riusata dalla tab dashboard senza
    # duplicare il formato "«testo» (p. X, offset Y–Z)".
    from talia.modulo1_fascicolo.report import descrivi_citazione
    from talia.modulo3_dashboard.app import _analizza_file_caricati

    report = _analizza_file_caricati(_fascicolo_bytes("fascicolo_critico"), valuta_llm=False)
    citati = [c for e in report.esiti for c in e.citazioni]
    assert citati, "il fascicolo critico deve produrre almeno una citazione"
    assert descrivi_citazione(citati[0]).startswith("«")
