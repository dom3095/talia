"""Test offline per costruisci_scrapers() (TAL-51 refactor, PR3).

Verifica che scripts/run_scrapers.py costruisca il dict degli scraper e la
lista di default leggendo un registro (list[EntryRegistro]) invece delle
vecchie liste Python hardcoded — per tutti gli 11 moduli, non solo le 5
famiglie parametriche originarie. Nessuna chiamata di rete: i runner delle
5 famiglie multi-tenant sono verificati mockando `scarica_atti` del modulo
fonte corrispondente.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from talia.modulo2_scraping.db import connetti, inizializza_db
from talia.modulo2_scraping.registry import EntryRegistro

_ROOT = Path(__file__).resolve().parents[1]

_MODULI = [
    "jcitygov",
    "portalepa",
    "halley",
    "urbi",
    "hspromila",
    "palermo",
    "catania",
    "trapani",
    "siracusa",
    "ribera",
    "agrigento",
]


@pytest.fixture(scope="module")
def rs():
    """Carica scripts/run_scrapers.py come modulo (scripts/ non è un package)."""
    spec = importlib.util.spec_from_file_location(
        "run_scrapers_test_target", _ROOT / "scripts" / "run_scrapers.py"
    )
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _entry(**overrides) -> EntryRegistro:
    base = dict(
        slug="test",
        denominazione="Comune di Test",
        codice_istat="999999",
        modulo="jcitygov",
        piattaforma_tecnica="Test",
        base_url="https://test.example.com",
        stato="attivo",
    )
    base.update(overrides)
    return EntryRegistro(**base)


# ---------------------------------------------------------------------------
# costruisci_scrapers()
# ---------------------------------------------------------------------------


def test_anac_sempre_presente(rs):
    scrapers, _ = rs.costruisci_scrapers([])
    assert "anac" in scrapers


def test_registro_vuoto_solo_anac(rs):
    scrapers, default = rs.costruisci_scrapers([])
    assert list(scrapers) == ["anac"]
    assert default == []


def test_ogni_modulo_produce_uno_scraper_eseguibile_e_di_default(rs):
    entries = [
        _entry(
            slug=f"comune_{m}",
            modulo=m,
            qs_base="DB_NAME=x" if m in ("urbi", "catania") else None,
            ente_mittente="ENTE TEST" if m in ("urbi", "catania") else None,
        )
        for m in _MODULI
    ]
    scrapers, default = rs.costruisci_scrapers(entries)
    for m in _MODULI:
        assert f"comune_{m}" in scrapers, f"modulo {m} non produce uno scraper"
        assert f"comune_{m}" in default, f"modulo {m} non finisce nel default"
    assert "anac" in scrapers
    assert "anac" not in default


def test_stato_escluso_default_eseguibile_ma_non_di_default(rs):
    entries = [_entry(slug="c1", stato="escluso_default")]
    scrapers, default = rs.costruisci_scrapers(entries)
    assert "c1" in scrapers
    assert "c1" not in default


def test_stato_bloccato_non_eseguibile(rs):
    entries = [_entry(slug="c1", stato="bloccato")]
    scrapers, default = rs.costruisci_scrapers(entries)
    assert "c1" not in scrapers


def test_stato_pending_non_eseguibile(rs):
    entries = [_entry(slug="c1", stato="pending")]
    scrapers, default = rs.costruisci_scrapers(entries)
    assert "c1" not in scrapers


def test_modulo_sconosciuto_solleva_runtime_error(rs):
    entries = [_entry(slug="c1", modulo="marziano")]
    with pytest.raises(RuntimeError, match="sconosciuto"):
        rs.costruisci_scrapers(entries)


def test_riga_anac_nel_registro_non_duplica(rs):
    """La riga modulo=anac nel registro non deve generare un secondo entry:
    'anac' è già garantito dal runner fisso _run_anac."""
    entries = [_entry(slug="anac", modulo="anac", base_url=None, codice_istat="")]
    scrapers, _ = rs.costruisci_scrapers(entries)
    assert scrapers["anac"] is rs._run_anac


def test_registro_produzione_costruisce_senza_errori(rs):
    """Il registro reale (data/registro_scraper.csv) deve produrre scrapers
    senza sollevare — protegge da PR future che aggiungono un modulo ignoto."""
    from talia.modulo2_scraping.registry import carica_registro

    scrapers, default = rs.costruisci_scrapers(carica_registro())
    assert "anac" in scrapers
    assert len(default) > 0
    assert set(default) <= set(scrapers)


# ---------------------------------------------------------------------------
# Runner: verifica che i parametri dell'EntryRegistro arrivino davvero
# alla funzione scarica_atti del modulo fonte (non la vecchia costante).
# ---------------------------------------------------------------------------


@pytest.fixture
def db():
    conn = connetti(":memory:")
    inizializza_db(conn)
    return conn


def test_runner_jcitygov_usa_base_url_e_codice_istat_di_entry(rs, monkeypatch, db):
    chiamate = []

    def _finto_scarica_atti(base_url, codice_istat, limit=200):
        chiamate.append((base_url, codice_istat, limit))
        return iter([])

    monkeypatch.setattr("talia.modulo2_scraping.fonti.jcitygov.scarica_atti", _finto_scarica_atti)

    entry = _entry(slug="comune_test", modulo="jcitygov", codice_istat="087099")
    runner = rs._make_jcitygov_runner(entry)
    runner(db, max_pagine=1)

    assert len(chiamate) == 1
    assert chiamate[0][0] == "https://test.example.com"
    assert chiamate[0][1] == "087099"


def test_runner_halley_propaga_skip_ssl_da_entry(rs, monkeypatch, db):
    chiamate = []

    def _finto_scarica_atti(base_url, codice_istat, max_pagine=10, skip_ssl=False):
        chiamate.append(skip_ssl)
        return iter([])

    monkeypatch.setattr("talia.modulo2_scraping.fonti.halley.scarica_atti", _finto_scarica_atti)

    entry = _entry(slug="comune_ssl", modulo="halley", skip_ssl=True)
    runner = rs._make_halley_runner(entry)
    runner(db, max_pagine=1)

    assert chiamate == [True]


def test_runner_urbi_propaga_qs_base_e_ente_mittente(rs, monkeypatch, db):
    chiamate = []

    def _finto_scarica_atti(base_url, qs_base, codice_istat, ente_mittente, max_pagine=50):
        chiamate.append((base_url, qs_base, codice_istat, ente_mittente))
        return iter([])

    monkeypatch.setattr("talia.modulo2_scraping.fonti.urbi.scarica_atti", _finto_scarica_atti)

    entry = _entry(
        slug="comune_urbi",
        modulo="urbi",
        qs_base="DB_NAME=abc123&w3cbt=S",
        ente_mittente="COMUNE DI TEST",
    )
    runner = rs._make_urbi_runner(entry)
    runner(db, max_pagine=1)

    assert chiamate == [
        ("https://test.example.com", "DB_NAME=abc123&w3cbt=S", "999999", "COMUNE DI TEST")
    ]
