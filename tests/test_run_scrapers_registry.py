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


def test_anac_da_riga_registro_produce_scraper(rs):
    """ANAC non ha più un seed hardcoded (fix code review 2026-07-11): è
    dispatchato uniformemente come ogni altro modulo via _FACTORY_PER_MODULO,
    e compare in _SCRAPERS solo se il registro ha davvero una riga anac."""
    entries = [_entry(slug="anac", modulo="anac", stato="escluso_default")]
    scrapers, default = rs.costruisci_scrapers(entries)
    assert "anac" in scrapers
    assert scrapers["anac"] is rs._run_anac
    assert "anac" not in default  # escluso_default: eseguibile ma non di default


def test_registro_vuoto_nessuno_scraper(rs):
    """Un registro vuoto non produce scrapers — nemmeno anac, che ora dipende
    interamente dal registro come tutti gli altri moduli (nessun caso
    speciale hardcoded)."""
    scrapers, default = rs.costruisci_scrapers([])
    assert scrapers == {}
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
    entries.append(_entry(slug="anac", modulo="anac", stato="escluso_default"))
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


def test_riga_anac_senza_base_url_ne_codice_istat_funziona(rs):
    """anac non richiede base_url/codice_istat (modulo senza ente, vedi
    registry.MODULI_SENZA_ENTE): il runner fisso _run_anac ignora l'entry."""
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

    def _finto_scarica_atti(
        base_url, qs_base, codice_istat, ente_mittente, max_pagine=50, **kwargs
    ):
        chiamate.append((base_url, qs_base, codice_istat, ente_mittente, kwargs))
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

    from talia.modulo2_scraping.fonti.urbi import MAX_PAGINE_PER_TIPOLOGIA

    assert chiamate == [
        (
            "https://test.example.com",
            "DB_NAME=abc123&w3cbt=S",
            "999999",
            "COMUNE DI TEST",
            {"max_pagine_per_tipologia": MAX_PAGINE_PER_TIPOLOGIA},
        )
    ]


def test_runner_urbi_backfill_disattiva_il_tetto_per_tipologia(rs, monkeypatch, db):
    """`--no-stop` significa "voglio tutto l'archivio", tetto incluso."""
    chiamate = []

    def _finto_scarica_atti(*_a, **kwargs):
        chiamate.append(kwargs.get("max_pagine_per_tipologia"))
        return iter([])

    monkeypatch.setattr("talia.modulo2_scraping.fonti.urbi.scarica_atti", _finto_scarica_atti)
    runner = rs._make_urbi_runner(
        _entry(slug="comune_urbi", modulo="urbi", qs_base="DB_NAME=x", ente_mittente="COMUNE X")
    )
    runner(db, max_pagine=1, no_stop=True)
    assert chiamate == [None]


# ---------------------------------------------------------------------------
# Stop-on-known per tipologia (TAL-68)
# ---------------------------------------------------------------------------


def _atto_urbi(n: int, tipologia: str | None):
    from talia.modulo2_scraping.db import AttoMetadato

    return AttoMetadato(
        ente_codice_istat="082022",
        tipo="determina",
        url_fonte=f"https://cloud.urbi.it/atto/{n}",
        fonte_scraper="urbi",
        data_accesso="2026-08-18T00:00:00+00:00",
        oggetto=f"Atto {n}",
        metadati={"tipologia_ricerca": tipologia} if tipologia else {},
    )


def test_stop_on_known_si_azzera_al_cambio_tipologia(rs, monkeypatch):
    """Regressione Caccamo: senza il reset, la prima tipologia già nota
    interromperebbe anche la scansione di tutte le successive."""
    from talia.modulo2_scraping.fonti import urbi

    # Tipologia "83": abbastanza duplicati da far scattare lo stop.
    # Tipologia "44": atti nuovi, che devono comunque essere raggiunti.
    noti = [_atto_urbi(i, "83") for i in range(rs._STOP_CONSECUTIVI + 5)]
    nuovi = [_atto_urbi(1000 + i, "44") for i in range(3)]
    monkeypatch.setattr(urbi, "scarica_atti", lambda *_a, **_k: iter(noti + nuovi))

    conn = connetti(":memory:")
    inizializza_db(conn)
    # Primo giro: tutto nuovo, popola il DB.
    rs._run_urbi_comune(
        conn,
        "caccamo",
        "https://x",
        "DB_NAME=y",
        "082022",
        "COMUNE DI CACCAMO",
        "Comune di Caccamo",
    )
    # Secondo giro: gli atti "83" sono ora duplicati, i "44" restano nuovi solo
    # se la scansione non si è fermata alla prima tipologia.
    monkeypatch.setattr(
        urbi,
        "scarica_atti",
        lambda *_a, **_k: iter(noti + [_atto_urbi(2000 + i, "44") for i in range(3)]),
    )
    esito = rs._run_urbi_comune(
        conn,
        "caccamo",
        "https://x",
        "DB_NAME=y",
        "082022",
        "COMUNE DI CACCAMO",
        "Comune di Caccamo",
    )
    assert esito["inseriti"] == 3


def test_stop_on_known_invariato_senza_tipologie(rs, monkeypatch):
    """I tenant normali (nessuna tipologia sugli atti) mantengono lo stop."""
    from talia.modulo2_scraping.fonti import urbi

    noti = [_atto_urbi(i, None) for i in range(rs._STOP_CONSECUTIVI + 5)]
    monkeypatch.setattr(urbi, "scarica_atti", lambda *_a, **_k: iter(noti))

    conn = connetti(":memory:")
    inizializza_db(conn)
    rs._run_urbi_comune(
        conn, "favara", "https://x", "DB_NAME=y", "082022", "COMUNE DI FAVARA", "Comune di Favara"
    )
    esito = rs._run_urbi_comune(
        conn, "favara", "https://x", "DB_NAME=y", "082022", "COMUNE DI FAVARA", "Comune di Favara"
    )
    # Si ferma dopo _STOP_CONSECUTIVI duplicati, senza leggere gli ultimi.
    assert esito["duplicati"] == rs._STOP_CONSECUTIVI
