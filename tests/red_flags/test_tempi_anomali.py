"""Test rilevamento tempi anomali di pubblicazione bandi — DB SQLite in-memory."""

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
from talia.modulo2_scraping.red_flags.tempi_anomali import (
    MIN_GIORNI_BANDO_SOTTO_SOGLIA,
    SOGLIA_UE_FORNITURE,
    rileva_tempi_anomali,
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
def ente_me(db: sqlite3.Connection) -> int:
    return upsert_ente(
        db,
        EnteMetadato(denominazione="Comune di Messina", codice_istat="083048", provincia="ME"),
    )


def _bando(
    istat: str,
    data_pub: str,
    data_scadenza: str,
    url_suff: str,
    importo: float | None = None,
) -> AttoMetadato:
    return AttoMetadato(
        ente_codice_istat=istat,
        tipo="bando",
        url_fonte=f"http://albo.me.it/{url_suff}",
        fonte_scraper="icity",
        data_accesso="2026-06-01T10:00:00",
        data_pub=data_pub,
        data_scadenza=data_scadenza,
        importo_euro=importo,
    )


# ---------------------------------------------------------------------------
# Caso positivo: finestra 5 giorni → sotto soglia (15 gg)
# ---------------------------------------------------------------------------


def test_tempo_anomalo_rilevato(db: sqlite3.Connection, ente_me: int) -> None:
    inserisci_atto(db, _bando("083048", "2026-01-01", "2026-01-06", "b1"))
    risultati = rileva_tempi_anomali(db)
    assert len(risultati) == 1
    r = risultati[0]
    assert r.giorni_pubblicazione == 5
    assert r.soglia_applicata == MIN_GIORNI_BANDO_SOTTO_SOGLIA


# ---------------------------------------------------------------------------
# Caso negativo: finestra 20 giorni → OK (≥ 15 gg)
# ---------------------------------------------------------------------------


def test_nessun_tempo_anomalo_finestra_ok(db: sqlite3.Connection, ente_me: int) -> None:
    inserisci_atto(db, _bando("083048", "2026-01-01", "2026-01-21", "b1"))
    assert rileva_tempi_anomali(db) == []


# ---------------------------------------------------------------------------
# Caso positivo: bando sopra soglia UE con finestra 25 giorni (< 30 gg)
# ---------------------------------------------------------------------------


def test_tempo_anomalo_sopra_soglia_ue(db: sqlite3.Connection, ente_me: int) -> None:
    importo_ue = SOGLIA_UE_FORNITURE + 1
    inserisci_atto(
        db,
        _bando("083048", "2026-02-01", "2026-02-26", "b2", importo=importo_ue),
    )
    risultati = rileva_tempi_anomali(db)
    assert len(risultati) == 1
    r = risultati[0]
    assert r.giorni_pubblicazione == 25
    assert r.soglia_applicata == 30


# ---------------------------------------------------------------------------
# Caso negativo: bando sopra soglia UE, finestra 31 giorni → OK
# ---------------------------------------------------------------------------


def test_bando_sopra_soglia_ue_finestra_ok(db: sqlite3.Connection, ente_me: int) -> None:
    importo_ue = SOGLIA_UE_FORNITURE + 1
    inserisci_atto(
        db,
        _bando("083048", "2026-02-01", "2026-03-04", "b3", importo=importo_ue),
    )
    assert rileva_tempi_anomali(db) == []


# ---------------------------------------------------------------------------
# Caso negativo: tipo != 'bando' (determine, delibere ignorati)
# ---------------------------------------------------------------------------


def test_non_bando_ignorato(db: sqlite3.Connection, ente_me: int) -> None:
    at = AttoMetadato(
        ente_codice_istat="083048",
        tipo="determina",
        url_fonte="http://albo.me.it/det1",
        fonte_scraper="icity",
        data_accesso="2026-06-01T10:00:00",
        data_pub="2026-01-01",
        data_scadenza="2026-01-03",
    )
    inserisci_atto(db, at)
    assert rileva_tempi_anomali(db) == []


# ---------------------------------------------------------------------------
# Caso negativo: data_pub o data_scadenza mancanti
# ---------------------------------------------------------------------------


def test_bando_senza_date_ignorato(db: sqlite3.Connection, ente_me: int) -> None:
    at_no_scad = AttoMetadato(
        ente_codice_istat="083048",
        tipo="bando",
        url_fonte="http://albo.me.it/b_noscad",
        fonte_scraper="icity",
        data_accesso="2026-06-01T10:00:00",
        data_pub="2026-01-01",
        # data_scadenza=None
    )
    inserisci_atto(db, at_no_scad)
    assert rileva_tempi_anomali(db) == []


# ---------------------------------------------------------------------------
# Caso: più bandi, solo uno anomalo
# ---------------------------------------------------------------------------


def test_solo_un_bando_anomalo(db: sqlite3.Connection, ente_me: int) -> None:
    inserisci_atto(db, _bando("083048", "2026-03-01", "2026-03-04", "anomalo"))  # 3 gg
    inserisci_atto(db, _bando("083048", "2026-04-01", "2026-04-20", "ok"))       # 19 gg

    risultati = rileva_tempi_anomali(db)
    assert len(risultati) == 1
    assert risultati[0].giorni_pubblicazione == 3
