"""Test rilevamento concentrazione affidamenti diretti — DB SQLite in-memory."""

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
from talia.modulo2_scraping.red_flags.concentrazione import (
    MIN_ATTI_ANNO,
    rileva_concentrazione,
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
def ente_ct(db: sqlite3.Connection) -> int:
    return upsert_ente(
        db,
        EnteMetadato(denominazione="Comune di Catania", codice_istat="087015", provincia="CT"),
    )


def _atto(
    istat: str,
    tipo: str,
    data: str,
    url_suff: str,
) -> AttoMetadato:
    return AttoMetadato(
        ente_codice_istat=istat,
        tipo=tipo,
        url_fonte=f"http://albo.ct.it/{url_suff}",
        fonte_scraper="icity",
        data_accesso="2026-06-01T10:00:00",
        data_atto=data,
        importo_euro=10_000.0,
    )


# ---------------------------------------------------------------------------
# Caso positivo: > 80% affidamenti diretti
# ---------------------------------------------------------------------------


def test_concentrazione_rilevata(db: sqlite3.Connection, ente_ct: int) -> None:
    # 9 determine + 1 bando = 90% diretti → supera soglia (80%)
    for i in range(9):
        inserisci_atto(db, _atto("087015", "determina", "2026-03-15", f"det{i}"))
    inserisci_atto(db, _atto("087015", "bando", "2026-03-20", "bando1"))

    risultati = rileva_concentrazione(db, anno=2026)
    assert len(risultati) == 1
    r = risultati[0]
    assert r.n_totale == 10
    assert r.n_diretti == 9
    assert r.n_bandi == 1
    assert r.quota_diretti == pytest.approx(0.9)
    assert r.anno == 2026


# ---------------------------------------------------------------------------
# Caso negativo: quota diretti entro soglia
# ---------------------------------------------------------------------------


def test_nessuna_concentrazione_quota_ok(db: sqlite3.Connection, ente_ct: int) -> None:
    # 5 determine + 5 bandi = 50% diretti → sotto soglia
    for i in range(5):
        inserisci_atto(db, _atto("087015", "determina", "2026-03-15", f"det{i}"))
    for i in range(5):
        inserisci_atto(db, _atto("087015", "bando", "2026-03-20", f"bando{i}"))

    assert rileva_concentrazione(db, anno=2026) == []


# ---------------------------------------------------------------------------
# Caso negativo: meno di MIN_ATTI_ANNO atti nell'anno
# ---------------------------------------------------------------------------


def test_nessuna_concentrazione_pochi_atti(db: sqlite3.Connection, ente_ct: int) -> None:
    for i in range(MIN_ATTI_ANNO - 1):
        inserisci_atto(db, _atto("087015", "determina", "2026-04-10", f"det{i}"))
    assert rileva_concentrazione(db, anno=2026) == []


# ---------------------------------------------------------------------------
# Caso positivo: anno senza filtro esplicito
# ---------------------------------------------------------------------------


def test_concentrazione_senza_filtro_anno(db: sqlite3.Connection, ente_ct: int) -> None:
    for i in range(10):
        inserisci_atto(db, _atto("087015", "determina", "2025-06-01", f"det{i}"))

    risultati = rileva_concentrazione(db)
    assert len(risultati) == 1
    assert risultati[0].anno == 2025


# ---------------------------------------------------------------------------
# Caso: atti senza data_atto non conteggiati
# ---------------------------------------------------------------------------


def test_data_atto_null_usa_data_pub_jcitygov(db: sqlite3.Connection, ente_ct: int) -> None:
    """Regressione: su jCityGov (76% degli atti nel DB reale) data_atto è
    sempre NULL, solo data_pub è popolato. Prima del fix questi atti erano
    invisibili al check (WHERE a.data_atto IS NOT NULL escludeva tutto)."""
    for i in range(9):
        at = AttoMetadato(
            ente_codice_istat="087015",
            tipo="determina",
            url_fonte=f"http://albo.ct.it/jcg{i}",
            fonte_scraper="jcitygov",
            data_accesso="2026-06-01T10:00:00",
            data_pub="2026-03-15",
            importo_euro=10_000.0,
        )
        inserisci_atto(db, at)
    inserisci_atto(
        db,
        AttoMetadato(
            ente_codice_istat="087015",
            tipo="bando",
            url_fonte="http://albo.ct.it/jcg_bando",
            fonte_scraper="jcitygov",
            data_accesso="2026-06-01T10:00:00",
            data_pub="2026-03-20",
            importo_euro=10_000.0,
        ),
    )

    risultati = rileva_concentrazione(db, anno=2026)
    assert len(risultati) == 1
    assert risultati[0].n_totale == 10
    assert risultati[0].n_diretti == 9


def test_atti_senza_data_ignorati(db: sqlite3.Connection, ente_ct: int) -> None:
    # Inserisce atti senza data: non devono contribuire al conteggio
    for i in range(10):
        at = AttoMetadato(
            ente_codice_istat="087015",
            tipo="determina",
            url_fonte=f"http://albo.ct.it/nd{i}",
            fonte_scraper="icity",
            data_accesso="2026-06-01T10:00:00",
            # data_atto=None
        )
        inserisci_atto(db, at)
    assert rileva_concentrazione(db, anno=2026) == []


# ---------------------------------------------------------------------------
# Caso: campione atti limitato a 5
# ---------------------------------------------------------------------------


def test_campione_atti_max_5(db: sqlite3.Connection, ente_ct: int) -> None:
    for i in range(12):
        inserisci_atto(db, _atto("087015", "determina", "2026-05-15", f"det{i}"))
    risultati = rileva_concentrazione(db, anno=2026)
    assert len(risultati) == 1
    assert len(risultati[0].atti_campione) <= 5
