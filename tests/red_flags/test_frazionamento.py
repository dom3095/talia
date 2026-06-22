"""Test rilevamento frazionamento artificioso — DB SQLite in-memory."""

from __future__ import annotations

import sqlite3

import pytest

from talia.modulo2_scraping.db import (
    AttoMetadato,
    EnteMetadato,
    connetti,
    inizializza_db,
    inserisci_atto,
    upsert_ente,
)
from talia.modulo2_scraping.red_flags.frazionamento import (
    N_ATTI_SOGLIA,
    SOGLIA_FORNITURE,
    rileva_frazionamento,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db() -> sqlite3.Connection:
    conn = connetti(":memory:")
    inizializza_db(conn)
    return conn


@pytest.fixture()
def ente_pa(db: sqlite3.Connection) -> int:
    return upsert_ente(
        db,
        EnteMetadato(denominazione="Comune di Palermo", codice_istat="082053", provincia="PA"),
    )


def _atto(
    istat: str,
    importo: float,
    data: str,
    url_suff: str = "",
) -> AttoMetadato:
    return AttoMetadato(
        ente_codice_istat=istat,
        tipo="determina",
        url_fonte=f"http://albo.pa.it/det{url_suff}",
        fonte_scraper="icity",
        data_accesso="2026-06-01T10:00:00",
        data_atto=data,
        importo_euro=importo,
    )


# ---------------------------------------------------------------------------
# Caso positivo: 3 atti sotto soglia, totale sopra soglia, in 90 gg
# ---------------------------------------------------------------------------


def test_frazionamento_rilevato(db: sqlite3.Connection, ente_pa: int) -> None:
    inserisci_atto(db, _atto("082053", 50_000.0, "2026-01-10", "1"))
    inserisci_atto(db, _atto("082053", 50_000.0, "2026-01-20", "2"))
    inserisci_atto(db, _atto("082053", 50_000.0, "2026-01-30", "3"))

    risultati = rileva_frazionamento(db)
    assert len(risultati) == 1
    r = risultati[0]
    assert r.n_atti == 3
    assert r.totale_euro == pytest.approx(150_000.0)
    assert r.periodo_da == "2026-01-10"
    assert r.periodo_a == "2026-01-30"
    assert len(r.atti) == 3


# ---------------------------------------------------------------------------
# Caso negativo: totale sotto soglia
# ---------------------------------------------------------------------------


def test_nessun_frazionamento_totale_basso(db: sqlite3.Connection, ente_pa: int) -> None:
    inserisci_atto(db, _atto("082053", 30_000.0, "2026-01-10", "1"))
    inserisci_atto(db, _atto("082053", 30_000.0, "2026-01-20", "2"))
    inserisci_atto(db, _atto("082053", 30_000.0, "2026-01-30", "3"))
    # totale = 90.000 < SOGLIA_FORNITURE (140.000)
    assert rileva_frazionamento(db) == []


# ---------------------------------------------------------------------------
# Caso negativo: atti separati oltre la finestra temporale
# ---------------------------------------------------------------------------


def test_nessun_frazionamento_fuori_finestra(db: sqlite3.Connection, ente_pa: int) -> None:
    inserisci_atto(db, _atto("082053", 50_000.0, "2026-01-01", "1"))
    inserisci_atto(db, _atto("082053", 50_000.0, "2026-05-01", "2"))  # >90 gg
    inserisci_atto(db, _atto("082053", 50_000.0, "2026-09-01", "3"))  # >90 gg
    assert rileva_frazionamento(db) == []


# ---------------------------------------------------------------------------
# Caso negativo: meno di N_ATTI_SOGLIA atti
# ---------------------------------------------------------------------------


def test_nessun_frazionamento_pochi_atti(db: sqlite3.Connection, ente_pa: int) -> None:
    for i in range(N_ATTI_SOGLIA - 1):
        inserisci_atto(db, _atto("082053", 80_000.0, f"2026-01-{i + 10:02d}", str(i)))
    # 2 atti, totale 160.000 > soglia ma solo 2 atti → sotto N_ATTI_SOGLIA
    assert rileva_frazionamento(db) == []


# ---------------------------------------------------------------------------
# Caso positivo: importo esattamente alla soglia (< soglia, NON ≤)
# ---------------------------------------------------------------------------


def test_frazionamento_importo_esattamente_sotto_soglia(
    db: sqlite3.Connection, ente_pa: int
) -> None:
    # Ogni atto vale SOGLIA - 1 EUR → sta nella finestra; totale > soglia
    sotto = SOGLIA_FORNITURE - 1
    inserisci_atto(db, _atto("082053", sotto, "2026-02-01", "1"))
    inserisci_atto(db, _atto("082053", sotto, "2026-02-10", "2"))
    inserisci_atto(db, _atto("082053", sotto, "2026-02-20", "3"))
    risultati = rileva_frazionamento(db)
    assert len(risultati) == 1


# ---------------------------------------------------------------------------
# Caso negativo: importo >= soglia (affidamento sopra-soglia, non rientra)
# ---------------------------------------------------------------------------


def test_nessun_frazionamento_importo_sopra_soglia(db: sqlite3.Connection, ente_pa: int) -> None:
    for i in range(3):
        inserisci_atto(db, _atto("082053", SOGLIA_FORNITURE, f"2026-03-{i + 1:02d}", str(i)))
    # importo == soglia → filtro WHERE importo_euro < soglia esclude questi atti
    assert rileva_frazionamento(db) == []


# ---------------------------------------------------------------------------
# Idempotenza: più enti separati, solo uno con frazionamento
# ---------------------------------------------------------------------------


def test_frazionamento_solo_un_ente(db: sqlite3.Connection, ente_pa: int) -> None:
    upsert_ente(db, EnteMetadato(denominazione="Catania", codice_istat="087015", provincia="CT"))

    # Palermo: frazionamento
    for i in range(3):
        inserisci_atto(db, _atto("082053", 55_000.0, f"2026-04-{i + 1:02d}", f"pa{i}"))

    # Catania: niente (totale troppo basso)
    for i in range(3):
        inserisci_atto(db, _atto("087015", 10_000.0, f"2026-04-{i + 1:02d}", f"ct{i}"))

    risultati = rileva_frazionamento(db)
    assert len(risultati) == 1
    assert risultati[0].codice_istat == "082053"
