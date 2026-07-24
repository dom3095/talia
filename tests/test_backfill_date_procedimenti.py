"""Test migrazione one-off backfill_date_procedimenti (TAL-48, 2026-07-20/21)."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

from talia.engine.catena import _evolvi_schema
from talia.modulo2_scraping.db import (
    AttoMetadato,
    EnteMetadato,
    connetti,
    inizializza_db,
    inserisci_atto,
    upsert_ente,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from backfill_date_procedimenti import esegui_backfill, ricalcola_data_avvio  # noqa: E402


@pytest.fixture()
def db():
    conn = connetti(":memory:")
    inizializza_db(conn)
    conn.row_factory = sqlite3.Row
    return conn


@pytest.fixture()
def ente_id(db):
    _evolvi_schema(db)
    return upsert_ente(
        db,
        EnteMetadato(denominazione="Comune di Esempio", codice_istat="099999"),
    )


def _atto_jcitygov(ente_id: int, url: str, ruolo: str, data_pub: str) -> AttoMetadato:
    return AttoMetadato(
        ente_codice_istat="099999",
        tipo="determina",
        url_fonte=url,
        fonte_scraper="jcitygov",
        data_accesso="2026-07-20T00:00:00",
        data_atto=None,
        data_pub=data_pub,
    )


def _crea_procedimento_stale(db, ente_id: int, metodo: str) -> int:
    """Simula un procedimento creato dal codice PRE-fix: data_avvio/data_chiusura
    NULL nonostante gli atti abbiano una data (via data_pub, non data_atto)."""
    cur = db.execute(
        """INSERT INTO procedimenti (ente_id, stato_finale, metodo_individuazione, creato_a)
           VALUES (?, 'revocato', ?, '2026-07-01')""",
        (ente_id, metodo),
    )
    return cur.lastrowid


def test_ricalcola_data_avvio_metodo_cig(db, ente_id):
    proc_id = _crea_procedimento_stale(db, ente_id, "cig")
    inserisci_atto(db, _atto_jcitygov(ente_id, "http://albo/avvio", "avvio", "2025-07-01"))
    inserisci_atto(db, _atto_jcitygov(ente_id, "http://albo/revoca", "revoca", "2025-12-22"))
    db.execute(
        "UPDATE atti SET procedimento_id = ?, ruolo_in_catena = 'avvio' WHERE url_fonte = ?",
        (proc_id, "http://albo/avvio"),
    )
    db.execute(
        "UPDATE atti SET procedimento_id = ?, ruolo_in_catena = 'revoca' WHERE url_fonte = ?",
        (proc_id, "http://albo/revoca"),
    )
    db.commit()

    assert ricalcola_data_avvio(db, proc_id, "cig") == "2025-07-01"


def test_ricalcola_data_avvio_metodo_contenimento_usa_ruolo_non_derivato(db, ente_id):
    """Il contenimento non prende semplicemente la data più vecchia: prende
    specificamente l'atto con ruolo NON derivato (l'originario), anche se
    per qualche motivo non fosse il più vecchio in assoluto."""
    proc_id = _crea_procedimento_stale(db, ente_id, "contenimento_oggetto")
    # L'originario (avvio) ha una data PIÙ RECENTE di un atto derivato di scarto
    # per verificare che la scelta sia per ruolo, non per data minima.
    inserisci_atto(db, _atto_jcitygov(ente_id, "http://albo/avvio", "avvio", "2025-06-01"))
    inserisci_atto(db, _atto_jcitygov(ente_id, "http://albo/revoca", "revoca", "2025-11-20"))
    db.execute(
        "UPDATE atti SET procedimento_id = ?, ruolo_in_catena = 'avvio' WHERE url_fonte = ?",
        (proc_id, "http://albo/avvio"),
    )
    db.execute(
        "UPDATE atti SET procedimento_id = ?, ruolo_in_catena = 'revoca' WHERE url_fonte = ?",
        (proc_id, "http://albo/revoca"),
    )
    db.commit()

    assert ricalcola_data_avvio(db, proc_id, "contenimento_oggetto") == "2025-06-01"


def test_ricalcola_data_avvio_nessun_atto_con_data(db, ente_id):
    proc_id = _crea_procedimento_stale(db, ente_id, "cig")
    assert ricalcola_data_avvio(db, proc_id, "cig") is None


def test_esegui_backfill_end_to_end(db, ente_id):
    proc_id = _crea_procedimento_stale(db, ente_id, "cig")
    inserisci_atto(db, _atto_jcitygov(ente_id, "http://albo/avvio", "avvio", "2025-07-01"))
    inserisci_atto(db, _atto_jcitygov(ente_id, "http://albo/revoca", "revoca", "2025-12-22"))
    db.execute(
        "UPDATE atti SET procedimento_id = ?, ruolo_in_catena = 'avvio' WHERE url_fonte = ?",
        (proc_id, "http://albo/avvio"),
    )
    db.execute(
        "UPDATE atti SET procedimento_id = ?, ruolo_in_catena = 'revoca' WHERE url_fonte = ?",
        (proc_id, "http://albo/revoca"),
    )
    db.commit()

    proc_prima = db.execute("SELECT * FROM procedimenti WHERE id = ?", (proc_id,)).fetchone()
    assert proc_prima["data_avvio"] is None
    assert proc_prima["data_chiusura"] is None

    risultato = esegui_backfill(db)
    assert risultato["data_avvio_aggiornati"] == 1
    assert risultato["data_chiusura_aggiornati"] == 1

    proc_dopo = db.execute("SELECT * FROM procedimenti WHERE id = ?", (proc_id,)).fetchone()
    assert proc_dopo["data_avvio"] == "2025-07-01"
    assert proc_dopo["data_chiusura"] == "2025-12-22"
    # stato_finale invariato: stessi ruoli di prima, solo le date cambiano
    assert proc_dopo["stato_finale"] == "revocato"


def test_esegui_backfill_idempotente(db, ente_id):
    proc_id = _crea_procedimento_stale(db, ente_id, "cig")
    inserisci_atto(db, _atto_jcitygov(ente_id, "http://albo/avvio", "avvio", "2025-07-01"))
    inserisci_atto(db, _atto_jcitygov(ente_id, "http://albo/revoca", "revoca", "2025-12-22"))
    db.execute(
        "UPDATE atti SET procedimento_id = ?, ruolo_in_catena = 'avvio' WHERE url_fonte = ?",
        (proc_id, "http://albo/avvio"),
    )
    db.execute(
        "UPDATE atti SET procedimento_id = ?, ruolo_in_catena = 'revoca' WHERE url_fonte = ?",
        (proc_id, "http://albo/revoca"),
    )
    db.commit()

    esegui_backfill(db)
    risultato_secondo_giro = esegui_backfill(db)
    assert risultato_secondo_giro["data_avvio_aggiornati"] == 0
    assert risultato_secondo_giro["data_chiusura_aggiornati"] == 0
